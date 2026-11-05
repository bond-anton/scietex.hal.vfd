# Vesper E5-8200 Modbus Protocol — Reference

Authoritative source: *Протокол управления ПЧ серии E5-8200 по последовательной
линии связи. MODBUS. Руководство пользователя*, Веспер, version 1.0. This
document is the condensed reference for the subset implemented in
`vesper/e5_8200/`. Where this file and the manual disagree, the manual wins.

**The map below has not been verified against hardware.** Every address and code
is transcribed from the manual. The manual is the only source for these values;
a `.doc` conversion of the same manual silently drops the `2523H`–`252FH`
monitor table, so always work from the PDF.

## 1. Transport

The drive speaks Modbus over RS485 in either RTU or ASCII mode. The frame
structure is at most 80 bytes. Four function codes are defined:

| Function | Meaning | Read limit | Write limit |
| --- | --- | --- | --- |
| `03H` | Read holding registers | 37 registers (RTU), 17 (ASCII) | — |
| `06H` | Write single register | — | one word |
| `08H` | Line check | — | — |
| `10H` | Write multiple registers | — | 35 registers (RTU), 15 (ASCII) |

Only `03H` and `06H` are used by this driver. RTU frames are
`ADDR FC DATA CRC_L CRC_H` with the standard Modbus CRC-16 (polynomial `A001H`,
initial value `FFFFH`, low byte transmitted first). ASCII frames are
`3AH ADDR FC ADDR_HI ADDR_LO LEN_HI LEN_LO LRC_HI LRC_LO 0DH`, with the LRC
computed as the two's complement of the byte sum.

The drive requires at least a 10 ms silent interval between a request and the
response.

### 1.1 Device addresses

`00H` is a broadcast: every drive acts on the command and none answers. `01H`
through `20H` (1–32) are the individual drive addresses, set by parameter
`09-00`.

### 1.2 Exception responses

A rejected request is answered with function code `80H` plus the original
function code and an error code:

| Code | Meaning |
| --- | --- |
| `51H` | Function-code error |
| `52H` | Address error |
| `53H` | Data-length error |
| `54H` | Data outside the permitted range |
| `55H` | Write-mode error |

The drive reports communication faults this way, not through a register, so
`read_error_code(comm=True)` always returns `0`.

## 2. Control registers (`2501H`, `2502H`)

`2501H` is a read/write bitfield. Every write must carry the complete desired
state: the drive acts on the bits it receives and does not remember the previous
write. Reserved bits must be written as `0`, and reserved registers must not be
written at all.

| Bit | Signal | Meaning |
| --- | --- | --- |
| 0 | Run command | `1` = run, `0` = stop |
| 1 | Direction | `1` = forward, `0` = reverse |
| 2 | External communication fault | `1` = signal `EFO` to the drive |
| 3 | Fault reset | `1` = reset the latched fault |
| 4 | Jog forward | `1` = jog forward |
| 5 | Jog reverse | `1` = jog reverse |
| 6 | Multi-function input S1 | `1` = on, `0` = off |
| 7 | Multi-function input S2 | `1` = on, `0` = off |
| 8 | Multi-function input S3 | `1` = on, `0` = off |
| 9 | Multi-function input S4 | `1` = on, `0` = off |
| A | Multi-function input S5 | `1` = on, `0` = off |
| B | Reserved | |
| C | Relay R1 | `1` = on, `0` = off |
| D–F | Reserved | |

`2502H` is the frequency setpoint in hundredths of a hertz: `5000` is `50.00 Hz`.
`2503H`–`251FH` are reserved.

The direction bit is only meaningful while the drive runs. The driver therefore
sets it together with the run bit and leaves it clear otherwise, so a stop
writes `0`.

## 3. Monitor registers (`2520H`–`252FH`, read only)

### 3.1 Status bitfield `2520H`

| Bit | Signal | Meaning |
| --- | --- | --- |
| 0 | Run | `1` = running, `0` = stopped |
| 1 | Direction | `1` = forward, `0` = reverse |
| 2 | Ready | `1` = ready to run |
| 3 | External communication fault | `1` = `EFO` |
| 4 | Data-entry error | `1` = error |
| 5–F | Reserved | |

A stopped drive has no direction, so the driver reports `STOPPED` regardless of
bit 1.

### 3.2 Fault code `2521H`

A single integer, `0`–`46`, not a bitfield. The full table is transcribed into
`vesper/e5_8200/errors.py`. Codes `5`, `17`, `22`, `36`, `37` and `43` are
marked reserved in the manual and are kept in the table so a caller sees the
manual's wording rather than a generic "unknown error".

Temperature appears only as a fault code — `01` (converter overheat), `25`
(converter overheat during operation), `44` and `45` (motor overheat warnings).
The drive exposes no temperature reading, so both temperature fields of
`VFDParameters` stay `None`.

### 3.3 Discrete I/O `2522H`

| Bit | Signal |
| --- | --- |
| 0–5 | Digital inputs S1–S6 |
| 6 | Relay R1 |
| 7 | Relay R2 |
| 9–F | Reserved |

### 3.4 Measurements `2523H`–`252FH`

| Address | Content | Scale |
| --- | --- | --- |
| `2523H` | Setpoint frequency | `1/100 Hz` |
| `2524H` | Output frequency | `1/100 Hz` |
| `2525H` | Output voltage | `1/10 V` |
| `2526H` | DC bus voltage | `1/1 V` |
| `2527H` | Output current | `1/10 A` |
| `2528H` | Reserved | |
| `2529H` | Reserved | |
| `252AH` | PID feedback | `1/10 %` of maximum frequency |
| `252BH` | PID input | `1/10 %` of maximum frequency |
| `252CH` | AVI analog input | `1000/10 V` |
| `252DH` | ACI analog input | `1000/10 V` |
| `252EH` | Reserved | |
| `252FH` | Model identification | `0x0110` for the E5-8200 |

The driver reads `2524H`–`2527H` as one four-register block: output frequency,
output voltage, DC bus voltage and output current. The block starts at the
output frequency rather than at the setpoint so a single read covers every
measurement the driver reports. The drive reports no output power, so
`output_power` stays `0.0`.

## 4. Parameter addressing

The register number is `XXxxH`: `XX` is the parameter group number in hex, `xx`
is the parameter index in hex. `08-03` is `0803H`; `10-11` is `0A0BH`.

| Parameter | Register | Meaning |
| --- | --- | --- |
| `00-02` | `0002H` | Main run/stop command source |
| `00-05` | `0005H` | Main frequency setpoint source |
| `09-00` | `0900H` | Drive address, 1–32 |
| `09-01` | `0901H` | Protocol: `0` = RTU, `1` = ASCII, `2` = BACnet |
| `09-02` | `0902H` | Baud rate: `0` = 4800, `1` = 9600, `2` = 19200, `3` = 34800 bit/s |
| `09-03` | `0903H` | Stop bits: `0` = 1, `1` = 2 |
| `09-04` | `0904H` | Parity: `0` = none, `1` = even, `2` = odd |
| `09-05` | `0905H` | Data bits: `0` = 8, `1` = 7 |
| `09-06` | `0906H` | Communication-error timeout, `0.0`–`25.5 s` |
| `09-07` | `0907H` | Action on communication loss |
| `09-08` | `0908H` | Permitted communication errors, 0–20 |
| `09-09` | `0909H` | Transmission delay, 5–65 |

## 5. Deployment prerequisites

The Scietex Modbus gateway owns the RS485 bus. It is configured 8 data bits, no
parity, one stop bit, and its baud rate must match the drive. The drive's
factory settings do not match that bus on two counts, so a drive straight out of
the box cannot be reached through the gateway at all:

| Parameter | Factory | Required | Why |
| --- | --- | --- | --- |
| `09-01` | `0` (RTU) | `0` (RTU) | The gateway speaks Modbus RTU; ASCII is not supported |
| `09-03` | `0` (1 stop bit) | `0` (1 stop bit) | Matches the gateway bus |
| `09-04` | `0` (no parity) | `0` (no parity) | Matches the gateway bus |
| `09-05` | `0` (8 data bits) | `0` (8 data bits) | Matches the gateway bus |
| `09-02` | `2` (19200) | The gateway's baud rate | A mismatch produces framing errors on both sides |
| `09-00` | `1` | The configured gateway device id | The gateway routes by device id; the value must match the gateway device entry |

Unlike the Intek SPE-B, the E5-8200's factory framing already matches the
gateway bus, so only the baud rate and the address need checking.

Two operational parameters decide whether the control registers act:

- `00-02` must be `2` (RS-485 command source). With the factory value `0` the
  drive ignores run, stop, jog and fault-reset commands from `2501H`.
- `00-05` must be `5` (RS-485 frequency source) for the setpoint `2502H` to be
  used.

`09-06` (timeout) stays `0.0` and `09-07` (action on loss) stays `0` unless the
installation wants the drive to stop when polling ceases. With `09-07` set to
`0`, `1` or `2` the drive stops on communication loss and does not restart when
the link returns; a new run command is required.

Once the drive answers on the bus, add it to the gateway with the
`vesper_e5_8200` driver descriptor (`scietex.modbus.drivers`, built into
`scietex.hal.serial`), which selects the built-in RTU framer and no translator.

## 6. Driver behaviour

| Concern | Behaviour |
| --- | --- |
| `connect()` | Opens the TCP connection to the gateway; raises if the gateway is unreachable |
| `read_parameters()` | One four-register block at `2524H`, then the status register |
| `frequency_percent` | Derived from `max_frequency_hz`, a constructor argument defaulting to `50.0` Hz |
| `read_error_code()` | Reads `2521H`; raises on a failed read, never reports "no fault" |
| `read_error_code(comm=True)` | Returns `0`: the drive has no communication fault register |
| `clear_error()` | Writes the fault-reset bit to `2501H`, then reads `2521H` back |
| `start()` / `stop()` | Single FC06 write to `2501H` |
| `set_frequency()` | Single FC06 write to `2502H`; raises `ValueError` on a negative value |
| `stop(freewheel=True)` | `freewheel` is ignored: the drive has no coast bit, stop behaviour is parameter `09-07` |
| `heatsink_temperature_c` / `motor_temperature_c` | Always `None`: the drive reports overheat only as a fault code |

The communication manual names no maximum-frequency parameter, so the driver
cannot read the configured maximum from the drive. `max_frequency_hz` defaults
to the factory base frequency of `50.0 Hz`; a caller whose drive runs a
different maximum must pass it to the constructor, or `frequency_percent` will
be wrong.
