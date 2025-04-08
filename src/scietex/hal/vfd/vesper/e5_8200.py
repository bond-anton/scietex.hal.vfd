"""Vesper E5-8200 VFD RS485 control routines"""

from typing import Union, Optional
from logging import Logger

from scietex.hal.serial import SerialConnectionConfig, ModbusSerialConnectionConfig
from ..base.rs485 import VFD, VFDError, VFDState, VFDParameters


E5_8200_ERROR_CODES = {
    # VFD errors
    0: VFDError(code=0, message="No error"),
    1: VFDError(code=1, message="Overheat of power converter"),
    2: VFDError(code=2, message="Current overload during stop"),
    3: VFDError(code=3, message="Undervoltage error"),
    4: VFDError(code=4, message="Overvoltage error"),
    5: VFDError(code=5, message="Reserved"),
    6: VFDError(code=6, message="External interlock"),
    7: VFDError(code=7, message="Current measurement circuit error"),
    8: VFDError(code=8, message="PID feedback connection loss"),
    9: VFDError(code=9, message="EEPROM IO error"),
    10: VFDError(code=10, message="Automatic tuning failure"),
    11: VFDError(code=11, message="Mechanical moment overload"),
    12: VFDError(code=12, message="VFD overload"),
    13: VFDError(code=13, message="Motor overload"),
    14: VFDError(code=14, message="Remote connection error"),
    15: VFDError(code=15, message="External signal emergency stop"),
    16: VFDError(code=16, message="Parameters locked"),
    17: VFDError(code=17, message="Reserved"),
    18: VFDError(code=18, message="Current overload at constant speed"),
    19: VFDError(code=19, message="Current overload during acceleration"),
    20: VFDError(code=20, message="Current overload during deceleration"),
    21: VFDError(code=21, message="Current overload during start"),
    22: VFDError(code=22, message="Reserved"),
    23: VFDError(code=23, message="Undervoltage during operation error"),
    24: VFDError(code=24, message="Voltage overload during deceleration"),
    25: VFDError(code=25, message="VFD overheat during operation error"),
    26: VFDError(code=26, message="Stop at zeero speed error"),
    27: VFDError(code=27, message="Autostart at power-on impossible"),
    28: VFDError(code=28, message="Control panel emergency stop"),
    29: VFDError(code=29, message="Control panel error"),
    30: VFDError(code=30, message="Parameter change error"),
    31: VFDError(code=31, message="Analog signal error"),
    32: VFDError(code=32, message="Parameter changed during remote connection error"),
    33: VFDError(code=33, message="Connection error"),
    34: VFDError(code=34, message="Parameter change error"),
    35: VFDError(code=35, message="Initialization error"),
    36: VFDError(code=36, message="Reserved"),
    37: VFDError(code=37, message="Reserved"),
    38: VFDError(code=38, message="Copy error with copy device"),
    39: VFDError(code=39, message="Incorrect copying of parameters"),
    40: VFDError(code=40, message="Over speed error"),
    41: VFDError(code=41, message="Input phase error"),
    42: VFDError(code=42, message="Power setting error"),
    43: VFDError(code=43, message="Reserved"),
    44: VFDError(code=44, message="Motor overheat error"),
    45: VFDError(code=45, message="Motor overheat error"),
    46: VFDError(code=46, message="Output current limit error"),
}


E5_8200_ERROR_CODES_COM = {
    # Communication errors
    0: VFDError(code=0, message="No error"),
}


class E5v8200(VFD):
    """Vesper E5-8200 VFD over pyModbus"""

    # pylint: disable=duplicate-code
    def __init__(
        self,
        con_params: Union[SerialConnectionConfig, ModbusSerialConnectionConfig],
        address: int = 1,
        label: str = "VFD",
        logger: Optional[Logger] = None,
        **kwargs,
    ):
        super().__init__(
            con_params=con_params,
            address=address,
            label=label,
            logger=logger,
            **kwargs,
        )
        self.error_codes = E5_8200_ERROR_CODES
        self.error_codes_com = E5_8200_ERROR_CODES_COM

    # Errors processing methods
    async def read_error_code(self, comm: bool = False) -> int:
        """Read error code from the VFD"""
        code: Optional[int]
        if comm:
            code = 0
            self.logger.debug("%s: Communication error code %d.", self.label, code)
        else:
            code = await self.read_register(0x2521, True, signed=False)
            self.logger.debug("%s: Error code %d.", self.label, code)
        if code is not None:
            return code
        return 0

    async def clear_error(self, comm: bool = False) -> int:
        """Clear error from the VFD"""
        self.logger.debug("%s: Clear error.", self.label)
        await self.write_register(0x2501, 8)
        return await self.read_error_code()

    # Parameters monitoring methods
    async def read_parameters(self) -> VFDParameters:
        """Start the VFD"""
        data = await self.read_registers(0x2523, count=5, holding=True)
        state = await self.read_state()
        if data is None:
            return VFDParameters(frequency=0, frequency_percent=0, state=VFDState.UNKNOWN)
        return VFDParameters(
            frequency=data[1],
            frequency_percent=(data[1] / data[0]) * 100,
            output_current=data[4],
            output_voltage=data[2],
            output_power=data[4] * data[2],
            state=state,
        )

    async def read_state(self) -> VFDState:
        """Start the VFD"""
        state = await self.read_register(0x2520, holding=True)
        if state is not None:
            if state & 24:
                return VFDState.UNKNOWN
            if (state & 3) == 3:
                return VFDState.RUNNING_FORWARD
            if (state & 3) == 1:
                return VFDState.RUNNING_BACKWARD
            return VFDState.STOPPED
        return VFDState.UNKNOWN

    # VFD Control methods
    async def start(self, forward: bool = True, slow: bool = False) -> None:
        """Start the VFD"""
        cmd: int = 11
        if not forward:
            cmd = 9
        await self.write_register(0x2501, value=cmd, signed=False)

    async def stop(self, freewheel: bool = False) -> None:
        """Start the VFD"""
        cmd: int = 0
        await self.write_register(0x2501, value=cmd, signed=False)
