# Single-pump recipe resources

The executable recipe is the deterministic result of `compile_plan` with explicit
scientific inputs and separately recorded capability/readback data. There is no
qualified default operating recipe in this package. `example_settings()` is an
explicitly labeled, nonbiological simulation example and cannot establish hardware
readiness.

The installed T660-1 A/B/C channels supply HF2LI reference, MIRcat pulse trigger
and T660-2 frame input. Channel D is OFF. T660-2 A/B are Fire/Q-switch; C is the
negative-polarity MIRcat Process Trigger; D remains OFF. The first early frame
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

Timing limits are sourced from the maintained T660 Manual F5: 10 ps edge grid,
3600 s delay-plus-width range, uint32 trigger predivider, 8192 frame slots and
80 ns–10 s train spacing on a 20 ns grid. Nonzero train counts are deliberately
unused because the frozen host uploader supports the explicit one-pulse frame
architecture. These command grids are not optical resolution or qualified IRF.

The hardware configuration and `instrument/wiring_map.yaml` define topology,
not sample operating values. Promoted calibration and condition/sample evidence
remain separately identified. Nominal 77 K alone never establishes sample
temperature, matrix/cell or state equivalence.
