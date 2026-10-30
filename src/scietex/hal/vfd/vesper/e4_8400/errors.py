"""
Vesper E4-8400 / E4-P8402 fault code tables.

Transcribed from the E4-8400 Modbus communication manual. The drive reports
faults in two different shapes, and this module keeps them apart:

- Five *bitfields* describe the current fault state: ``0014h`` (drive faults),
  ``0017h`` (EEPROM), ``0019h`` (faults detected while stopped), ``001Eh``
  (current meter) and ``001Fh`` (warnings). A bitfield can carry several faults
  at once, so :func:`decode_faults` returns a list.
- Three *code registers* hold the fault history: ``0090h``-``0092h`` are the
  last three fault codes, each a single value from the manual's fault-code
  table.

The bitfield positions and the history codes are different numbering schemes
for the same faults, so they are separate tables. ``0014h`` bit 8 is heatsink
overheat while history code ``09h`` is the same fault; conflating them would
report the wrong fault.

Attributes:
    E4_8400_FAULT_BITS: Fault bitfield positions in ``0014h``.
    E4_8400_EEPROM_FAULT_BITS: Fault bitfield positions in ``0017h``.
    E4_8400_STOP_FAULT_BITS: Fault bitfield positions in ``0019h``.
    E4_8400_CURRENT_METER_FAULT_BITS: Fault bitfield positions in ``001Eh``.
    E4_8400_WARNING_BITS: Warning bitfield positions in ``001Fh``.
    E4_8400_FAULT_CODES: Fault history codes, as stored in ``0090h``-``0092h``.
    E4_8400_ERROR_CODES_COM: Communication fault code table.
"""

from ...base.data import VFDError

E4_8400_FAULT_BITS: dict[int, VFDError] = {
    1: VFDError(code=1, message="Low DC bus voltage (UV1)"),
    3: VFDError(code=3, message="No pre-charge completion signal (UV3)"),
    4: VFDError(code=4, message="Short circuit (SC)"),
    6: VFDError(code=6, message="Overcurrent (OC)"),
    7: VFDError(code=7, message="Overvoltage (OV)"),
    8: VFDError(code=8, message="Heatsink overheat (OH)"),
    10: VFDError(code=10, message="Motor overload (OL1)"),
    11: VFDError(code=11, message="Converter overload (OL2)"),
}

E4_8400_EEPROM_FAULT_BITS: dict[int, VFDError] = {
    3: VFDError(code=3, message="EEPROM fault (CPF03)"),
}

E4_8400_STOP_FAULT_BITS: dict[int, VFDError] = {
    0: VFDError(code=0, message="Low DC bus voltage"),
    1: VFDError(code=1, message="High DC bus voltage"),
    2: VFDError(code=2, message="Heatsink overheat"),
    7: VFDError(code=7, message="External interlock (b.b.)"),
}

E4_8400_CURRENT_METER_FAULT_BITS: dict[int, VFDError] = {
    0: VFDError(code=0, message="Current meter fault (CTER)"),
}

E4_8400_WARNING_BITS: dict[int, VFDError] = {
    0: VFDError(code=0, message="PID feedback loss (FBL)"),
    2: VFDError(code=2, message="External emergency stop (E.S.)"),
    3: VFDError(code=3, message="Zero frequency setpoint (STP0)"),
    4: VFDError(code=4, message="Run inhibited (STP1)"),
    5: VFDError(code=5, message="Stopped from the control panel (STP2)"),
}

E4_8400_FAULT_CODES: dict[int, VFDError] = {
    0x00: VFDError(code=0x00, message="No error"),
    0x02: VFDError(code=0x02, message="Low DC bus voltage (UV1)"),
    0x05: VFDError(code=0x05, message="Short circuit (SC)"),
    0x07: VFDError(code=0x07, message="Overcurrent (OC)"),
    0x08: VFDError(code=0x08, message="Overvoltage (OV)"),
    0x09: VFDError(code=0x09, message="Heatsink overheat (OH)"),
    0x0B: VFDError(code=0x0B, message="Motor overload (OL1)"),
    0x0C: VFDError(code=0x0C, message="Converter overload (OL2)"),
    0x1F: VFDError(code=0x1F, message="EEPROM fault (CPF03)"),
    0x31: VFDError(code=0x31, message="Current meter fault (CTER)"),
    0x34: VFDError(code=0x34, message="External interlock (b.b.)"),
    0x35: VFDError(code=0x35, message="PID feedback loss (FBL)"),
}

E4_8400_ERROR_CODES_COM: dict[int, VFDError] = {
    0: VFDError(code=0, message="No error"),
}


def decode_faults(raw: int, table: dict[int, VFDError]) -> list[VFDError]:
    """
    Decode a fault bitfield into the faults it carries.

    Args:
        raw: The bitfield value read from the drive.
        table: The bit-position table for that register.

    Returns:
        list[VFDError]: One entry per set bit the table defines, in ascending
            bit order. An empty list means no fault. Bits the table does not
            define are ignored: the manual marks them reserved.
    """
    return [table[bit] for bit in sorted(table) if raw & (1 << bit)]
