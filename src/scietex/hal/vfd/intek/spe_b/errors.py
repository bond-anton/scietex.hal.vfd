"""
Intek SPE-B fault code tables.

Transcribed from the SPE-B user manual, section 7.4: the drive faults read from
`REG_DRIVE_FAULT` (0x8000) and the communication-protocol faults read from
`REG_COMM_FAULT` (0x8001). Code 0 means "no fault" in both tables; a code that
is missing from a table is reported as an unknown error by
`parse_error_code`.
"""

from ...base.data import VFDError

SPE_B_ERROR_CODES = {
    # VFD errors
    0: VFDError(code=0, message="No error"),
    1: VFDError(code=1, message="Reserved"),
    2: VFDError(code=2, message="Current overload during acceleration"),
    3: VFDError(code=3, message="Current overload during deceleration"),
    4: VFDError(code=4, message="Current overload at constant speed"),
    5: VFDError(code=5, message="Voltage overload during acceleration"),
    6: VFDError(code=6, message="Voltage overload during deceleration"),
    7: VFDError(code=7, message="Voltage overload at constant speed"),
    8: VFDError(code=8, message="Control circuits power failure"),
    9: VFDError(code=9, message="Undervoltage error"),
    10: VFDError(code=10, message="VFD overload"),
    11: VFDError(code=11, message="Motor overload"),
    12: VFDError(code=12, message="Input phase error"),
    13: VFDError(code=13, message="Output phase error"),
    14: VFDError(code=14, message="Overheat of power converter"),
    15: VFDError(code=15, message="External error"),
    16: VFDError(code=16, message="Remote connection error"),
    17: VFDError(code=17, message="Internal contactor failure"),
    18: VFDError(code=18, message="Current sensor failure"),
    19: VFDError(code=19, message="Automatic motor tuning failure"),
    21: VFDError(code=21, message="EEPROM IO error"),
    22: VFDError(code=22, message="VFD hardware error"),
    23: VFDError(code=23, message="Grounding failure"),
    24: VFDError(code=24, message="Reserved"),
    25: VFDError(code=25, message="Reserved"),
    26: VFDError(code=26, message="Total operation timeout"),
    27: VFDError(code=27, message="User error 1"),
    28: VFDError(code=28, message="User error 2"),
    29: VFDError(code=29, message="Power on timeout"),
    30: VFDError(code=30, message="Underloaded error"),
    31: VFDError(code=31, message="PID feedback connection loss"),
    40: VFDError(code=40, message="IGBT current limiter failure"),
    41: VFDError(code=41, message="Running motor switch error"),
    42: VFDError(code=42, message="Speed error"),
    43: VFDError(code=43, message="Over speed error"),
    45: VFDError(code=45, message="Motor overheat error"),
    92: VFDError(code=92, message="Positioning error"),
    94: VFDError(code=94, message="Calculated speed error"),
}


SPE_B_ERROR_CODES_COM = {
    # Communication errors
    0: VFDError(code=0, message="No error"),
    1: VFDError(code=1, message="Wrong password"),
    2: VFDError(code=2, message="Command code error"),
    3: VFDError(code=3, message="CRC error"),
    4: VFDError(code=4, message="Invalid address"),
    5: VFDError(code=5, message="Invalid parameter"),
    6: VFDError(code=6, message="Parameter can not be edited"),
    7: VFDError(code=7, message="System is blocked"),
    8: VFDError(code=8, message="EEPROM write during operation"),
}
