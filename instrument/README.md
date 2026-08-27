# Runtime instrument authority

This directory is the interface between promoted scientific results and the control
application. The application consumes only versioned promoted bundles and current
hardware/wiring configuration—not raw campaign evidence or prose reports.

`hardware_configuration.yaml`, `wiring_map.yaml`, schemas, and runtime recipes are
canonical in this directory. `control_app.paths` resolves them for the GUI and also
accepts historic path strings in retained manifests without recreating legacy
directories.
