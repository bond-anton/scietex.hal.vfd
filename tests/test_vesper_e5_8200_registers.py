"""Vesper E5-8200 register map and scaling tests."""

import pytest

from scietex.hal.vfd.base.data import VFDState
from scietex.hal.vfd.vesper.e5_8200 import registers


def test_output_frequency_is_hundredths_of_a_hz():
    """2524H is in 1/100 Hz, so 5000 is 50 Hz."""
    assert registers.output_frequency_hz(5000) == pytest.approx(50.0)
    assert registers.output_frequency_hz(2550) == pytest.approx(25.5)


def test_setpoint_frequency_is_hundredths_of_a_hz():
    """2523H uses the same scale as the output frequency."""
    assert registers.setpoint_frequency_hz(6000) == pytest.approx(60.0)


def test_hz_to_setpoint_raw_round_trips():
    """A frequency written and read back is unchanged."""
    raw = registers.hz_to_setpoint_raw(37.5)
    assert raw == 3750
    assert registers.setpoint_frequency_hz(raw) == pytest.approx(37.5)


def test_hz_to_setpoint_raw_rejects_negative():
    """The register is unsigned, so a negative value would wrap."""
    with pytest.raises(ValueError):
        registers.hz_to_setpoint_raw(-1.0)


def test_output_voltage_is_tenths_of_a_volt():
    """2525H is in 1/10 V."""
    assert registers.output_voltage_v(3800) == pytest.approx(380.0)


def test_output_current_is_tenths_of_an_amp():
    """2527H is in 1/10 A."""
    assert registers.output_current_a(105) == pytest.approx(10.5)


@pytest.mark.parametrize(
    "monitor, expected",
    [
        (0b000, VFDState.STOPPED),
        (0b011, VFDState.RUNNING_FORWARD),
        (0b010, VFDState.STOPPED),
        (0b001, VFDState.RUNNING_BACKWARD),
        (0b101, VFDState.RUNNING_BACKWARD),
    ],
)
def test_status_to_state(monitor, expected):
    """Run bit gates the state; direction bit only matters while running."""
    assert registers.status_to_state(monitor) is expected


def test_control_word_forward_run():
    """Forward run sets the run and direction bits."""
    assert registers.control_word(run=True, forward=True) == 0b11


def test_control_word_reverse_run():
    """Reverse run sets the run bit and clears the direction bit."""
    assert registers.control_word(run=True, forward=False) == 0b01


def test_control_word_jog_forward():
    """Jog forward sets the jog bit, not the run bit."""
    assert registers.control_word(jog=True, forward=True) == 1 << registers.CTRL_JOG_FORWARD


def test_control_word_jog_reverse():
    """Jog reverse sets the reverse jog bit."""
    assert registers.control_word(jog=True, forward=False) == 1 << registers.CTRL_JOG_REVERSE


def test_control_word_fault_reset():
    """Fault reset sets only the reset bit."""
    assert registers.control_word(fault_reset=True) == 1 << registers.CTRL_FAULT_RESET


def test_control_word_stop_is_zero():
    """A stop command clears every bit the driver sets."""
    assert registers.control_word() == 0


def test_parameters_block_covers_every_measurement():
    """The block read must span output frequency through output current."""
    start = registers.PARAMETERS_BLOCK_ADDRESS
    end = start + registers.PARAMETERS_BLOCK_COUNT - 1
    assert start == registers.REG_OUTPUT_FREQUENCY
    assert end >= registers.REG_OUTPUT_CURRENT
    assert registers.REG_OUTPUT_VOLTAGE <= end
    assert registers.REG_DC_BUS_VOLTAGE <= end


def test_parameter_addresses_match_the_manual():
    """The setup parameters the doc names must resolve to the manual's registers."""
    assert registers.PARAM_COMMAND_SOURCE == 0x0002
    assert registers.PARAM_FREQUENCY_SOURCE == 0x0005
    assert registers.PARAM_ADDRESS == 0x0900
    assert registers.PARAM_PROTOCOL == 0x0901
    assert registers.PARAM_BAUDRATE == 0x0902
    assert registers.PARAM_STOP_BITS == 0x0903
    assert registers.PARAM_PARITY == 0x0904
    assert registers.PARAM_DATA_BITS == 0x0905
