# Arduino MUX future support

The MUX is disabled future work. It is not part of current experiment wiring,
startup, acquisition readiness or end-to-end UI development. HF2LI digital inputs
cannot be mirrored one-to-one onto digital outputs. Reuse requires a separately
specified physical wiring configuration; no current MUX channel assignment is
provided here.

The retained firmware and Python service are optional development resources for
an Arduino UNO R4 Minima, identity `ARDUINO_MUX_V1`, protocol
`MUX_ROUTE_PROTOCOL_1`. Their compiled pin/route definitions are not installed
wiring instructions and must not be used to infer current detector routes.
Do not flash or activate this subsystem as part of current experiment verification.

Current [direct wiring](../../../../instrument/default_wiring_state.md) connects
sample/reference detectors to HF2LI Signal 1/2 In (+) and PicoScope A/B, and MIRcat
DB9 pin 2 to HF2LI DIO21 and PicoScope EXT. No MUX is required.
