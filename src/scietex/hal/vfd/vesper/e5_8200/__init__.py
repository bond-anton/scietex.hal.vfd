"""
Vesper E5-8200 drivers.

Two transports are supported for the same register map:

- :class:`VesperE58200` talks Modbus RTU to the drive over a direct serial
  connection.
- :class:`VesperE58200ModbusVFD` talks Modbus/TCP to the Scietex Modbus
  gateway, which owns the serial bus and routes requests to the drive by unit
  id.

Modules:
    registers: Register addresses, control and monitor bitfields, scaling helpers.
    errors: Drive and communication fault code tables.
    rs485: The direct-serial client.
    client: The Modbus/TCP gateway client.
"""

from .client import VesperE58200ModbusVFD
from .errors import E5_8200_ERROR_CODES, E5_8200_ERROR_CODES_COM
from .rs485 import VesperE58200

__all__ = [
    "E5_8200_ERROR_CODES",
    "E5_8200_ERROR_CODES_COM",
    "VesperE58200",
    "VesperE58200ModbusVFD",
]
