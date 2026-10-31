# scietex.hal.vfd

The `scietex.hal.vfd` package is a Python library for interfacing with variable
frequency drives (VFD). It defines a transport-agnostic driver contract
(`VFDProtocol`) plus the data structures and capability model shared by every
driver, and ships concrete implementations for three drive families.

A driver reaches a drive over one of two transports:

- **Direct RS485** — the driver owns the serial port and speaks Modbus RTU to
  the drive itself (`scietex.hal.vfd.base.rs485.VFD`).
- **Scietex Modbus gateway** — the gateway owns the RS485 bus, and the driver
  speaks Modbus/TCP to a gateway device entry that routes to the drive by unit
  id (`scietex.hal.vfd.intek.spe_b.client.IntekSPEBModbusVFD`).

## Features

- `VFDProtocol`, a runtime-checkable contract: connect, disconnect, read
  parameters, read state, read and reset faults, start, stop and set the
  frequency setpoint.
- `VFDCapabilities`, which advertises optional control surface (direction, jog,
  freewheel stop, fault reset, frequency setpoint) so a caller can reject an
  unsupported command before dispatching it.
- `VFDParameters`, which reports frequency in both Hz and percent of the
  configured maximum, plus output current, voltage and power, and the optional
  DC bus voltage and temperatures a drive exposes. An optional field is `None`
  when the drive does not report it, which is distinct from a reported `0.0`.
- Implemented drive models, each with both transports:
  - `Intek SPE-B` — direct RS485 (`SPEvB`) and gateway (`IntekSPEBModbusVFD`).
  - `Vesper E5-8200` — direct RS485 (`VesperE58200`) and gateway
    (`VesperE58200ModbusVFD`).
  - `Vesper E4-8400` / `E4-P8402` — direct RS485 (`VesperE48400`) and gateway
    (`VesperE48400ModbusVFD`).
- Driver descriptors for the gateway (`scietex.modbus.drivers` entry-point
  group) and driver classes for a service (`scietex.hal.vfd.drivers` group).

### What each drive reports

| Field | Intek SPE-B | Vesper E5-8200 | Vesper E4-8400 |
| --- | --- | --- | --- |
| `frequency_hz` | yes¹ | yes | yes |
| `frequency_percent` | yes | yes | yes |
| `output_current` | yes | yes | yes |
| `output_voltage` | yes | yes | yes |
| `output_power` | yes | no (`0.0`) | no (`0.0`) |
| `dc_bus_voltage` | yes | yes | yes |
| `heatsink_temperature_c` | no (`None`) | no (`None`) | yes |
| `motor_temperature_c` | no (`None`) | no (`None`) | no (`None`) |

Only the E4-8400 exposes a live temperature reading (`004Dh`, U1-46). The other
two report overheat only as a fault code, and a fault is not a temperature.

¹ The SPE-B reports the operating frequency only as a percentage of `P0.10`, so
`frequency_hz` is `None` until `P0.10` has been read. A drive that refuses
`P0.10` still reports `frequency_percent`, current, voltage and power; the
connection stays usable and only the Hz field degrades. `set_frequency` is
refused in that state, because no percentage can be computed.

## Installation

Install the package via pip (assuming it's published to PyPI):

```bash
pip install scietex.hal.vfd
```

Alternatively, clone the repository and install locally:

```bash
git clone https://github.com/bond-anton/scietex.hal.vfd.git
cd scietex.hal.vfd
pip install .
```

## Requirements

- Python 3.10 or higher.
- `scietex.hal.serial` 2.4 or newer (RS485 transport and Modbus gateway
  descriptors).
- `pymodbus` 3.15 or newer (Modbus/TCP client for the gateway transport).

## Usage

Every driver implements `VFDProtocol`: `connect`, `close`, `read_data`,
`read_parameters`, `read_state`, `read_error_code`, `clear_error`, `start`,
`stop` and `set_frequency`. Check `driver.capabilities` before issuing an
optional command.

Direct RS485 with the Intek SPE-B VFD:

```python
import asyncio

from scietex.hal.serial import ModbusSerialConnectionConfig
from scietex.hal.vfd.intek import SPEvB


async def main(serial_conf: ModbusSerialConnectionConfig):
    """Main function."""
    vfd = SPEvB(serial_conf, address=1, label="Intek VFD")
    data = await vfd.read_data()
    print(data)


if __name__ == "__main__":
    serial_configuration = ModbusSerialConnectionConfig(
        port="/dev/serial0", baudrate=19200
    )
    asyncio.run(main(serial_configuration))
```

The same drive behind the Scietex Modbus gateway:

```python
import asyncio

from scietex.hal.vfd.intek import IntekSPEBModbusVFD


async def main():
    """Main function."""
    vfd = IntekSPEBModbusVFD("gateway.local", port=502, unit_id=1)
    await vfd.connect()
    try:
        print(await vfd.read_data())
        print(await vfd.read_error_code())
    finally:
        await vfd.close()


if __name__ == "__main__":
    asyncio.run(main())
```

A Vesper drive behind the gateway works the same way:

```python
from scietex.hal.vfd.vesper import VesperE48400ModbusVFD

vfd = VesperE48400ModbusVFD("gateway.local", port=502, unit_id=1)
```

`set_frequency` takes Hz, not percent: the caller works in engineering units and
each driver converts with its own maximum-frequency parameter. The E5-8200's
communication manual names no maximum-frequency parameter, so its driver takes
`max_frequency_hz` from the constructor (default `50.0`, the factory base
frequency); a caller whose drive runs a different maximum must pass it, or
`frequency_percent` will be wrong.

A drive that has never been configured for the gateway answers neither
transport. See the per-family references for the register maps, the fault tables
and the settings the gateway requires:

- [`intek/docs/protocol.md`](src/scietex/hal/vfd/intek/docs/protocol.md) —
  Intek SPE-B (`Pd.01`/`Pd.05`/`Pd.02`).
- [`vesper/docs/README.md`](src/scietex/hal/vfd/vesper/docs/README.md) — Vesper
  E5-8200 and E4-8400, plus the transport facts both manuals share.

## Contributing

Contributions are welcome! To contribute:

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/YourFeature`).
3. Commit your changes (`git commit -m "Add your message"`).
4. Push to the branch (`git push origin feature/YourFeature`).
5. Open a Pull Request.

Run the checks before opening a pull request:

```bash
tox -e format,lint,type,test
```

`format` and `lint` run `ruff`, `type` runs `ty`, and `test` runs `pytest` across
Python 3.10, 3.12 and 3.14.

## License

This project is licensed under the **MIT License** - see the LICENSE file for details.
