# Vesper E4-8400 / E4-P8402 Modbus Protocol — Reference

Authoritative source: *Протокол управления ПЧ серии E4-8400 и Е4-Р8402 по
последовательной линии связи. MODBUS. Руководство пользователя*, Веспер,
version 1.0. This document is the condensed reference for the subset implemented
in `vesper/e4_8400/`. Where this file and the manual disagree, the manual wins.

**The map below has not been verified against hardware.** Every address and code
is transcribed from the manual.

The E4-8400 is a different drive from the E5-8200, not a variant of it: the
command register is a bitfield at `0000h` rather than a command code at `2501H`,
the monitor block starts at `0010h` rather than `2520H`, fault information is
spread over five bitfields rather than one code, and parameter addressing uses a
letter-to-hex group map rather than a decimal group number. Only the Modbus
transport is shared.

## 1. Transport

The drive speaks Modbus over RS485 in either RTU or ASCII mode. Four function
codes are defined:

| Function | Meaning | Read limit | Write limit |
| --- | --- | --- | --- |
| `03H` | Read holding registers | 37 registers (RTU), 14 (ASCII) | — |
| `06H` | Write single register | — | one word |
| `08H` | Line check | — | — |
| `10H` | Write multiple registers | — | 24 registers (RTU), 12 (ASCII) |

Only `03H` and `06H` are used by this driver. RTU frames are
`ADDR FC DATA CRC_L CRC_H` with the standard Modbus CRC-16 (polynomial `A001H`,
initial value `FFFFH`). ASCII frames are `3AH ADDR FC ADDR_HI ADDR_LO LEN_HI
LEN_LO LRC_HI LRC_LO 0DH`, with the LRC computed as the two's complement of the
byte sum.

The response follows the request after 3.5 bytes plus the `H5-06` delay; the
next request may follow 24 bytes after the response.

### 1.1 Device addresses

`0` is a broadcast: every drive acts on the command and none answers. `1`
through `31` are the individual drive addresses, set by parameter `H5-01`. The
manual's setup table gives the range as `1~32`, but the RTU chapter states
`1`–`31`; the driver does not depend on the upper bound.

### 1.2 Exception responses (`OPE14`)

A rejected request is answered with function code `80H` plus the original
function code and an error code:

| Code | Meaning | Cause |
| --- | --- | --- |
| `01H` | Function-code error | Function code is not `03H`, `06H`, `08H` or `10H` |
| `02H` | Register-address error | A register address is not registered, or the start register is not `0000H`/`0001H` |
| `03H` | Data-length error | Length is not 1–16, or is not a whole number of registers |
| `21H` | Data-value error | Value outside the permitted range |
| `22H` | Write not permitted | Write attempted during a PLC run command, or a `CPF03` fault with parameters set for PLC input |

The drive reports communication faults this way, not through a register, so
`read_error_code(comm=True)` always returns `0`.

## 2. Command registers (`0000h`, `0001h`)

Both registers live in volatile memory: a write takes effect immediately and is
lost on power-off.

`0000h` is a read/write bitfield. Every write must carry the complete desired
state: the drive acts on the bits it receives and does not remember the previous
write. Reserved bits must be written as `0`.

| Bit | Signal | Meaning |
| --- | --- | --- |
| 0 | Forward run | `1` = run forward |
| 1 | Reverse run | `1` = run reverse |
| 2 | Digital input D1 | `1` = on |
| 3 | Digital input D2 | `1` = on |
| 4 | Digital input D3 | `1` = on |
| 5 | Digital input D4 | `1` = on |
| 6 | Digital input D5 | `1` = on |
| 7 | Digital input D6 | `1` = on |
| 8 | Reserved | |
| 9 | Fault reset | `1` = reset the latched fault |
| A | Jog forward | `1` = jog forward |
| B | Jog reverse | `1` = jog reverse |
| C | Relay R1 | `1` = active |
| D | Relay R2 | `1` = active |
| E | Digital output DO | `1` = active |
| F | External fault | `1` = signal a fault |

`0001h` is the frequency setpoint in hundredths of a hertz: the manual states
`50.00 Hz` is `5000` decimal, `1388` hex. `0002h`–`0005h` are reserved.

The drive has no coast-to-stop bit: stop behaviour is parameter `B1-03`, so
`stop(freewheel=True)` is ignored.

## 3. Monitor registers (`0010h`–`0095h`, read only)

All monitor registers live in volatile memory and are lost on power-off.

### 3.1 Status bitfield `0010h`

| Bit | Signal | Meaning |
| --- | --- | --- |
| 0 | Running | `1` = running, `0` = stopped |
| 1 | Reserved | |
| 2 | Reverse | `1` = reverse, `0` = forward |
| 3–4 | Reserved | |
| 5 | Ready | `1` = ready to run |
| 6–F | Reserved | |

A stopped drive has no direction, so the driver reports `STOPPED` regardless of
bit 2.

### 3.2 Fault bitfields

The live fault state is spread over five registers. A bitfield can carry several
faults at once, so the driver returns a list.

`0014h` — drive faults:

| Bit | Fault |
| --- | --- |
| 1 | Low DC bus voltage (UV1) |
| 3 | No pre-charge completion signal (UV3) |
| 4 | Short circuit (SC) |
| 6 | Overcurrent (OC) |
| 7 | Overvoltage (OV) |
| 8 | Heatsink overheat (OH) |
| A | Motor overload (OL1) |
| B | Converter overload (OL2) |

`0017h` — EEPROM fault: bit 3 is `CPF03`.

`0019h` — faults detected while stopped: bit 0 low DC bus voltage, bit 1 high DC
bus voltage, bit 2 heatsink overheat, bit 7 external interlock (`b.b.`).

`001Eh` — current-meter fault: bit 0 is `CTER`.

`001Fh` — warnings: bit 0 PID feedback loss (`FBL`), bit 2 external emergency
stop (`E.S.`), bit 3 zero frequency setpoint (`STP0`), bit 4 run inhibited
(`STP1`), bit 5 stopped from the control panel (`STP2`).

### 3.3 Fault history codes `0090h`–`0092h`

`0090h`, `0091h` and `0092h` hold the last three fault codes, most recent first.
These are **codes**, not bit positions, and they use a different numbering
scheme from the bitfields above: `0014h` bit 8 is heatsink overheat while history
code `09h` is the same fault. Conflating the two would report the wrong fault, so
the driver keeps them in separate tables.

| Code | Fault |
| --- | --- |
| `00h` | No error |
| `02h` | Low DC bus voltage (UV1) |
| `05h` | Short circuit (SC) |
| `07h` | Overcurrent (OC) |
| `08h` | Overvoltage (OV) |
| `09h` | Heatsink overheat (OH) |
| `0Bh` | Motor overload (OL1) |
| `0Ch` | Converter overload (OL2) |
| `1Fh` | EEPROM fault (CPF03) |
| `31h` | Current meter fault (CTER) |
| `34h` | External interlock (`b.b.`) |
| `35h` | PID feedback loss (FBL) |

`0093h`–`0095h` hold the timestamps of those three faults.

The drive has no single "current fault code" register, so `read_error_code()`
returns `0090h` — the most recent history code — which is what a caller
comparing against a fault table expects. Use `read_faults()` for the live
bitfields and `read_fault_history()` for all three codes.

### 3.4 Monitor registers `0020h`–`0050h` (UX-XX)

| Address | Parameter | Content | Scale |
| --- | --- | --- | --- |
| `0020h` | U1-01 | Setpoint frequency | `1/100 Hz` |
| `0021h` | U1-02 | Output frequency | `1/100 Hz` |
| `0022h` | U1-03 | Output current | `1/10 A` |
| `0025h` | U1-06 | Output voltage | `1 V` |
| `0026h` | U1-07 | DC bus voltage | `1 V` |
| `0029h` | U1-10 | Input terminal state | bitfield |
| `002Ah` | U1-11 | Output terminal state | bitfield |
| `002Dh` | U1-14 | Software version | `xx.xxx` |
| `002Eh` | U1-15 | AVI input level | `1/10` |
| `002Fh` | U1-16 | ACI input level | `1/10` |
| `0037h` | U1-24 | PID feedback level | `1/10` |
| `004Dh` | U1-46 | **Power-module temperature** | `1 °C` |
| `004Eh` | U1-47 | Counter value | counts |
| `004Fh` | U1-48 | Run time 1 | |
| `0050h` | U1-49 | Run time 2 | |

`004Dh` is the only live temperature reading any drive in this package exposes.
The driver populates `heatsink_temperature_c` from it. The drive reports motor
overheat only as a fault, so `motor_temperature_c` stays `None`.

The driver reads `0020h`–`0023h` as one four-register block: setpoint frequency,
output frequency, output current and the reserved register `0023h`. Voltage, DC
bus voltage and the temperature are read separately because the gaps between
them would otherwise pull in reserved registers.

### 3.5 Fault snapshot `0083h`–`0088h`

Captured when the last fault occurred; not updated while the drive runs.

| Address | Parameter | Content |
| --- | --- | --- |
| `0083h` | U2-04 | Output frequency at fault |
| `0084h` | U2-05 | Output current at fault |
| `0085h` | U2-06 | Processor temperature at fault |
| `0086h` | U2-08 | DC bus voltage at fault |
| `0087h` | U2-09 | IGBT temperature at fault |
| `0088h` | U2-10 | Drive state at fault |

The two temperatures here are snapshots taken at the fault, not live readings,
so the driver does not use them for `heatsink_temperature_c`.

## 4. Parameter addressing

The register address is a four-digit hex number. The first digit is the
parameter group, the second is the first digit after the group letter, and the
last two are the parameter number **written in decimal but encoded as hex**.

| Group | A | B | C | D | E | H | L | O | P | T |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Hex code | 1 | 2 | 3 | 4 | 5 | 7 | 8 | A | B | C |

The manual's worked examples: `E1-09` is `5109h` (`E`→`5`, `1`→`1`, `09`→`09`);
`P1-20` is `B114h` (`P`→`B`, `1`→`1`, `20` decimal → `14` hex).

| Parameter | Register | Meaning |
| --- | --- | --- |
| `A1-02` | `1102h` | Control mode |
| `B1-01` | `2101h` | Frequency setpoint source |
| `B1-02` | `2102h` | Run/stop command source |
| `B1-03` | `2103h` | Stop method |
| `E1-04` | `5104h` | Maximum output frequency |
| `E1-09` | `5109h` | Minimum output frequency |
| `H5-01` | `7501h` | Drive address, 1–32 |
| `H5-02` | `7502h` | Baud rate: `0` = 1200, `1` = 2400, `2` = 4800, `3` = 9600, `4` = 19200 bit/s |
| `H5-03` | `7503h` | Parity: `0` = none, `1` = even, `2` = odd |
| `H5-04` | `7504h` | Action on communication loss |
| `H5-06` | `7508h` | Transmission delay, `(1~16) × 2 ms` |
| `H5-08` | `7509h` | Modbus mode: `0` = RTU, `1` = ASCII |
| `H5-09` | `750Ah` | Stop bits: `0` = 1, `1` = 2 |
| `H5-10` | `750Bh` | Data bits: `0` = 8, `1` = 7 |
| `H5-11` | `750Ch` | Communication-loss timeout, `0.0`–`25.5 s` |
| `H5-12` | `750Dh` | Permitted communication errors, 1–20 |

## 5. Deployment prerequisites

The Scietex Modbus gateway owns the RS485 bus. It is configured 8 data bits, no
parity, one stop bit, and its baud rate must match the drive. The drive's
factory settings do not match that bus on two counts, so a drive straight out of
the box cannot be reached through the gateway at all:

| Parameter | Factory | Required | Why |
| --- | --- | --- | --- |
| `H5-08` | `0` (RTU) | `0` (RTU) | The gateway speaks Modbus RTU; ASCII is not supported |
| `H5-09` | `0` (1 stop bit) | `0` (1 stop bit) | Matches the gateway bus |
| `H5-10` | `0` (8 data bits) | `0` (8 data bits) | Matches the gateway bus |
| `H5-03` | `0` (no parity) | `0` (no parity) | Matches the gateway bus |
| `H5-02` | `3` (9600) | The gateway's baud rate | A mismatch produces framing errors on both sides |
| `H5-01` | `1` | The configured gateway device id | The gateway routes by device id; the value must match the gateway device entry |

The factory baud rate is `9600`, not the `19200` the Scietex gateway commonly
runs at, so `H5-02` usually needs changing.

Two operational parameters decide whether the command registers act:

- `B1-02` must be `2` (RS-485 command source). With the factory value `0` the
  drive ignores run, stop, jog and fault-reset commands from `0000h`.
- `B1-01` must be `2` (RS-485 frequency source) for the setpoint `0001h` to be
  used.

`H5-11` (timeout) stays `0.0` and `H5-04` (action on loss) stays `0` unless the
installation wants the drive to stop when polling ceases.

Once the drive answers on the bus, add it to the gateway with the
`vesper_e4_8400` driver descriptor (`scietex.modbus.drivers`, built into
`scietex.hal.serial`), which selects the built-in RTU framer and no translator.

## 6. Driver behaviour

| Concern | Behaviour |
| --- | --- |
| `connect()` | Opens the TCP connection to the gateway; raises if the gateway is unreachable |
| `read_parameters()` | One four-register block at `0020h`, then voltage, DC bus, temperature and status |
| `frequency_percent` | Derived from `E1-04`, read once on the first parameters read unless passed to the constructor |
| `read_error_code()` | Reads `0090h`, the most recent fault history code; raises on a failed read |
| `read_error_code(comm=True)` | Returns `0`: the drive has no communication fault register |
| `read_faults()` | Reads `0014h` and returns every set fault bit |
| `read_fault_history()` | Reads `0090h`–`0092h`, the last three fault codes |
| `clear_error()` | Writes the fault-reset bit to `0000h`, then reads `0090h` back |
| `start()` / `stop()` | Single FC06 write to `0000h` |
| `set_frequency()` | Single FC06 write to `0001h`; raises `ValueError` on a negative value |
| `stop(freewheel=True)` | `freewheel` is ignored: the drive has no coast bit, stop behaviour is parameter `B1-03` |
| `heatsink_temperature_c` | Populated from `004Dh` (U1-46) |
| `motor_temperature_c` | Always `None`: the drive reports motor overheat only as a fault |
