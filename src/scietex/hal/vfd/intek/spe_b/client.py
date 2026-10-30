"""
Modbus/TCP client for an Intek SPE-B drive behind the Scietex Modbus gateway.

The gateway owns the RS485 bus and speaks standard Modbus RTU to the drive once
Pd.05 is set to 1; this client speaks plain Modbus/TCP (FC03/FC06) and addresses
the drive by its Modbus unit id. It never touches the RS485 framing.

Two scale factors are read from the drive once, in :meth:`connect`, and cached
for the lifetime of the connection:

    P0.10 (EEPROM 0xF00A)  maximum output frequency, 0.01 Hz units
    Pd.06 (EEPROM 0x7006)  output-current resolution, 0.01 A or 0.1 A

The drive reports operating frequency as a percentage of P0.10 and output
current in counts of the Pd.06 resolution, so neither value is usable without
its factor.

Classes:
    IntekSPEBModbusVFD: A Modbus/TCP client for the Intek SPE-B drive.
"""

from logging import Logger, getLogger
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.pdu import ExceptionResponse
from scietex.hal.serial import ModbusOperationError

from ...base.capabilities import VFDCapabilities
from ...base.data import VFDError, VFDParameters, VFDState
from ...base.protocol import VFDProtocol
from . import registers
from .errors import SPE_B_ERROR_CODES, SPE_B_ERROR_CODES_COM


class IntekSPEBModbusVFD(VFDProtocol):
    """
    Modbus/TCP client for an Intek SPE-B drive behind the gateway.

    The client owns one TCP connection to the gateway and addresses the drive by
    its Modbus unit id. SPE-B exposes both rotation directions, jog commands, a
    coasting stop, a fault reset and a communication-protocol setpoint register
    (0x1000), which :meth:`set_frequency` writes.

    The drive reports no temperature: overheat reaches the caller only as fault
    code 0x0E (power module) or 0x2D (motor), so both temperature fields of
    `VFDParameters` stay ``None``.

    Attributes:
        label (str): Human-readable drive label.
        capabilities (VFDCapabilities): The SPE-B control surface.
        error_codes (dict[int, VFDError]): Drive fault code table.
        error_codes_com (dict[int, VFDError]): Communication fault code table.
    """

    capabilities = VFDCapabilities(
        direction=True,
        jog=True,
        freewheel_stop=True,
        fault_reset=True,
        frequency_setpoint=True,
    )
    display_name = "Intek SPE-B"

    def __init__(
        self,
        host: str,
        port: int = 502,
        unit_id: int = 1,
        label: str = "Intek SPE-B",
        timeout: float = 1.0,
        logger: Logger | None = None,
    ) -> None:
        """
        Initialize the client.

        Args:
            host: Gateway host name or address.
            port: Gateway TCP port.
            unit_id: Modbus unit id the gateway routes to the drive. This is the
                drive's Pd.02 address.
            label: Human-readable drive label.
            timeout: Per-request timeout in seconds.
            logger: Optional logger for diagnostics.
        """
        self.label = label
        self.unit_id = unit_id
        self.logger = logger if logger is not None else getLogger(__name__)
        self.error_codes = SPE_B_ERROR_CODES
        self.error_codes_com = SPE_B_ERROR_CODES_COM
        self._host = host
        self._port = port
        self._timeout = timeout
        self._max_frequency_hz = 0.0
        self._current_resolution = registers.CURRENT_RESOLUTION_FINE
        # `AsyncModbusTcpClient` binds to the running event loop in its
        # constructor, so it cannot be built here: the client is created in
        # `connect()`, which always runs inside the loop.
        self._client: AsyncModbusTcpClient | None = None

    async def connect(self) -> None:
        """
        Open the TCP connection to the gateway and read the drive's scale factors.

        Raises:
            ModbusOperationError: If the gateway is unreachable, or if P0.10
                cannot be read. pymodbus reports a failed connect by returning
                ``False`` rather than raising, so the result is checked here;
                otherwise an unreachable drive would look connected and only
                fail on the first read.
        """
        if self._client is None:
            self._client = AsyncModbusTcpClient(self._host, port=self._port, timeout=self._timeout)
        if not await self._client.connect():
            raise ModbusOperationError(
                f"Failed to connect to VFD gateway at {self._host}:{self._port}"
            )
        await self._read_scale_factors()

    async def close(self) -> None:
        """Close the TCP connection to the gateway."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def _require_client(self) -> AsyncModbusTcpClient:
        """
        Return the connected client, or raise if ``connect()`` was not called.

        Raises:
            RuntimeError: If the client has not been connected.
        """
        if self._client is None:
            raise RuntimeError("VFD is not connected; call connect() first")
        return self._client

    async def _read_registers(self, address: int, count: int) -> list[int]:
        """
        Read holding registers, raising on a Modbus exception response.

        Args:
            address: Starting register address.
            count: Number of registers to read.

        Returns:
            list[int]: The register values.

        Raises:
            ModbusOperationError: If the gateway returns an exception response.
        """
        response = await self._require_client().read_holding_registers(
            address, count=count, device_id=self.unit_id
        )
        if isinstance(response, ExceptionResponse):
            raise ModbusOperationError(
                f"Read of register {address} failed: exception code {response.exception_code}"
            )
        return list(response.registers)

    async def _read_optional_registers(self, address: int, count: int) -> list[int] | None:
        """
        Read holding registers, returning ``None`` instead of raising on failure.

        Used for readings that refine a snapshot but must not fail it: a drive
        that refuses one diagnostic register still reports its frequency,
        current and state, and a poll loop that raised on every optional read
        would never publish anything.

        Args:
            address: Starting register address.
            count: Number of registers to read.

        Returns:
            list[int] | None: The register values, or ``None`` when the read
                failed.
        """
        try:
            return await self._read_registers(address, count)
        except ModbusOperationError as exc:
            self.logger.warning(
                "%s: Optional register %s is unreadable (%s).", self.label, address, exc
            )
            return None

    async def _write_register(self, address: int, value: int) -> None:
        """
        Write a single holding register, raising on a Modbus exception response.

        Args:
            address: Register address.
            value: Value to write.

        Raises:
            ModbusOperationError: If the gateway returns an exception response.
        """
        response = await self._require_client().write_register(
            address, value, device_id=self.unit_id
        )
        if isinstance(response, ExceptionResponse):
            raise ModbusOperationError(
                f"Write of register {address} failed: exception code {response.exception_code}"
            )

    async def _read_scale_factors(self) -> None:
        """
        Read and cache the P0.10 maximum frequency and the Pd.06 resolution.

        Raises:
            ModbusOperationError: If P0.10 cannot be read, because every
                frequency this client reports would then be a guess.
        """
        raw = await self._read_registers(registers.PARAM_MAX_FREQUENCY_EEPROM, 1)
        self._max_frequency_hz = raw[0] / registers.PARAMETER_FREQUENCY_RESOLUTION
        if self._max_frequency_hz <= 0:
            self.logger.warning(
                "%s: P0.10 reads %d, frequency is reported as 0 Hz.", self.label, raw[0]
            )
        # Pd.06 only refines the current reading, so a drive that refuses the
        # read keeps working with the factory resolution instead of failing
        # the connection: stop and fault reset must stay available.
        try:
            raw = await self._read_registers(registers.PARAM_CURRENT_RESOLUTION_EEPROM, 1)
        except ModbusOperationError as exc:
            self.logger.warning("%s: Pd.06 is unreadable (%s), assuming 0.01 A.", self.label, exc)
            return
        self._current_resolution = (
            registers.CURRENT_RESOLUTION_COARSE
            if raw[0] == 1
            else registers.CURRENT_RESOLUTION_FINE
        )

    def _percent_to_hz(self, percent: float) -> float:
        """
        Convert an operating frequency percentage into Hz.

        Args:
            percent: Frequency as reported by the drive.

        Returns:
            float: The frequency in Hz, or 0.0 while P0.10 is unknown.
        """
        if self._max_frequency_hz <= 0:
            return 0.0
        return registers.percent_to_hz(percent, self._max_frequency_hz)

    async def read_parameters(self) -> VFDParameters:
        """
        Read the drive's operating parameters in one transaction.

        The block spans 0x1001..0x1005: operating frequency, DC bus voltage,
        output voltage, current and power. Voltage and power are reported as the
        drive sends them, because the manual states no scaling factor for
        either; current is scaled by the Pd.06 resolution.

        The run state is read separately and is optional: a drive that refuses
        the status register still reports its measurements, so the state falls
        back to ``VFDState.UNKNOWN`` instead of failing the whole snapshot.

        Returns:
            VFDParameters: The decoded parameters. Both temperature fields are
                ``None``: SPE-B reports overheat as a fault code, not a reading.

        Raises:
            ModbusOperationError: If the measurement block cannot be read.
        """
        block = await self._read_registers(
            registers.PARAMETERS_BLOCK_ADDRESS, registers.PARAMETERS_BLOCK_COUNT
        )
        percent = registers.frequency_raw_to_percent(
            block[registers.REG_OPERATING_FREQUENCY - registers.PARAMETERS_BLOCK_ADDRESS]
        )
        current = (
            block[registers.REG_OUTPUT_CURRENT - registers.PARAMETERS_BLOCK_ADDRESS]
            * self._current_resolution
        )
        parameters = VFDParameters(
            frequency_hz=self._percent_to_hz(percent),
            frequency_percent=percent,
            output_current=float(current),
            output_voltage=float(
                block[registers.REG_OUTPUT_VOLTAGE - registers.PARAMETERS_BLOCK_ADDRESS]
            ),
            output_power=float(
                block[registers.REG_OUTPUT_POWER - registers.PARAMETERS_BLOCK_ADDRESS]
            ),
            dc_bus_voltage=float(
                block[registers.REG_DC_BUS_VOLTAGE - registers.PARAMETERS_BLOCK_ADDRESS]
            ),
            state=await self.read_state(),
        )
        self.logger.debug("%s: %s", self.label, parameters)
        return parameters

    async def read_state(self) -> VFDState:
        """
        Read the drive's run state.

        Returns:
            VFDState: The decoded state, or ``VFDState.UNKNOWN`` when the status
                register is unreadable or holds a value the manual does not
                define.
        """
        raw = await self._read_optional_registers(registers.REG_STATUS, 1)
        if raw is None:
            return VFDState.UNKNOWN
        state = registers.status_to_state(raw[0])
        self.logger.debug("%s: Current state: %s", self.label, state)
        return state

    async def read_error_code(self, comm: bool = False) -> int:
        """
        Read the latched fault code.

        Args:
            comm: Read the communication-protocol fault code instead of the
                drive fault code.

        Returns:
            int: The fault code; 0 means no fault.

        Raises:
            ModbusOperationError: If the register cannot be read. A failed read
                is never reported as fault code 0.
        """
        address = registers.REG_COMM_FAULT if comm else registers.REG_DRIVE_FAULT
        raw = await self._read_registers(address, 1)
        if comm:
            self.logger.debug("%s: Communication error code %d.", self.label, raw[0])
        else:
            self.logger.debug("%s: Error code %d.", self.label, raw[0])
        return raw[0]

    def parse_error_code(self, code: int, comm: bool = False) -> VFDError:
        """
        Look a fault code up in the SPE-B tables.

        Args:
            code: The fault code.
            comm: Look the code up in the communication fault table.

        Returns:
            VFDError: The matching entry, or an "unknown error" entry.
        """
        table = self.error_codes_com if comm else self.error_codes
        return table.get(code, VFDError(code=code, message="Unknown error"))

    async def clear_error(self, comm: bool = False) -> int:
        """
        Reset the latched fault and read the code back.

        The drive has a single fault-reset command for both fault tables, so
        ``comm`` only selects which code is read back afterwards.

        Args:
            comm: Read the communication-protocol fault code back instead of the
                drive fault code.

        Returns:
            int: The fault code read after the reset; 0 means the fault is gone.
        """
        await self._write_register(registers.REG_CONTROL, registers.CONTROL_FAULT_RESET)
        return await self.read_error_code(comm)

    async def start(self, forward: bool = True, slow: bool = False) -> None:
        """
        Start the motor.

        Args:
            forward: Run in the forward direction; ``False`` runs in reverse.
            slow: Use the jog command instead of the normal run command.
        """
        await self._write_register(registers.REG_CONTROL, registers.start_command(forward, slow))

    async def stop(self, freewheel: bool = False) -> None:
        """
        Stop the motor.

        Args:
            freewheel: Coast to a stop instead of ramping down.
        """
        await self._write_register(registers.REG_CONTROL, registers.stop_command(freewheel))

    async def set_frequency(self, frequency_hz: float) -> None:
        """
        Write the communication-protocol frequency setpoint.

        The setpoint register takes hundredths of a percent of P0.10, so the
        value is converted with the maximum frequency cached in :meth:`connect`.
        The drive only honours the register when P0.03 selects the
        communication-protocol setpoint source; see ``intek/docs/protocol.md``.

        Args:
            frequency_hz: The requested output frequency in Hz.

        Raises:
            ValueError: If P0.10 is unknown, because no percentage can then be
                computed, or if the request exceeds the maximum frequency.
        """
        if self._max_frequency_hz <= 0:
            raise ValueError(
                f"{self.label}: maximum frequency (P0.10) is unknown; cannot set a setpoint"
            )
        percent = registers.hz_to_percent(frequency_hz, self._max_frequency_hz)
        if percent > 100.0:
            raise ValueError(
                f"{self.label}: {frequency_hz} Hz exceeds the maximum {self._max_frequency_hz} Hz"
            )
        raw = round(percent * registers.FREQUENCY_PERCENT_RESOLUTION)
        await self._write_register(registers.REG_COMM_SETPOINT, raw)

    async def read_data(self) -> dict[str, Any]:
        """
        Read a snapshot of the drive's current values.

        Returns:
            dict[str, Any]: The `VFDParameters` fields, keyed by field name.
        """
        parameters = await self.read_parameters()
        return {field: getattr(parameters, field) for field in parameters.__struct_fields__}
