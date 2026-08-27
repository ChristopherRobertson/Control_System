# MIRcat SDK Package

Thank you for using the MIRcat SDK. This package contains all the resources needed to integrate MIRcat SDK functionality
into your application.

---

## CONTENTS OF THE PACKAGE

1. **bin/**
    - `MIRcatSDK.dll` - The dynamic-link library containing the implementation of the MIRcat SDK. You need to include
      this in your application directory.

2. **dependencies/**
    - `CDM212364_Setup.exe` - Required driver installation package for USB communication. Please install this before
      using the SDK.
    - `vc_redist.x64.exe` - Microsoft Visual C++ Redistributable for Visual Studio 2015–2022. Required for running
      applications that use the MIRcat SDK.

3. **include/**
    - `MIRcatSDK.h` - The SDK's header file. Include this in your project to access the MIRcat SDK functions.

4. **lib/**
    - `MIRcatSDK.lib` - The symbol file for linking with the MIRcat SDK in your C++ project.

---

## INSTALLATION AND SETUP GUIDE

1. **Install Required Dependencies**:
    - Run `CDM212364_Setup.exe` to install the USB driver for the laser devices.
    - Run `vc_redist.x64.exe` to install the necessary runtime files for Microsoft Visual C++.

2. **Linking to the SDK**:
    - Add `MIRcatSDK.lib` from the `lib/` directory to your project's linker configuration.
    - Ensure `MIRcatSDK.dll` is placed in the same directory as your application executable or in a location on the
      system's PATH.

3. **Include the SDK Header**:
    - Include the `MIRcatSDK.h` file in your C++ source files to access the API functions.

---

We hope the MIRcat SDK meets your development needs! Should you encounter any issues,
please [contact our support team](mailto:DLS-Support@drs.com) for additional help.
