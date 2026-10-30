"""
Base VFD subpackage.

Provides the transport-agnostic driver contract, the capability model, the
shared data structures, and the RS485 base class the direct-serial drivers
derive from.

Classes:
    VFD: Base class for drivers that own a serial connection.
    VFDCapabilities: The control surface of one drive.
    VFDError: A fault code paired with its message.
    VFDParameters: A snapshot of the drive's operating parameters.
    VFDProtocol: The contract every driver implements.
    VFDState: The drive run state.

Modules:
    protocol: Defines the `VFDProtocol` driver contract.
    capabilities: Defines the `VFDCapabilities` model.
    data: Defines the data structures shared by every driver.
    rs485: Defines the `VFD` serial base class.
"""

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
from .rs485 import VFD

__all__ = [
    "VFD",
    "VFDCapabilities",
    "VFDClearErrorCMD",
    "VFDError",
    "VFDParameters",
    "VFDProtocol",
    "VFDSetFrequencyCMD",
    "VFDStartCMD",
    "VFDState",
    "VFDStopCMD",
]
