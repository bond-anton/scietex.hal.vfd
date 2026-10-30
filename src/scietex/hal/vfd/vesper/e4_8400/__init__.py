"""
Vesper E4-8400 / E4-P8402 drivers.

Two transports are supported for the same register map:

- :class:`VesperE48400` talks Modbus RTU to the drive over a direct serial
  connection.
- :class:`VesperE48400ModbusVFD` talks Modbus/TCP to the Scietex Modbus
  gateway, which owns the serial bus and routes requests to the drive by unit
  id.

Modules:
    registers: Register addresses, command and status bitfields, scaling helpers.
    errors: Fault bitfield and fault history code tables.
    rs485: The direct-serial client.
    client: The Modbus/TCP gateway client.
"""

from .client import VesperE48400ModbusVFD
from .errors import (
    E4_8400_ERROR_CODES_COM,
    E4_8400_FAULT_BITS,
    E4_8400_FAULT_CODES,
    decode_faults,
)
from .rs485 import VesperE48400

__all__ = [
    "E4_8400_ERROR_CODES_COM",
    "E4_8400_FAULT_BITS",
    "E4_8400_FAULT_CODES",
    "VesperE48400",
    "VesperE48400ModbusVFD",
    "decode_faults",
]
