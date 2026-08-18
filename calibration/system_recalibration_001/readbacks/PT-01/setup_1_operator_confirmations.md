# PT-01 Setup 1 operator confirmations

Campaign: `system_recalibration_001`  
Phase: `PT-01`  
Operator: Christopher Robertson

This continuation record preserves operator-reported Setup 1 state. It does
not replace the passed initial preflight or any earlier PT-01 evidence.

| Confirmation UTC | Setup condition | Operator observation | Status |
|---|---|---|---|
| 2026-08-17T16:26:16Z | Complete Nd:YAG timing DB9 disconnected from the laser | Operator reported: "Its disconnected" | CONFIRMED |
| 2026-08-17T16:51:18Z | Adapter A signal clip connected to disconnected Nd:YAG timing DB9 harness pin 7 | Operator reported both requested clips attached | CONFIRMED |
| 2026-08-17T16:51:18Z | Adapter A shield/ground clip connected to disconnected Nd:YAG timing DB9 harness pin 2 | Operator reported both requested clips attached | CONFIRMED |
| 2026-08-17T16:51:34Z | Adapter A BNC connected directly to PicoScope channel A | Operator reported: "its conected" | CONFIRMED |
| 2026-08-17T16:58:05Z | Complete Setup 1 wiring: MIRCAT-DB9-CABLE-01 disconnected only at MIRcat; Adapter B signal/shield on destination pins 4/7 and BNC on PicoScope CHB; reserved pin 5 disconnected; pins 6/8 unused and unwired; T660-1 CHD disconnected; T660-2 CHB/CHC normal routes disabled; T660-2 CHD connected to T660-1 TRIG IN; Nd:YAG path remains isolated on Adapter A to PicoScope CHA | Operator reported: "Wiring setup is complete" | CONFIRMED |

No measurement output was enabled by the initial connection confirmations.
The remaining Setup 1 conditions and required post-connection safe-idle
readback were subsequently completed before acquisition.

## Final restoration

| Confirmation UTC | Restored state | Operator observation | Status |
|---|---|---|---|
| 2026-08-17T17:16:47Z | Adapter A and Adapter B measurement connections removed; complete Nd:YAG timing DB9 and MIRCAT-DB9-CABLE-01 restored to their devices; normal T660 routes retained; T660-1 CHD remains disconnected; no splitter moved | Operator reported: "Default wiring has been restored." | CONFIRMED |
