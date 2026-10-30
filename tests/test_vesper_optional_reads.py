"""
Tests for the optional readings in the Vesper gateway clients.

A poll loop publishes whatever `read_parameters` returns, so a drive that
refuses one diagnostic register must still report its frequency, current and
voltage. Only the measurement block is mandatory; the run state and the
separate diagnostic registers degrade to ``None`` / ``VFDState.UNKNOWN``.

The pymodbus client is replaced by a stub that returns canned responses, so
these cover the degradation rules rather than the transport.
"""

import asyncio

import pytest
from pymodbus.pdu import ExceptionResponse
from pymodbus.pdu.register_message import ReadHoldingRegistersResponse
from scietex.hal.serial import ModbusOperationError

from scietex.hal.vfd.base.data import VFDState
from scietex.hal.vfd.vesper.e4_8400 import registers as e4_registers
from scietex.hal.vfd.vesper.e4_8400.client import VesperE48400ModbusVFD
from scietex.hal.vfd.vesper.e5_8200 import registers as e5_registers
from scietex.hal.vfd.vesper.e5_8200.client import VesperE58200ModbusVFD

#: E1-04 = 50.00 Hz, the factory maximum output frequency.
E4_MAX_FREQUENCY_RAW = 5000


class _StubClient:
    """Stand-in for `AsyncModbusTcpClient` that replays canned responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def read_holding_registers(self, address, *, count=1, device_id=1):
        """Record the read and return the next canned response."""
        self.calls.append(("read", address, count, device_id))
        if not self.responses:
            raise AssertionError("stub ran out of canned responses")
        return self.responses.pop(0)


def _read(values):
    return ReadHoldingRegistersResponse(registers=list(values))


def _refused():
    return ExceptionResponse(function_code=3)


def _e5(responses):
    """Build an E5-8200 client whose stub replays ``responses``."""
    vfd = VesperE58200ModbusVFD("127.0.0.1")
    vfd._client = _StubClient(responses)
    return vfd


def _e4(responses):
    """Build an E4-8400 client with E1-04 pre-supplied, so no extra read is queued."""
    vfd = VesperE48400ModbusVFD("127.0.0.1", max_frequency_hz=50.0)
    vfd._client = _StubClient(responses)
    return vfd


# -- E5-8200 ----------------------------------------------------------------


def test_e5_read_parameters_survives_an_unreadable_monitor_register():
    """A refused monitor read keeps the measurements and reports an unknown state."""
    vfd = _e5([_read([5000, 3800, 540, 105]), _refused()])
    parameters = asyncio.run(vfd.read_parameters())
    assert parameters.frequency_hz == pytest.approx(50.0)
    assert parameters.output_voltage == pytest.approx(380.0)
    assert parameters.dc_bus_voltage == pytest.approx(540.0)
    assert parameters.output_current == pytest.approx(10.5)
    assert parameters.state is VFDState.UNKNOWN


def test_e5_read_parameters_still_raises_when_the_block_fails():
    """The measurement block is mandatory: without it there is nothing to report."""
    vfd = _e5([_refused()])
    with pytest.raises(ModbusOperationError):
        asyncio.run(vfd.read_parameters())


def test_e5_read_state_returns_unknown_when_the_monitor_register_is_refused():
    """A refused monitor read is "unknown", not an exception."""
    vfd = _e5([_refused()])
    assert asyncio.run(vfd.read_state()) is VFDState.UNKNOWN


# -- E4-8400 ----------------------------------------------------------------


def test_e4_read_parameters_survives_unreadable_diagnostics():
    """Voltage, DC bus, temperature and state all degrade instead of raising."""
    vfd = _e4(
        [
            _read([5000, 5000, 105, 0]),  # setpoint, output freq, current
            _refused(),  # U1-06 output voltage
            _refused(),  # U1-07 DC bus voltage
            _refused(),  # U1-46 heatsink temperature
            _refused(),  # status
        ]
    )
    parameters = asyncio.run(vfd.read_parameters())
    assert parameters.frequency_hz == pytest.approx(50.0)
    assert parameters.output_current == pytest.approx(10.5)
    assert parameters.output_voltage == pytest.approx(0.0)
    assert parameters.dc_bus_voltage is None
    assert parameters.heatsink_temperature_c is None
    assert parameters.state is VFDState.UNKNOWN


def test_e4_read_parameters_keeps_the_temperature_when_only_the_state_fails():
    """One refused register must not blank the others."""
    vfd = _e4(
        [
            _read([5000, 5000, 105, 0]),
            _read([380]),  # U1-06 output voltage
            _read([540]),  # U1-07 DC bus voltage
            _read([42]),  # U1-46 heatsink temperature
            _refused(),  # status
        ]
    )
    parameters = asyncio.run(vfd.read_parameters())
    assert parameters.output_voltage == pytest.approx(380.0)
    assert parameters.dc_bus_voltage == pytest.approx(540.0)
    assert parameters.heatsink_temperature_c == pytest.approx(42.0)
    assert parameters.state is VFDState.UNKNOWN


def test_e4_read_parameters_still_raises_when_the_block_fails():
    """The measurement block is mandatory: without it there is nothing to report."""
    vfd = _e4([_refused()])
    with pytest.raises(ModbusOperationError):
        asyncio.run(vfd.read_parameters())


def test_e4_read_state_returns_unknown_when_the_status_register_is_refused():
    """A refused status read is "unknown", not an exception."""
    vfd = _e4([_refused()])
    assert asyncio.run(vfd.read_state()) is VFDState.UNKNOWN


def test_e4_read_parameters_reads_e1_04_when_no_maximum_is_supplied():
    """Without a constructor maximum the drive's own E1-04 is read first."""
    vfd = VesperE48400ModbusVFD("127.0.0.1")
    vfd._client = _StubClient(
        [
            _read([E4_MAX_FREQUENCY_RAW]),  # E1-04
            _read([5000, 2500, 105, 0]),  # setpoint, output freq, current
            _read([380]),
            _read([540]),
            _read([42]),
            _read([0b011]),  # running forward
        ]
    )
    parameters = asyncio.run(vfd.read_parameters())
    assert vfd._client.calls[0] == (
        "read",
        e4_registers.parameter_register(e4_registers.PARAM_MAX_FREQUENCY),
        1,
        1,
    )
    assert parameters.frequency_hz == pytest.approx(25.0)
    assert parameters.frequency_percent == pytest.approx(50.0)
    assert parameters.state is VFDState.RUNNING_FORWARD


def test_e5_parameter_block_addresses_are_unchanged():
    """Guard the block the optional-read refactor reads from."""
    assert e5_registers.PARAMETERS_BLOCK_ADDRESS == e5_registers.REG_OUTPUT_FREQUENCY
    assert e5_registers.PARAMETERS_BLOCK_COUNT == 4
