"""
Vesper E5-8200 register map and scaling helpers.

Transcribed from the E5-8200 Modbus communication manual, version 1.0. The
manual is the only source for these values; see ``vesper/docs/protocol-e5-8200.md``
for the full reference, including the parameter addressing scheme and the
communication settings a drive needs before it can talk to the Scietex Modbus
gateway.

The drive reports frequency in hundredths of a hertz, voltage in tenths of a
volt and current in tenths of an amp, so every reading needs a scale factor.
Unlike the Intek SPE-B, the E5-8200 reports frequency directly in Hz rather
than as a percentage of a maximum, so no maximum-frequency parameter is needed
to decode a reading.

Functions:
    output_frequency_hz: Convert the output-frequency register into Hz.
    setpoint_frequency_hz: Convert the setpoint-frequency register into Hz.
    hz_to_setpoint_raw: Convert a frequency in Hz into the setpoint register value.
    output_voltage_v: Convert the output-voltage register into volts.
    output_current_a: Convert the output-current register into amps.
    status_to_state: Decode the monitor bitfield into a `VFDState`.
    control_word: Build the control-register value for a command.
"""

from ...base.data import VFDState

# Control registers, read and written with FC03/FC06.
REG_CONTROL = 0x2501  # Control bitfield, read/write
REG_SETPOINT = 0x2502  # Frequency setpoint, hundredths of a Hz

# Control bitfield positions in `REG_CONTROL`.
CTRL_RUN = 0  # 1 = run, 0 = stop
CTRL_DIRECTION = 1  # 1 = forward, 0 = reverse
CTRL_EXTERNAL_FAULT = 2  # 1 = signal "EFO" to the drive
CTRL_FAULT_RESET = 3  # 1 = reset the latched fault
CTRL_JOG_FORWARD = 4  # 1 = jog forward
CTRL_JOG_REVERSE = 5  # 1 = jog reverse
CTRL_S1 = 6  # Multi-function input S1
CTRL_S2 = 7  # Multi-function input S2
CTRL_S3 = 8  # Multi-function input S3
CTRL_S4 = 9  # Multi-function input S4
CTRL_S5 = 10  # Multi-function input S5
CTRL_RELAY_R1 = 12  # Relay R1

# Monitor registers, read only.
REG_MONITOR = 0x2520  # Status bitfield
REG_FAULT = 0x2521  # Fault code, 0..46
REG_DISCRETE = 0x2522  # Digital input and output bitfield
REG_SETPOINT_FREQUENCY = 0x2523  # Setpoint frequency, hundredths of a Hz
REG_OUTPUT_FREQUENCY = 0x2524  # Output frequency, hundredths of a Hz
REG_OUTPUT_VOLTAGE = 0x2525  # Output voltage, tenths of a volt
REG_DC_BUS_VOLTAGE = 0x2526  # DC bus voltage, volts
REG_OUTPUT_CURRENT = 0x2527  # Output current, tenths of an amp
REG_PID_FEEDBACK = 0x252A  # PID feedback, tenths of a percent of max frequency
REG_PID_INPUT = 0x252B  # PID input, tenths of a percent of max frequency
REG_AVI_INPUT = 0x252C  # AVI analog input, 1000/10 V
REG_ACI_INPUT = 0x252D  # ACI analog input, 1000/10 V
REG_MODEL_ID = 0x252F  # Model identification, 0x0110 for E5-8200

# The five consecutive registers `read_parameters` fetches in one transaction:
# output frequency, output voltage, DC bus voltage, output current and the
# reserved register 0x2528. The block starts at the output frequency rather
# than at the setpoint so a single read covers every measurement the driver
# reports.
PARAMETERS_BLOCK_ADDRESS = REG_OUTPUT_FREQUENCY
PARAMETERS_BLOCK_COUNT = 4

# Monitor bitfield positions in `REG_MONITOR`.
MON_RUN = 0  # 1 = running, 0 = stopped
MON_DIRECTION = 1  # 1 = forward, 0 = reverse
MON_READY = 2  # 1 = ready to run
MON_EXTERNAL_FAULT = 3  # 1 = "EFO" external communication fault
MON_DATA_ERROR = 4  # 1 = data-entry error

# Scale factors.
FREQUENCY_RESOLUTION = 100.0  # Hundredths of a Hz
VOLTAGE_RESOLUTION = 10.0  # Tenths of a volt
CURRENT_RESOLUTION = 10.0  # Tenths of an amp

# The drive's factory base frequency. The communication manual names no
# maximum-frequency parameter, so this is the default the driver uses to
# convert Hz into a percentage; a caller with a different configured maximum
# passes it to the constructor.
DEFAULT_MAX_FREQUENCY_HZ = 50.0

# Parameter addressing: the high byte is the group number in hex, the low byte
# is the parameter index in hex. 08-03 is 0x0803, 10-11 is 0x0A0B.
PARAM_COMMAND_SOURCE = 0x0002  # 00-02, main run/stop command source
PARAM_FREQUENCY_SOURCE = 0x0005  # 00-05, main frequency setpoint source
PARAM_ADDRESS = 0x0900  # 09-00, drive address, 1..32
PARAM_PROTOCOL = 0x0901  # 09-01, 0 = RTU, 1 = ASCII, 2 = BACnet
PARAM_BAUDRATE = 0x0902  # 09-02, 0 = 4800 .. 3 = 34800 bit/s
PARAM_STOP_BITS = 0x0903  # 09-03, 0 = 1 stop bit, 1 = 2 stop bits
PARAM_PARITY = 0x0904  # 09-04, 0 = none, 1 = even, 2 = odd
PARAM_DATA_BITS = 0x0905  # 09-05, 0 = 8 data bits, 1 = 7 data bits

# Values the drive needs for RS-485 control, from the manual's setup table.
COMMAND_SOURCE_RS485 = 2  # 00-02 = 2
FREQUENCY_SOURCE_RS485 = 5  # 00-05 = 5
PROTOCOL_RTU = 0  # 09-01 = 0
STOP_BITS_ONE = 0  # 09-03 = 0
PARITY_NONE = 0  # 09-04 = 0
DATA_BITS_EIGHT = 0  # 09-05 = 0


def output_frequency_hz(raw: int) -> float:
    """
    Convert the output-frequency register into Hz.

    Args:
        raw: The value read from `REG_OUTPUT_FREQUENCY`.

    Returns:
        float: The output frequency in Hz.
    """
    return raw / FREQUENCY_RESOLUTION


def setpoint_frequency_hz(raw: int) -> float:
    """
    Convert the setpoint-frequency register into Hz.

    Args:
        raw: The value read from `REG_SETPOINT_FREQUENCY`.

    Returns:
        float: The setpoint frequency in Hz.
    """
    return raw / FREQUENCY_RESOLUTION


def hz_to_setpoint_raw(frequency_hz: float) -> int:
    """
    Convert a frequency in Hz into the setpoint register value.

    Args:
        frequency_hz: The requested frequency in Hz.

    Returns:
        int: The value to write to `REG_SETPOINT`, in hundredths of a Hz.

    Raises:
        ValueError: If the frequency is negative, because the register is
            unsigned and a negative value would wrap to a huge setpoint.
    """
    if frequency_hz < 0:
        raise ValueError(f"Frequency must not be negative, got {frequency_hz}")
    return round(frequency_hz * FREQUENCY_RESOLUTION)


def output_voltage_v(raw: int) -> float:
    """
    Convert the output-voltage register into volts.

    Args:
        raw: The value read from `REG_OUTPUT_VOLTAGE`.

    Returns:
        float: The output voltage in volts.
    """
    return raw / VOLTAGE_RESOLUTION


def output_current_a(raw: int) -> float:
    """
    Convert the output-current register into amps.

    Args:
        raw: The value read from `REG_OUTPUT_CURRENT`.

    Returns:
        float: The output current in amps.
    """
    return raw / CURRENT_RESOLUTION


def status_to_state(monitor: int) -> VFDState:
    """
    Decode the monitor bitfield into a `VFDState`.

    The drive reports run state and direction as two independent bits, so a
    stopped drive has no direction and is reported as ``STOPPED`` regardless of
    the direction bit.

    Args:
        monitor: The value read from `REG_MONITOR`.

    Returns:
        VFDState: The decoded state.
    """
    if not monitor & (1 << MON_RUN):
        return VFDState.STOPPED
    if monitor & (1 << MON_DIRECTION):
        return VFDState.RUNNING_FORWARD
    return VFDState.RUNNING_BACKWARD


def control_word(
    run: bool = False,
    forward: bool = True,
    jog: bool = False,
    fault_reset: bool = False,
) -> int:
    """
    Build a control-register value.

    The control register is a bitfield, not a command code: every write must
    carry the complete desired state, because the drive acts on the bits it
    receives and does not remember the previous write. Bits the driver does not
    set are written as zero, which the manual requires for reserved bits.

    The direction bit is only meaningful while the drive runs, so it is set
    together with the run bit and left clear otherwise. A stop therefore writes
    zero, which is what the drive expects.

    Args:
        run: Set the run bit.
        forward: Set the direction bit to forward; ``False`` selects reverse.
        jog: Set the jog bit for the selected direction instead of the run bit.
        fault_reset: Set the fault-reset bit.

    Returns:
        int: The value to write to `REG_CONTROL`.
    """
    word = 0
    if run:
        word |= 1 << CTRL_RUN
        if forward:
            word |= 1 << CTRL_DIRECTION
    if jog:
        word |= 1 << (CTRL_JOG_FORWARD if forward else CTRL_JOG_REVERSE)
    if fault_reset:
        word |= 1 << CTRL_FAULT_RESET
    return word
