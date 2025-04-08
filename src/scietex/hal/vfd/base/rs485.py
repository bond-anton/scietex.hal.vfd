"""Basic VD device prototype class to be inherited by particular implementations."""

from typing import Union, Optional, Any
from logging import Logger

from scietex.hal.serial import RS485Client, SerialConnectionConfig, ModbusSerialConnectionConfig

from .data import VFDError, VFDState, VFDParameters, VFDStartCMD, VFDStopCMD


class VFD(RS485Client):
    """VFD control base class"""

    # pylint: disable=too-many-public-methods

    def __init__(
        self,
        con_params: Union[SerialConnectionConfig, ModbusSerialConnectionConfig],
        address: int = 1,
        label: str = "VFD",
        logger: Optional[Logger] = None,
        **kwargs,
    ):
        # pylint: disable=too-many-arguments
        super().__init__(
            con_params=con_params,
            address=address,
            label=label,
            logger=logger,
            **kwargs,
        )
        self.error_codes: dict[int, VFDError] = {0: VFDError(code=0, message="No error")}
        self.error_codes_com: dict[int, VFDError] = {0: VFDError(code=0, message="No error")}

    # Errors processing methods
    async def read_error_code(self, comm: bool = False) -> int:
        """Read error code from the VFD"""
        code = 0
        if comm:
            self.logger.debug("%s: Communication error code %d.", self.label, code)
        else:
            self.logger.debug("%s: Error code %d.", self.label, code)
        return code

    def parse_error_code(self, code: int, comm: bool = False) -> VFDError:
        """Parse error code from the VFD"""
        if comm:
            if code in self.error_codes_com:
                return self.error_codes_com[code]
        else:
            if code in self.error_codes:
                return self.error_codes[code]
        return VFDError(code=code, message="Unknown error")

    async def clear_error(self, comm: bool = False) -> int:
        """Clear error from the VFD"""
        if comm:
            self.logger.debug("%s: Clear communication error.", self.label)
        else:
            self.logger.debug("%s: Clear error.", self.label)
        return await self.read_error_code()

    # Parameters monitoring methods
    async def read_parameters(self) -> VFDParameters:
        """Start the VFD"""
        parameters = VFDParameters(frequency=0.0, frequency_percent=0.0)
        self.logger.debug("%s: %s", self.label, parameters)
        return parameters

    async def read_state(self) -> VFDState:
        """Start the VFD"""
        state = VFDState.UNKNOWN
        self.logger.debug("%s: Current state: %s", self.label, state)
        return state

    # VFD Control methods
    async def start(self, forward: bool = True, slow: bool = False) -> None:
        """Start the VFD"""
        self.logger.debug("%s: Start (forward: %s, slow: %s)", self.label, forward, slow)

    # pylint: disable=unused-argument
    async def stop(self, freewheel: bool = False) -> None:
        """Start the VFD"""
        self.logger.debug("%s: Start (freewheel: %s)", self.label, freewheel)

    async def read_data(self):
        parameters = await self.read_parameters()
        return {f: getattr(parameters, f) for f in parameters.__struct_fields__}

    async def process_message(self, message: dict[str, Any]) -> None:
        await super().process_message(message)
        if "cmd" in message:
            if message["cmd"] == "start":
                start_params = VFDStartCMD()
                if "data" in message:
                    try:
                        start_params = VFDStartCMD(**message["data"])
                    except (TypeError, ValueError):
                        pass
                await self.start(forward=start_params.forward, slow=start_params.slow)
            elif message["cmd"] == "stop":
                stop_params = VFDStopCMD()
                if "data" in message:
                    try:
                        stop_params = VFDStopCMD(**message["data"])
                    except (TypeError, ValueError):
                        pass
                await self.stop(freewheel=stop_params.freewheel)
            elif message["cmd"] == "clear_error":
                await self.clear_error()
