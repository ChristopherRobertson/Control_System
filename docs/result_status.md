# Acquisition result status

All existing acquisitions, including archived acquisitions, and all future acquisitions are functionality tests until Christopher Robertson explicitly changes this designation. Completion, successful processing, saved qualification fields, or software test results do not establish scientific claims, dissertation accuracy, publication eligibility, or runtime calibration.

Current priority is to make each experiment tab work end to end in the custom UI: configuration, planning, acquisition, cancellation, preservation, loading, analysis and export. Characterization and calibration follow that functionality work. No existing result is selected as a runtime calibration. Preserve nominal electrical settings and safety limits; do not replace them with test-derived corrections.

Original measurement records remain unchanged. This standing designation governs their interpretation even when older metadata uses stronger language. There is no automatic expiration, promotion or release based on passing a test. Any future change requires an explicit operator instruction and applicable scientific evidence. Missing calibration is a stated limitation of test results, not a reason to invent parameters or remove hardware safety checks.

Current wiring uses direct detector branches: sample to HF2LI Signal 1 In (+) and PicoScope A; reference to Signal 2 In (+) and PicoScope B. MIRcat DB9 pin 2 branches to HF2LI logical DIO21 and PicoScope EXT; pin 7 is its ground reference. Both marker receivers are high impedance. DIO numbers are logical bits, not connector pin numbers. MUX development is deferred and does not block current experiment functionality.
