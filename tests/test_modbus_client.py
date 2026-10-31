"""
Tests for the Modbus/TCP SPE-B client.

The pymodbus client is replaced by a stub that records calls and returns canned
responses, so these cover the register map, the scaling and the error handling
rather than the transport. The stub is attached before ``connect()``, which is
the same state a real connected client is in minus the socket.
"""

import asyncio

import pytest
from pymodbus.pdu import ExceptionResponse
from pymodbus.pdu.register_message import (
    ReadHoldingRegistersResponse,
    WriteSingleRegisterResponse,
)
from scietex.hal.serial import ModbusOperationError

from scietex.hal.vfd.base.data import VFDState
from scietex.hal.vfd.intek.spe_b import registers
from scietex.hal.vfd.intek.spe_b.client import IntekSPEBModbusVFD

DEFAULT_MAX_FREQUENCY_RAW = 5000  # P0.10 = 50.00 Hz


class _StubClient:
    """Stand-in for `AsyncModbusTcpClient` that records calls."""

    def __init__(self, responses=None, connect_result=True):
        self.responses = list(responses or [])
        self.calls = []
        self.closed = False
        self.connect_result = connect_result

    async def connect(self):
        """Pretend to connect, reporting the configured result."""
        return self.connect_result

    def close(self):
        """Record the close."""
        self.closed = True

    def _next(self):
        if not self.responses:
            raise AssertionError("stub ran out of canned responses")
        return self.responses.pop(0)

    async def read_holding_registers(self, address, *, count=1, device_id=1):
        """Record the read and return the next canned response."""
        self.calls.append(("read", address, count, device_id))
        return self._next()

    async def write_register(self, address, value, *, device_id=1):
        """Record the write and return the next canned response."""
        self.calls.append(("write", address, value, device_id))
        return self._next()


def _read(registers_):
    return ReadHoldingRegistersResponse(registers=list(registers_))


def _write(address, value=0):
    return WriteSingleRegisterResponse(address=address, registers=[value])


def _connected(responses=(), max_frequency_raw=DEFAULT_MAX_FREQUENCY_RAW, current_raw=0):
    """Build a client whose scale factors are already read from the stub."""
    stub = _StubClient([_read([max_frequency_raw]), _read([current_raw]), *responses])
    vfd = IntekSPEBModbusVFD("127.0.0.1")
    vfd._client = stub
    asyncio.run(vfd.connect())
    stub.calls.clear()
    return vfd, stub


# -- connection -------------------------------------------------------------


def test_connect_reads_scale_factors_from_the_drive():
    """P0.10 and Pd.06 are read once, by unit id, and cached."""
    stub = _StubClient([_read([6000]), _read([1])])
    vfd = IntekSPEBModbusVFD("127.0.0.1")
    vfd._client = stub
    asyncio.run(vfd.connect())
    assert stub.calls == [
        ("read", registers.PARAM_MAX_FREQUENCY_EEPROM, 1, 1),
        ("read", registers.PARAM_CURRENT_RESOLUTION_EEPROM, 1, 1),
    ]
    assert vfd._max_frequency_hz == pytest.approx(60.0)
    assert vfd._current_resolution == pytest.approx(0.1)


def test_connect_raises_when_gateway_unreachable(monkeypatch):
    """A failed connect raises instead of leaving the drive looking connected."""
    stub = _StubClient(connect_result=False)
    monkeypatch.setattr(
        "scietex.hal.vfd.intek.spe_b.client.AsyncModbusTcpClient",
        lambda *args, **kwargs: stub,
    )
    vfd = IntekSPEBModbusVFD("127.0.0.1")
    with pytest.raises(ModbusOperationError):
        asyncio.run(vfd.connect())


def test_connect_keeps_the_factory_current_resolution_when_pd06_fails():
    """A drive that refuses Pd.06 still connects, so stop stays available."""
    stub = _StubClient([_read([DEFAULT_MAX_FREQUENCY_RAW]), ExceptionResponse(function_code=3)])
    vfd = IntekSPEBModbusVFD("127.0.0.1")
    vfd._client = stub
    asyncio.run(vfd.connect())
    assert vfd._current_resolution == pytest.approx(registers.CURRENT_RESOLUTION_FINE)


def test_close_releases_the_client():
    """Closing drops the client so a later read reports "not connected"."""
    vfd, stub = _connected()
    asyncio.run(vfd.close())
    assert stub.closed is True
    assert vfd._client is None


def test_read_before_connect_raises():
    """Reading without connect fails loudly instead of touching a closed socket."""
    vfd = IntekSPEBModbusVFD("127.0.0.1")
    with pytest.raises(RuntimeError):
        asyncio.run(vfd.read_state())


# -- parameters -------------------------------------------------------------


def test_read_parameters_scales_percent_current_and_reads_state():
    """One block read at 0x1001, then the status register."""
    vfd, stub = _connected([_read([5000, 540, 380, 123, 45]), _read([1])])
    parameters = asyncio.run(vfd.read_parameters())

    assert stub.calls == [
        (
            "read",
            registers.PARAMETERS_BLOCK_ADDRESS,
            registers.PARAMETERS_BLOCK_COUNT,
            1,
        ),
        ("read", registers.REG_STATUS, 1, 1),
    ]
    assert parameters.frequency_percent == pytest.approx(50.0)
    assert parameters.frequency_hz == pytest.approx(25.0)
    assert parameters.output_current == pytest.approx(1.23)
    assert parameters.output_voltage == pytest.approx(380.0)
    assert parameters.output_power == pytest.approx(45.0)
    assert parameters.state is VFDState.RUNNING_FORWARD


def test_read_parameters_uses_the_coarse_current_resolution():
    """Pd.06 = 1 means 0.1 A per count."""
    vfd, _ = _connected([_read([0, 0, 0, 123, 0]), _read([3])], current_raw=1)
    assert asyncio.run(vfd.read_parameters()).output_current == pytest.approx(12.3)


def test_read_parameters_reports_no_hz_when_p010_is_zero():
    """An unusable maximum frequency keeps the percentage but cannot scale it."""
    vfd, _ = _connected([_read([5000, 0, 0, 0, 0]), _read([3])], max_frequency_raw=0)
    parameters = asyncio.run(vfd.read_parameters())
    assert parameters.frequency_percent == pytest.approx(50.0)
    assert parameters.frequency_hz is None


def test_connect_survives_a_refused_p010_and_still_reports_measurements():
    """A drive that refuses P0.10 must not blank the whole snapshot.

    An SPE-B that has not been configured for Modbus (Pd.01/Pd.05) answers the
    gateway with exception 11 for every register. Raising from `connect()` made
    the poll loop log a connect failure every cycle and publish nothing; the
    percentage, current, voltage and power are still readable, so only
    `frequency_hz` degrades to None.
    """
    stub = _StubClient(
        [
            ExceptionResponse(function_code=3),  # P0.10
            _read([1]),  # Pd.06 = coarse, 0.1 A
            _read([5000, 540, 380, 123, 45]),
            _read([1]),  # status: running forward
        ]
    )
    vfd = IntekSPEBModbusVFD("127.0.0.1")
    vfd._client = stub
    asyncio.run(vfd.connect())
    parameters = asyncio.run(vfd.read_parameters())
    assert parameters.frequency_percent == pytest.approx(50.0)
    assert parameters.frequency_hz is None
    assert parameters.output_current == pytest.approx(12.3)
    assert parameters.output_voltage == pytest.approx(380.0)
    assert parameters.dc_bus_voltage == pytest.approx(540.0)
    assert parameters.state is VFDState.RUNNING_FORWARD


def test_set_frequency_still_refuses_when_p010_is_unknown():
    """Without P0.10 no percentage can be computed, so the write is rejected."""
    vfd, _ = _connected([], max_frequency_raw=0)
    with pytest.raises(ValueError, match="P0.10"):
        asyncio.run(vfd.set_frequency(25.0))


def test_read_parameters_survives_an_unreadable_status_register():
    """A refused status read must not discard the measurements.

    The poll loop publishes whatever `read_parameters` returns; raising here
    would mean a drive that refuses one diagnostic register never reports its
    frequency, current or voltage at all.
    """
    vfd, _ = _connected([_read([5000, 540, 380, 123, 45]), ExceptionResponse(function_code=3)])
    parameters = asyncio.run(vfd.read_parameters())
    assert parameters.frequency_hz == pytest.approx(25.0)
    assert parameters.output_current == pytest.approx(1.23)
    assert parameters.output_voltage == pytest.approx(380.0)
    assert parameters.state is VFDState.UNKNOWN


def test_read_parameters_still_raises_when_the_measurement_block_fails():
    """The measurement block is mandatory: without it there is nothing to report."""
    vfd, _ = _connected([ExceptionResponse(function_code=3)])
    with pytest.raises(ModbusOperationError):
        asyncio.run(vfd.read_parameters())


def test_read_state_returns_unknown_when_the_status_register_is_refused():
    """A refused status read is "unknown", not an exception."""
    vfd, _ = _connected([ExceptionResponse(function_code=3)])
    assert asyncio.run(vfd.read_state()) is VFDState.UNKNOWN


# -- state and faults -------------------------------------------------------


@pytest.mark.parametrize(
    "status, expected",
    [
        (1, VFDState.RUNNING_FORWARD),
        (2, VFDState.RUNNING_BACKWARD),
        (3, VFDState.STOPPED),
        (0, VFDState.UNKNOWN),
        (7, VFDState.UNKNOWN),
    ],
)
def test_read_state_maps_the_status_register(status, expected):
    """The manual defines 1..3; anything else is unknown."""
    vfd, stub = _connected([_read([status])])
    assert asyncio.run(vfd.read_state()) is expected
    assert stub.calls == [("read", registers.REG_STATUS, 1, 1)]


@pytest.mark.parametrize(
    "comm, address",
    [(False, registers.REG_DRIVE_FAULT), (True, registers.REG_COMM_FAULT)],
)
def test_read_error_code_reads_the_selected_table(comm, address):
    """The two fault tables live at consecutive registers."""
    vfd, stub = _connected([_read([11])])
    assert asyncio.run(vfd.read_error_code(comm=comm)) == 11
    assert stub.calls == [("read", address, 1, 1)]


def test_read_error_code_raises_instead_of_reporting_zero():
    """A failed read must not look like "no fault"."""
    vfd, _ = _connected([ExceptionResponse(function_code=3)])
    with pytest.raises(ModbusOperationError):
        asyncio.run(vfd.read_error_code())


def test_clear_error_writes_the_reset_and_reads_the_code_back():
    """Reset is one control write followed by a read of the drive table."""
    vfd, stub = _connected([_write(registers.REG_CONTROL), _read([0])])
    assert asyncio.run(vfd.clear_error()) == 0
    assert stub.calls == [
        ("write", registers.REG_CONTROL, registers.CONTROL_FAULT_RESET, 1),
        ("read", registers.REG_DRIVE_FAULT, 1, 1),
    ]


def test_clear_error_reads_the_communication_table_when_asked():
    """`comm=True` only changes which table is read back."""
    vfd, stub = _connected([_write(registers.REG_CONTROL), _read([3])])
    assert asyncio.run(vfd.clear_error(comm=True)) == 3
    assert stub.calls[1] == ("read", registers.REG_COMM_FAULT, 1, 1)


@pytest.mark.parametrize(
    "code, comm, message",
    [
        (2, False, "Current overload during acceleration"),
        (3, True, "CRC error"),
        (0, True, "No error"),
        (999, False, "Unknown error"),
    ],
)
def test_parse_error_code(code, comm, message):
    """Codes map through the matching table, unknown codes included."""
    vfd = IntekSPEBModbusVFD("127.0.0.1")
    assert vfd.parse_error_code(code, comm=comm).message == message


# -- control ----------------------------------------------------------------


@pytest.mark.parametrize(
    "forward, slow, expected",
    [(True, False, 1), (False, False, 2), (True, True, 3), (False, True, 4)],
)
def test_start_writes_the_control_register(forward, slow, expected):
    """Direction and jog select one of the four run codes."""
    vfd, stub = _connected([_write(registers.REG_CONTROL)])
    asyncio.run(vfd.start(forward=forward, slow=slow))
    assert stub.calls == [("write", registers.REG_CONTROL, expected, 1)]


@pytest.mark.parametrize("freewheel, expected", [(False, 6), (True, 5)])
def test_stop_writes_the_control_register(freewheel, expected):
    """Coasting stop is 5, ramp stop is 6."""
    vfd, stub = _connected([_write(registers.REG_CONTROL)])
    asyncio.run(vfd.stop(freewheel=freewheel))
    assert stub.calls == [("write", registers.REG_CONTROL, expected, 1)]


def test_write_raises_on_an_exception_response():
    """A rejected control write surfaces as an error, not silence."""
    vfd, _ = _connected([ExceptionResponse(function_code=6)])
    with pytest.raises(ModbusOperationError):
        asyncio.run(vfd.stop())


def test_read_data_returns_the_parameter_fields():
    """`read_data` flattens `VFDParameters` into a plain mapping."""
    vfd, _ = _connected([_read([5000, 0, 380, 100, 10]), _read([2])])
    data = asyncio.run(vfd.read_data())
    assert data == {
        "frequency_hz": pytest.approx(25.0),
        "frequency_percent": pytest.approx(50.0),
        "output_current": pytest.approx(1.0),
        "output_voltage": pytest.approx(380.0),
        "output_power": pytest.approx(10.0),
        "dc_bus_voltage": pytest.approx(0.0),
        "heatsink_temperature_c": None,
        "motor_temperature_c": None,
        "state": VFDState.RUNNING_BACKWARD,
    }
