import time
from MIRcatSDKConstants import *


def ArmAndWaitForTemp(SDK, numQcls):  # Do not pass in numQcls by reference
    atTemp = c_bool(False)
    isArmed = c_bool(False)
    ret = SDK.MIRcatSDK_IsLaserArmed(byref(isArmed))
    if not isArmed.value:
        ret = SDK.MIRcatSDK_ArmDisarmLaser()
        print(" Test Result: \tret:{0}".format(ret))

        print("#****************************************************************#")
        print("Test: Is Laser Armed?")

    while not isArmed.value:
        ret = SDK.MIRcatSDK_IsLaserArmed(byref(isArmed))
        print(" Test Result: \tret:{0} \tIsArmed: {1}".format(ret, isArmed.value))
        time.sleep(1)

    # Wait until TECs are at temperature before doing any tuning/scanning
    # Note: This can take a while depending on how the laser is cooled.
    print("#****************************************************************#")
    print("Test : TEC Temperature Status")
    ret = SDK.MIRcatSDK_AreTECsAtSetTemperature(byref(atTemp))
    print(" Test Result: {0} \tatTemp = {1}".format(ret, atTemp.value))
    tecCur = c_uint16(0)
    qclTemp = c_float(0)
    while not atTemp.value:
        for i in range(1, numQcls.value + 1):
            ret = SDK.MIRcatSDK_GetQCLTemperature(c_uint8(i), byref(qclTemp))
            print(" Test Result: \tret:{0} \tQCL:{1} \tTemp: {2:.5} C".format(ret, i, qclTemp.value))
            ret = SDK.MIRcatSDK_GetTecCurrent(c_uint8(i), byref(tecCur))
            print(" Test Result: \tret:{0} \tTEC:{1} \tCurrent: {2} mA".format(ret, i, tecCur.value))

        ret = SDK.MIRcatSDK_AreTECsAtSetTemperature(byref(atTemp))
        print("TECs at Temperature: \tret:{0} \tatTemp = {1}".format(ret, atTemp.value))
        time.sleep(.1)

    return atTemp
