# ACTION REQUIRED - IR Spectroscopy Control Interface

## Overview
This document tracks required information and missing parameters needed to complete the hardware control interface development.

## Phase 0 Status: ✅ COMPLETE
- ✅ Document Analysis Complete
- ✅ Project Structure Created
- ✅ Global Instructions Implemented

## Current System Status
- ✅ Backend FastAPI server running on port 8000
- ✅ Frontend React application running on port 5000
- ✅ Basic device module structure in place
- ✅ GUI analysis complete for devices with screenshots

## Missing Information Required from User

### 1. Physical Connection Details (HIGH PRIORITY)
Please provide the actual connection parameters for your system:

- **Arduino MUX Port**: Currently set to "UNKNOWN" - need actual COM port or device path
- **Quantum Composers 9524 Port**: Currently set to "COM4" - verify this is correct for your system
- **Zurich HF2LI Device ID**: Currently set to "dev####" - need actual device serial number

### 2. Hardware Driver Verification (MEDIUM PRIORITY)
Confirm the following drivers are installed and working:

- **PicoScope 5244D**: PicoSDK installed and accessible
- **Zurich HF2LI**: LabOne software and Python API installed
- **Daylight MIRcat**: MIRcat SDK properly installed (currently configured for Windows path)

### 3. System Integration Questions (MEDIUM PRIORITY)

#### Continuum Nd:YAG Laser TTL Control
- Which Quantum Composers 9524 channel(s) control the Nd:YAG laser?
- What are the required TTL pulse timing parameters?
- What is the trigger sequence for synchronized operation?

#### Sample Positioning (Arduino MUX)
- How many sample positions are available?
- What commands does the Arduino expect for positioning?
- Are there limit switches or position feedback?

### 4. Parameter Validation (LOW PRIORITY)
The following parameters in hardware_configuration.toml need verification:

#### PicoScope 5244D Parameters
- Confirm supported voltage ranges for each channel
- Verify maximum sampling rates
- Confirm trigger capabilities

#### Zurich HF2LI Parameters
- Verify frequency range limits for your specific unit
- Confirm input/output configuration
- Validate time constant ranges

#### Quantum Composers 9524 Parameters
- Provide valid ranges for `duty_cycle_on` and `duty_cycle_off` counts used in system duty cycle mode

## Next Immediate Steps

### For User:
1. **Update connection parameters** in hardware_configuration.toml with actual COM ports/device IDs
2. **Verify driver installation** on target computer with hardware
3. **Test basic connectivity** to each device using manufacturer software
4. **Provide TTL wiring details** for Nd:YAG laser control via Quantum Composers

### For Development:
1. ✅ Complete Phase 1 Part C module scaffolding for all devices with screenshots
2. ✅ Implement device control panels matching manufacturer GUIs  
3. ⏳ Live hardware testing with updated connection parameters
4. ⏳ Integration testing of synchronized measurement sequences

## Live Hardware Test Plan

Once connection parameters are provided, test each control:

### Daylight MIRcat
- [ ] Connect to device and verify status indicators
- [ ] Test wavenumber tuning in different ranges
- [ ] Verify laser mode switching (Pulsed/CW/Modulation)
- [ ] Test safety interlocks and emission controls
- [ ] Validate temperature monitoring and limits

### PicoScope 5244D  
- [ ] Initialize device and verify channel configuration
- [ ] Test data acquisition in different timebase settings
- [ ] Verify trigger functionality
- [ ] Test measurement and analysis features
- [ ] Validate data streaming and storage

### Quantum Composers 9524
- [ ] Connect and verify channel configuration
- [ ] Test pulse generation on each channel
- [ ] Verify external trigger/gate functionality  
- [ ] Test synchronized multi-channel operation
- [ ] Validate TTL output to Nd:YAG laser

### System Integration
- [ ] Test synchronized laser firing sequence
- [ ] Verify data acquisition timing with pulse generation
- [ ] Test complete pump-probe measurement cycle
- [ ] Validate emergency stop and safety systems

## References Consulted
- ✅ Device manuals in `/docs/manuals/`
- ✅ GUI screenshots in `/docs/gui_screenshots/`
- ✅ SDK documentation in `/docs/sdks/`
- ✅ GitHub repositories in `/docs/references/GITHUB_REPOSITORIES.md`

---

**Status**: Phase 0 Complete, Phase 1 Part C In Progress  
**Last Updated**: December 2024  
**Next Review**: After connection parameters provided
