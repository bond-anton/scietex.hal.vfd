"""Vesper E5-8200 VFD control over a direct RS485 connection.

This is the point-to-point path: the client owns the serial port and speaks
Modbus RTU to the drive itself. When the drive hangs on a shared bus behind the
Scietex Modbus gateway, use
:class:`scietex.hal.vfd.vesper.e5_8200.client.VesperE58200ModbusVFD` instead and
let the gateway own the port.

The register map and the scaling rules live in :mod:`.registers`; this module
only wires them to the serial transport.
"""

from logging import Logger

from scietex.hal.serial import (
    ModbusOperationError,
    ModbusSerialConnectionConfig,
    SerialConnectionConfig,
)

from ...base.capabilities import VFDCapabilities
from ...base.data import VFDParameters, VFDState
from ...base.rs485 import VFD
from . import registers
from .errors import E5_8200_ERROR_CODES, E5_8200_ERROR_CODES_COM


class VesperE58200(VFD):
    """Vesper E5-8200 VFD over pyModbus"""

    display_name = "Vesper E5-8200"
    capabilities = VFDCapabilities(
        direction=True,
        jog=True,
        freewheel_stop=False,
        fault_reset=True,
        frequency_setpoint=True,
    )

    def __init__(
        self,
        con_params: SerialConnectionConfig | ModbusSerialConnectionConfig,
        address: int = 1,
        label: str = "VFD",
        logger: Logger | None = None,
        max_frequency_hz: float = registers.DEFAULT_MAX_FREQUENCY_HZ,
        **kwargs,
    ):
        """
        Initialize the driver.

        Args:
            con_params: Serial connection parameters.
            address: The drive's Modbus address (parameter 09-00).
            label: Human-readable drive label.
            logger: Optional logger for diagnostics.
            max_frequency_hz: The drive's configured maximum output frequency,
                used only to derive ``frequency_percent``. The communication
                manual names no maximum-frequency parameter, so the factory
                base frequency is the default; pass the configured value when
                the drive runs a different maximum.
        """
        super().__init__(
            con_params=con_params,
            address=address,
            label=label,
            logger=logger,
            **kwargs,
        )
        self.error_codes = E5_8200_ERROR_CODES
        self.error_codes_com = E5_8200_ERROR_CODES_COM
        self.max_frequency_hz = max_frequency_hz

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

    # Errors processing methods
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
        code = await self.read_register(registers.REG_FAULT, holding=True)
        if code is None:
            raise ModbusOperationError(f"Read of the fault register {registers.REG_FAULT} failed")
        return code

    async def clear_error(self, comm: bool = False) -> int:
        """
        Reset the latched fault and read the code back.

        Args:
            comm: Read the communication fault code back instead of the drive
                fault code. The drive has no such code, so this always reads 0.

        Returns:
            int: The fault code read after the reset; 0 means the fault is gone.
        """
        await self.write_register(registers.REG_CONTROL, registers.control_word(fault_reset=True))
        return await self.read_error_code(comm)

    # Parameters monitoring methods
    async def read_parameters(self) -> VFDParameters:
        """
        Read the drive's operating parameters in one transaction.

        The block spans 0x2524..0x2527: output frequency, output voltage, DC bus
        voltage and output current. The drive reports no output power, so that
        field stays 0.0, and no temperature, so both temperature fields stay
        ``None``.

        The run state is read separately and is optional: a drive that refuses
        the monitor register still reports its measurements, so the state falls
        back to ``VFDState.UNKNOWN`` instead of failing the whole snapshot.

        Returns:
            VFDParameters: The decoded parameters. Both hours fields stay
                ``None``: the drive exposes no run-time counter, so the caller
                accumulates the hours.

        Raises:
            ModbusOperationError: If the measurement block cannot be read.
        """
        block = await self.read_registers(
            registers.PARAMETERS_BLOCK_ADDRESS,
            registers.PARAMETERS_BLOCK_COUNT,
            holding=True,
        )
        if block is None:
            raise ModbusOperationError(
                f"Read of the parameters block at {registers.PARAMETERS_BLOCK_ADDRESS} failed"
            )
        offset = registers.PARAMETERS_BLOCK_ADDRESS
        frequency_hz = registers.output_frequency_hz(block[registers.REG_OUTPUT_FREQUENCY - offset])
        return VFDParameters(
            frequency_hz=frequency_hz,
            frequency_percent=self._percent(frequency_hz),
            output_current=registers.output_current_a(block[registers.REG_OUTPUT_CURRENT - offset]),
            output_voltage=registers.output_voltage_v(block[registers.REG_OUTPUT_VOLTAGE - offset]),
            dc_bus_voltage=float(block[registers.REG_DC_BUS_VOLTAGE - offset]),
            state=await self.read_state(),
        )

    async def read_state(self) -> VFDState:
        """
        Read the drive's run state.

        Returns:
            VFDState: The decoded state, or ``VFDState.UNKNOWN`` if the monitor
                register cannot be read.
        """
        monitor = await self._read_optional_register(registers.REG_MONITOR)
        if monitor is None:
            return VFDState.UNKNOWN
        return registers.status_to_state(monitor)

    # VFD Control methods
    async def start(self, forward: bool = True, slow: bool = False) -> None:
        """
        Start the motor.

        Args:
            forward: Run in the forward direction; ``False`` runs in reverse.
            slow: Use the jog bit instead of the run bit.
        """
        await self.write_register(
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
        await self.write_register(registers.REG_CONTROL, registers.control_word())

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
        await self.write_register(
            registers.REG_SETPOINT, registers.hz_to_setpoint_raw(frequency_hz)
        )
