# Archive Inventory

This file records cleanup moves that intentionally keep generated evidence and
draft table artifacts out of the active development tree.

## 2026-06-24 Repository Cleanup

Generated acquisition outputs, command logs, and calibration outputs were moved
from active tracked paths into the ignored repository archive:

`archive/20260624_repo_cleanup/`

The archive is ignored by git through `.gitignore`, so these files are retained
locally without being synchronized to GitHub.

### Repository Paths Moved

| Original path | Archive path | Contents |
|---|---|---|
| `runs/` | `archive/20260624_repo_cleanup/runs/` | Hardware run directories and raw/summary outputs from Day 1 through Day 8 |
| `logs/` | `archive/20260624_repo_cleanup/logs/` | Hardware command logs and early completion/inventory notes |
| `calibration/` | `archive/20260624_repo_cleanup/calibration/` | Generated calibration/readback outputs, including final Day 8 timing calibration CSV/YAML |

The run archive contains these top-level run folders:

- `20260615_arduino_mux_diagnostic`
- `20260615_t660_reproducibility`
- `20260615_timing_recipe_readbacks`
- `20260616_mircat_status_tune`
- `20260616_picoscope_settings_test`
- `20260617_arduino_mux_diagnostic`
- `20260617_hf2li_60s_record`
- `20260618_arduino_mux_diagnostic`
- `20260618_day7_workflow_interface`
- `20260618_day7_workflow_interface_smoke`
- `20260618_hf2li_60s_record`
- `20260618_picoscope_settings_test`
- `20260618_timing_recipe_readbacks`
- `20260621_day8_timing_hf2li_ref_to_daq_rerun`
- `20260621_day8_timing_hf2li_ref_to_qcl`
- `20260622_day8_diag_preflight_chb_equal_cables`
- `20260622_day8_diag_t6602_chb_2ft_8ft_cables`
- `20260622_day8_diag_t6602_chb_2ft_8ft_cables_retry1`
- `20260622_day8_diag_t6602_chb_8ft_2ft_cables`
- `20260622_day8_diag_t6602_chb_equal_cables`
- `20260622_day8_diag_t6602_chc_equal_cables`
- `20260622_day8_diag_t6602_chd_equal_cables`
- `20260623_day8_timing_pump_fire_to_q_switch_t6601_equal_cables`
- `20260623_day8_timing_t6601_cha_chc_equal_cables`
- `20260623_day8_timing_t6601_trigger_to_pump_fire_splitter`
- `20260623_day8_timing_t6601_trigger_to_pump_fire_splitter_retry1`
- `20260623_day8_timing_t6601_trigger_to_pump_fire_splitter_retry2`
- `20260623_day8_timing_t6601_trigger_to_pump_fire_splitter_retry3`
- `20260624_day8_timing_t6601_cha_chd_equal_cables`
- `20260624_day8_timing_t6601_trigger_to_pump_fire_sparse_clock`

Source code, recipes, hardware configuration, hardware manuals, and UI-facing
implementation files were left in their active locations.

## 2026-06-24 RSI Article Table Cleanup

The Article 1 RSI `Tables` folder was condensed so the active folder contains
only the current consolidated Day 8 timing workbook:

`Day8_Final_Timing_Calibration_Tables_and_Corrections_20260624.xlsx`

Superseded and planning table files were moved to:

`C:\Users\Chris\Documents\UC Davis\SETI\Thesis\Article 1 - Review of Scientific Instruments\Archive\Tables_20260624_cleanup\`

### Article Table Archive Contents

`day8_superseded/`

- `Day8_T6602_ChannelSkew_and_RG316_CableDelay_Diagnostics_20260622.xlsx`
- `Day8_Timing_Calibration_Corrected_Table_20260624.csv`
- `Day8_Timing_Calibration_Table.csv`
- `Day8_Timing_Derived_Values_20260624.csv`
- `Day8_Timing_Export_Plan.md`
- `Day8_Timing_Uncertainty_Budget.csv`

`old_planning_tables/`

- `Component_Table.xlsx`
- `Day6_Placeholder_To_Evidence_Map.xlsx`
- `Figure_Data_Dependencies.xlsx`
- `Final_Claim_Table.xlsx`
- `HF2LI_Detector_Variables.xlsx`
- `Laser_Operating_Sequence.xlsx`
- `Myoglobin_CO_Experiment_Plan.xlsx`
- `Source_Data_Index.xlsx`
- `Table_Data_Dependencies.xlsx`
- `Timing_Claims_To_Measure.xlsx`

`temp_files/`

- `~$Wiring Table.xlsx`

The consolidated Day 8 thesis-style methods/results document remains in the
Article 1 RSI `Supplemental Information` folder.
