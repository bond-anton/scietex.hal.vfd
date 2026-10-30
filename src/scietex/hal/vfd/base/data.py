"""VFD data structures.

:class:`VFDParameters` names the operating frequency ``frequency_hz`` so it
cannot be confused with ``frequency_percent``, which is the unit some drives
report natively. The two frequency fields are the only ones guaranteed to be
populated; every other field is optional and stays ``None`` when the drive's
protocol does not expose it.

``None`` and ``0.0`` mean different things throughout this module: ``None`` is
"this drive does not report the value", ``0.0`` is "the drive reports zero".
A caller that plots a temperature must check for ``None`` rather than treating
a missing reading as a cold drive.
"""

from enum import Enum

import msgspec


class VFDState(Enum):
    """Possible states of a Variable Frequency Drive (VFD)."""

    UNKNOWN = 0
    STOPPED = 1
    RUNNING_FORWARD = 2
    RUNNING_BACKWARD = 3  # or RUNNING_REVERSE

    def __str__(self) -> str:
        """Return a human-readable string representation."""
        return self.name.replace("_", " ").title()


class VFDError(msgspec.Struct, frozen=True):
    """Model of a VFD error with code and message."""

    code: int
    message: str = "Unknown error"

    def __str__(self) -> str:
        return f"VFDError(code={self.code}, message='{self.message}')"


class VFDParameters(msgspec.Struct, frozen=True):
    """Model for VFD operational parameters.

    Attributes:
        frequency_hz: Output frequency in Hz.
        frequency_percent: Output frequency as a percentage of the configured
            maximum, 0-100.
        output_current: Output current in Amps.
        output_voltage: Output voltage in Volts.
        output_power: Output power in kW.
        dc_bus_voltage: DC bus (link) voltage in Volts, or ``None`` when the
            drive does not report it.
        heatsink_temperature_c: Power-module or heatsink temperature in degrees
            Celsius, or ``None`` when the drive does not report it. A drive that
            signals overheat only through a fault code reports ``None`` here:
            a fault is not a temperature.
        motor_temperature_c: Motor winding or PTC temperature in degrees
            Celsius, or ``None`` when the drive does not report it.
        state: Current VFD state.
    """

    frequency_hz: float  # Current operating frequency in Hz
    frequency_percent: float  # Frequency as a percentage of max (0-100%)
    output_current: float = 0.0  # Output current in Amps
    output_voltage: float = 0.0  # Output voltage in Volts
    output_power: float = 0.0  # Output power in kW
    dc_bus_voltage: float | None = None  # DC bus voltage in Volts
    heatsink_temperature_c: float | None = None  # Power-module temperature, deg C
    motor_temperature_c: float | None = None  # Motor temperature, deg C
    state: VFDState = VFDState.STOPPED  # Current VFD state

    def __str__(self) -> str:
        return (
            f"VFDParameters(frequency={self.frequency_hz} Hz, "
            f"frequency_percent={self.frequency_percent}%, "
            f"current={self.output_current} A, "
            f"voltage={self.output_voltage} V, "
            f"power={self.output_power} kW, "
            f"dc_bus={self.dc_bus_voltage} V, "
            f"heatsink={self.heatsink_temperature_c} C, "
            f"motor={self.motor_temperature_c} C, "
            f"state={self.state})"
        )


class VFDStartCMD(msgspec.Struct, frozen=True):
    """VFD start command."""

    forward: bool = True
    slow: bool = False

    def __str__(self) -> str:
        return f"VFDStartCMD(forward={self.forward}, slow={self.slow})"


class VFDStopCMD(msgspec.Struct, frozen=True):
    """VFD stop command."""

    freewheel: bool = False

    def __str__(self) -> str:
        return f"VFDStopCMD(freewheel={self.freewheel})"


class VFDClearErrorCMD(msgspec.Struct, frozen=True):
    """VFD clear error command."""

    communication: bool = False

    def __str__(self) -> str:
        return f"VFDClearErrorCMD(communication={self.communication})"


class VFDSetFrequencyCMD(msgspec.Struct, frozen=True):
    """VFD frequency setpoint command."""

    frequency_hz: float = 0.0

    def __str__(self) -> str:
        return f"VFDSetFrequencyCMD(frequency_hz={self.frequency_hz})"
