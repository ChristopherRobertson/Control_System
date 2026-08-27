# Campaign planning instructions

`registry/phase_registry.yaml` is the sole prospective phase/dependency authority.
Detailed plans define methods but must not maintain a competing execution order.
Creating or editing a plan never authorizes hardware or changes phase status.

Completed evidence remains at the path in `registry/evidence_locations.yaml` and is
linked by stable IDs. Never copy it into a new phase as a new acquisition. Unknown
numeric inputs remain `USER_INPUT_REQUIRED` until prospectively frozen.
