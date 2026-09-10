# Single-pump recipe resources

`compile_plan` builds a finite recipe from five main inputs: spectral start/stop,
scan speed, early observation coverage and total observation duration. Each
Advanced value left automatic is resolved independently from installed readbacks,
module defaults and the requested scan. Overriding one value leaves the others
automatic. The retained plan contains both requested and resolved settings.

Connected discovery selects the QCL covering both spectral endpoints and reads
its pulse parameters/current. HF2LI rates and filter settings are selected from
supported values within aggregate throughput. Provisional offline requests are
labeled as such and resolved again against connected capabilities. The maintained
2 MHz/150 ns probe recipe and nominal 179830 ns Fire-to-Q-switch delay supply
fallbacks; the latter is a command delay, not a measured optical correction.
Material, temperature, calibration, promotion and approval metadata do not gate
planning or select operating values.

The installed T660-1 A/B/C channels supply HF2LI reference, MIRcat pulse trigger
and T660-2 frame input. Channel D is OFF. T660-2 A/B are Fire/Q-switch; C is the
negative-polarity MIRcat Process Trigger; D remains OFF. Fire/Q-switch command
polarity defaults negative, matching the maintained Nd:YAG recipe. The first early frame
alone enables A/B. Every subsequent early scan, later burst, preliminary, control
and final spectrum keeps those pump outputs OFF. Each table includes an all-OFF
terminal frame, frame repetition one and train count zero. Train count zero still
produces an enabled channel's first pulse.

The complete early train must fit the installed physical frame capacity. It is
never silently split. Later bursts and the final state measurement are explicit
separate unpumped tables; observations establish their actual timing relative to
the retained original pump epoch. The host's documented pending-field uploader
provides acknowledged incremental progress and cancellation while outputs are
inhibited. Host scheduling may prepare tables; it does not establish precise
edges or erase actual gaps.

The automatic early count covers the requested horizon through the last scan end.
Later observations are logarithmically spaced explicit blocks, followed by final
spectra at the observation limit. The single-detector blank is a brief reusable
unpumped spectral acquisition. Native detector samples, DIO scan activity and
marker timestamps determine actual timing and spectral support. Cross-detector
matching uses declared tolerances derived from sampling rate and scan speed.

Timing limits are sourced from the maintained T660 Manual F5: 10 ps edge grid,
3600 s delay-plus-width range, uint32 trigger predivider, 8192 frame slots and
80 ns–10 s train spacing on a 20 ns grid. Nonzero train counts are deliberately
unused because the frozen host uploader supports the explicit one-pulse frame
architecture. These command grids do not establish optical resolution or IRF.
The planner checks timing, rate, duty, frame capacity, memory and declared storage
and exposure budgets before creating or uploading an oversized table. Dark waits
disable probe channel B while retaining reference A and the original time epoch.
