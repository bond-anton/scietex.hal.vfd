"""Basic VFD device prototype class to be inherited by particular implementations."""

from logging import Logger
from typing import Any

from scietex.hal.serial import (
    ModbusSerialConnectionConfig,
    RS485Client,
    SerialConnectionConfig,
)

from .capabilities import VFDCapabilities
from .data import (
    VFDClearErrorCMD,
    VFDError,
    VFDParameters,
    VFDSetFrequencyCMD,
    VFDStartCMD,
    VFDState,
    VFDStopCMD,
)
from .protocol import VFDProtocol


class VFD(RS485Client, VFDProtocol):
    """VFD control base class"""

    capabilities = VFDCapabilities()
    display_name = "VFD"

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
        self.error_codes: dict[int, VFDError] = {0: VFDError(code=0, message="No error")}
        self.error_codes_com: dict[int, VFDError] = {0: VFDError(code=0, message="No error")}

    async def connect(self) -> None:
        """Nothing to do: the serial client opens the port once per operation."""
        self.logger.debug("%s: Connect (per-operation serial client).", self.label)

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
        return await self.read_error_code(comm)

    # Parameters monitoring methods
    async def read_parameters(self) -> VFDParameters:
        """Read the VFD operating parameters"""
        parameters = VFDParameters(frequency_hz=0.0, frequency_percent=0.0)
        self.logger.debug("%s: %s", self.label, parameters)
        return parameters

    async def read_state(self) -> VFDState:
        """Read the VFD run state"""
        state = VFDState.UNKNOWN
        self.logger.debug("%s: Current state: %s", self.label, state)
        return state

    # VFD Control methods
    async def start(self, forward: bool = True, slow: bool = False) -> None:
        """Start the VFD"""
        self.logger.debug("%s: Start (forward: %s, slow: %s)", self.label, forward, slow)

    async def stop(self, freewheel: bool = False) -> None:
        """Stop the VFD"""
        self.logger.debug("%s: Stop (freewheel: %s)", self.label, freewheel)

    async def set_frequency(self, frequency_hz: float) -> None:
        """Set the VFD frequency setpoint"""
        self.logger.debug("%s: Set frequency %s Hz.", self.label, frequency_hz)

    async def read_data(self) -> dict[str, Any]:
        """
        Read the VFD operating parameters as a plain dictionary.

        The return type is widened to ``Any`` because `VFDParameters` carries
        optional fields (temperatures, DC bus voltage) that are ``None`` when the
        drive does not report them, which the inherited `RS485Client` signature
        does not allow.
        """
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
                clear_params = VFDClearErrorCMD()
                if "data" in message:
                    try:
                        clear_params = VFDClearErrorCMD(**message["data"])
                    except (TypeError, ValueError):
                        pass
                await self.clear_error(comm=clear_params.communication)
            elif message["cmd"] == "set_frequency":
                frequency_params = VFDSetFrequencyCMD()
                if "data" in message:
                    try:
                        frequency_params = VFDSetFrequencyCMD(**message["data"])
                    except (TypeError, ValueError):
                        pass
                await self.set_frequency(frequency_hz=frequency_params.frequency_hz)
