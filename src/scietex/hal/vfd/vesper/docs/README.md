# Vesper VFD Protocol References

Two Vesper drive families are supported, each with its own protocol reference:

- [`protocol-e5-8200.md`](protocol-e5-8200.md) — Vesper E5-8200.
- [`protocol-e4-8400.md`](protocol-e4-8400.md) — Vesper E4-8400 and E4-P8402.

Both manuals are *Протокол управления ПЧ … по последовательной линии связи.
MODBUS. Руководство пользователя*, Веспер, version 1.0.

The two drives are separate implementations, not variants of one: the command
register, the monitor block, the fault model and the parameter addressing all
differ. Only the Modbus transport is shared.

## Shared transport facts

Both manuals state the same framing rules, so they are recorded once here rather
than repeated in each reference.

- **RS485, RTU or ASCII.** The Scietex Modbus gateway speaks RTU only, so both
  drivers require the drive's protocol parameter set to RTU (`09-01` = `0` on
  the E5-8200, `H5-08` = `0` on the E4-8400).
- **Function codes.** `03H` read holding registers, `06H` write single register,
  `08H` line check, `10H` write multiple registers. Both drivers use only `03H`
  and `06H`.
- **CRC-16.** Polynomial `A001H`, initial value `FFFFH`, low byte transmitted
  first. This is the standard Modbus CRC, so the gateway's built-in RTU framer
  handles it.
- **LRC.** ASCII mode only: the two's complement of the byte sum. Unused by the
  gateway path.
- **Broadcast.** Address `0` reaches every drive on the bus and none answers.
- **Exception responses.** A rejected request is answered with function code
  `80H` plus an error code. Neither drive exposes a communication fault register,
  so `read_error_code(comm=True)` returns `0` on both.
- **Bus wiring.** Up to 1200 m of cable, with 120 Ω / 0.25 W terminators at both
  ends.

## Shared gateway prerequisites

The Scietex Modbus gateway bus is 8 data bits, no parity, one stop bit. Both
drives must be configured to match before the gateway can reach them:

| Setting | E5-8200 | E4-8400 | Required |
| --- | --- | --- | --- |
| Protocol | `09-01` | `H5-08` | RTU (`0`) |
| Stop bits | `09-03` | `H5-09` | 1 (`0`) |
| Data bits | `09-05` | `H5-10` | 8 (`0`) |
| Parity | `09-04` | `H5-03` | none (`0`) |
| Baud rate | `09-02` | `H5-02` | the gateway's baud rate |
| Address | `09-00` | `H5-01` | the gateway device id |
| Command source | `00-02` = `2` | `B1-02` = `2` | RS-485 |
| Frequency source | `00-05` = `5` | `B1-01` = `2` | RS-485 |

The E5-8200's factory framing already matches the gateway bus; only its baud
rate and address need checking. The E4-8400's factory baud rate is `9600`, which
usually differs from the gateway's, so `H5-02` normally needs changing.

## Temperature

Only the E4-8400 reports a live temperature: `004Dh` (U1-46), the power-module
temperature in degrees Celsius. The E5-8200 reports overheat only as a fault
code, so both temperature fields of `VFDParameters` stay `None` for it. A drive
that signals overheat only through a fault is not reporting a temperature.
