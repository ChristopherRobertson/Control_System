# Arduino MUX Firmware

Status: archived/inactive. The Arduino MUX is disabled and bypassed in the
active control system until the MUX inputs are rewired and requalified.

Firmware for the Arduino UNO R4 Minima that controls the IR spectroscope MUX boards documented in `docs/Wiring Table.xlsx`.

## Hardware Target

- Board: Arduino UNO R4 Minima
- Serial baud: `115200`
- Line ending: newline, or both CR and LF
- Device identity: `ARDUINO_MUX_V1`
- Firmware version: `0.1.0`
- Protocol: `MUX_ROUTE_PROTOCOL_1`

## Pin Topology

The firmware follows the MUX topology in `hardware_configuration.yaml`:

- DMB1 enable: `D2`, routes digital signals to MUX Output A
- DMB2 enable: `D3`, routes digital signals to MUX Output B
- AMB1 enable: `D4`, routes analog signals to MUX Output A
- AMB2 enable: `D5`, routes analog signals to MUX Output B
- DMB3 enable: `A0`, routes digital signals to MUX Output EXT
- Output A select bus: `D6`, `D7`, `D8`, `D9`
- Output B select bus: `D10`, `D11`, `D12`, `D13`
- Output EXT select bus: `A1`, `A2`, `A3`, `A4`

The firmware assumes active-low MUX enable pins, which is typical for 16-channel mux boards. If the installed boards use active-high enables, change `MUX_ENABLE_ACTIVE_LOW` in the sketch and reflash.

## Serial Protocol

Commands are ASCII and case-insensitive. Responses are one line unless noted.

| Command | Response | Purpose |
| --- | --- | --- |
| `WHOAMI` | `ARDUINO_MUX_V1` | Device identity check |
| `VERSION` | `0.1.0` | Firmware version |
| `PROTOCOL` | `MUX_ROUTE_PROTOCOL_1` | Protocol version |
| `ROLE` | `mux_controller` | Device role |
| `PING` | `PONG` | Communication check |
| `STATUS` | `READY A=<route> B=<route> EXT=<route>` | Basic state and route latch |
| `ROUTES?` | `ROUTES A=<route> B=<route> EXT=<route>` | Latched route readback |
| `ROUTE A <route>` | `OK ROUTE A <route>` | Route MUX Output A |
| `ROUTE B <route>` | `OK ROUTE B <route>` | Route MUX Output B |
| `ROUTE EXT <route>` | `OK ROUTE EXT <route>` | Route MUX Output EXT |
| `SAFE` | `OK SAFE` | Disable all MUX boards |
| `PINS?` | Multiple `PINS ...` lines | Pin topology readback |
| `RESET` | `RESETTING` then reboot | Reset the Arduino |
| `HELP` | Multiple lines | Command list |

Unknown commands return `ERROR UNKNOWN_COMMAND <command>`. Unknown routes return `ERROR UNKNOWN_ROUTE <route>`.

## Route Names

MUX Output A digital routes:

- `dmb1_c0_hf2li_dio9`
- `dmb1_c1_hf2li_dio10`
- `dmb1_c2_hf2li_dio11`
- `dmb1_c3_hf2li_dio12`
- `dmb1_c4_hf2li_dio13`
- `dmb1_c5_hf2li_dio14`
- `dmb1_c6_hf2li_dio15`

MUX Output B digital routes:

- `dmb2_c0_hf2li_dio9`
- `dmb2_c1_hf2li_dio10`
- `dmb2_c2_hf2li_dio11`
- `dmb2_c3_hf2li_dio12`
- `dmb2_c4_hf2li_dio13`
- `dmb2_c5_hf2li_dio14`
- `dmb2_c6_hf2li_dio15`

MUX Output EXT digital routes:

- `dmb3_c0_hf2li_dio9`
- `dmb3_c1_hf2li_dio10`
- `dmb3_c2_hf2li_dio11`
- `dmb3_c3_hf2li_dio12`
- `dmb3_c4_hf2li_dio13`
- `dmb3_c5_hf2li_dio14`
- `dmb3_c6_hf2li_dio15`

MUX Output A analog routes:

- `amb1_c0_hf2li_aux1`
- `amb1_c1_hf2li_aux2`
- `amb1_c2_hf2li_aux3`
- `amb1_c3_hf2li_aux4`

MUX Output B analog routes:

- `amb2_c0_hf2li_aux1`
- `amb2_c1_hf2li_aux2`
- `amb2_c2_hf2li_aux3`
- `amb2_c3_hf2li_aux4`

Route commands are case-insensitive. The firmware stores and reports route names in uppercase.

## Operational verification

After flashing this firmware, the configured Python command templates are:

```yaml
command_protocol:
  identify: "WHOAMI"
  version: "VERSION"
  status: "STATUS"
  query_active_route: "ROUTES?"
  set_output_a_route: "ROUTE A {route}"
  set_output_b_route: "ROUTE B {route}"
  set_output_ext_route: "ROUTE EXT {route}"
  safe_idle: "SAFE"
```

Manual serial checks before running the Arduino MUX diagnostic:

```text
WHOAMI
VERSION
STATUS
ROUTE A dmb1_c0_hf2li_dio9
ROUTE B dmb2_c1_hf2li_dio10
ROUTE EXT dmb3_c2_hf2li_dio11
ROUTES?
SAFE
```

The firmware only verifies that the requested HF2LI DIO/AUX diagnostic route was latched and the correct select/en pins were driven. It does not route or validate T660 TTL timing lines; those lines go directly to MIRcat TRIG IN, Nd:YAG FIRE/Q-SWITCH, and the HF2LI DIO timing inputs.
