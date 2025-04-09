# scietex.hal.vfd

The `scietex.hal.vfd` package is a Python library for interfacing with variable frequency drives (VFD).
It provides an abstract base class (`VFD`), which in its turn inherits `scietex.hal.serial.RS485Client`.
The concrete implementations for two models of VFD manufactured by Vesper and Intek are provided.

## Features
- Abstract base class (`VFD`) for consistent VFD implementations.
- Implemented VFD models:
  - `Intek SPE-B`.
  - `Vesper E5-8200`.

## Installation
Install the package via pip (assuming it’s published to PyPI):
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

 - Python 3.9 or higher.
 - `scietex.hal.serial` (For RS485 communication support).

## Usage
The package uses `VFD` as a base class, requiring subclasses to implement
`read_error_code`, `clear_error`, `read_parameters`, `read_state`, `start`, and `stop` methods.

Basic example with the Intek SPE-B VFD:

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
    serial_configuration = ModbusSerialConnectionConfig(port="/dev/serial0", baudrate=19200)
    asyncio.run(main(serial_configuration))
```
 
## Contributing

Contributions are welcome! To contribute:

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/YourFeature`).
3. Commit your changes (`git commit -m "Add your message"`).
4. Push to the branch (`git push origin feature/YourFeature`).
5. Open a Pull Request.

Please include tests (if applicable) and follow PEP 8 style guidelines.

## License

This project is licensed under the **MIT License** - see the LICENSE file for details.
