# Runtime instrument authority

This directory is the interface between promoted scientific results and the control
application. The application consumes only versioned promoted bundles and current
hardware/wiring configuration—not raw campaign evidence or prose reports.

`hardware_configuration.yaml`, `wiring_map.yaml`, schemas, and runtime recipes are
canonical in this directory. `control_app.paths` resolves them for the GUI and also
accepts contemporaneous path strings in retained manifests without recreating
inactive directories.

[Default wiring](default_wiring_state.md) connects each detector signal through
its own female-to-female BNC adapter and then a male-to-two-female BNC tee:
sample feeds HF2LI Signal 1 In (+) and PicoScope CHA; reference feeds HF2LI
Signal 2 In (+) and PicoScope CHB. Both receivers remain connected and the
Arduino MUX remains bypassed. [wiring_table.xlsx](wiring_table.xlsx) mirrors
these detector connections and the complete timing topology.

T660-2 supplies the shared 10 MHz clock and the pump/process trains and frames.
T660-1 supplies the HF2LI reference, MIRcat probe trigger, and T660-2 trigger input.
Both channel D outputs are spare. HF2LI DIO1 is an unconnected optional acquisition
window input. MIRcat DB9 pin 2 feeds HF2LI DIO21 and PicoScope EXT.

Promotion also requires accepted source-phase procedural writeups under
`docs/phase_record_contract.md`. The writeups document the
scientific reasoning and claim boundaries; promoted machine-readable bundles and
their indexed source evidence remain the runtime/numerical authority.
