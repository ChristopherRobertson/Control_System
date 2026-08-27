# Runtime instrument authority

This directory is the interface between promoted scientific results and the control
application. The application consumes only versioned promoted bundles and current
hardware/wiring configuration—not raw campaign evidence or prose reports.

During migration, `hardware_configuration.yaml`, `wiring_map.yaml`, and `recipes/`
remain at their established locations for GUI compatibility. `control_app.paths`
provides the stable lookup layer.
