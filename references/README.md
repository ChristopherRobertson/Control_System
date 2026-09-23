# Instrument references

This directory contains supplier manuals, certificates, SDKs and drivers used by
the control software. The [reference registry](reference_registry.yaml) identifies
resource directories. Required vendor-library paths are resolved by the device
services and installation configuration.

| Directory | Contents |
| --- | --- |
| `manuals/` | Device operation, programming and specification references |
| `certificates/` | Supplier calibration certificates with their stated validity |
| `sdk/` | Vendor libraries, SDK headers and installation resources |

Use the [runtime configuration](../instrument/README.md) for installed identities,
selected values and operating limits, and [operator documentation](../docs/README.md)
for application workflows. Supplier specifications are not measurements of the
installed system. Certificates apply only to their named device and stated terms;
file presence does not extend calibration validity or authorize a firmware update.

Scientific measurements, acquired readbacks and analysis belong under the external
research root. Keep only the selected runtime settings needed by the application
in `instrument/`; native research records are not runtime resources.
