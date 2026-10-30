"""Vesper E4-8400 / E4-P8402 VFD control over a direct RS485 connection.

This is the point-to-point path: the client owns the serial port and speaks
Modbus RTU to the drive itself. When the drive hangs on a shared bus behind the
Scietex Modbus gateway, use
:class:`scietex.hal.vfd.vesper.e4_8400.client.VesperE48400ModbusVFD` instead and
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
from ...base.data import VFDError, VFDParameters, VFDState
from ...base.rs485 import VFD
from . import registers
from .errors import (
    E4_8400_ERROR_CODES_COM,
    E4_8400_FAULT_BITS,
    E4_8400_FAULT_CODES,
    decode_faults,
)


class VesperE48400(VFD):
    """Vesper E4-8400 / E4-P8402 VFD over pyModbus"""

    display_name = "Vesper E4-8400"
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
        max_frequency_hz: float | None = None,
        **kwargs,
    ):
        """
        Initialize the driver.

        Args:
            con_params: Serial connection parameters.
            address: The drive's Modbus address (parameter H5-01).
            label: Human-readable drive label.
            logger: Optional logger for diagnostics.
            max_frequency_hz: The drive's maximum output frequency, used only to
                derive ``frequency_percent``. ``None`` reads parameter E1-04
                from the drive on the first parameters read; pass a value to
                skip that read.
        """
        super().__init__(
            con_params=con_params,
            address=address,
            label=label,
            logger=logger,
            **kwargs,
        )
        self.error_codes = E4_8400_FAULT_CODES
        self.error_codes_com = E4_8400_ERROR_CODES_COM
        self._max_frequency_hz = max_frequency_hz

    async def _read_max_frequency(self) -> float:
        """
        Read parameter E1-04 and cache it.

        Returns:
            float: The maximum output frequency in Hz, or 0.0 when the drive
                reports a non-positive value.
        """
        if self._max_frequency_hz is None:
            raw = await self.read_register(
                registers.parameter_register(registers.PARAM_MAX_FREQUENCY), holding=True
            )
            self._max_frequency_hz = (raw or 0) / registers.FREQUENCY_RESOLUTION
            if self._max_frequency_hz <= 0:
                self.logger.warning(
                    "%s: E1-04 reads %s, frequency is reported as 0%%.", self.label, raw
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

    # Errors processing methods
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
        code = await self.read_register(registers.REG_LAST_FAULT, holding=True)
        if code is None:
            raise ModbusOperationError(
                f"Read of the fault register {registers.REG_LAST_FAULT} failed"
            )
        return code

    async def read_faults(self) -> list[VFDError]:
        """
        Read the live fault bitfield.

        Returns:
            list[VFDError]: The faults currently signalled, in ascending bit
                order. An empty list means no fault.

        Raises:
            ModbusOperationError: If the register cannot be read.
        """
        raw = await self.read_register(registers.REG_FAULT, holding=True)
        if raw is None:
            raise ModbusOperationError(f"Read of the fault register {registers.REG_FAULT} failed")
        return decode_faults(raw, E4_8400_FAULT_BITS)

    async def read_fault_history(self) -> list[int]:
        """
        Read the last three fault codes.

        Returns:
            list[int]: The codes from ``0090h``-``0092h``, most recent first.
                A code of 0 means that slot holds no fault.

        Raises:
            ModbusOperationError: If the registers cannot be read.
        """
        block = await self.read_registers(registers.REG_LAST_FAULT, 3, holding=True)
        if block is None:
            raise ModbusOperationError(
                f"Read of the fault history at {registers.REG_LAST_FAULT} failed"
            )
        return list(block)

    async def clear_error(self, comm: bool = False) -> int:
        """
        Reset the latched fault and read the code back.

        Args:
            comm: Read the communication fault code back instead of the drive
                fault code. The drive has no such code, so this always reads 0.

        Returns:
            int: The fault code read after the reset; 0 means the fault is gone.
        """
        await self.write_register(registers.REG_COMMAND, registers.control_word(fault_reset=True))
        return await self.read_error_code(comm)

    # Parameters monitoring methods
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
        voltage = await self.read_register(registers.REG_OUTPUT_VOLTAGE, holding=True)
        dc_bus = await self.read_register(registers.REG_DC_BUS_VOLTAGE, holding=True)
        temperature = await self.read_register(registers.REG_HEATSINK_TEMPERATURE, holding=True)
        return VFDParameters(
            frequency_hz=frequency_hz,
            frequency_percent=self._percent(frequency_hz),
            output_current=registers.output_current_a(block[registers.REG_OUTPUT_CURRENT - offset]),
            output_voltage=float(voltage or 0),
            dc_bus_voltage=float(dc_bus) if dc_bus is not None else None,
            heatsink_temperature_c=float(temperature) if temperature is not None else None,
            state=await self.read_state(),
        )

    async def read_state(self) -> VFDState:
        """
        Read the drive's run state.

        Returns:
            VFDState: The decoded state, or ``VFDState.UNKNOWN`` if the status
                register cannot be read.
        """
        status = await self.read_register(registers.REG_STATUS, holding=True)
        if status is None:
            return VFDState.UNKNOWN
        return registers.status_to_state(status)

    # VFD Control methods
    async def start(self, forward: bool = True, slow: bool = False) -> None:
        """
        Start the motor.

        Args:
            forward: Run in the forward direction; ``False`` runs in reverse.
            slow: Use the jog bit instead of the run bit.
        """
        await self.write_register(
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
        await self.write_register(registers.REG_COMMAND, registers.control_word())

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
        await self.write_register(
            registers.REG_SETPOINT, registers.hz_to_setpoint_raw(frequency_hz)
        )
