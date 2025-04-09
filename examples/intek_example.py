"""Intek SPE B operation example"""

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
