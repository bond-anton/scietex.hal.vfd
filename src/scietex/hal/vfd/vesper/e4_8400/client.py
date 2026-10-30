"""
Modbus/TCP client for a Vesper E4-8400 / E4-P8402 drive behind the Scietex
Modbus gateway.

The gateway owns the RS485 bus and speaks standard Modbus RTU to the drive once
parameter H5-08 is set to 0; this client speaks plain Modbus/TCP (FC03/FC06) and
addresses the drive by its Modbus unit id. It never touches the RS485 framing.

The E4-8400 is the only drive in this package that reports a live temperature:
register ``004Dh`` (U1-46) is the power-module temperature in degrees Celsius,
and :meth:`read_parameters` populates ``heatsink_temperature_c`` from it.

Classes:
    VesperE48400ModbusVFD: A Modbus/TCP client for the Vesper E4-8400 drive.
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
from .errors import (
    E4_8400_ERROR_CODES_COM,
    E4_8400_FAULT_BITS,
    E4_8400_FAULT_CODES,
    decode_faults,
)


class VesperE48400ModbusVFD(VFDProtocol):
    """
    Modbus/TCP client for a Vesper E4-8400 drive behind the gateway.

    The client owns one TCP connection to the gateway and addresses the drive by
    its Modbus unit id. The E4-8400 exposes both rotation directions, jog
    commands, a fault reset and a frequency setpoint register (0x0001), which
    :meth:`set_frequency` writes.

    The drive reports a live power-module temperature (U1-46), so
    ``heatsink_temperature_c`` is populated. It reports motor overheat only as a
    fault, so ``motor_temperature_c`` stays ``None``.

    Attributes:
        label (str): Human-readable drive label.
        capabilities (VFDCapabilities): The E4-8400 control surface.
        error_codes (dict[int, VFDError]): Fault history code table.
        error_codes_com (dict[int, VFDError]): Communication fault code table.
    """

    capabilities = VFDCapabilities(
        direction=True,
        jog=True,
        freewheel_stop=False,
        fault_reset=True,
        frequency_setpoint=True,
    )
    display_name = "Vesper E4-8400"

    def __init__(
        self,
        host: str,
        port: int = 502,
        unit_id: int = 1,
        label: str = "Vesper E4-8400",
        timeout: float = 1.0,
        logger: Logger | None = None,
        max_frequency_hz: float | None = None,
    ) -> None:
        """
        Initialize the client.

        Args:
            host: Gateway host name or address.
            port: Gateway TCP port.
            unit_id: Modbus unit id the gateway routes to the drive. This is the
                drive's H5-01 address.
            label: Human-readable drive label.
            timeout: Per-request timeout in seconds.
            logger: Optional logger for diagnostics.
            max_frequency_hz: The drive's maximum output frequency, used only to
                derive ``frequency_percent``. ``None`` reads parameter E1-04
                from the drive on the first parameters read; pass a value to
                skip that read.
        """
        self.label = label
        self.unit_id = unit_id
        self.logger = logger if logger is not None else getLogger(__name__)
        self.error_codes = E4_8400_FAULT_CODES
        self.error_codes_com = E4_8400_ERROR_CODES_COM
        self._max_frequency_hz = max_frequency_hz
        self._host = host
        self._port = port
        self._timeout = timeout
        # `AsyncModbusTcpClient` binds to the running event loop in its
        # constructor, so it cannot be built here: the client is created in
        # `connect()`, which always runs inside the loop.
        self._client: AsyncModbusTcpClient | None = None

    async def connect(self) -> None:
        """
        Open the TCP connection to the gateway.

        Raises:
            ModbusOperationError: If the gateway is unreachable. pymodbus
                reports a failed connect by returning ``False`` rather than
                raising, so the result is checked here; otherwise an
                unreachable drive would look connected and only fail on the
                first read.
        """
        if self._client is None:
            self._client = AsyncModbusTcpClient(self._host, port=self._port, timeout=self._timeout)
        if not await self._client.connect():
            raise ModbusOperationError(
                f"Failed to connect to VFD gateway at {self._host}:{self._port}"
            )

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

    async def _read_max_frequency(self) -> float:
        """
        Read parameter E1-04 and cache it.

        Returns:
            float: The maximum output frequency in Hz, or 0.0 when the drive
                reports a non-positive value.
        """
        if self._max_frequency_hz is None:
            raw = await self._read_registers(
                registers.parameter_register(registers.PARAM_MAX_FREQUENCY), 1
            )
            self._max_frequency_hz = raw[0] / registers.FREQUENCY_RESOLUTION
            if self._max_frequency_hz <= 0:
                self.logger.warning(
                    "%s: E1-04 reads %d, frequency is reported as 0%%.", self.label, raw[0]
                )
        return self._max_frequency_hz

    def _percent(self, frequency_hz: float) -> float:
        """
        Convert a frequency into a percentage of the configured maximum.

        Args:
            frequency_hz: The frequency in Hz.

        Returns:
            float: The percentage, or 0.0 when the maximum is not positive.
        """
        if not self._max_frequency_hz or self._max_frequency_hz <= 0:
            return 0.0
        return frequency_hz / self._max_frequency_hz * 100.0

    async def read_parameters(self) -> VFDParameters:
        """
        Read the drive's operating parameters.

        The setpoint and output frequency and the output current come from one
        four-register block; voltage, DC bus voltage and the power-module
        temperature are read separately because the gaps between them would
        otherwise pull in reserved registers.

        Returns:
            VFDParameters: The decoded parameters. ``heatsink_temperature_c`` is
                populated from U1-46; ``motor_temperature_c`` stays ``None``
                because the drive reports motor overheat only as a fault.

        Raises:
            ModbusOperationError: If any read fails.
        """
        await self._read_max_frequency()
        block = await self._read_registers(
            registers.PARAMETERS_BLOCK_ADDRESS, registers.PARAMETERS_BLOCK_COUNT
        )
        offset = registers.PARAMETERS_BLOCK_ADDRESS
        frequency_hz = registers.output_frequency_hz(block[registers.REG_OUTPUT_FREQUENCY - offset])
        voltage = await self._read_registers(registers.REG_OUTPUT_VOLTAGE, 1)
        dc_bus = await self._read_registers(registers.REG_DC_BUS_VOLTAGE, 1)
        temperature = await self._read_registers(registers.REG_HEATSINK_TEMPERATURE, 1)
        parameters = VFDParameters(
            frequency_hz=frequency_hz,
            frequency_percent=self._percent(frequency_hz),
            output_current=registers.output_current_a(block[registers.REG_OUTPUT_CURRENT - offset]),
            output_voltage=float(voltage[0]),
            dc_bus_voltage=float(dc_bus[0]),
            heatsink_temperature_c=float(temperature[0]),
            state=await self.read_state(),
        )
        self.logger.debug("%s: %s", self.label, parameters)
        return parameters

    async def read_state(self) -> VFDState:
        """
        Read the drive's run state.

        Returns:
            VFDState: The decoded state.

        Raises:
            ModbusOperationError: If the status register cannot be read.
        """
        raw = await self._read_registers(registers.REG_STATUS, 1)
        state = registers.status_to_state(raw[0])
        self.logger.debug("%s: Current state: %s", self.label, state)
        return state

    async def read_error_code(self, comm: bool = False) -> int:
        """
        Read the most recent fault code from the fault history.

        The drive has no single "current fault code" register: the live fault
        state is spread over five bitfields, and ``0090h`` holds the most recent
        fault code. This method returns that code, which is what a caller
        comparing against a fault table expects. Use :meth:`read_faults` for the
        live bitfields.

        Args:
            comm: Ignored. The drive reports communication faults as Modbus
                exception responses, not as a register value, so there is no
                communication fault code to read.

        Returns:
            int: The fault code; 0 means no fault.

        Raises:
            ModbusOperationError: If the register cannot be read. A failed read
                is never reported as fault code 0.
        """
        if comm:
            return 0
        raw = await self._read_registers(registers.REG_LAST_FAULT, 1)
        self.logger.debug("%s: Error code %d.", self.label, raw[0])
        return raw[0]

    async def read_faults(self) -> list[VFDError]:
        """
        Read the live fault bitfield.

        Returns:
            list[VFDError]: The faults currently signalled, in ascending bit
                order. An empty list means no fault.

        Raises:
            ModbusOperationError: If the register cannot be read.
        """
        raw = await self._read_registers(registers.REG_FAULT, 1)
        return decode_faults(raw[0], E4_8400_FAULT_BITS)

    async def read_fault_history(self) -> list[int]:
        """
        Read the last three fault codes.

        Returns:
            list[int]: The codes from ``0090h``-``0092h``, most recent first.
                A code of 0 means that slot holds no fault.

        Raises:
            ModbusOperationError: If the registers cannot be read.
        """
        return await self._read_registers(registers.REG_LAST_FAULT, 3)

    def parse_error_code(self, code: int, comm: bool = False) -> VFDError:
        """
        Look a fault code up in the E4-8400 tables.

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

        Args:
            comm: Read the communication fault code back instead of the drive
                fault code. The drive has no such code, so this always reads 0.

        Returns:
            int: The fault code read after the reset; 0 means the fault is gone.
        """
        await self._write_register(registers.REG_COMMAND, registers.control_word(fault_reset=True))
        return await self.read_error_code(comm)

    async def start(self, forward: bool = True, slow: bool = False) -> None:
        """
        Start the motor.

        Args:
            forward: Run in the forward direction; ``False`` runs in reverse.
            slow: Use the jog bit instead of the run bit.
        """
        await self._write_register(
            registers.REG_COMMAND,
            registers.control_word(run=not slow, forward=forward, jog=slow),
        )

    async def stop(self, freewheel: bool = False) -> None:
        """
        Stop the motor.

        The drive has no coast-to-stop bit in the command register: the stop
        behaviour is set by parameter B1-03, so ``freewheel`` is ignored.

        Args:
            freewheel: Ignored; see the class docstring.
        """
        await self._write_register(registers.REG_COMMAND, registers.control_word())

    async def set_frequency(self, frequency_hz: float) -> None:
        """
        Write the frequency setpoint.

        The setpoint register is already in hundredths of a Hz, so no maximum
        frequency is needed. The drive only honours the setpoint when parameter
        B1-01 selects the RS-485 source; see ``vesper/docs/protocol-e4-8400.md``.

        Args:
            frequency_hz: The requested output frequency in Hz.

        Raises:
            ValueError: If the frequency is negative.
        """
        await self._write_register(
            registers.REG_SETPOINT, registers.hz_to_setpoint_raw(frequency_hz)
        )

    async def read_data(self) -> dict[str, Any]:
        """
        Read a snapshot of the drive's current values.

        Returns:
            dict[str, Any]: The `VFDParameters` fields, keyed by field name.
        """
        parameters = await self.read_parameters()
        return {field: getattr(parameters, field) for field in parameters.__struct_fields__}
