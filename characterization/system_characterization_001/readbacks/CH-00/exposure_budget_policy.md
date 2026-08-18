# Exposure-budget policy

Policy ID: `CH00-EXPOSURE-v1`

CH-00 authorizes zero emitted shots and zero sample exposure. Every later
emitting phase requires separate written authorization and a phase-specific
budget frozen before emission.

The later budget must enumerate each planned emitted event by configuration,
condition, control, replicate, and permitted retry. Rejected acquisition does
not create another shot. Unused budget cannot transfer to another phase or
condition. Preview, alignment, fault, control, and repeat events count unless
explicitly non-emitting. Hardware interlocks, safe idle, operator readiness,
source ownership, sample-plane containment, and restoration remain independent
gates.

Only average power is directly metered under the present equipment set. Mean
pulse energy may be derived from average power and verified repetition rate;
direct pulse-energy distributions and calibrated peak power are excluded.
Mylar is pump-off in the minimum validation path. Biological sample exposure,
damage, recovery, refresh, and replacement budgets remain experiment-specific
pilot decisions and do not enter characterization.
