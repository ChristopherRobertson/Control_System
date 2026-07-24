# P0 physical inventory

Campaign: `20260722_complete_system_recalibration_001`  
Collection status: **COLLECTED WITH DEFERRED ITEMS**  
Collection method: Operator inspection of physical labels; no device connection
or hardware query.

## PicoScope

| Field | Exact value | Source | Recorded timestamp |
|---|---|---|---|
| Model | `5244D` | Operator-reported physical label inspection | `2026-07-23T16:46:23.3554291-07:00` |
| Serial number | `10261` | Operator confirmation | `2026-07-23T16:46:58.4722918-07:00` |
| SDK identifier | `10261/0071` | Operator confirmation | `2026-07-23T16:46:58.4722918-07:00` |

## Highland Technology digital delay generators

No device was queried during P0. The printed model family is `T660`, but the
authoritative device identifiers remain `T660-1` and `T660-2`; they must not be
collapsed or interchanged because channel maps, recipes, wiring, and dependent
procedures use that distinction. Serial assignments were confirmed by the
operator from careful identification performed previously using PuTTY.

| Authoritative device identifier | Printed model family | Serial number | Source | Recorded timestamp |
|---|---|---|---|---|
| T660-1 | `T660` | `00369` | Printed model label and operator-confirmed prior PuTTY identification | `2026-07-23T16:48:20.8361527-07:00` |
| T660-2 | `T660` | `00431` | Printed model label and operator-confirmed prior PuTTY identification | `2026-07-23T16:48:20.8361527-07:00` |

## MIRcat

| Field | Exact value | Source | Recorded timestamp |
|---|---|---|---|
| Model | `MIRcat-QT-Z-2100` | Operator-confirmed physical label | `2026-07-23T16:49:11.6775518-07:00` |
| Serial number | `10524` | Operator-confirmed physical label | `2026-07-23T16:49:33.3636526-07:00` |

## Zurich Instruments lock-in

| Field | Exact value | Source | Recorded timestamp |
|---|---|---|---|
| Model | `HF2LI` | Operator-confirmed physical label | `2026-07-23T16:50:11.1513463-07:00` |
| Device ID | `dev18500` | Operator-confirmed exact displayed form; configuration stores numeric portion `18500` | `2026-07-23T16:51:11.2415596-07:00` |
| Serial number | `HF2-DEV18500` | Operator-confirmed physical label | `2026-07-23T16:52:19.6260632-07:00` |

## Nd:YAG/OPO procurement identity

The following identities are supported by the purchase quote and do not by
themselves establish the serial numbers of the installed units.

| Item | Exact purchased identity | Documentary source | Recorded timestamp |
|---|---|---|---|
| Nd:YAG laser | Amplitude Laser Inc. `Surelite EX`; Q-switched oscillator, 10 Hz, 1064 nm, optimized for OPO and Ti:Sapphire systems | Quote `US-208-2023-A4198-03`, created `2023-02-28` | `2026-07-23T16:54:38.9808197-07:00` |
| Harmonic generators | `SD-1, ST`; second Type-I and third harmonic generators | Same quote | `2026-07-23T16:54:38.9808197-07:00` |
| OPO | `Surelite OPO Plus Blue`; broadband visible and IR OPO source, 410–2500 nm, for a 355 nm pump source | Same quote | `2026-07-23T16:54:38.9808197-07:00` |
| Separation package | `SSP-2`; Surelite separation package for second or third harmonic outputs | Same quote | `2026-07-23T16:54:38.9808197-07:00` |

Document path:
`C:\Users\Chris\Documents\UC Davis\SETI\Documentation\Instruments\Lasers\Continuum Laser\f._Amplitude_quote_SLEX_OPO.pdf`

Document SHA-256:
`eaead78c8ab70bc928c7c32fcc2986fc282f44c78a5e82038230c0fb05830deb`

### Installed label identities

| Installed unit | Exact model on label | Exact serial number on label | Source | Recorded timestamp |
|---|---|---|---|---|
| Nd:YAG | `SL EX` | `24366-1` | Operator-reported physical sticker | `2026-07-23T17:00:03.7579845-07:00` |
| OPO | `SLOPO PLUS` | `24366-2` | Operator-reported physical sticker | `2026-07-23T17:00:03.7579845-07:00` |

The installed label forms are retained exactly and are associated with, but not
silently substituted for, the procurement identities `Surelite EX` and
`Surelite OPO Plus Blue`.

## Detectors

### Sample channel

Manufacturer: `VIGO Photonics`

| Label field | Exact value | Source | Recorded timestamp |
|---|---|---|---|
| TYPE | `SIP-DC-250M` | Operator-reported physical sticker | `2026-07-23T17:04:03.7313722-07:00` |
| SIP serial number | `445160800` | Operator-reported physical sticker | `2026-07-23T17:04:03.7313722-07:00` |
| DET TYPE | `PVM-10.6-1x1` | Operator-reported physical sticker | `2026-07-23T17:04:03.7313722-07:00` |
| Detector serial number | `16023` | Operator-reported physical sticker | `2026-07-23T17:04:03.7313722-07:00` |

### Reference channel replacement

Status: **IN SHIPMENT — INSTALLED IDENTITY UNRESOLVED**

The replacement is planned to be identical to the sample detector:
manufacturer `VIGO Photonics`, TYPE `SIP-DC-250M`, and DET TYPE
`PVM-10.6-1x1`. Its SIP serial number and detector serial number remain
**UNRESOLVED** until the physical labels can be inspected. Requested zero
placeholders `0000000000` and `00000` were not used because the campaign
prohibits representing unknown identifiers as zero.

This item can be deferred through S0 but blocks reference-detector identity
closure and dependent detector/optical execution phases.

## Signal-dependent PicoScope measurement assemblies

Recorded from the operator's physical-path description at
`2026-07-23T17:11:52.6832185-07:00`.

There is no single permanent PicoScope Channel A or Channel B timing cable.
Assemblies and scope-channel assignments vary with the measured signal. The
specific BNC lead, adapters, probe/breakout, and Channel A/B assignment must be
frozen and identified for each later measurement setup.

### Digital delay generator signals

Path:

`DDG SMB output` → `12-inch SMB-to-BNC bulkhead cable/connector assembly` →
`BNC cable of setup-dependent length` → `PicoScope Channel A or Channel B`

All DDG SMB-to-BNC bulkhead cable assemblies are reported as 12 inches. BNC
cable lengths vary.

The fixed 12-inch assemblies are identified by their installed route labels,
which state what each route connects to. They are never disconnected from the
DDG or bulkhead and do not require additional serial-style tags. During an
experiment or calibration rewire, only the destination end of the downstream
BNC cable is disconnected from its normal destination and moved to PicoScope
Channel A or Channel B. This handling rule was recorded from the operator at
`2026-07-23T17:14:23.9534544-07:00`.

Reported installed downstream BNC cable lengths are recorded below. The timing
procedure now preserves every fixed 12-inch assembly, moves only the applicable
downstream BNC connection, and requires exact restoration of the CLOCK splitter
before clock-dependent recipes.

### Splitter topology clarification

Recorded from the operator at `2026-07-23T17:16:37.7063678-07:00`:

- The only splitter in the installed normal wiring is connected to the
  `T660-2 CLOCK` output and feeds the `T660-1` and `HF2LI` clock inputs.
- In legacy measurements, this same splitter was temporarily repurposed so
  T660-2 `CH D` could simultaneously feed T660-1 `TRIG IN` and PicoScope
  Channel A.
- That legacy CH D splitter configuration is not installed and must not be
  represented as current wiring or copied forward as calibration evidence.

Operator decision recorded at `2026-07-23T17:17:53.5645478-07:00`:

- The installed CLOCK splitter may be removed temporarily and used for bounded
  calibration setups.
- It must be restored to the T660-2 CLOCK distribution feeding T660-1 and
  HF2LI before any later timing recipe that requires synchronized clocks.
- Restoration and visual verification must be included in the applicable
  connection table and safe-idle-controlled rewire sequence.

Splitter availability is therefore resolved. The campaign procedure still
requires connection-text corrections so temporary calibration uses the fixed
SMB-to-bulkhead topology and explicitly restores CLOCK distribution before
clock-dependent recipes.

Splitter manufacturer, model, part number, and serial markings: **UNMARKED**  
Campaign-local identifier: `CLOCK-SPLITTER-01`  
Source: Operator inspection  
Recorded: `2026-07-23T17:18:20.6685967-07:00`

`CLOCK-SPLITTER-01` is an administrative identity only. It does not establish
manufacturer, bandwidth, insertion loss, branch symmetry, or calibration.
Those characteristics remain unresolved and must be bounded by measurement or
authoritative documentation before dependent claims.

Measured impedance: `50 Ω`  
Source: Operator-reported prior measurement; instrument, method, and date **UNRESOLVED**  
Available impedance uncertainty: **UNRESOLVED**  
Operator clarification recorded: `2026-07-23T17:19:52.3787051-07:00`

Physical connector arrangement: `one BNC input to three BNC outputs`  
Source: Operator inspection  
Corrected: `2026-07-23T17:19:52.3787051-07:00`

### Installed downstream cable lengths

Source: Operator report  
Recorded: `2026-07-24T11:08:01.2374815-07:00`  
Available length uncertainty: **UNRESOLVED**

| Installed path | Reported physical length |
|---|---:|
| T660-2 CH A bulkhead → HF2LI DIO0/EXT REF | `1 ft` |
| T660-2 CH B bulkhead → MIRcat TRIG IN | `9 ft` |
| T660-2 CH C bulkhead → HF2LI DIO1/DAQ trigger | `1 ft` |
| T660-2 CH D bulkhead → T660-1 TRIG IN | `1.5 ft` |
| `CLOCK-SPLITTER-01` → T660-1 CLOCK | `1.5 ft` |
| `CLOCK-SPLITTER-01` → HF2LI CLOCK | `1.5 ft` |
| T660-1 CH C bulkhead → MIRcat process-trigger breakout path | `2 ft` |
| Sample detector output → HF2LI Sample input | `40 in` |
| Reference detector output → HF2LI Reference input | `40 in` |

Physical length does not substitute for measured propagation delay, branch
skew, connector delay, or uncertainty.

The sample-detector cable is also the optical-timing detector-to-PicoScope
cable. It is temporarily disconnected from the HF2LI Sample input and moved to
the PicoScope under the applicable safe-idle and rewire gate; no separate
detector-to-PicoScope cable is used.

Campaign-local identifier: `SAMPLE-DETECTOR-OUT-01`  
Length: `40 in`  
Source: Operator confirmation  
Recorded: `2026-07-24T11:08:47.1962787-07:00`

Reference-channel campaign-local cable identifier:
`REFERENCE-DETECTOR-OUT-01`  
Length: `40 in`  
The replacement detector identity remains unresolved until arrival.

### Installed but inactive MUX-related cables

The following cables are physically present but are not permitted calibration
paths. The Arduino MUX remains disabled and excluded; calibration uses direct
wiring only.

| Inactive installed path | Reported physical length |
|---|---:|
| MIRcat TRIG OUT → MUX back panel | `8.5 ft` |
| HF2LI AUX 1 → MUX back panel | `28 in` |
| HF2LI AUX 2 → MUX back panel | `28 in` |
| HF2LI AUX 3 → MUX back panel | `28 in` |
| HF2LI AUX 4 → MUX back panel | `28 in` |
| MUX A → PicoScope CH A | `2.5 ft` |
| MUX B → PicoScope CH B | `2.5 ft` |

Source: Operator report  
Recorded: `2026-07-24T11:08:01.2374815-07:00`

### Electrical attenuators

No standalone electrical attenuators are used between the T660/DB9 timing
signals and the PicoScope.

Source: Operator confirmation  
Recorded: `2026-07-23T17:21:02.6058667-07:00`

This statement does not cover optical attenuation, which remains to be
inventoried separately.

### Additional electrical adapters and terminators

No standalone BNC adapters, standalone terminators, or T-connectors are used
beyond the already described fixed bulkheads and two-wire-probe-to-BNC
connector.

Source: Operator confirmation  
Recorded: `2026-07-23T17:21:29.1637295-07:00`

PicoScope input termination is an instrument configuration setting and is not
counted here as a standalone accessory.

### Optical attenuation

No optical attenuator, neutral-density filter, or other attenuation element is
currently used between the Nd:YAG/OPO output and either detector.

Source: Operator confirmation  
Recorded: `2026-07-23T17:21:58.4584821-07:00`

Any attenuation element introduced later for preview, saturation control, or
measurement must be separately identified and reviewed before use.

## Spectral-reference materials and later samples

Recorded from the operator at `2026-07-23T17:22:57.3007037-07:00`.

Available spectral-reference materials:

- `Polystyrene`
- `Mylar`

Detailed identities and available markings are recorded below. Neither
material includes a supplied certificate, authoritative peak list, or stated
spectral uncertainty.

### Polystyrene reference identity

| Field | Exact value | Source | Recorded timestamp |
|---|---|---|---|
| Form | `FT-IR Spectroscopy card insert` | Operator-reported physical item/packaging | `2026-07-23T17:24:06.6955103-07:00` |
| Manufacturer | `PerkinElmer` | Operator-reported physical item/packaging | `2026-07-23T17:24:06.6955103-07:00` |
| PART No. | `L120 2057` | Operator-reported physical item/packaging | `2026-07-23T17:24:06.6955103-07:00` |
| Lot/batch/serial marking | `none present` | Operator inspection of card/packaging | `2026-07-23T17:24:45.7914703-07:00` |
| Thickness/path length marking | `none present` | Operator inspection of card/packaging | `2026-07-23T17:25:40.9494972-07:00` |
| Supplied certificate | `none` | Operator inspection | `2026-07-23T17:25:59.2551163-07:00` |
| Supplied reference peak list | `none` | Operator inspection | `2026-07-23T17:25:59.2551163-07:00` |
| Stated wavenumber uncertainty | `none` | Operator inspection | `2026-07-23T17:25:59.2551163-07:00` |

The missing thickness/path length limits quantitative absorbance and
path-length claims but does not by itself prevent spectral feature-position
checks.

Without a certificate, supplied peak list, or stated uncertainty, this item may
support non-traceable feature comparison but does not independently support a
traceable absolute-wavenumber claim.

### Mylar reference identity

| Field | Exact value | Source | Recorded timestamp |
|---|---|---|---|
| Manufacturer | `SPEX SamplePrep` | Operator-reported physical item/packaging | `2026-07-23T17:27:10.3678981-07:00` |
| Product/use description | `Thin film for XRF` | Operator-reported physical item/packaging | `2026-07-23T17:27:10.3678981-07:00` |
| Product marking | `3517 MYLAR` | Operator-reported physical item/packaging | `2026-07-23T17:27:10.3678981-07:00` |
| Stated thickness | `0.25 mil (6 µm)` | Operator-reported physical item/packaging; operator entered `6um` | `2026-07-23T17:27:10.3678981-07:00` |
| Lot/batch/serial marking | `none present` | Operator inspection of packaging | `2026-07-23T17:27:39.8606211-07:00` |
| Thickness tolerance/uncertainty | `none supplied` | Operator inspection of packaging | `2026-07-23T17:28:02.2134477-07:00` |
| Supplied certificate | `none` | Operator inspection | `2026-07-23T17:28:02.2134477-07:00` |
| Supplied reference peak list | `none` | Operator inspection | `2026-07-23T17:28:02.2134477-07:00` |
| Stated spectral uncertainty | `none` | Operator inspection | `2026-07-23T17:28:02.2134477-07:00` |

The Mylar film may support non-traceable comparison using its nominal identity
and thickness, but it does not independently support a traceable absolute
spectral claim.

## Environmental instrument

| Field | Exact value | Source | Recorded timestamp |
|---|---|---|---|
| Manufacturer | `Freshliance` | Operator-reported physical label | `2026-07-23T17:30:55.7504999-07:00` |
| Product name | `TagPlus-TN` | Operator-reported physical label | `2026-07-23T17:30:55.7504999-07:00` |
| Product number | `250105084H` | Operator-reported physical label | `2026-07-23T17:30:55.7504999-07:00` |
| Function | `Thermometer and Hygrometer` | Operator report | `2026-07-23T17:30:55.7504999-07:00` |
| Displayed temperature | `26.3 °C` | Operator-reported current display reading | `2026-07-23T17:30:55.7504999-07:00` |
| Displayed relative humidity | `44.9 %RH` | Operator-reported current display reading | `2026-07-23T17:30:55.7504999-07:00` |
| Calibration/certificate status | `none` | Operator confirmation | `2026-07-23T17:31:35.8968374-07:00` |
| Temperature uncertainty | **UNRESOLVED** | Pending documentation | — |
| Relative-humidity uncertainty | **UNRESOLVED** | Pending documentation | — |

The displayed values are a timestamped environmental observation, not a claim
of calibrated accuracy. Without a calibration certificate, the instrument may
document ambient conditions but does not support traceable temperature or
relative-humidity claims.

## Operator

Operator name: `Christopher Robertson`  
Source: Operator entry  
Recorded: `2026-07-23T17:32:07.5742513-07:00`

## Calibration certificates and traceability records

### PicoScope 5244D, serial 10261

Certificate availability: `yes`  
Certificate identifier: **UNRESOLVED — document not currently available**  
Issuing organization: **UNRESOLVED**  
Calibration date: **UNRESOLVED**  
Expiration/recalibration date: **UNRESOLVED**  
Applicable uncertainty: **UNRESOLVED**  
Source: Operator confirmation  
Recorded: `2026-07-23T17:32:57.0544814-07:00`

The missing certificate metadata does not block S0. It limits traceability and
must be retrieved before final PicoScope uncertainty and traceability claims.

### Other reported available certificates

The operator reports that calibration certificates or corresponding equipment
records exist for the following equipment, but the documents are not currently
on hand:

- T660-1, serial `00369`
- T660-2, serial `00431`
- MIRcat, serial `10524`
- Nd:YAG `SL EX`, serial `24366-1`
- OPO `SLOPO PLUS`, serial `24366-2`
- Detector equipment
- HF2LI, device ID `dev18500`, serial `HF2-DEV18500`

For every listed record, certificate identifier, issuing organization,
calibration date, expiration/recalibration date, applicable uncertainty, and
exact equipment association remain **UNRESOLVED**.

Source: Operator confirmation  
Recorded: `2026-07-23T17:33:48.2916043-07:00`; HF2LI availability added
`2026-07-23T17:34:24.7787551-07:00`

Certificate existence alone is not treated as traceability. These documents do
not block S0 but must be inventoried before the associated final uncertainty or
traceability claims.

Later full-photolysis experimental samples:

- `Myoglobin-CO`
- `Horseradish Peroxidase`

The two biological samples are not classified as calibration standards. They
will be used later in full photolysis experiments and cannot establish
traceable spectral accuracy without separate supporting evidence.

### MIRcat DB9-board signals

Path:

`straight-through RS232/DB9 cable terminated at the board` → `approximately
6 inches of electrical wire` → `BNC bulkhead connector` → `BNC cable of
setup-dependent length` → `PicoScope Channel A or Channel B`

The exact DB9 cable, breakout/bulkhead, wire, and BNC cable identifiers remain
**UNRESOLVED**.

MIRcat breakout description: `generic DB9-to-RS232 board`  
Campaign-local identifier: `MIRCAT-DB9-BOARD-01`  
Manufacturer/model/part number: **not provided / unresolved**  
Source: Operator description  
Recorded: `2026-07-23T17:36:05.4232640-07:00`

Straight-through DB9 cable description: `generic`  
Campaign-local identifier: `MIRCAT-DB9-CABLE-01`  
Manufacturer/model/part number: **not provided / unresolved**  
Length: `3 m`  
Source: Operator description  
Recorded: `2026-07-24T10:50:46.2169143-07:00`; length added
`2026-07-24T10:53:01.4283027-07:00`

“RS232” identifies the physical connector/breakout format only. Electrical pin
functions and levels remain governed by the Daylight DB9 documentation; the
board must not be treated as converting those signals to generic RS-232
electrical levels.

### Nd:YAG DB9 signals

The installed signal cable was described as an RS232-to-BNC cable. For
PicoScope measurement, a two-wire-probe-to-BNC connector can be attached to the
corresponding pins at the DB9 end and routed to PicoScope Channel A or Channel
B.

Here, “RS232” records the operator's physical cable/connector description only.
The Surelite DB9 fire-command pin 7 and Q-switch-command pin 6 are TTL-level
signals and must never be treated or driven as RS-232 electrical-level signals.
Installed cable description: unmarked DB9/RS232-to-BNC signal cable supplied
with the laser/OPO system  
Campaign-local identifier: `NDYAG-DB9-BNC-01`  
Manufacturer part number/serial marking: `none present`  
Source: Operator description and inspection  
Recorded: `2026-07-23T17:38:08.9840491-07:00`

Construction: wired as instructed in the laser manual, with two equal-length
branches  
Branch length: `13.25 ft` each  
Length source: Operator report  
Recorded: `2026-07-24T10:49:35.8006300-07:00`

The applicable manual revision, length measurement method, and length
uncertainty remain unresolved. Equal reported physical length does not
substitute for the planned electrical branch-skew measurement.

Physical branch labels:

- `FIRE` — repository/manual wiring contract assigns DB9 pin 7
- `Q-SWITCH` — repository/manual wiring contract assigns DB9 pin 6

Source: Operator confirmation  
Recorded: `2026-07-24T10:50:13.8979163-07:00`

Two-wire-probe-to-BNC connector description: `generic`  
Campaign-local identifier: `NDYAG-2WIRE-BNC-01`  
Manufacturer/model/part number: **not provided / unresolved**  
Source: Operator description  
Recorded: `2026-07-23T17:37:05.5116756-07:00`

## Remaining inventory

The following items remain explicitly unresolved or deferred:

- Replacement reference-detector SIP and detector serial numbers, pending
  arrival.
- Certificate identifiers, issuers, calibration/recalibration dates,
  uncertainties, and exact equipment associations for reported available
  certificates.
- T660 firmware versions, deferred to safe readback after the S0 ownership and
  safe-idle gate.
- Manufacturer specifications or measured uncertainty for unmarked/generic
  splitter, breakout, probe, and cable assemblies.
- Cable-length measurement uncertainty and all electrical propagation-delay
  terms; later phases must measure these rather than infer them from length.
- Traceable peak authorities and uncertainty for the polystyrene and Mylar
  references.
- Traceable temperature and humidity uncertainty.
- Exact per-setup connection text for the fixed SMB-to-bulkhead topology,
  including CLOCK splitter restoration, before MS-01.

No unresolved value is represented as zero. These items are classified in the
separate P0 blocker table by affected phase and deferral status.
