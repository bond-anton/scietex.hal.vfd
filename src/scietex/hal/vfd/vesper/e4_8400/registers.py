"""
Vesper E4-8400 / E4-P8402 register map and scaling helpers.

Transcribed from the E4-8400 Modbus communication manual. The manual is the only
source for these values; see ``vesper/docs/protocol-e4-8400.md`` for the full
reference, including the parameter addressing scheme and the communication
settings a drive needs before it can talk to the Scietex Modbus gateway.

The E4-8400 is a different drive from the E5-8200, not a variant of it: the
control register is a bitfield at ``0000h`` rather than a command code at
``2501H``, the monitor block starts at ``0010h`` rather than ``2520H``, the
fault information is spread over five bitfields rather than one code, and the
parameter addressing uses a letter-to-hex group map rather than a decimal group
number. Only the Modbus transport is shared.

Unlike the E5-8200, this drive reports a live power-module temperature
(``004Dh``, U1-46), which is the only temperature reading any drive in this
package exposes.

Functions:
    output_frequency_hz: Convert the output-frequency register into Hz.
    setpoint_frequency_hz: Convert the setpoint-frequency register into Hz.
    hz_to_setpoint_raw: Convert a frequency in Hz into the setpoint register value.
    output_current_a: Convert the output-current register into amps.
    status_to_state: Decode the status bitfield into a `VFDState`.
    control_word: Build the command-register value for a command.
    parameter_register: Convert a parameter number such as ``E1-04`` into its register.
"""

from ...base.data import VFDState

# Command registers, read and written with FC03/FC06.
REG_COMMAND = 0x0000  # Command bitfield, read/write
REG_SETPOINT = 0x0001  # Frequency setpoint, hundredths of a Hz

# Command bitfield positions in `REG_COMMAND`.
CMD_FORWARD_RUN = 0  # 1 = run forward
CMD_REVERSE_RUN = 1  # 1 = run reverse
CMD_D1 = 2  # Digital input D1
CMD_D2 = 3  # Digital input D2
CMD_D3 = 4  # Digital input D3
CMD_D4 = 5  # Digital input D4
CMD_D5 = 6  # Digital input D5
CMD_D6 = 7  # Digital input D6
CMD_FAULT_RESET = 9  # 1 = reset the latched fault
CMD_JOG_FORWARD = 10  # 1 = jog forward
CMD_JOG_REVERSE = 11  # 1 = jog reverse
CMD_RELAY_R1 = 12  # Relay R1
CMD_RELAY_R2 = 13  # Relay R2
CMD_DIGITAL_OUTPUT = 14  # Digital output DO
CMD_EXTERNAL_FAULT = 15  # 1 = signal an external fault

# Monitor registers, read only.
REG_STATUS = 0x0010  # Status bitfield
REG_FAULT = 0x0014  # Fault bitfield
REG_EEPROM_FAULT = 0x0017  # EEPROM fault bitfield
REG_STOP_FAULT = 0x0019  # Fault bitfield for faults detected while stopped
REG_CURRENT_METER_FAULT = 0x001E  # Current-meter fault bitfield
REG_WARNING = 0x001F  # Warning bitfield

# Status bitfield positions in `REG_STATUS`.
STATUS_RUNNING = 0  # 1 = running, 0 = stopped
STATUS_REVERSE = 2  # 1 = reverse, 0 = forward
STATUS_READY = 5  # 1 = ready to run

# Fault bitfield positions in `REG_FAULT`.
FAULT_UV1 = 1  # Low DC bus voltage
FAULT_UV3 = 3  # No pre-charge completion signal
FAULT_SC = 4  # Short circuit
FAULT_OC = 6  # Overcurrent
FAULT_OV = 7  # Overvoltage
FAULT_OH = 8  # Heatsink overheat
FAULT_OL1 = 10  # Motor overload
FAULT_OL2 = 11  # Converter overload

# EEPROM fault bitfield positions in `REG_EEPROM_FAULT`.
EEPROM_FAULT_CPF03 = 3  # EEPROM fault

# Stop-mode fault bitfield positions in `REG_STOP_FAULT`.
STOP_FAULT_LOW_DC_BUS = 0  # Low DC bus voltage
STOP_FAULT_HIGH_DC_BUS = 1  # High DC bus voltage
STOP_FAULT_OH = 2  # Heatsink overheat
STOP_FAULT_EXTERNAL = 7  # External interlock (b.b.)

# Current-meter fault bitfield positions in `REG_CURRENT_METER_FAULT`.
CURRENT_METER_FAULT_CTER = 0  # Current meter fault

# Warning bitfield positions in `REG_WARNING`.
WARNING_FBL = 0  # PID feedback loss
WARNING_EXTERNAL_STOP = 2  # External emergency stop (E.S.)
WARNING_STP0 = 3  # Zero frequency setpoint (STP0)
WARNING_STP1 = 4  # Run inhibited (STP1)
WARNING_STP2 = 5  # Stopped from the control panel (STP2)

# Monitor registers, read only. The manual calls this block "UX-XX".
REG_SETPOINT_FREQUENCY = 0x0020  # U1-01, setpoint frequency, hundredths of a Hz
REG_OUTPUT_FREQUENCY = 0x0021  # U1-02, output frequency, hundredths of a Hz
REG_OUTPUT_CURRENT = 0x0022  # U1-03, output current, tenths of an amp
REG_OUTPUT_VOLTAGE = 0x0025  # U1-06, output voltage, volts
REG_DC_BUS_VOLTAGE = 0x0026  # U1-07, DC bus voltage, volts
REG_INPUT_TERMINALS = 0x0029  # U1-10, input terminal state
REG_OUTPUT_TERMINALS = 0x002A  # U1-11, output terminal state
REG_SOFTWARE_VERSION = 0x002D  # U1-14, software version
REG_AVI_INPUT = 0x002E  # U1-15, AVI input level
REG_ACI_INPUT = 0x002F  # U1-16, ACI input level
REG_PID_FEEDBACK = 0x0037  # U1-24, PID feedback level
REG_HEATSINK_TEMPERATURE = 0x004D  # U1-46, power-module temperature, deg C
REG_COUNTER = 0x004E  # U1-47, counter value
REG_RUN_TIME_1 = 0x004F  # U1-48, run time 1
REG_RUN_TIME_2 = 0x0050  # U1-49, run time 2

# Fault snapshot, read only. The values are captured when the last fault
# occurred and are not updated while the drive runs.
REG_FAULT_OUTPUT_FREQUENCY = 0x0083  # U2-04, output frequency at fault
REG_FAULT_OUTPUT_CURRENT = 0x0084  # U2-05, output current at fault
REG_FAULT_CPU_TEMPERATURE = 0x0085  # U2-06, processor temperature at fault
REG_FAULT_DC_BUS_VOLTAGE = 0x0086  # U2-08, DC bus voltage at fault
REG_FAULT_IGBT_TEMPERATURE = 0x0087  # U2-09, IGBT temperature at fault
REG_FAULT_DRIVE_STATE = 0x0088  # U2-10, drive state at fault

# Fault history, read only. The codes are the values listed in the manual's
# fault-code table, not bitfield positions.
REG_LAST_FAULT = 0x0090  # U3-01, most recent fault code
REG_SECOND_FAULT = 0x0091  # U3-02, second most recent fault code
REG_THIRD_FAULT = 0x0092  # U3-03, third most recent fault code
REG_LAST_FAULT_TIME = 0x0093  # U3-04, time of the most recent fault
REG_SECOND_FAULT_TIME = 0x0094  # U3-05, time of the second fault
REG_THIRD_FAULT_TIME = 0x0095  # U3-06, time of the third fault

# The four consecutive registers `read_parameters` fetches in one transaction:
# setpoint frequency, output frequency, output current and the reserved
# register 0x0023. The block starts at the setpoint so a single read covers
# both frequencies; voltage, DC bus and temperature are read separately because
# the gaps between them would otherwise pull in reserved registers.
PARAMETERS_BLOCK_ADDRESS = REG_SETPOINT_FREQUENCY
PARAMETERS_BLOCK_COUNT = 4

# Scale factors.
FREQUENCY_RESOLUTION = 100.0  # Hundredths of a Hz
CURRENT_RESOLUTION = 10.0  # Tenths of an amp

# Parameter addressing: the group letter maps to a hex digit, the parameter
# number is hex. E1-04 is 5104h, P1-20 is B114h.
PARAM_GROUP_CODES: dict[str, int] = {
    "A": 0x1,
    "B": 0x2,
    "C": 0x3,
    "D": 0x4,
    "E": 0x5,
    "H": 0x7,
    "L": 0x8,
    "O": 0xA,
    "P": 0xB,
    "T": 0xC,
}

# Parameters the driver reads or documents.
PARAM_FREQUENCY_SOURCE = "B1-01"  # 2101h, frequency setpoint source
PARAM_COMMAND_SOURCE = "B1-02"  # 2102h, run/stop command source
PARAM_STOP_METHOD = "B1-03"  # 2103h, stop method
PARAM_MAX_FREQUENCY = "E1-04"  # 5104h, maximum output frequency
PARAM_ADDRESS = "H5-01"  # 7501h, drive address, 1..32
PARAM_BAUDRATE = "H5-02"  # 7502h, 0 = 1200 .. 4 = 19200 bit/s
PARAM_PARITY = "H5-03"  # 7503h, 0 = none, 1 = even, 2 = odd
PARAM_STOP_BITS = "H5-09"  # 750Ah, 0 = 1 stop bit, 1 = 2 stop bits
PARAM_DATA_BITS = "H5-10"  # 750Bh, 0 = 8 data bits, 1 = 7 data bits
PARAM_PROTOCOL = "H5-08"  # 7509h, 0 = RTU, 1 = ASCII

# Values the drive needs for RS-485 control, from the manual's setup table.
FREQUENCY_SOURCE_RS485 = 2  # b1-01 = 2
COMMAND_SOURCE_RS485 = 2  # b1-02 = 2
PROTOCOL_RTU = 0  # H5-08 = 0
STOP_BITS_ONE = 0  # H5-09 = 0
PARITY_NONE = 0  # H5-03 = 0
DATA_BITS_EIGHT = 0  # H5-10 = 0


def parameter_register(parameter: str) -> int:
    """
    Convert a parameter number into its Modbus register address.

    The manual's addressing scheme is a letter-to-hex group map followed by the
    parameter number in hex: ``E1-04`` is ``5104h`` and ``P1-20`` is ``B114h``.

    Args:
        parameter: The parameter number, such as ``"E1-04"``.

    Returns:
        int: The register address.

    Raises:
        ValueError: If the parameter is malformed or its group letter is not in
            the manual's map.
    """
    group, _, number = parameter.partition("-")
    if not group or not number:
        raise ValueError(f"Malformed parameter number: {parameter!r}")
    code = PARAM_GROUP_CODES.get(group[0].upper())
    if code is None:
        raise ValueError(f"Unknown parameter group in {parameter!r}")
    # The manual's example is P1-20 -> B114h: the group letter becomes the high
    # nibble, the group index the next nibble, and the parameter number is
    # written in decimal but encoded as hex (20 decimal -> 0x14).
    return (code << 12) | (int(group[1:], 16) << 8) | int(f"{int(number):X}", 16)


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


def output_current_a(raw: int) -> float:
    """
    Convert the output-current register into amps.

    Args:
        raw: The value read from `REG_OUTPUT_CURRENT`.

    Returns:
        float: The output current in amps.
    """
    return raw / CURRENT_RESOLUTION


def status_to_state(status: int) -> VFDState:
    """
    Decode the status bitfield into a `VFDState`.

    The drive reports run state and direction as two independent bits, so a
    stopped drive has no direction and is reported as ``STOPPED`` regardless of
    the direction bit.

    Args:
        status: The value read from `REG_STATUS`.

    Returns:
        VFDState: The decoded state.
    """
    if not status & (1 << STATUS_RUNNING):
        return VFDState.STOPPED
    if status & (1 << STATUS_REVERSE):
        return VFDState.RUNNING_BACKWARD
    return VFDState.RUNNING_FORWARD


def control_word(
    run: bool = False,
    forward: bool = True,
    jog: bool = False,
    fault_reset: bool = False,
) -> int:
    """
    Build a command-register value.

    The command register is a bitfield, not a command code: every write must
    carry the complete desired state, because the drive acts on the bits it
    receives and does not remember the previous write. Bits the driver does not
    set are written as zero, which the manual requires for reserved bits.

    Args:
        run: Set the run bit for the selected direction.
        forward: Set the forward bit; ``False`` sets the reverse bit instead.
        jog: Set the jog bit for the selected direction instead of the run bit.
        fault_reset: Set the fault-reset bit.

    Returns:
        int: The value to write to `REG_COMMAND`.
    """
    word = 0
    if run:
        word |= 1 << (CMD_FORWARD_RUN if forward else CMD_REVERSE_RUN)
    if jog:
        word |= 1 << (CMD_JOG_FORWARD if forward else CMD_JOG_REVERSE)
    if fault_reset:
        word |= 1 << CMD_FAULT_RESET
    return word
