"""
Tests for the SPE-B register map and its scaling helpers.

These cover the decode rules on their own, so a wrong constant or factor is
caught without a transport in the way.
"""

import pytest

from scietex.hal.vfd.base.data import VFDState
from scietex.hal.vfd.intek.spe_b import registers


def test_monitoring_registers_match_the_manual():
    """Spot-check the addresses the client reads."""
    assert registers.REG_COMM_SETPOINT == 0x1000
    assert registers.REG_OPERATING_FREQUENCY == 0x1001
    assert registers.REG_OUTPUT_VOLTAGE == 0x1003
    assert registers.REG_OUTPUT_CURRENT == 0x1004
    assert registers.REG_OUTPUT_POWER == 0x1005
    assert registers.REG_STATUS == 0x3000
    assert registers.REG_DRIVE_FAULT == 0x8000
    assert registers.REG_COMM_FAULT == 0x8001


def test_parameter_registers_follow_the_addressing_scheme():
    """P0.10 is 0xF00A in EEPROM and 0x000A in RAM; Pd.06 is 0x7006."""
    assert registers.PARAM_MAX_FREQUENCY_EEPROM == 0xF00A
    assert registers.PARAM_MAX_FREQUENCY_RAM == 0x000A
    assert registers.PARAM_CURRENT_RESOLUTION_EEPROM == 0x7006


def test_parameters_block_starts_at_the_operating_frequency():
    """The block read in one transaction spans 0x1001..0x1005."""
    assert registers.PARAMETERS_BLOCK_ADDRESS == registers.REG_OPERATING_FREQUENCY
    assert (
        registers.PARAMETERS_BLOCK_ADDRESS + registers.PARAMETERS_BLOCK_COUNT - 1
        == registers.REG_OUTPUT_POWER
    )


def test_run_time_block_spans_the_two_counters():
    """Power-on time is 0x101A and run time 0x101B, so one read covers both."""
    assert registers.RUN_TIME_BLOCK_ADDRESS == 0x101A
    assert registers.RUN_TIME_BLOCK_COUNT == 2
    assert registers.RUN_TIME_BLOCK_ADDRESS + registers.RUN_TIME_BLOCK_COUNT - 1 == 0x101B


@pytest.mark.parametrize("raw, expected_hours", [(0, 0.0), (60, 1.0), (3231, 53.85)])
def test_run_time_to_hours(raw, expected_hours):
    """The counters are minutes: the drive was measured incrementing by one per minute."""
    assert registers.run_time_to_hours(raw) == pytest.approx(expected_hours)


@pytest.mark.parametrize(
    "percent, expected_hz",
    [(100.0, 50.0), (50.0, 25.0), (0.0, 0.0), (-100.0, -50.0), (200.0, 100.0)],
)
def test_percent_to_hz(percent, expected_hz):
    """100% is the P0.10 maximum, not a fixed 50 Hz."""
    assert registers.percent_to_hz(percent, 50.0) == pytest.approx(expected_hz)


def test_percent_to_hz_rejects_a_non_positive_maximum():
    """No percentage can be converted without a positive maximum."""
    with pytest.raises(ValueError):
        registers.percent_to_hz(50.0, 0.0)


@pytest.mark.parametrize("frequency_hz", [-50.0, 0.0, 12.5, 50.0, 100.0])
def test_hz_to_percent_round_trips(frequency_hz):
    """Hz to percent to Hz is lossless for a positive maximum."""
    percent = registers.hz_to_percent(frequency_hz, 50.0)
    assert registers.percent_to_hz(percent, 50.0) == pytest.approx(frequency_hz)


def test_hz_to_percent_rejects_a_non_positive_maximum():
    """A non-positive maximum is rejected instead of dividing by zero."""
    with pytest.raises(ValueError):
        registers.hz_to_percent(10.0, -1.0)


@pytest.mark.parametrize(
    "raw, expected_percent",
    [(0, 0.0), (0x4000, 16384 / 0x7FFF * 100.0), (0x7FFF, 100.0)],
)
def test_raw_to_percent(raw, expected_percent):
    """The AOV, AO and pulse outputs span 0..0x7FFF for 0..100%."""
    assert registers.raw_to_percent(raw) == pytest.approx(expected_percent)


@pytest.mark.parametrize("raw, expected_percent", [(0, 0.0), (5000, 50.0), (10000, 100.0)])
def test_frequency_raw_to_percent(raw, expected_percent):
    """The operating-frequency register uses the setpoint's hundredths scale."""
    assert registers.frequency_raw_to_percent(raw) == pytest.approx(expected_percent)


@pytest.mark.parametrize(
    "status, expected_state",
    [
        (1, VFDState.RUNNING_FORWARD),
        (2, VFDState.RUNNING_BACKWARD),
        (3, VFDState.STOPPED),
        (0, VFDState.UNKNOWN),
        (4, VFDState.UNKNOWN),
        (0xFFFF, VFDState.UNKNOWN),
    ],
)
def test_status_to_state(status, expected_state):
    """The manual defines 1..3 only, so 0 is not 'stopped'."""
    assert registers.status_to_state(status) is expected_state


@pytest.mark.parametrize(
    "forward, slow, expected",
    [
        (True, False, 1),
        (False, False, 2),
        (True, True, 3),
        (False, True, 4),
    ],
)
def test_start_command(forward, slow, expected):
    """Forward/reverse and run/jog select four distinct command codes."""
    assert registers.start_command(forward, slow) == expected


@pytest.mark.parametrize(
    "freewheel, expected",
    [(False, 6), (True, 5)],
)
def test_stop_command(freewheel, expected):
    """Freewheel stop is 5, ramp stop is 6."""
    assert registers.stop_command(freewheel) == expected


def test_control_codes_match_the_manual():
    """The six run/stop codes and the fault reset come from the manual."""
    assert registers.CONTROL_FORWARD_RUN == 1
    assert registers.CONTROL_REVERSE_RUN == 2
    assert registers.CONTROL_FORWARD_JOG == 3
    assert registers.CONTROL_REVERSE_JOG == 4
    assert registers.CONTROL_FREEWHEEL_STOP == 5
    assert registers.CONTROL_RAMP_STOP == 6
    assert registers.CONTROL_FAULT_RESET == 7
