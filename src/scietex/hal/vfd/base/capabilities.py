"""
VFD capability model.

A drive advertises what it can do through a single :class:`VFDCapabilities`
value. The fields are the operations a caller can dispatch without inspecting
the driver: whether the drive accepts a direction choice, a jog command, a
coasting stop, a fault reset, and a frequency setpoint.

The set is a frozen dataclass so a driver declares it once as a class attribute
and callers cannot mutate it.

Capabilities describe the *control* surface only. Whether a drive reports a
particular *reading* — a heatsink temperature, a DC bus voltage — is answered by
the corresponding :class:`scietex.hal.vfd.base.data.VFDParameters` field being
``None``, not by a flag here. One source of truth cannot drift from the driver.

Classes:
    VFDCapabilities: The control surface of one drive.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VFDCapabilities:
    """
    The control surface of one drive.

    Every field defaults to "unsupported", so a driver declares only what its
    hardware exposes. Read-side operations (parameters, state, error code) are
    mandatory for every driver and are therefore not advertised here.

    Attributes:
        direction (bool): Whether the drive can be started in either rotation
            direction. ``False`` means forward only.
        jog (bool): Whether the drive accepts a jog command.
        freewheel_stop (bool): Whether the drive can stop by coasting instead of
            ramping down.
        fault_reset (bool): Whether the drive accepts an explicit fault reset.
        frequency_setpoint (bool): Whether the drive accepts a frequency
            setpoint over the communication protocol, independent of the
            keypad or an analog input.
    """

    direction: bool = True
    jog: bool = False
    freewheel_stop: bool = False
    fault_reset: bool = False
    frequency_setpoint: bool = False
