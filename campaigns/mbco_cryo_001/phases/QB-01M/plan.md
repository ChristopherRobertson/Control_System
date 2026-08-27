# QB-01M — cryogenic MbCO MIRcat probe and acquisition optimization

Campaign: `mbco-cryo-001`  
Domain: `characterization`  
Registry status: `optional`  
Required dependencies: `R9`  
Optional dependencies: `none`  

This is the canonical phase plan. It does not authorize hardware,
acquisition, status changes, or promotion. Universal execution,
retention, restoration, and procedural-writeup requirements are in
the campaign `../../requirements.md`.

## Phase-specific procedure and deliverables

The detailed phase text below was materialized from the former combined procedure catalog. Git commit `75b138a` preserves that pre-split source.

### QB-01M — cryogenic MbCO MIRcat probe and acquisition optimization

This gate belongs only to the optional branch after HRP closeout, restoration, and
handoff. Qualify cryostat geometry/windows/transmission, temperature stability,
gradients, condensation and recovery; MIRcat 20-25 ns through 1005 ns pulse widths,
T660-2 rate, current, wavelength/linewidth, latency/jitter, power stability;
detector/Pico response/saturation; HF2LI only inside its measured envelope; and all
three acquisition modes in `campaigns/methods/time_resolved_acquisition_modes.md`.

Enforce `rate_Hz*pulse_width_s <= 0.30` with a lower documented operating margin.
At 2 MHz the ceiling is 150 ns, so 1005 ns is prohibited. Use direct
detector/PicoScope for pulse-level resolution. If the slowed feature remains outside
HF2LI support, retain the direct path, narrow the claim, or stop the branch.

## Closeout

The phase-specific products above are additional to the common data
contract. Closure requires retained/indexed evidence, acceptance
evaluation, restoration where applicable, `final_report.md`, and an
indexed, manifest-linked, reviewer-accepted `procedural_writeup.md`.
