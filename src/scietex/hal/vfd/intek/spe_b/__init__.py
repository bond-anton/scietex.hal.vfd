"""
Intek SPE-B drivers.

Two transports are supported for the same register map:

- :class:`SPEvB` talks Modbus RTU to the drive over a direct serial connection.
- :class:`IntekSPEBModbusVFD` talks Modbus/TCP to the Scietex Modbus gateway,
  which owns the serial bus and routes requests to the drive by unit id.

Modules:
    registers: Register addresses, control and status codes, scaling helpers.
    errors: Drive and communication fault code tables.
    rs485: The direct-serial client.
    client: The Modbus/TCP gateway client.
"""

from .client import IntekSPEBModbusVFD
from .errors import SPE_B_ERROR_CODES, SPE_B_ERROR_CODES_COM
from .rs485 import SPEvB

__all__ = [
    "IntekSPEBModbusVFD",
    "SPE_B_ERROR_CODES",
    "SPE_B_ERROR_CODES_COM",
    "SPEvB",
]
