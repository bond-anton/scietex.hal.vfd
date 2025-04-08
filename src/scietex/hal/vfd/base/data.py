"""VFD data structures."""

from enum import Enum
import msgspec


class VFDState(Enum):
    """Possible states of a Variable Frequency Drive (VFD)."""

    UNKNOWN = 0
    STOPPED = 1
    RUNNING_FORWARD = 2
    RUNNING_BACKWARD = 3  # or RUNNING_REVERSE

    def __str__(self):
        """Return a human-readable string representation."""
        return self.name.replace("_", " ").title()


# pylint: disable=too-few-public-methods
class VFDError(msgspec.Struct, frozen=True):
    """Model of a VFD error with code and message."""

    code: int
    message: str = "Unknown error"

    def __str__(self) -> str:
        return f"VFDError(code={self.code}, message='{self.message}')"


# pylint: disable=too-few-public-methods
class VFDParameters(msgspec.Struct, frozen=True):
    """Model for VFD operational parameters."""

    frequency: float  # Current operating frequency in Hz
    frequency_percent: float  # Frequency as a percentage of max (0-100%)
    output_current: float = 0.0  # Output current in Amps
    output_voltage: float = 0.0  # Output voltage in Volts
    output_power: float = 0.0  # Output power in kW
    state: VFDState = VFDState.STOPPED  # Current VFD state

    def __str__(self) -> str:
        return (
            f"VFDParameters(frequency={self.frequency} Hz, "
            f"frequency_percent={self.frequency_percent}%, "
            f"current={self.output_current} A, "
            f"voltage={self.output_voltage} V, "
            f"power={self.output_power} kW, "
            f"state={self.state})"
        )


# pylint: disable=too-few-public-methods
class VFDStartCMD(msgspec.Struct, frozen=True):
    """VFD start command."""

    forward: bool = True
    slow: bool = False

    def __str__(self) -> str:
        return f"VFDStartCMD(forward={self.forward}, slow={self.slow})"


# pylint: disable=too-few-public-methods
class VFDStopCMD(msgspec.Struct, frozen=True):
    """VFD stop command."""

    freewheel: bool = False

    def __str__(self) -> str:
        return f"VFDStopCMD(freewheel={self.freewheel})"


# pylint: disable=too-few-public-methods
class VFDClearErrorCMD(msgspec.Struct, frozen=True):
    """VFD clear error command."""

    communication: bool = False

    def __str__(self) -> str:
        return f"VFDClearErrorCMD(communication={self.communication})"
