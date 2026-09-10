# Fixed-Wavenumber Kinetics

The independently registered tabs are **Fixed-Wavenumber Kinetics**
(`fixed_wavenumber_kinetics:single`) and **Dual-Detector Fixed-Wavenumber
Kinetics** (`fixed_wavenumber_kinetics:dual`). They share implementation within
this module and keep separate settings, data, cancellation and operation state.

## Operation

1. Choose the top-bar Save Location and enter the selected wavenumber.
2. Set the time before the pump, recovery time, and finite event count. Select
   **No pump** for an unpumped control. A sample label is optional.
3. For single-detector blank correction, place the blank in the sample path and
   use **Acquire blank**, or **Load blank**. Replace it with the sample before
   sample acquisition. Without a blank the tab records native and
   baseline-relative sample signals. Dual mode records sample and reference
   simultaneously and does not require a separate blank capture.
4. **Acquire sample - pump off** provides an optional retained unpumped sample.
   **Start** records a baseline within the measurement and then executes the
   requested finite events; no separate preliminary or review is required.
5. **Stop** requests cancellation. Wait for retrieval, cleanup and native saving
   before another operation. **New run** clears this tab's selected data while
   retaining settings and all saved files.

Connected instruments are the default. The tab checks connected settings when
shown; **Check connected device** repeats this capability check. A plan can
be edited and saved before connecting. Every acquisition resolves automatic
settings again under exclusive host ownership, verifies the installed devices,
and records requested, selected and actual settings. A concrete device error
must be corrected before that operation can proceed.

The check closes its owned sessions using established device cleanup, including
the MIRcat alignment-pointer safe-off behavior. It does not acquire a spectrum.

Temperature, material, condition and preparation fields in older saved records
remain annotations. They do not select a different procedure or restrict event
counts. There are no verification checkboxes, hidden acceptance flags, promoted
profile requirements or fresh-state approval gates. Interlocks, actual device
errors, finite event counts, exclusive ownership and cleanup remain enforced.
Manual sample exchange and shutters are operator actions; the application does
not claim to control unsupported hardware.

## Automatic settings and overrides

The default detector rate, filter, input configuration and probe/pump settings
come from current connected readbacks and device capabilities. The maintained
wiring supplies channel identities. Durations, event counts, storage estimates
and timing frames are derived from the entered experiment inputs. The probe
carrier and finite pump interval are distinct.

The MIRcat internal pulse rate is also independent of the external T660 probe
trigger. Its connected setting must exceed the external rate and remain within
QCL 1's pulse-rate, width and duty limits. External-rate overrides do
not overwrite the internal rate. Both are recorded and checked before emission.
The installed instrument has one QCL. Current operations always use QCL 1 and
its connected tuning range; historical QCL metadata cannot route a new run to
another laser channel. Repetition rate multiplied by pulse width in seconds
must not exceed 0.30. The internal pulse duty also remains at or below 30%,
and tighter vendor limits still apply.

The framed **Advanced overrides** form stays visible. It contains **Repetition
rate**, **Pulse width**, **Event interval**, and detector **Rate**, **Time constant**
and **Filter order**. Dual mode provides independent sample and reference
columns. A blank value means Automatic. Changing one override does not freeze
other automatic choices. **Restore automatic settings** clears instrument
overrides. Loading older GUI preferences or plans resets removed engineering
controls to current defaults or Automatic; their former values remain historical
provenance and cannot silently steer a new run. Native runs and analysis records
remain unchanged.

**Other positions** accepts comma-separated wavenumbers; **Load** imports a
measured selection. Additional positions execute in entered order; the result is a sequence of fixed
points, not a simultaneously measured spectrum. Requested later events remain
separately identifiable. Observed recovery/reset outcomes are recorded; an
incomplete reset does not silently certify later events as equivalent or permit
an automatic biological retry.

## Signal calculations and limits

The HF2LI is the spectral recorder. The dual-detector calculation uses valid
matched device ticks, `Q = S/R`, an actually observed unpumped `Q0`, and
`delta A = -log10(Q/Q0)`. Single mode uses a compatible measured sequential blank
when supplied. Without one, its displayed ratio is measured `S/S0` and its log
signal is `-log10(S/S0)`; these are baseline-relative quantities, not
blank-corrected transmission or absolute absorbance.

Absolute absorbance is available only with an applicable measured path-balance
factor `B`, as `A = -log10(Q/B)`. A sample baseline is never substituted for B.
Nonpositive, nonfinite or missing reference support stays missing. Covariance
and valid support are retained.

Apparent recovery fits convolve the exponential-plus-offset/drift model with an
available measured acquisition response. Without a qualified response, raw and
relative traces remain available and the lifetime fit is marked unresolved.
Fit residuals and conditional uncertainty are retained when a fit is supported.
A fixed point does not establish full band area or a microscopic pathway;
fine timestamp precision does not establish nanosecond temporal resolution.
**Export comparison** writes a versioned exchange file for comparison with an
appropriate stroboscopic data product, without importing that experiment.

## Retention and integrity

Each explicitly planned event/position block has a continuous HF2 subscription.
Disk chunks do not reset the original device-clock pump epoch or restart the
acquisition. Gaps, overlaps, missing references, overload/unlock and event-count
errors remain explicit. Native numeric values, dtypes and integer ticks are
preserved; bounded display/fit subsets do not replace the full native chunks.

Timing tables use acknowledged T660 pending-field uploads. Actual observed
electrical pump markers remain distinct from programmed commands and optical
arrival. All real access uses the host's ownership scope through safe cleanup
and required preservation. Cleanup faults remain host faults even after a worker
finishes. Interrupted, rejected and restoration records are retained.

T660 cleanup restores and verifies the original edge-reference relationships,
timing modes, values, polarities and terminations, while keeping sources and
outputs OFF. MIRcat cleanup verifies the original internal pulse settings.

Runs are stored under `measurements/fixed_wavenumber_kinetics/<mode>/` with unique
run IDs. The Save Location is frozen at operation start. Plan/run loading checks
experiment, schema, detector mode and actual data compatibility. Optional
annotations do not invalidate measured data. Incompatible optional parents are
not used for normalization, and files are never replaced by a search for a
similar-looking record. Full native chunks remain on disk if a selected external
parent is unavailable. No repository checksum matching gate is introduced.

## Verification

Module tests exercise pure planning, deterministic finite schedules, both
installed-adapter paths using injected services, native retention, relative
normalization, missing/invalid streams, cancellation, cleanup-failure precedence,
tab isolation and the common compact panel. UI inspection uses retained test
data and loaded fonts; no physical measurement is performed for screenshots.

The module suite passed all **185 tests**, including QCL 1 routing, independent
MIRcat rates and duty boundaries, old-settings migration, T660 reference-topology
restoration, failed-readback preservation and offline activation without
hardware-access attempts. Shared host, service and existing
Phase Scan regression coverage passed **277 tests**, with **6 skipped**. Both
tabs were rendered in the actual application shell at 1100 by 780 pixels, with
every override field visible, no outer vertical scrolling, no horizontal
settings scrolling and no clipped plot labels.

No lasers were fired and no physical acquisition was performed during this
overhaul. Injected-device verification establishes the implemented connected
software path, not measured optical timing, detector response or sample kinetics.
