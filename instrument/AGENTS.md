# Runtime instrument-bundle instructions

The control application may load only bundles explicitly marked `PROMOTED` in both
the bundle registry and manifest. Creating a directory or manifest does not promote
it. Bundles contain machine-readable runtime values, validity envelopes, versions,
and source IDs; raw campaign evidence and prose decisions stay outside this tree.

Do not add hash-matching operational gates. Promotion still requires the existing
explicit user authorization phrases and scientific closeout gates. Those gates
include an accepted `procedural_writeup.md` under
`docs/phase_record_contract.md` for every source phase
material to the proposed runtime value, uncertainty, or validity envelope.
