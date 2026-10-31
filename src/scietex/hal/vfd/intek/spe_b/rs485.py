"""Intek SPE-B VFD control over a direct RS485 connection.

This is the point-to-point path: the client owns the serial port and speaks
Modbus RTU to the drive itself. When the drive hangs on a shared bus behind the
Scietex Modbus gateway, use
:class:`scietex.hal.vfd.intek.spe_b.client.IntekSPEBModbusVFD` instead and let
the gateway own the port.

The register map and the scaling rules live in :mod:`.registers`; this module
only wires them to the serial transport.
"""

from logging import Logger

from scietex.hal.serial import (
    ModbusOperationError,
    ModbusSerialConnectionConfig,
    SerialConnectionConfig,
)

from ...base.data import VFDParameters, VFDState
from ...base.rs485 import VFD
from . import registers
from .errors import SPE_B_ERROR_CODES, SPE_B_ERROR_CODES_COM


class SPEvB(VFD):
    """Intek SPE-B VFD over pyModbus"""

    display_name = "Intek SPE-B"

    def __init__(
        self,
        con_params: SerialConnectionConfig | ModbusSerialConnectionConfig,
        address: int = 1,
        label: str = "VFD",
        logger: Logger | None = None,
        **kwargs,
    ):
        super().__init__(
            con_params=con_params,
            address=address,
            label=label,
            logger=logger,
            **kwargs,
        )
        self.error_codes = SPE_B_ERROR_CODES
        self.error_codes_com = SPE_B_ERROR_CODES_COM
        # Scale factors are read from the drive on the first parameters read:
        # the serial client opens the port per operation, so there is no
        # connection event to hook them onto.
        self._max_frequency_hz: float | None = None
        self._current_resolution = registers.CURRENT_RESOLUTION_FINE

    async def _read_scale_factors(self) -> None:
        """
        Read P0.10 and Pd.06 from the drive once and cache them.

        P0.10 is optional: a drive that refuses it still reports its operating
        percentage, current, voltage and power, so only ``frequency_hz``
        degrades to ``None``. Raising here would fail the whole snapshot.
        """
        raw = await self.read_register(
            registers.PARAM_MAX_FREQUENCY_EEPROM,
            holding=True,
            raise_on_error=False,
        )
        self._max_frequency_hz = (raw or 0) / registers.PARAMETER_FREQUENCY_RESOLUTION
        if self._max_frequency_hz <= 0:
            self.logger.warning(
                "%s: P0.10 reads %s, frequency is reported as None.", self.label, raw
            )
        # Pd.06 only refines the current reading, so a drive that refuses the
        # read keeps working with the factory resolution.
        raw = await self.read_register(
            registers.PARAM_CURRENT_RESOLUTION_EEPROM,
            holding=True,
            raise_on_error=False,
        )
        self._current_resolution = (
            registers.CURRENT_RESOLUTION_COARSE if raw == 1 else registers.CURRENT_RESOLUTION_FINE
        )

    # Errors processing methods
    async def read_error_code(self, comm: bool = False) -> int:
        """Read the latched fault code from the VFD"""
        register = registers.REG_COMM_FAULT if comm else registers.REG_DRIVE_FAULT
        code = await self.read_register(register, holding=True)
        if code is None:
            raise ModbusOperationError(f"Read of error code register {register} failed")
        if comm:
            self.logger.debug("%s: Communication error code %d.", self.label, code)
        else:
            self.logger.debug("%s: Error code %d.", self.label, code)
        return code

    async def clear_error(self, comm: bool = False) -> int:
        """Reset the latched fault and read the code back"""
        self.logger.debug("%s: Clear error.", self.label)
        await self.write_register(registers.REG_CONTROL, registers.CONTROL_FAULT_RESET)
        return await self.read_error_code(comm)

    # Parameters monitoring methods
    async def read_parameters(self) -> VFDParameters:
        """Read the VFD operating parameters"""
        if self._max_frequency_hz is None:
            await self._read_scale_factors()
        block = await self.read_registers(
            registers.PARAMETERS_BLOCK_ADDRESS,
            registers.PARAMETERS_BLOCK_COUNT,
            holding=True,
        )
        if block is None:
            raise ModbusOperationError(
                f"Read of the parameters block at {registers.PARAMETERS_BLOCK_ADDRESS} failed"
            )
        percent = registers.frequency_raw_to_percent(
            block[registers.REG_OPERATING_FREQUENCY - registers.PARAMETERS_BLOCK_ADDRESS]
        )
        current = (
            block[registers.REG_OUTPUT_CURRENT - registers.PARAMETERS_BLOCK_ADDRESS]
            * self._current_resolution
        )
        frequency_hz = (
            registers.percent_to_hz(percent, self._max_frequency_hz)
            if self._max_frequency_hz
            else None
        )
        state = await self.read_state()
        return VFDParameters(
            frequency_hz=frequency_hz,
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
            state=state,
        )

    async def read_state(self) -> VFDState:
        """Read the VFD run state"""
        status = await self._read_optional_register(registers.REG_STATUS)
        if status is None:
            return VFDState.UNKNOWN
        return registers.status_to_state(status)

    # VFD Control methods
    async def start(self, forward: bool = True, slow: bool = False) -> None:
        """Start the VFD"""
        await self.write_register(registers.REG_CONTROL, registers.start_command(forward, slow))

    async def stop(self, freewheel: bool = False) -> None:
        """Stop the VFD"""
        await self.write_register(registers.REG_CONTROL, registers.stop_command(freewheel))

    async def set_frequency(self, frequency_hz: float) -> None:
        """Write the communication-protocol frequency setpoint"""
        if self._max_frequency_hz is None:
            await self._read_scale_factors()
        if not self._max_frequency_hz:
            raise ValueError(
                f"{self.label}: maximum frequency (P0.10) is unknown; cannot set a setpoint"
            )
        percent = registers.hz_to_percent(frequency_hz, self._max_frequency_hz)
        if percent > 100.0:
            raise ValueError(
                f"{self.label}: {frequency_hz} Hz exceeds the maximum {self._max_frequency_hz} Hz"
            )
        raw = round(percent * registers.FREQUENCY_PERCENT_RESOLUTION)
        await self.write_register(registers.REG_COMM_SETPOINT, raw)
