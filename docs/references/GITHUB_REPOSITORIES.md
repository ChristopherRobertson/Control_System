# GitHub Repository References

This document contains essential GitHub repositories that serve as references for developing the IR Pump-Probe Spectroscopy Control Interface. These repositories provide examples, SDKs, and best practices for integrating with the hardware components.

## PicoScope / Pico Technology

### picosdk-python-wrappers
- **URL**: https://github.com/picotech/picosdk-python-wrappers
- **Purpose**: Official Python wrappers for PicoSDK
- **Relevance**: Essential for PicoScope 5244D integration
- **Key Features**:
  - Python bindings for all PicoScope models
  - Example code for data acquisition
  - Streaming and block mode examples
  - Trigger configuration examples

**Usage Notes**:
- Use as primary reference for PicoScope 5244D module development
- Contains examples for oscilloscope functionality we need
- Provides proper error handling patterns
- Shows best practices for data acquisition

## Zurich Instruments

### zhinst-toolkit
- **URL**: https://github.com/zhinst/zhinst-toolkit
- **Purpose**: High-level Python toolkit for Zurich Instruments devices
- **Relevance**: Primary toolkit for HF2LI lock-in amplifier
- **Key Features**:
  - Device-specific high-level interfaces
  - Automated measurement routines
  - Data acquisition and processing tools
  - Configuration management

### zhinst-meta
- **URL**: https://github.com/zhinst/zhinst-meta
- **Purpose**: Meta-package for Zurich Instruments Python ecosystem
- **Relevance**: Package management and dependencies
- **Key Features**:
  - Unified installation of all ZI Python packages
  - Version compatibility management
  - Documentation and examples

### labone-api-examples
- **URL**: https://github.com/zhinst/labone-api-examples
- **Purpose**: Example code for LabOne API usage
- **Relevance**: Direct examples for HF2LI programming
- **Key Features**:
  - Lock-in amplifier examples
  - Data acquisition patterns
  - Real-time measurement examples
  - Best practices for API usage

### zhinst-utils
- **URL**: https://github.com/zhinst/zhinst-utils
- **Purpose**: Utility functions for Zurich Instruments devices
- **Relevance**: Helper functions and common patterns
- **Key Features**:
  - Data processing utilities
  - Configuration helpers
  - Common measurement patterns
  - Error handling utilities

### labone-python
- **URL**: https://github.com/zhinst/labone-python
- **Purpose**: Core Python API for LabOne
- **Relevance**: Low-level API for HF2LI control
- **Key Features**:
  - Direct device communication
  - Low-level parameter access
  - Streaming data acquisition
  - Event handling

**Usage Notes**:
- Use `zhinst-toolkit` as primary interface for HF2LI module
- Reference `labone-api-examples` for specific measurement patterns
- Use `labone-python` for low-level operations if needed
- Follow patterns from `zhinst-utils` for data processing

## Development Guidelines

### Integration Strategy

1. **PicoScope Integration**:
   - Clone `picosdk-python-wrappers` for reference
   - Use their Python wrapper patterns
   - Adapt their examples for our specific use case
   - Follow their error handling conventions

2. **Zurich Instruments Integration**:
   - Install `zhinst-toolkit` as primary dependency
   - Reference `labone-api-examples` for implementation patterns
   - Use `zhinst-utils` for common operations
   - Follow their high-level API approach

### Best Practices

1. **Code Organization**:
   - Study how these repositories structure their code
   - Follow their naming conventions
   - Adopt their documentation patterns
   - Use similar error handling approaches

2. **Testing Patterns**:
   - Reference their test structures
   - Adopt their mocking strategies for hardware
   - Use their validation approaches
   - Follow their CI/CD patterns

3. **Documentation**:
   - Study their README structures
   - Follow their API documentation style
   - Use their example code patterns
   - Adopt their troubleshooting approaches

### Repository Cloning Commands

For development reference, clone these repositories locally:

```bash
# PicoScope
git clone https://github.com/picotech/picosdk-python-wrappers.git

# Zurich Instruments
git clone https://github.com/zhinst/zhinst-toolkit.git
git clone https://github.com/zhinst/zhinst-meta.git
git clone https://github.com/zhinst/labone-api-examples.git
git clone https://github.com/zhinst/zhinst-utils.git
git clone https://github.com/zhinst/labone-python.git
```

### Version Compatibility

- **PicoSDK**: Use latest stable version compatible with Python 3.11+
- **Zurich Instruments**: Use zhinst-toolkit 0.6+ for latest features
- **Python**: Ensure compatibility with Python 3.11+ as used in our project

### License Considerations

- **PicoSDK**: Check license terms for commercial use
- **Zurich Instruments**: MIT licensed, suitable for our project
- **Attribution**: Provide proper attribution in our documentation

---

**Last Updated**: August 2025  
**Maintained By**: IR Spectroscopy Control Interface Development Team  
**Review Schedule**: Update when new versions are released

