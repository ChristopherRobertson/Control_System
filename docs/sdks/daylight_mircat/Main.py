import os
import time
from MIRcatSDKConstants import *
from MIRcatSDKHelpers import ArmAndWaitForTemp

os.chdir("../libs/x64") # Change the working directory to reference libraries based on version of python x32 or x64
SDK = CDLL("MIRcatSDK")


# Get MIRcat API Version
major = c_uint16()
minor = c_uint16()
patch = c_uint16()

print("Test: Get API Version")
ret = SDK.MIRcatSDK_GetAPIVersion(byref(major), byref(minor), byref(patch))
print(" Result: {0} \tVersion: {1}.{2}.{3}".format(ret, major.value, minor.value, patch.value))


# Initialize MIRcatSDK & Connect to MIRcat laser
print("Test: Initialize MIRcatSDK")
ret = SDK.MIRcatSDK_Initialize()
if ret == MIRcatSDK_RET_SUCCESS.value:
    print(" Successfully Connected to MIRcat")
else:
    print(" Failure to Initialize API. \tError Code: {0}".format(ret))
    exit(0)

isInterlockSet = c_bool(False)
isKeySwitchSet = c_bool(False)
numQCLs = c_uint8(0)

# Step 1: Get the number of installed QCLs
print("#****************************************************************#")
print("Test: How many QCLs?")
SDK.MIRcatSDK_GetNumInstalledQcls(byref(numQCLs))
print(" QCLs: {0}".format(numQCLs.value))


# Step 2: Check for Interlock Status
print("#****************************************************************#")
print("Test: Is Interlock Set?")
ret = SDK.MIRcatSDK_IsInterlockedStatusSet(byref(isInterlockSet))
if isInterlockSet.value:
    print(" Interlock Set: {0}".format(isInterlockSet.value))
else:
    print(" Interlock Set: {0} \tret:{0}".format(isInterlockSet.value, ret))
    exit(0)

# Step 3: Check for Key Switch Status
print("#****************************************************************#")
print("Test: Is Key Switch Set?")
ret = SDK.MIRcatSDK_IsKeySwitchStatusSet(byref(isKeySwitchSet))
if isKeySwitchSet.value:
    print(" KeySwitch Set: {0}".format(isKeySwitchSet.value))
else:
    print(" KeySwitch Set: {0} \tret:{1}".format(isKeySwitchSet.value, ret))
    exit(0)

# Step 4: Arm the laser
print("#****************************************************************#")
print("Test: Arm Laser")
ArmAndWaitForTemp(SDK, numQCLs)


# Single Tune Test
print("#****************************************************************#")
print("Staring single tune test\n")
print("Test: Tune to WW 8.80")
ret = SDK.MIRcatSDK_TuneToWW(c_float(8.835), MIRcatSDK_UNITS_MICRONS, c_uint8(1))
print(" Test Result: \tret:{0}".format(ret))

print("#****************************************************************#")
print("Test: Check Tuned Wavelength")
tunedWW = c_float()
units = c_uint8()
QCL = c_uint8()
ret = SDK.MIRcatSDK_GetTuneWW(byref(tunedWW), byref(units), byref(QCL))
print(" Test Results:\tret:{0} \tWavelength: {1:.5} \tUnits: {2} \tQCL:{3}".format(ret, tunedWW.value, units.value, QCL.value))

print("#****************************************************************#")
print("Test: Is Tuned?")
isTuned = c_bool(False)
actualWW = c_float()
lightValid = c_bool()
while not isTuned.value:
    """"Check Tuning Status"""
    ret = SDK.MIRcatSDK_IsTuned(byref(isTuned))
    print(" Test Result:\tret:{0} \tisTuned: {1}".format(ret, isTuned.value))
    """Check Actual Wavelength"""
    ret = SDK.MIRcatSDK_GetActualWW(byref(actualWW), byref(units), byref(lightValid))
    print(" Test Result:\tret:{0} \tActual WW: {1:.5} \tUnits:{2} \tLight Valid: {3}".format(ret, actualWW.value, units.value, lightValid.value))
    time.sleep(0.05)

print("#****************************************************************#")
print("Test: Enable Laser Emission")
ret = SDK.MIRcatSDK_TurnEmissionOn()
print(" Test Result: ret:{0}".format(ret))

print("#****************************************************************#")
print("Test : Is laser emitting?")
isEmitting = c_bool(False)
while not isEmitting.value:
    ret = SDK.MIRcatSDK_IsEmissionOn(byref(isEmitting))
    print(" Test Result:\tret:{0} \tIs Emitting: {1}".format(ret, isEmitting.value))
    time.sleep(0.5)

print("#****************************************************************#")
print("Test: Disable Laser")
ret = SDK.MIRcatSDK_TurnEmissionOff()
print(" Test Result:\tret:{0}".format(ret))

print("#****************************************************************#")
print("Test : Is laser emitting?")
ret = SDK.MIRcatSDK_IsEmissionOn(byref(isEmitting))
print(" Test Result:\tret:{0} \tIs Emitting: {1}".format(ret, isEmitting.value))

print("#****************************************************************#")
print("Test: Cancel Manual Scan Mode")
ret = SDK.MIRcatSDK_CancelManualTuneMode()
print(" Test Result:\tret:{0}".format(ret))


# Sweep Scan
print("#****************************************************************#")
# Step 5: Start Sweep Scan
print("Starting Sweep mode scan from 6.7 to 7.2 um with a speed 100 microns")
ret = SDK.MIRcatSDK_StartSweepScan(c_float(6.7), c_float(7.2), c_float(.1), MIRcatSDK_UNITS_MICRONS, c_uint16(1), c_bool(True), c_uint8(1))
print(" Test Result:\tret:{0}".format(ret))
if ret == MIRcatSDK_RET_SUCCESS.value:
    isScanInProgress = c_bool(True)
    isScanActive = c_bool(False)
    isScanPaused = c_bool(False)
    curScanNum = c_uint16()
    curScanPercent = c_uint16()
    curWW = c_float()
    isTECinProgress = c_bool()
    isMotionInProgress = c_bool()
    print("#****************************************************************#")

    while isScanInProgress.value:
        print("Test: Get Scan Status")
        ret = SDK.MIRcatSDK_GetScanStatus( byref(isScanInProgress), byref(isScanActive), byref(isScanPaused),
                                       byref(curScanNum), byref(curScanPercent), byref(curWW),
                                       byref(units), byref(isTECinProgress), byref(isMotionInProgress))
        print(" Test Result:\tisScanInProgress = {} \tisScanActive = {} \tbisScanPaused = {} \tCurScanNum = {}"
              .format(isScanInProgress.value, isScanActive.value, isScanPaused.value, curScanNum.value))
        print(" Test Result:\tCurrentWW= {0:.3} \tUnits = {1} \tCurrentScanPercent = {2} \tisTECInProgress = {3} \tisMotionInProgress = {4}"
              .format(curWW.value, units.value, curScanPercent.value, isTECinProgress.value, isMotionInProgress.value))
        ret = SDK.MIRcatSDK_GetActualWW(byref(actualWW), byref(units), byref(lightValid))
        print(" Test Result:\tActual WW: {:.3} \tValid: {}\n"
              .format(actualWW.value, lightValid.value))
        time.sleep(0.3)


# Step-Measure Scan
print("#****************************************************************#")
print("Starting Step-Measure Scan")
ret = SDK.MIRcatSDK_StartStepMeasureModeScan(c_float(6.7), c_float(7.0), c_float(0.25), MIRcatSDK_UNITS_MICRONS, c_uint8(1))
print(" Test Result:\tret:{}".format(ret))
time.sleep(0.1)
if ret == MIRcatSDK_RET_SUCCESS.value:
    isScanInProgress = c_bool(True)
    print("#****************************************************************#")
    while isScanInProgress.value:
        print("Test: Get Scan Status")
        ret = SDK.MIRcatSDK_GetScanStatus(byref(isScanInProgress), byref(isScanActive), byref(isScanPaused),
                                          byref(curScanNum), byref(curScanPercent), byref(curWW),
                                          byref(units), byref(isTECinProgress), byref(isMotionInProgress))
        print(" Test Result:\tisScanInProgress = {} \tisScanActive = {} \tbisScanPaused = {} \tCurScanNum = {}"
              .format(isScanInProgress.value, isScanActive.value, isScanPaused.value, curScanNum.value))
        print(
            " Test Result:\tCurrentWW= {0:.3} \tUnits = {1} \tCurrentScanPercent = {2} \tisTECInProgress = {3} \tisMotionInProgress = {4}"
            .format(curWW.value, units.value, curScanPercent.value, isTECinProgress.value, isMotionInProgress.value))
        ret = SDK.MIRcatSDK_GetActualWW(byref(actualWW), byref(units), byref(lightValid))
        print(" Test Result:\tActual WW: {:.3} \tValid: {}\n"
              .format(actualWW.value, lightValid.value))
        time.sleep(0.3)


# Multi-Spectral Scan
print("#****************************************************************#")
print("Starting Multi-Spectral Scan\n\n")
# Step 5: Set the amount of Multi-Spectral Elements
print("Test: SetNumMultiSpectralElements")
SDK.MIRcatSDK_SetNumMultiSpectralElements(10)
print(" Test Result:\tret:{0}".format(ret))
# Step 6: Add Multi-Spectral Elements
fScanWW = 5.7
i = 0.0
while i < 5.0: # Python does not easily support for-loops with floats
    print("Test : AddMultiSpectralElement")
    ret = SDK.MIRcatSDK_AddMultiSpectralElement(c_float(fScanWW + i), MIRcatSDK_UNITS_MICRONS, c_uint32(1000), c_uint32(1000))
    print(" Test Result:\tret:{0}".format(ret))
    i += 0.5
print("#****************************************************************#")
print("Test: StartMultiSpectralModeScan")
# Step 7: Start the Multi-Spectral Scan
ret = SDK.MIRcatSDK_StartMultiSpectralModeScan(c_uint16(1))
print(" Test Result:\tret:{0}".format(ret))
if ret == MIRcatSDK_RET_SUCCESS.value:
    isScanInProgress = c_bool(True)
    print("#****************************************************************#")
    while isScanInProgress.value:
        print("Test: Get Scan Status")
        ret = SDK.MIRcatSDK_GetScanStatus(byref(isScanInProgress), byref(isScanActive), byref(isScanPaused),
                                          byref(curScanNum), byref(curScanPercent), byref(curWW),
                                          byref(units), byref(isTECinProgress), byref(isMotionInProgress))
        print(" Test Result:\tisScanInProgress = {} \tisScanActive = {} \tbisScanPaused = {} \tCurScanNum = {}"
              .format(isScanInProgress.value, isScanActive.value, isScanPaused.value, curScanNum.value))
        print(
            " Test Result:\tCurrentWW= {0:.3} \tUnits = {1} \tCurrentScanPercent = {2} \tisTECInProgress = {3} \tisMotionInProgress = {4}"
            .format(curWW.value, units.value, curScanPercent.value, isTECinProgress.value, isMotionInProgress.value))
        ret = SDK.MIRcatSDK_GetActualWW(byref(actualWW), byref(units), byref(lightValid))
        print(" Test Result:\tActual WW: {:.3} \tValid: {}\n"
              .format(actualWW.value, lightValid.value))
        time.sleep(0.3)


# Disarm Laser
print("#****************************************************************#")
print("Attempting to Disarm Laser...")
ret = SDK.MIRcatSDK_DisarmLaser()
print(" Test Result: {0}".format(ret))


# Check Arming Status
print("#****************************************************************#")
print("Test: Is Laser Armed?")
isArmed = c_bool(True)
ret = SDK.MIRcatSDK_IsLaserArmed(byref(isArmed))
print(" Test Result: {0} \tIs Armed: {1}".format(ret, isArmed.value))


# Disconnect from MIRcat
print("#****************************************************************#")
print("Attempting to De-Initialize MIRcatSDK...")
ret = SDK.MIRcatSDK_DeInitialize()
print(" Test Result: {0}".format(ret))
