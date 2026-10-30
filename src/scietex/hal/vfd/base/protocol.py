"""
VFD protocol.

This module defines the transport-agnostic contract every variable frequency
drive driver implements, plus the capability model that tells a caller which
optional control operations a given drive supports. The contract is deliberately
narrow: a driver must be able to connect, disconnect, read the operating
parameters and state, read and reset the fault code, start and stop the motor,
and set the frequency. Everything else — a jog command, for example — is
advertised through :attr:`VFDProtocol.capabilities`, so a caller can reject an
unsupported command before dispatching it instead of catching an exception after
the fact.

The same contract covers both transports in this package: the direct RS485
clients derived from :class:`scietex.hal.vfd.base.rs485.VFD` and the Modbus/TCP
clients that address a drive through the Scietex Modbus gateway.

Classes:
    VFDProtocol: The runtime-checkable protocol every drive driver satisfies.
"""

from typing import Any, Protocol, runtime_checkable

from .capabilities import VFDCapabilities
from .data import VFDParameters, VFDState


@runtime_checkable
class VFDProtocol(Protocol):
    """
    Contract implemented by every variable frequency drive driver.

    Attributes:
        label (str): Human-readable drive label, unique within a service.
        capabilities (VFDCapabilities): What this drive can do.
        display_name (str): Model name reported to the user interface.
    """

    label: str

    capabilities: VFDCapabilities = VFDCapabilities()
    display_name: str = "VFD"

    async def connect(self) -> None:
        """Open the transport to the drive."""

    async def close(self) -> None:
        """Close the transport to the drive."""

    async def read_data(self) -> dict[str, Any]:
        """
        Read a snapshot of the drive's current values.

        Returns:
            dict[str, Any]: Field name to value mapping. ``state`` is always
                present; the remaining keys depend on the driver.
        """

    async def read_parameters(self) -> VFDParameters:
        """
        Read the drive's operating parameters.

        Returns:
            VFDParameters: Frequency in both Hz and percent of the configured
                maximum, output current, voltage, power and state, plus the
                optional DC bus voltage and temperatures the drive reports.
        """

    async def read_state(self) -> VFDState:
        """
        Read the drive's run state.

        Returns:
            VFDState: The state, or ``VFDState.UNKNOWN`` when the drive reports
                a value the protocol does not define.
        """

    async def read_error_code(self, comm: bool = False) -> int:
        """
        Read the latched fault code.

        Args:
            comm: Read the communication-protocol fault code instead of the
                drive fault code.

        Returns:
            int: The fault code; ``0`` means no fault.
        """

    async def clear_error(self, comm: bool = False) -> int:
        """
        Reset the latched fault and read the code back.

        Args:
            comm: Reset the communication-protocol fault instead of the drive
                fault.

        Returns:
            int: The fault code read after the reset; ``0`` means the fault is
                gone.
        """

    async def start(self, forward: bool = True, slow: bool = False) -> None:
        """
        Start the motor.

        Args:
            forward: Run in the forward direction; ``False`` runs in reverse.
            slow: Use the jog (slow) command instead of the normal run command.
        """

    async def stop(self, freewheel: bool = False) -> None:
        """
        Stop the motor.

        Args:
            freewheel: Coast to a stop instead of ramping down.
        """

    async def set_frequency(self, frequency_hz: float) -> None:
        """
        Set the frequency setpoint.

        The value is in Hz, not percent: the caller works in engineering units
        and each driver converts with its own maximum-frequency parameter.

        Args:
            frequency_hz: The requested output frequency in Hz.
        """
