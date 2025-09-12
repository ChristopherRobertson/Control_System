# GUI Screenshots Directory

This directory is intended to contain screenshots of manufacturer GUI interfaces for each hardware device. These screenshots will be used to guide the development of Phase 1C individual device control panels.

## Expected Contents

### Device Screenshots Needed:
- **Arduino Uno R4**: Development environment or serial monitor interface
- **Continuum Surelite**: Laser control software interface
- **Daylight MIRcat**: MIRcat control software interface
- **PicoScope 5244D**: PicoScope software interface
- **Quantum Composers 9524**: Signal generator control interface
- **Zurich HF2LI**: LabOne interface for lock-in amplifier

## Usage Instructions

1. **Screenshot Collection**: Capture high-resolution screenshots of each device's native control software
2. **File Naming**: Use descriptive names like `mircat_main_interface.png`, `picoscope_timebase_settings.png`
3. **Organization**: Create subdirectories for each device if multiple screenshots are needed
4. **Analysis**: Screenshots will be analyzed to extract UI component requirements and control parameters

## Phase 1C Development

Once screenshots are provided, they will be used to:
- Extract specific control parameters and layouts
- Identify required UI components for each device
- Update hardware_configuration.toml with GUI-specific parameters
- Guide the development of manufacturer-style control panels

## Current Status

📁 **Directory Created**: Ready to receive GUI screenshots
⏳ **Awaiting**: User to provide manufacturer GUI screenshots
🎯 **Next Step**: Analyze screenshots and update configuration for Phase 1C

