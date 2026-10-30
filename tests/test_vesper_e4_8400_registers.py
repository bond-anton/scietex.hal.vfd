"""Vesper E4-8400 register map, scaling and fault decoding tests."""

import pytest

from scietex.hal.vfd.base.data import VFDState
from scietex.hal.vfd.vesper.e4_8400 import registers
from scietex.hal.vfd.vesper.e4_8400.errors import (
    E4_8400_FAULT_BITS,
    E4_8400_FAULT_CODES,
    E4_8400_WARNING_BITS,
    decode_faults,
)


@pytest.mark.parametrize(
    "parameter, expected",
    [
        ("E1-04", 0x5104),
        ("E1-09", 0x5109),
        ("P1-20", 0xB114),
        ("H5-01", 0x7501),
        ("B1-01", 0x2101),
        ("A1-02", 0x1102),
        ("T1-01", 0xC101),
    ],
)
def test_parameter_register_matches_the_manual(parameter, expected):
    """The manual's worked examples must resolve to the documented registers."""
    assert registers.parameter_register(parameter) == expected


def test_parameter_register_rejects_unknown_group():
    """A group letter outside the manual's map is an error, not a guess."""
    with pytest.raises(ValueError):
        registers.parameter_register("Z1-01")


def test_parameter_register_rejects_malformed():
    """A parameter without a group separator is an error."""
    with pytest.raises(ValueError):
        registers.parameter_register("E104")


def test_output_frequency_is_hundredths_of_a_hz():
    """0021h is in 1/100 Hz."""
    assert registers.output_frequency_hz(5000) == pytest.approx(50.0)


def test_hz_to_setpoint_raw_matches_the_manual_example():
    """The manual states 50.00 Hz is 5000 decimal, 1388 hex."""
    assert registers.hz_to_setpoint_raw(50.0) == 0x1388


def test_hz_to_setpoint_raw_rejects_negative():
    """The register is unsigned, so a negative value would wrap."""
    with pytest.raises(ValueError):
        registers.hz_to_setpoint_raw(-0.5)


def test_output_current_is_tenths_of_an_amp():
    """0022h is in 1/10 A."""
    assert registers.output_current_a(105) == pytest.approx(10.5)


@pytest.mark.parametrize(
    "status, expected",
    [
        (0b000000, VFDState.STOPPED),
        (0b000001, VFDState.RUNNING_FORWARD),
        (0b000101, VFDState.RUNNING_BACKWARD),
        (0b000100, VFDState.STOPPED),
    ],
)
def test_status_to_state(status, expected):
    """Run bit gates the state; the reverse bit only matters while running."""
    assert registers.status_to_state(status) is expected


def test_control_word_forward_run():
    """Forward run sets bit 0."""
    assert registers.control_word(run=True, forward=True) == 1 << registers.CMD_FORWARD_RUN


def test_control_word_reverse_run():
    """Reverse run sets bit 1."""
    assert registers.control_word(run=True, forward=False) == 1 << registers.CMD_REVERSE_RUN


def test_control_word_jog_forward():
    """Jog forward sets bit A."""
    assert registers.control_word(jog=True, forward=True) == 1 << registers.CMD_JOG_FORWARD


def test_control_word_jog_reverse():
    """Jog reverse sets bit B."""
    assert registers.control_word(jog=True, forward=False) == 1 << registers.CMD_JOG_REVERSE


def test_control_word_fault_reset():
    """Fault reset sets bit 9."""
    assert registers.control_word(fault_reset=True) == 1 << registers.CMD_FAULT_RESET


def test_control_word_stop_is_zero():
    """A stop command clears every bit the driver sets."""
    assert registers.control_word() == 0


def test_decode_faults_returns_every_set_bit():
    """A bitfield can carry several faults at once."""
    raw = (1 << registers.FAULT_OH) | (1 << registers.FAULT_OC)
    faults = decode_faults(raw, E4_8400_FAULT_BITS)
    assert [f.code for f in faults] == [registers.FAULT_OC, registers.FAULT_OH]


def test_decode_faults_ignores_reserved_bits():
    """Reserved bits are not faults."""
    assert decode_faults(1 << 0, E4_8400_FAULT_BITS) == []


def test_decode_faults_empty_for_zero():
    """A zero bitfield means no fault."""
    assert decode_faults(0, E4_8400_FAULT_BITS) == []


def test_decode_faults_warnings():
    """The warning table decodes independently of the fault table."""
    faults = decode_faults(1 << 0, E4_8400_WARNING_BITS)
    assert [f.code for f in faults] == [0]


def test_fault_history_codes_match_the_manual():
    """The history codes are the manual's fault-code table, not bit positions."""
    assert E4_8400_FAULT_CODES[0x09].message.startswith("Heatsink overheat")
    assert E4_8400_FAULT_CODES[0x0B].message.startswith("Motor overload")
    assert E4_8400_FAULT_CODES[0x1F].message.startswith("EEPROM fault")


def test_heatsink_temperature_register_is_u1_46():
    """004Dh is the only live temperature reading in the package."""
    assert registers.REG_HEATSINK_TEMPERATURE == 0x004D


def test_parameters_block_covers_both_frequencies_and_current():
    """The block read must span setpoint frequency through output current."""
    start = registers.PARAMETERS_BLOCK_ADDRESS
    end = start + registers.PARAMETERS_BLOCK_COUNT - 1
    assert start == registers.REG_SETPOINT_FREQUENCY
    assert end >= registers.REG_OUTPUT_CURRENT
