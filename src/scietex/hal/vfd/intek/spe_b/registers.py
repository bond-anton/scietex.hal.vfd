"""
Intek SPE-B register map and scaling helpers.

Transcribed from the SPE-B user manual, section 7.4 ("Addresses of registers").
The manual is the only source for these values; see
``intek/docs/protocol.md`` for the full reference, including the parameter
addressing scheme and the communication settings a drive needs before it can
talk to the Scietex Modbus gateway.

The drive reports frequency as a percentage of its maximum output frequency
(parameter P0.10), never in Hz, and current in counts of a resolution selected
by parameter Pd.06. Both factors are read from the drive and applied here, so a
caller always sees engineering units.

Functions:
    frequency_raw_to_percent: Convert the operating-frequency register into a percentage.
    percent_to_hz: Convert a drive frequency percentage into Hz.
    hz_to_percent: Convert a frequency in Hz into a drive percentage.
    raw_to_percent: Convert a 0..0x7FFF analog/pulse register into a percentage.
    status_to_state: Decode the status register into a `VFDState`.
    start_command: Build the run command code for `REG_CONTROL`.
    stop_command: Build the stop command code for `REG_CONTROL`.
"""

from ...base.data import VFDState

# Monitoring registers, read with FC03 from 0x1000 upwards.
REG_COMM_SETPOINT = 0x1000  # Communication-protocol setpoint, write only
REG_OPERATING_FREQUENCY = 0x1001  # Operating frequency, percent of P0.10
REG_DC_BUS_VOLTAGE = 0x1002  # DC bus voltage, raw
REG_OUTPUT_VOLTAGE = 0x1003  # Output voltage, raw
REG_OUTPUT_CURRENT = 0x1004  # Output current, counts of the Pd.06 resolution
REG_OUTPUT_POWER = 0x1005  # Output power, raw
REG_OPERATING_SPEED = 0x1007  # Operating speed, raw
REG_DI_STATE = 0x1008  # Digital input state, bitfield
REG_DO_STATE = 0x1009  # Digital output state, bitfield
REG_AI1_VOLTAGE = 0x100A  # Analog input AI1 voltage, raw
REG_COUNTER_INPUT = 0x100D  # Counter input, raw
REG_LOAD_SPEED = 0x100F  # Load speed, raw
REG_PID_SETPOINT = 0x1010  # PID setpoint, raw
REG_PID_FEEDBACK = 0x1011  # PID feedback, raw
REG_INPUT_PULSE_FREQUENCY_001KHZ = 0x1013  # Input pulse frequency, 0.01 kHz
REG_REMAINING_RUN_TIME = 0x1015  # Remaining run time, raw
REG_LINEAR_SPEED = 0x1019  # Linear speed, raw
REG_TOTAL_POWER_ON_TIME = 0x101A  # Total power-on time, raw
REG_TOTAL_RUN_TIME = 0x101B  # Total run time, raw
REG_INPUT_PULSE_FREQUENCY_HZ = 0x101C  # Input pulse frequency, 1 Hz
REG_COMM_SETPOINT_READBACK = 0x101D  # Communication-protocol setpoint, readable
REG_MAIN_FREQUENCY_X = 0x101F  # Main frequency X, raw
REG_AUX_FREQUENCY_Y = 0x1020  # Auxiliary frequency Y, raw

# The five consecutive registers `read_parameters` fetches in one transaction:
# operating frequency, DC bus voltage, output voltage, current and power.
PARAMETERS_BLOCK_ADDRESS = REG_OPERATING_FREQUENCY
PARAMETERS_BLOCK_COUNT = 5

# The two consecutive run-time counters, read as a second block because they sit
# outside the measurement block. The manual calls them "raw" and states no unit;
# the drive was measured incrementing 0x101A by one per minute, so both are
# minutes. `0x1015` (remaining run time) is deliberately not read: it is the
# countdown to a maintenance interval, not a total, and it reads 0 when no
# interval is configured.
RUN_TIME_BLOCK_ADDRESS = REG_TOTAL_POWER_ON_TIME
RUN_TIME_BLOCK_COUNT = 2
RUN_TIME_RESOLUTION = 60.0  # Counter units per hour

# Control register, FC06 write only.
REG_CONTROL = 0x2000
CONTROL_FORWARD_RUN = 1
CONTROL_REVERSE_RUN = 2
CONTROL_FORWARD_JOG = 3
CONTROL_REVERSE_JOG = 4
CONTROL_FREEWHEEL_STOP = 5
CONTROL_RAMP_STOP = 6
CONTROL_FAULT_RESET = 7

# Status register, read only.
REG_STATUS = 0x3000
STATUS_RUNNING_FORWARD = 1
STATUS_RUNNING_BACKWARD = 2
STATUS_STOPPED = 3

# Fault registers.
REG_DRIVE_FAULT = 0x8000  # Drive fault code, 0x0000..0x005E
REG_COMM_FAULT = 0x8001  # Communication-protocol fault code, 0x0000..0x0008

# Discrete and analog outputs, read only.
REG_DO_BITFIELD = 0x2001  # BIT0 DO1, BIT2 relay, BIT4 FM, BIT5..9 VDO..VDO5
REG_AOV_OUTPUT = 0x2002  # AOV analog output, 0..0x7FFF = 0..100%
REG_AO_OUTPUT = 0x2003  # AO analog output, 0..0x7FFF = 0..100%
REG_PULSE_OUTPUT = 0x2004  # Pulse output, 0..0x7FFF = 0..100%

# Parameter lock. Writing the unlock code releases the keypad lock.
REG_PARAMETER_LOCK = 0x1F00
PARAMETER_UNLOCK_CODE = 0x8888

# Parameter addressing: the high address byte selects the group and the storage
# type, the low byte is the parameter index in hex. EEPROM groups are F0-FF
# (P0-PF), A0-AF (b0-bF) and 70-7F (d0-dF); the RAM mirror replaces the high
# byte with 00 for the P group and 40 for the b group. P3.12 is therefore 0xF30C
# in EEPROM and 0x030C in RAM.
PARAM_MAX_FREQUENCY_EEPROM = 0xF00A  # P0.10, max output frequency
PARAM_MAX_FREQUENCY_RAM = 0x000A  # P0.10 RAM mirror
PARAM_CURRENT_RESOLUTION_EEPROM = 0x7006  # Pd.06, current display resolution

# P0.10 and the frequency parameters are stored in 0.01 Hz units; the value
# range is 50.00..500.0 Hz with a 50.00 Hz factory default.
PARAMETER_FREQUENCY_RESOLUTION = 100.0

# Pd.06 selects the output-current resolution: 0 = 0.01 A, 1 = 0.1 A.
CURRENT_RESOLUTION_FINE = 0.01
CURRENT_RESOLUTION_COARSE = 0.1

# The manual gives the communication setpoint as hundredths of a percent
# (10000 = 100.00%) and calls the operating-frequency register a percentage
# without stating its resolution. This driver assumes the same hundredths
# scale; the assumption is unverified against hardware, see
# ``intek/docs/protocol.md``.
FREQUENCY_PERCENT_RESOLUTION = 100.0

# Analog and pulse outputs span the full signed 15-bit range for 0..100%.
ANALOG_OUTPUT_MAX_RAW = 0x7FFF

# The communication-protocol setpoint is a percentage in hundredths: 10000 is
# 100.00%, -10000 is -100.00%.
COMM_SETPOINT_LIMIT = 10000


def frequency_raw_to_percent(raw: int) -> float:
    """
    Convert the operating-frequency register into a percentage of P0.10.

    Args:
        raw: The value read from `REG_OPERATING_FREQUENCY`.

    Returns:
        float: The frequency as a percentage of the maximum output frequency.
    """
    return raw / FREQUENCY_PERCENT_RESOLUTION


def percent_to_hz(percent: float, max_frequency_hz: float) -> float:
    """
    Convert a drive frequency percentage into Hz.

    Args:
        percent: Frequency as reported by the drive, where 100% is the maximum
            output frequency configured in P0.10.
        max_frequency_hz: The maximum output frequency from P0.10, in Hz.

    Returns:
        float: The frequency in Hz.

    Raises:
        ValueError: If ``max_frequency_hz`` is not positive, because no
            percentage can then be converted into a frequency.
    """
    if max_frequency_hz <= 0:
        raise ValueError(f"Maximum frequency must be positive, got {max_frequency_hz}")
    return percent / 100.0 * max_frequency_hz


def hz_to_percent(frequency_hz: float, max_frequency_hz: float) -> float:
    """
    Convert a frequency in Hz into the percentage the drive expects.

    Args:
        frequency_hz: The frequency in Hz.
        max_frequency_hz: The maximum output frequency from P0.10, in Hz.

    Returns:
        float: The frequency as a percentage of the maximum.

    Raises:
        ValueError: If ``max_frequency_hz`` is not positive.
    """
    if max_frequency_hz <= 0:
        raise ValueError(f"Maximum frequency must be positive, got {max_frequency_hz}")
    return frequency_hz / max_frequency_hz * 100.0


def raw_to_percent(raw: int) -> float:
    """
    Convert a 0..0x7FFF output register into a percentage.

    The AOV, AO and pulse output registers share this scale, where 0x7FFF is
    100%.

    Args:
        raw: The register value.

    Returns:
        float: The percentage, 0..100 for an in-range register value.
    """
    return raw / ANALOG_OUTPUT_MAX_RAW * 100.0


def run_time_to_hours(raw: int) -> float:
    """
    Convert a run-time counter register into hours.

    The manual states no unit for `REG_TOTAL_POWER_ON_TIME` and
    `REG_TOTAL_RUN_TIME`. The drive was measured incrementing the power-on
    counter by exactly one over sixty seconds, so the counters are minutes.

    Args:
        raw: The register value.

    Returns:
        float: The counter as hours.
    """
    return raw / RUN_TIME_RESOLUTION


def status_to_state(status: int) -> VFDState:
    """
    Decode the status register into a `VFDState`.

    The manual defines three values only. A drive that answers with anything
    else — including 0, which the protocol does not define and which a gateway
    returns when the request never reached the drive — is reported as unknown
    rather than guessed into ``STOPPED``.

    Args:
        status: The value read from `REG_STATUS`.

    Returns:
        VFDState: The decoded state.
    """
    if status == STATUS_RUNNING_FORWARD:
        return VFDState.RUNNING_FORWARD
    if status == STATUS_RUNNING_BACKWARD:
        return VFDState.RUNNING_BACKWARD
    if status == STATUS_STOPPED:
        return VFDState.STOPPED
    return VFDState.UNKNOWN


def start_command(forward: bool = True, slow: bool = False) -> int:
    """
    Build the run command code for `REG_CONTROL`.

    Args:
        forward: Use the forward command; ``False`` uses the reverse one.
        slow: Use the jog command instead of the normal run command.

    Returns:
        int: The command code to write to `REG_CONTROL`.
    """
    if slow:
        return CONTROL_FORWARD_JOG if forward else CONTROL_REVERSE_JOG
    return CONTROL_FORWARD_RUN if forward else CONTROL_REVERSE_RUN


def stop_command(freewheel: bool = False) -> int:
    """
    Build the stop command code for `REG_CONTROL`.

    Args:
        freewheel: Use the coast-to-stop command instead of the ramp stop.

    Returns:
        int: The command code to write to `REG_CONTROL`.
    """
    return CONTROL_FREEWHEEL_STOP if freewheel else CONTROL_RAMP_STOP
