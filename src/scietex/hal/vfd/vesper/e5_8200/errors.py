"""
Vesper E5-8200 fault code tables.

Transcribed from the E5-8200 Modbus communication manual, version 1.0. The
drive reports one fault code at a time in register ``2521H``; the code is a
plain integer, not a bitfield, so the table is a direct lookup.

Codes 5, 17, 22, 36, 37 and 43 are marked "reserved" in the manual. They are
kept in the table so a caller sees the manual's wording rather than a generic
"unknown error", which would suggest the code is outside the documented range.

The communication fault table is empty apart from code 0: the drive answers a
bad request with a Modbus exception response (function code ``80H`` plus an
error code), not with a value in a register, so there is no communication fault
code to read. :meth:`read_error_code` therefore always returns 0 for
``comm=True``.

Attributes:
    E5_8200_ERROR_CODES: Drive fault code table.
    E5_8200_ERROR_CODES_COM: Communication fault code table.
"""

from ...base.data import VFDError

E5_8200_ERROR_CODES: dict[int, VFDError] = {
    0: VFDError(code=0, message="No error"),
    1: VFDError(code=1, message="Power converter overheat (OH)"),
    2: VFDError(code=2, message="Current overload during stop (OC)"),
    3: VFDError(code=3, message="Undervoltage (LU)"),
    4: VFDError(code=4, message="Overvoltage (OU)"),
    5: VFDError(code=5, message="Reserved"),
    6: VFDError(code=6, message="External interlock (bb)"),
    7: VFDError(code=7, message="Current measurement circuit error (CtEr)"),
    8: VFDError(code=8, message="PID feedback signal loss (PDER)"),
    9: VFDError(code=9, message="EEPROM fault (EPR)"),
    10: VFDError(code=10, message="Auto-tuning error (ATER)"),
    11: VFDError(code=11, message="Torque overload (OL3)"),
    12: VFDError(code=12, message="Converter overload (OL2)"),
    13: VFDError(code=13, message="Motor overload (OL1)"),
    14: VFDError(code=14, message="External communication fault (EFO)"),
    15: VFDError(code=15, message="Emergency stop by external signal (E.S.)"),
    16: VFDError(code=16, message="Parameters locked (LOC)"),
    17: VFDError(code=17, message="Reserved"),
    18: VFDError(code=18, message="Current overload at constant speed (OC-C)"),
    19: VFDError(code=19, message="Current overload during acceleration (OC-A)"),
    20: VFDError(code=20, message="Current overload during deceleration (OC-D)"),
    21: VFDError(code=21, message="Current overload during start (OC-S)"),
    22: VFDError(code=22, message="Reserved"),
    23: VFDError(code=23, message="Undervoltage during operation (LV-C)"),
    24: VFDError(code=24, message="Overvoltage during deceleration (OV-C)"),
    25: VFDError(code=25, message="Converter overheat during operation (OH-C)"),
    26: VFDError(code=26, message="Stop at zero speed (STP0)"),
    27: VFDError(code=27, message="Autostart at power-on impossible (STP1)"),
    28: VFDError(code=28, message="Emergency stop from the control panel (STP2)"),
    29: VFDError(code=29, message="Local control panel control error (Err1)"),
    30: VFDError(code=30, message="Parameter setting error (Err2)"),
    31: VFDError(code=31, message="Analog signal error (Err4)"),
    32: VFDError(code=32, message="Parameter change during external communication (Err5)"),
    33: VFDError(code=33, message="Communication failure (Err6)"),
    34: VFDError(code=34, message="Parameter setting error (Err7)"),
    35: VFDError(code=35, message="Initialization error (Err8)"),
    36: VFDError(code=36, message="Reserved"),
    37: VFDError(code=37, message="Reserved"),
    38: VFDError(code=38, message="Copy error with the copy device (EPR1)"),
    39: VFDError(code=39, message="Incorrect parameter copying (EPR2)"),
    40: VFDError(code=40, message="Overspeed (OVSP)"),
    41: VFDError(code=41, message="Input phase loss (PF)"),
    42: VFDError(code=42, message="Power setting error (HPERR)"),
    43: VFDError(code=43, message="Reserved"),
    44: VFDError(code=44, message="Motor overheat warning (OH4)"),
    45: VFDError(code=45, message="Motor overheat warning (OH3)"),
    46: VFDError(code=46, message="Output current reached the limit level (CL)"),
}

E5_8200_ERROR_CODES_COM: dict[int, VFDError] = {
    0: VFDError(code=0, message="No error"),
}
