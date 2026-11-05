# Intek SPE-B Modbus Protocol — Reference

Authoritative source: *Руководство по эксплуатации преобразователей частоты
INTEK серии SPE-B*, chapter 7 ("Протокол связи MODBUS"), section 7.4
("Адреса регистров"), section 4.14 (communication parameters `Pd.00`–`Pd.06`)
and the `P0.10` entry of section 4.2. This document is the condensed reference
for the subset implemented in `intek/spe_b/`. Where this file and the manual
disagree, the manual wins.

**The map below has not been verified against hardware.** Every address and
code is transcribed from the manual; the scaling assumptions marked
"assumption" are inferred and must be confirmed with a live drive before they
are relied on.

## 1. Transport

The drive speaks Modbus RTU over RS485. Only two function codes are used:

| Function | Meaning | Limits |
| --- | --- | --- |
| `03` | Read holding registers | 12 words per request (manual 7.2) |
| `06` | Write single register | one word per request |

Each frame is `ADR CMD ... CRC_L CRC_H`, standard Modbus CRC-16. The drive
answers with the same `CMD` and echoes the written value; an unsupported
address or value is answered with a Modbus exception response, and the bus-side
fault is also latched in the communication fault register (see §6).

## 2. Monitoring registers (read with FC03)

| Address | Content | Unit |
| --- | --- | --- |
| `0x1000` | Communication-protocol setpoint | `-10000..10000` = `-100.00..100.00%`, write only |
| `0x1001` | Operating frequency | percent of `P0.10`, see §9 |
| `0x1002` | DC bus voltage | raw |
| `0x1003` | Output voltage | raw |
| `0x1004` | Output current | counts of the `Pd.06` resolution |
| `0x1005` | Output power | raw |
| `0x1007` | Operating speed | raw |
| `0x1008` | Digital input state (DI) | bitfield |
| `0x1009` | Digital output state (DO) | bitfield |
| `0x100A` | Analog input AI1 voltage | raw |
| `0x100C` | Reserved | |
| `0x100D` | Counter input | raw |
| `0x100E` | Length-measurement input | raw |
| `0x100F` | Load speed | raw |
| `0x1010` | PID setpoint | raw |
| `0x1011` | PID feedback | raw |
| `0x1012` | PLC sequence | raw |
| `0x1013` | Input pulse frequency | `0.01 kHz` |
| `0x1015` | Remaining run time | raw |
| `0x1016` | AI1 voltage before correction | raw |
| `0x1019` | Linear speed | raw |
| `0x101A` | Total power-on time | raw |
| `0x101B` | Total run time | raw |
| `0x101C` | Input pulse frequency | `1 Hz` |
| `0x101D` | Communication-protocol setpoint, readable back | `-10000..10000` |
| `0x101F` | Main frequency X | raw |
| `0x1020` | Auxiliary frequency Y | raw |

The driver reads `0x1001..0x1005` as one block (5 words, inside the 12-word
limit). `0x1002` populates `dc_bus_voltage`; `0x1005` populates `output_power`.

### 2.1 Temperature

The SPE-B exposes no temperature reading. Overheat reaches the caller only as a
fault code — `0x0E` (power-module overheat) and `0x2D` (motor overheat) in §6.1 —
so both `heatsink_temperature_c` and `motor_temperature_c` stay `None`. A drive
that signals overheat only through a fault is not reporting a temperature, and
reporting `0.0` would look like a cold drive.

### 2.2 Run-time counters

`0x101A` (total power-on time) and `0x101B` (total run time) are contiguous, so
the driver reads them as one 2-word block. The manual states no unit for either.
The drive was measured incrementing `0x101A` by exactly one over sixty seconds,
so both counters are minutes; the driver divides by 60 and reports hours.

`0x1015` (remaining run time) is deliberately not read: it is the countdown to a
maintenance interval, not a total, and it reads `0` when no interval is
configured — which is indistinguishable from "no time remaining".

## 3. Control register (FC06, write only)

Address `0x2000`:

| Value | Command |
| --- | --- |
| `1` | Run forward |
| `2` | Run reverse |
| `3` | Jog forward |
| `4` | Jog reverse |
| `5` | Freewheel (coast) stop |
| `6` | Ramp stop |
| `7` | Fault reset |

Manual examples: `01 06 20 00 00 01 43 CA` runs forward, `01 06 20 00 00 06 02
08` ramps to a stop. There is no separate stop-for-a-given-direction code: the
stop command stops whichever direction is running.

## 4. Status register (read only)

Address `0x3000`:

| Value | State |
| --- | --- |
| `1` | Running forward |
| `2` | Running reverse |
| `3` | Stopped |

Only these three values are defined. The driver maps anything else, `0`
included, to `VFDState.UNKNOWN` rather than guessing "stopped": a gateway that
returns `0` because the request never reached the drive must not look like a
stopped, healthy drive.

## 5. Parameter lock

Address `0x1F00` holds the parameter password. Writing `0x8888` releases a
keypad-set lock. The driver does not write it.

## 6. Discrete and analog outputs, faults

| Address | Content |
| --- | --- |
| `0x2001` | DO bitfield: BIT0 DO1, BIT2 relay, BIT4 FM, BIT5..BIT9 VDO..VDO5 |
| `0x2002` | AOV analog output, `0..0x7FFF` = `0..100%` |
| `0x2003` | AO analog output, `0..0x7FFF` = `0..100%` |
| `0x2004` | Pulse output, `0..0x7FFF` = `0..100%` |
| `0x8000` | Drive fault code, `0x0000..0x005E` |
| `0x8001` | Communication fault code, `0x0000..0x0008` |

### 6.1 Drive faults (`0x8000`)

| Code | Fault | Code | Fault |
| --- | --- | --- | --- |
| `0x00` | No fault | `0x1A` | Total operation time limit reached |
| `0x01` | Reserved | `0x1B` | User-defined fault 1 |
| `0x02` | Current overload during acceleration | `0x1C` | User-defined fault 2 |
| `0x03` | Current overload during deceleration | `0x1D` | Power-on time limit reached |
| `0x04` | Current overload at constant speed | `0x1E` | Underload fault |
| `0x05` | Voltage overload during acceleration | `0x1F` | PID feedback lost while running |
| `0x06` | Voltage overload during deceleration | `0x28` | IGBT current-limiter fault |
| `0x07` | Voltage overload at constant speed | `0x29` | Error switching a rotating motor |
| `0x08` | Control-circuit power failure | `0x2A` | Invalid speed error |
| `0x09` | Undervoltage | `0x2B` | Motor over-speed |
| `0x0A` | Drive overload | `0x2D` | Motor overheat |
| `0x0B` | Motor overload | `0x5C` | Positioning error |
| `0x0C` | Input phase loss | `0x5E` | Feedback-sensor speed error |
| `0x0D` | Output phase loss | | |
| `0x0E` | Power-module overheat | | |
| `0x0F` | External fault | | |
| `0x10` | Remote-communication fault | | |
| `0x11` | Internal contactor fault | | |
| `0x12` | Current-sensor fault | | |
| `0x13` | Auto motor-tuning fault | | |
| `0x15` | EEPROM read/write fault | | |
| `0x16` | Drive hardware fault | | |
| `0x17` | Ground fault | | |
| `0x18` | Reserved | | |
| `0x19` | Reserved | | |

### 6.2 Communication faults (`0x8001`)

| Code | Fault |
| --- | --- |
| `0x00` | No fault |
| `0x01` | Wrong password |
| `0x02` | Command code error |
| `0x03` | CRC error |
| `0x04` | Invalid address |
| `0x05` | Invalid parameter |
| `0x06` | Parameter cannot be edited |
| `0x07` | System is locked |
| `0x08` | EEPROM write attempted while running |

Both tables are transcribed verbatim into `intek/spe_b/errors.py`. A code
missing from a table is reported as an unknown error, never as "no fault".

## 7. Parameter addressing

Parameter numbers map onto register addresses. The high byte selects the group
and the storage type, the low byte is the hexadecimal parameter index:

| High byte | Group |
| --- | --- |
| `F0`..`FF` | `P0`..`PF`, EEPROM |
| `A0`..`AF` | `b0`..`bF`, EEPROM |
| `70`..`7F` | `d0`..`dF`, EEPROM |

RAM mirrors avoid EEPROM wear. Replace `F` with `0` for the `P` group and `A`
with `4` for the `b` group; the low byte is unchanged.

| Parameter | EEPROM | RAM |
| --- | --- | --- |
| `P3.12` | `0xF30C` | `0x030C` |
| `P0.18` | `0xF012` | `0x0012` |
| `P0.10` | `0xF00A` | `0x000A` |
| `Pd.06` | `0x7006` | — |

The `PF` group is neither readable nor writable, and the `d` group is
read-only. The driver reads `P0.10` and `Pd.06` from EEPROM once, in
`connect()`, and caches both.

## 8. Communication parameters `Pd.00`–`Pd.06`

| Parameter | Meaning | Range | Factory default |
| --- | --- | --- | --- |
| `Pd.00` | Baud rate | `0`=300, `1`=600, `2`=1200, `3`=2400, `4`=4800, `5`=9600, `6`=19200, `7`=38400, `8`=57600, `9`=115200 | 19200 (`6`) |
| `Pd.01` | Frame format | `0`=8-N-2, `1`=8-E-1, `2`=8-O-1, `3`=8-N-1 | `0` (8-N-2) |
| `Pd.02` | Device address | `1..247` (`0` = master) | `1` |
| `Pd.03` | Response delay | `0..20 ms` | `2 ms` |
| `Pd.04` | Watchdog timeout | `0.0` = off, `0.1..60.0 s` | `0.0` |
| `Pd.05` | Modbus variant | `0` = non-standard, `1` = standard | `0` |
| `Pd.06` | Output-current resolution | `0` = 0.01 A, `1` = 0.1 A | `0` |

The manual's default cell for `Pd.00` prints `6005`, which is not a valid
baud-rate code; the table is read as `6` (19200) because that is the code the
manual uses in its own framing examples and the only value consistent with the
rest of the row.

## 9. Scaling

| Value | Scaling |
| --- | --- |
| Setpoint `0x1000` / `0x101D` | Hundredths of a percent: `10000` = `100.00%` |
| Operating frequency `0x1001` | See below |
| Output current `0x1004` | Counts of the `Pd.06` resolution: `0.01 A` or `0.1 A` |
| DC bus voltage, output voltage, output power | No scaling given in the manual; reported raw |
| AOV/AO/pulse outputs | `0..0x7FFF` = `0..100%` |

Frequency: the manual states only that "frequency data is a percentage, 100%
corresponds to the maximum frequency (`P0.10`)" without giving a resolution.
**Assumption:** the register uses the same hundredths-of-a-percent scale as the
setpoint, so `5000` reads as `50.00%`. This is unverified. If the drive instead
returns whole percents, every frequency this driver reports is 100 times too
low; the value in Hz is derived as `percent / 100 * P0.10`.

`P0.10` itself is stored in `0.01 Hz` units: range `50.00..500.0 Hz`, default
`50.00 Hz`, resolution `0.01 Hz`. It is read once at `connect()` and cached; a
drive that refuses the read reports `frequency_hz` as `None` while
`frequency_percent` stays valid.

## 10. Deployment prerequisites

The Scietex Modbus gateway owns the RS485 bus. It is configured 8 data bits, no
parity, one stop bit, and its baud rate must match the drive. The drive's
factory settings do not match that bus on two counts, so a drive straight out
of the box cannot be reached through the gateway at all:

| Parameter | Factory | Required | Why |
| --- | --- | --- | --- |
| `Pd.01` | `0` (8-N-2) | `3` (8-N-1) | The gateway bus is 8-N-1; the extra stop bit breaks every frame |
| `Pd.05` | `0` (non-standard) | `1` (standard) | The gateway speaks standard Modbus RTU |
| `Pd.02` | `1` | `1` (or the configured gateway device id) | The gateway routes by device id; the value must match the gateway device entry |
| `Pd.00` | `6` (19200) | The gateway's baud rate | A mismatch produces framing errors on both sides |

Because the drive is unreachable until `Pd.01` and `Pd.05` are fixed, these
changes are made from the drive's keypad (or over a direct serial link
configured for the drive's current framing), not through the gateway. Once the
drive answers on the bus, add it to the gateway with the `intek_spe_b` driver
descriptor (`scietex.modbus.drivers`, built into `scietex.hal.serial`), which
selects the built-in RTU framer and no translator.

Two operational parameters decide whether the control registers act:

- `P0.02` must be `2` (control via the digital network). With the factory value
  `0` the drive ignores run, stop, jog and fault-reset commands from `0x2000`
  and only the keypad drives it.
- `P0.03` must be `9` (frequency from the digital network) for the Modbus
  setpoint `0x1000` to be used. `set_frequency()` writes that register, so this
  parameter decides whether a frequency command has any effect.

`Pd.03` (response delay) can stay at its factory `2 ms`, and `Pd.04` (watchdog)
stays off unless the installation wants the drive to stop when polling ceases.

## 11. Driver behaviour

| Concern | Behaviour |
| --- | --- |
| `connect()` | Opens the TCP connection, then reads `P0.10` and `Pd.06` |
| `P0.10` unreadable | Warning, connection kept, `frequency_hz` reported as `None`: the percentage, current, voltage and power are still readable, and raising here would blank the whole snapshot |
| `Pd.06` unreadable | Warning, connection kept, `0.01 A` assumed: stop and fault reset must stay available |
| `read_parameters()` | One 5-word block read at `0x1001`, one 2-word block at `0x101A`, then the status register |
| Status register unreadable | Warning, `state` reported as `VFDState.UNKNOWN`: the measurements are still published |
| Run-time block unreadable | Warning, both hours fields reported as `None`: the measurements are still published |
| `read_error_code()` | Raises on a failed read; a transport failure is never reported as "no fault" |
| `clear_error()` | Writes `7` to `0x2000`, then reads the requested fault table back |
| `start()` / `stop()` | Single FC06 write to `0x2000` |
| `set_frequency()` | Writes `0x1000` as hundredths of a percent of `P0.10`; raises `ValueError` when `P0.10` is unknown or the request exceeds the maximum |
| `heatsink_temperature_c` / `motor_temperature_c` | Always `None`: the drive reports overheat only as a fault code (§2.1) |
| `total_run_hours` / `total_power_on_hours` | From `0x101B` / `0x101A`, divided by 60: the counters are minutes (§2.2) |
