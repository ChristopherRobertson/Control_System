# Control-system software

The importable package remains at repository-root `control_app/` during migration so
`python -m control_app.ui.app` and existing deployments continue to work. This
directory defines the logical software boundary and may later receive packaging and
deployment files after the compatibility layer is proven.

Scientific phase ordering, evidence status, and acceptance decisions do not belong in
the application. The application may load a promoted bundle from `instrument/` and
write a new run package to `runs/` or an explicitly approved evidence destination.
