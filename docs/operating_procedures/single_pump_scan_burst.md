# Single-pump scan bursts

The **Single-Pump Scan Bursts** and **Dual-Detector Single-Pump Scan Bursts**
tabs acquire an initial rapid sequence and later logarithmically spaced bursts
after one pump trigger. Each tab has independent settings, records and output.

Set the spectral range, scan speed, early coverage and total observation time.
The application derives the scan interval, burst counts, later start times,
device timing and acquisition rates. **Advanced** contains independent overrides;
return an individual override to Auto to recalculate it. The summary above the
plots shows the resulting schedule. Connected device operations obtain current
capabilities and preserve requested settings, resolved values and readbacks.

Use **Blank** to record an unpumped blank spectrum and **Sample** to record the
unpumped sample. They use the same acquisition procedure. Matching records can
be loaded and reused; changing descriptive sample or temperature metadata does
not change the procedure. Single-detector absorbance uses a compatible blank;
relative changes can be measured without it.
Dual-detector relative measurements use the simultaneous reference detector.
**Start** acquires the pumped sequence. Missing normalization support leaves
raw data available and the unsupported derived result unavailable.

**Stop** cancels acquisition and retains partial native data. Device restoration
and saving complete before instrument ownership is released. A failed or
interrupted sequence never fires an automatic replacement pump. **New run**
starts a separate record. **Save Plan**, **Load Plan**, **Load Run** and **Export**
operate on this tab's data and use the application's selected save location.

The native spectral recorder is the HF2LI: demodulator 0 records the sample,
demodulator 3 the reference in dual mode, and demodulator 2 timing/DIO.
T660-1 provides the probe/reference clock; T660-2 provides the finite pump and
sweep-trigger sequence. Later bursts contain no pump trigger. Native integer
timestamps, detector samples, marker/direction observations and device health
remain in the run, including partial and failed records.
Native subscriptions cover captures and bounded clock-observation pages;
programming, tuning and the intervals between pages remain explicitly unobserved.

Ordinary timing is relative to the observed electrical pump trigger. An optional
independent optical measurement may establish optical arrival; an electrical
edge does not establish optical arrival or optical response resolution. The
default PicoScope detector routing is not an independent visible-pump monitor.

Single-detector processing uses `Q=S/blank` when a compatible blank is present,
or `Q=S` for relative changes without a blank. Dual-detector processing uses
`Q=S/R`. Changes relative to the unpumped sample are `Delta A=-log10(Q/Q0)`.
Dual-detector absolute absorbance requires a measured balance spectrum.
Matching uses existing measured coordinates and scan direction. Unsupported,
clipped or unlocked samples stay flagged; display selection and analysis do not
fill gaps between bursts. Recovery fractions describe observed changes within
the recorded time window and do not establish a molecular mechanism.

Plans and runs retain the version-1 module schema. Pointwise analysis version 2
records whether normalization used a blank and the observed timing reference.
Existing processed chunks retain their own recorded version. Legacy descriptive fields
remain readable. Native NPZ chunks and the append-only JSONL journal are retained
alongside derived arrays and summaries; no checksum-match requirement gates use.
The prior procedure is preserved in
[the documentation archive](../../.archive/docs/operating_procedures/single_pump_scan_burst.md).

Development verification uses injected device transports and offscreen GUI
renders. It does not constitute a physical instrument measurement.
