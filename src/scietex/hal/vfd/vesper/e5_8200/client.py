"""
Modbus/TCP client for a Vesper E5-8200 drive behind the Scietex Modbus gateway.

The gateway owns the RS485 bus and speaks standard Modbus RTU to the drive once
parameter 09-01 is set to 0; this client speaks plain Modbus/TCP (FC03/FC06) and
addresses the drive by its Modbus unit id. It never touches the RS485 framing.

The drive reports frequency, voltage and current in scaled integer units, so
every reading is converted in :mod:`.registers`. No scale factor has to be read
from the drive first: unlike the Intek SPE-B, the E5-8200 reports frequency
directly in hundredths of a hertz rather than as a percentage of a maximum.

Classes:
    VesperE58200ModbusVFD: A Modbus/TCP client for the Vesper E5-8200 drive.
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
from .errors import E5_8200_ERROR_CODES, E5_8200_ERROR_CODES_COM


class VesperE58200ModbusVFD(VFDProtocol):
    """
    Modbus/TCP client for a Vesper E5-8200 drive behind the gateway.

    The client owns one TCP connection to the gateway and addresses the drive by
    its Modbus unit id. The E5-8200 exposes both rotation directions, jog
    commands, a fault reset and a frequency setpoint register (0x2502), which
    :meth:`set_frequency` writes.

    The drive reports no temperature: overheat reaches the caller only as fault
    code 1 (converter), 25 (converter during operation), 44 or 45 (motor), so
    both temperature fields of `VFDParameters` stay ``None``.

    Attributes:
        label (str): Human-readable drive label.
        capabilities (VFDCapabilities): The E5-8200 control surface.
        error_codes (dict[int, VFDError]): Drive fault code table.
        error_codes_com (dict[int, VFDError]): Communication fault code table.
    """

    capabilities = VFDCapabilities(
        direction=True,
        jog=True,
        freewheel_stop=False,
        fault_reset=True,
        frequency_setpoint=True,
    )
    display_name = "Vesper E5-8200"

    def __init__(
        self,
        host: str,
        port: int = 502,
        unit_id: int = 1,
        label: str = "Vesper E5-8200",
        timeout: float = 1.0,
        logger: Logger | None = None,
        max_frequency_hz: float = registers.DEFAULT_MAX_FREQUENCY_HZ,
    ) -> None:
        """
        Initialize the client.

        Args:
            host: Gateway host name or address.
            port: Gateway TCP port.
            unit_id: Modbus unit id the gateway routes to the drive. This is the
                drive's 09-00 address.
            label: Human-readable drive label.
            timeout: Per-request timeout in seconds.
            logger: Optional logger for diagnostics.
            max_frequency_hz: The drive's configured maximum output frequency,
                used only to derive ``frequency_percent``. The communication
                manual names no maximum-frequency parameter, so the factory
                base frequency is the default; pass the configured value when
                the drive runs a different maximum.
        """
        self.label = label
        self.unit_id = unit_id
        self.logger = logger if logger is not None else getLogger(__name__)
        self.error_codes = E5_8200_ERROR_CODES
        self.error_codes_com = E5_8200_ERROR_CODES_COM
        self.max_frequency_hz = max_frequency_hz
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

    def _percent(self, frequency_hz: float) -> float:
        """
        Convert a frequency into a percentage of the configured maximum.

        Args:
            frequency_hz: The frequency in Hz.

        Returns:
            float: The percentage, or 0.0 when the maximum is not positive.
        """
        if self.max_frequency_hz <= 0:
            return 0.0
        return frequency_hz / self.max_frequency_hz * 100.0

    async def read_parameters(self) -> VFDParameters:
        """
        Read the drive's operating parameters in one transaction.

        The block spans 0x2524..0x2527: output frequency, output voltage, DC bus
        voltage and output current. The drive reports no output power, so that
        field stays 0.0, and no temperature, so both temperature fields stay
        ``None``.

        Returns:
            VFDParameters: The decoded parameters.

        Raises:
            ModbusOperationError: If the block cannot be read.
        """
        block = await self._read_registers(
            registers.PARAMETERS_BLOCK_ADDRESS, registers.PARAMETERS_BLOCK_COUNT
        )
        offset = registers.PARAMETERS_BLOCK_ADDRESS
        frequency_hz = registers.output_frequency_hz(block[registers.REG_OUTPUT_FREQUENCY - offset])
        parameters = VFDParameters(
            frequency_hz=frequency_hz,
            frequency_percent=self._percent(frequency_hz),
            output_current=registers.output_current_a(block[registers.REG_OUTPUT_CURRENT - offset]),
            output_voltage=registers.output_voltage_v(block[registers.REG_OUTPUT_VOLTAGE - offset]),
            dc_bus_voltage=float(block[registers.REG_DC_BUS_VOLTAGE - offset]),
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
            ModbusOperationError: If the monitor register cannot be read.
        """
        raw = await self._read_registers(registers.REG_MONITOR, 1)
        state = registers.status_to_state(raw[0])
        self.logger.debug("%s: Current state: %s", self.label, state)
        return state

    async def read_error_code(self, comm: bool = False) -> int:
        """
        Read the latched fault code.

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
        raw = await self._read_registers(registers.REG_FAULT, 1)
        self.logger.debug("%s: Error code %d.", self.label, raw[0])
        return raw[0]

    def parse_error_code(self, code: int, comm: bool = False) -> VFDError:
        """
        Look a fault code up in the E5-8200 tables.

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
        await self._write_register(registers.REG_CONTROL, registers.control_word(fault_reset=True))
        return await self.read_error_code(comm)

    async def start(self, forward: bool = True, slow: bool = False) -> None:
        """
        Start the motor.

        Args:
            forward: Run in the forward direction; ``False`` runs in reverse.
            slow: Use the jog bit instead of the run bit.
        """
        await self._write_register(
            registers.REG_CONTROL,
            registers.control_word(run=not slow, forward=forward, jog=slow),
        )

    async def stop(self, freewheel: bool = False) -> None:
        """
        Stop the motor.

        The drive has no coast-to-stop bit in the control register: the stop
        behaviour is set by parameter 09-07, so ``freewheel`` is ignored.

        Args:
            freewheel: Ignored; see the class docstring.
        """
        await self._write_register(registers.REG_CONTROL, registers.control_word())

    async def set_frequency(self, frequency_hz: float) -> None:
        """
        Write the frequency setpoint.

        The drive only honours the setpoint when parameter 00-05 selects the
        RS-485 source; see ``vesper/docs/protocol-e5-8200.md``.

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
