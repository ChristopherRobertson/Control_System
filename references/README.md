# Instrument references

Manuals, certificates, drivers, and SDK packages remain in their existing `docs/`
and `vendor/` locations during the non-destructive migration. `registry.yaml` gives
their logical class and location. Runtime code may depend on an SDK library; it does
not depend on a manual or completed campaign directory.
