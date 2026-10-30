"""
Modbus gateway driver descriptors for the supported VFD families.

Each descriptor advertises a drive's RS485 protocol bundle through the
``scietex.modbus.drivers`` entry point group. All three drives speak standard
Modbus RTU once their communication parameters are set, so every descriptor
reuses pymodbus' built-in RTU framer and needs no custom decoder, PDU or
translator — the same shape as the ``scietex_ftmone`` descriptor in
:mod:`scietex.hal.serial.gateway.builtin_drivers`.

The serial line settings are not part of a descriptor: the gateway opens the
port with its own configuration and the drive must be configured to match it.
Each drive's required settings are documented in its protocol reference:

- ``intek/docs/protocol.md`` — Pd.01 and Pd.05
- ``vesper/docs/protocol-e5-8200.md`` — 09-01 through 09-05
- ``vesper/docs/protocol-e4-8400.md`` — H5-08 through H5-10

Attributes:
    intek_spe_b: Intek SPE-B descriptor.
    vesper_e5_8200: Vesper E5-8200 descriptor.
    vesper_e4_8400: Vesper E4-8400 / E4-P8402 descriptor.
"""

from scietex.hal.serial.gateway.drivers import ModbusDriver

intek_spe_b = ModbusDriver(
    name="intek_spe_b",
    label="Intek SPE-B",
    description="Intek SPE-B variable frequency drive speaking standard Modbus RTU.",
    device_type="Variable Frequency Drive",
    framer="RTU",
    decoder=None,
    pdus=[],
    translator=None,
)

vesper_e5_8200 = ModbusDriver(
    name="vesper_e5_8200",
    label="Vesper E5-8200",
    description="Vesper E5-8200 variable frequency drive speaking standard Modbus RTU.",
    device_type="Variable Frequency Drive",
    framer="RTU",
    decoder=None,
    pdus=[],
    translator=None,
)

vesper_e4_8400 = ModbusDriver(
    name="vesper_e4_8400",
    label="Vesper E4-8400",
    description=(
        "Vesper E4-8400 / E4-P8402 variable frequency drive speaking standard Modbus RTU."
    ),
    device_type="Variable Frequency Drive",
    framer="RTU",
    decoder=None,
    pdus=[],
    translator=None,
)
