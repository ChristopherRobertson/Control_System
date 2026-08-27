//@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
// MIRcatSDK.h
//
// Copyright © 2025 Daylight Solutions, Inc.
//
// DRS Daylight Solutions
// 16465 Via Esprillo
// San Diego, CA 92127
//
// For support and technical questions, contact Daylight Solutions
// Email: dls-support@drs.com
// Phone: +1 858-362-8971
// Website: daylightsolutions.com
//@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

#ifndef _MIRcatSDK_H_
#define _MIRcatSDK_H_
#include <stdint.h>

#ifndef MIRCAT_LIB
#ifdef MIRCAT_SDK_STATIC
#define MIRCAT_LIB
#elif defined(WIN32_EXPORT)
#define MIRCAT_LIB __declspec(dllexport)
#elif defined(__linux__)
#define MIRCAT_LIB
#else
#define MIRCAT_LIB __declspec(dllimport)
#endif
#endif

/**
 * @defgroup Constants Constants
 * @brief Constants used throughout the SDK.
 * @{
 */

/**
 * @defgroup DeviceHandle Device Handle
 * @brief Functions and types for managing MIRcat device handles
 *
 * This group contains functions and type definitions for working with MIRcat device handles.
 * Device handles are used to identify and communicate with connected MIRcat laser devices.
 *
 * @{
 */

/**
 * @typedef DLS_SCI_DEVICE_HANDLE
 * @brief The device handle type for use with all functions that communicate with a connected device.
 *
 * This type represents a unique identifier for a MIRcat device. It is used by all
 * functions that need to specify which device to communicate with.
 */
typedef unsigned int DLS_SCI_DEVICE_HANDLE;

/**
 * @def DLS_SCI_DEVICE_NULL_HANDLE
 * @brief The null value for DLS_SCI_DEVICE_HANDLE.
 *
 * This constant represents an invalid or null device handle. A connected device
 * should never have this value. Use this to initialize handle variables or
 * check for invalid handles.
 */
#define DLS_SCI_DEVICE_NULL_HANDLE                      (0x0)

/** @} */ // end of DeviceHandle group

//-----------------------------------------------------------//
//                RETURN CODE CONSTANTS                      //
//-----------------------------------------------------------//

/**
 * @defgroup ReturnCodes Return Codes
 * @brief Codes that are returned by functions.
 * @{
 */

/**
 * @brief Success return code.
 * @details Compare return value from function with this value to check for success.
 */
#define MIRcatSDK_RET_SUCCESS                           ((uint32_t)0)

/**
 * @defgroup CommunicationAndTransportErrors Communication and Transport Errors
 * @brief Errors occurring during communication and transport.
 * @{
 */

/** @brief If the user-specified `commType` is invalid. */
#define MIRcatSDK_RET_UNSUPPORTED_TRANSPORT             ((uint32_t)1)

/** @} End of CommunicationAndTransportErrors */

/**
 * @defgroup InitializationErrors Initialization Errors
 * @brief Errors occurring while initializing MIRcat systems.
 * @{
 */

/** @brief If no system found was found. */
#define MIRcatSDK_RET_NO_SYSTEM_FOUND                   ((uint32_t)30)
/** @brief If MIRcat controller initialization failed. */
#define MIRcatSDK_RET_INITIALIZATION_FAILURE            ((uint32_t)32)

/** @} End of InitializationErrors*/

/**
 * @defgroup UserReturnErrorCodes User Error Codes
 * @brief Error codes that are due to a user error.
 */
/**
 * @defgroup SystemReturnErrorCodes System Error Codes
 * @brief Error codes that are due to a system error.
 */

/**
 * @brief If the system fails to either arm or disarm the laser.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_ARMDISARM_FAILURE                 ((uint32_t)64)
/**
 * @brief If the system fails to tune the laser to the user-specified wavelength.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_STARTTUNE_FAILURE                 ((uint32_t)65)
/**
 * @brief If the interlock status is not set or the key switch is not set.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_INTERLOCKS_KEYSWITCH_NOTSET       ((uint32_t)66)
/**
 * @brief If the system fails to successfully stop the scan in progress.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_STOP_SCAN_FAILURE                 ((uint32_t)67)
/**
 * @brief If the system fails to pause the scan in progress.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_PAUSE_SCAN_FAILURE                ((uint32_t)68)
/**
 * @brief If the system fails to resume the scan in progress.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_RESUME_SCAN_FAILURE               ((uint32_t)69)
/**
 * @brief If the system fails to manually move to the next step.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_MANUAL_STEP_SCAN_FAILURE          ((uint32_t)70)
/**
 * @brief If the system fails to start a sweep scan.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_START_SWEEPSCAN_FAILURE           ((uint32_t)71)
/**
 * @brief If the system fails to start a step and measure scan.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_START_STEPMEASURESCAN_FAILURE     ((uint32_t)72)
/**
 * @brief If the user-specified index is invalid and out of bounds.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_INDEX_OUTOFBOUNDS                 ((uint32_t)73)
/**
 * @brief If the system fails to start a multi-spectral scan.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_START_MULTISPECTRALSCAN_FAILURE   ((uint32_t)74)
/**
 * @brief The user-specified number of elements is too large.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_TOO_MANY_ELEMENTS                 ((uint32_t)75)
/**
 * @brief If the user does not define enough multi-spectral scan elements.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_NOT_ENOUGH_ELEMENTS               ((uint32_t)76)
/**
 * @brief If the user-specified buffer is too small for the character array.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_BUFFER_TOO_SMALL                  ((uint32_t)77)
/**
 * @brief If the user specifies an invalid favorite name.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_FAVORITE_NAME_NOTRECOGNIZED       ((uint32_t)78)
/**
 * @brief If the system fails to recall the favorite with the user-specified name.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_FAVORITE_RECALL_FAILURE           ((uint32_t)79)
/**
 * @brief If the user-specified wavelength is out of the valid range.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_WW_OUTOFTUNINGRANGE               ((uint32_t)80)
/**
 * @brief If the user attempts to modify a scan when there is no current scan in progress.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_NO_SCAN_INPROGRESS                ((uint32_t)81)
/**
 * @brief If the system fails to enable the laser emission.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_EMISSION_ON_FAILURE               ((uint32_t)82)
/**
 * @brief If the user attempts to disable laser emission when it is already disabled.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_EMISSION_ALREADY_OFF              ((uint32_t)83)
/**
 * @brief If the system fails to disable the laser emission.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_EMISSION_OFF_FAILURE              ((uint32_t)84)
/**
 * @brief If the user attempts to enable the laser emission while the laser is already emitting.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_EMISSION_ALREADY_ON               ((uint32_t)85)
/**
 * @brief If the user-specified pulse rate is invalid and out of range.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_PULSERATE_OUTOFRANGE              ((uint32_t)86)
/**
 * @brief If the user-specified pulse width is invalid and out of range.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_PULSEWIDTH_OUTOFRANGE             ((uint32_t)87)
/**
 * @brief If the user specifies a current value that is out of range.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_CURRENT_OUTOFRANGE                ((uint32_t)88)
/**
 * @brief If the system fails to save the QCL settings.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_SAVE_SETTINGS_FAILURE             ((uint32_t)89)
/**
 * @brief If the user-specified QCL is out of range. Must be 1-4.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_QCL_NUM_OUTOFRANGE                ((uint32_t)90)
/**
 * @brief If the user attempts to arm the laser when it has already been armed.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_LASER_ALREADY_ARMED               ((uint32_t)91)
/**
 * @brief If the user attempts to disarm the laser when it has already been disarmed.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_LASER_ALREADY_DISARMED            ((uint32_t)92)
/**
 * @brief If the user attempts to modify the laser when the laser is not yet armed.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_LASER_NOT_ARMED                   ((uint32_t)93)
/**
 * @brief If the user attempts to enable laser emission before tuning the laser.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_LASER_NOT_TUNED                   ((uint32_t)94)
/**
 * @brief If the system is not operating at the set temperature.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_TECS_NOT_AT_SET_TEMPERATURE       ((uint32_t)95)
/**
 * @brief If the user-specified QCL does not support CW.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_CW_NOT_ALLOWED_ON_QCL             ((uint32_t)96)
/**
 * @brief If the user specifies an invalid laser mode.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_INVALID_LASER_MODE                ((uint32_t)97)
/**
 * @brief If the user specifies a temperature value that is out of range.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_TEMPERATURE_OUT_OF_RANGE          ((uint32_t)98)
/**
 * @brief If the system fails to power off the laser.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_LASER_POWER_OFF_ERROR             ((uint32_t)99)
/**
 * @brief If communication to the system fails.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_COMM_ERROR                        ((uint32_t)100)
/**
 * @brief If the user attempts to modify the MIRcat object or call a function before the MIRcatController is
 * initialized.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_NOT_INITIALIZED                   ((uint32_t)101)
/**
 * @brief If the user attempts to create a new MIRcatObject when an instance has already been initialized.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_ALREADY_CREATED                   ((uint32_t)102)
/**
 * @brief If the system fails to start a sweep-advanced scan.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_START_SWEEP_ADVANCED_SCAN_FAILURE ((uint32_t)103)
/**
 * @brief If the system fails to inject a process trigger.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_INJECT_PROC_TRIG_ERROR            ((uint32_t)104)
/**
 * @brief If the user passes an invalid or null pointer as a parameter.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_PASSED_NULL_POINTER               ((uint32_t)105)
/**
 * @brief Table number out of range.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_TABLE_NUM_OUT_OF_RANGE            ((uint32_t)106)
/**
 * @brief String copy error.
 * @ingroup SystemReturnErrorCodes
 */
#define MIRcatSDK_RET_STRCPY_ERROR                      ((uint32_t)107)
/**
 * @brief Too many calibration entries.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_TOO_MANY_CAL_ENTRIES              ((uint32_t)108)
/**
 * @brief Cannot delete factory calibration.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_CANNOT_DELETE_FACTORY_CAL         ((uint32_t)109)
/**
 * @brief Cannot overwrite factory calibration.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_CANNOT_OVERWRITE_FACTORY_CAL      ((uint32_t)110)
/**
 * @brief Admin password incorrect.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_ADMIN_PASSWORD_INCORRECT          ((uint32_t)111)
/**
 * @brief No device at handle.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_NO_DEVICE_AT_HANDLE               ((uint32_t)112)
/**
 * @brief Connect failure at handle.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_CONNECT_FAIL_AT_HANDLE            ((uint32_t)113)
/**
 * @brief No controller at handle.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_NO_CONTROLLER_AT_HANDLE           ((uint32_t)114)
/**
 * @brief Disconnect error.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_DISCONNECT_ERROR                  ((uint32_t)115)
/**
 * @brief Pointing not supported.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_POINTING_NOT_SUPPORTED            ((uint32_t)116)
/**
 * @brief Deprecated parameter warning.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_WARNING_DEPRECATED_PARAMETER      ((uint32_t)117)
/**
 * @brief Deprecated function warning.
 * @ingroup UserReturnErrorCodes
 */
#define MIRcatSDK_RET_WARNING_DEPRECATED_FUNCTION       ((uint32_t)118)

/** @} */ // End of ReturnCodes group

//-----------------------------------------------------------//
//                 STATUS MASK FLAGS                         //
//-----------------------------------------------------------//
/**
 * @defgroup StatusMaskFlags Status Mask Flags
 * @brief Flags for interpreting the current status mask of the system.
 * @{
 */

/** @brief Enabled when the interlock is closed. */
#define MIRcatSDK_STATUS_MASK_INTERLOCKED               ((uint32_t)0x00000001)
/** @brief Enabled when the keyswitch is closed. */
#define MIRcatSDK_STATUS_MASK_KEY_SWITCH                ((uint32_t)0x00000002)
/** @brief Enabled when the TECs are at the target temperature. */
#define MIRcatSDK_STATUS_MASK_AT_TARGET_TEMPERATURE     ((uint32_t)0x00000004)
/** @brief Reserved flag 0. */
#define MIRcatSDK_STATUS_MASK_RESERVED_0                ((uint32_t)0x00000008)
/** @brief Reserved flag 1. */
#define MIRcatSDK_STATUS_MASK_RESERVED_1                ((uint32_t)0x00000010)
/** @brief Enabled when the system is actively scanning. */
#define MIRcatSDK_STATUS_MASK_SCANNING                  ((uint32_t)0x00000020)
/** @brief Enabled when the system is in the manual tune mode. */
#define MIRcatSDK_STATUS_MASK_MANUAL_TUNING             ((uint32_t)0x00000040)
/** @brief Reserved flag 2. */
#define MIRcatSDK_STATUS_MASK_RESERVED_2                ((uint32_t)0x00000080)
/** @brief Enabled when the system is reporting an error. */
#define MIRcatSDK_STATUS_MASK_SYSTEM_ERROR              ((uint32_t)0x00000100)
/** @brief Enabled when the system is reporting a warning. */
#define MIRcatSDK_STATUS_MASK_SYSTEM_WARNING            ((uint32_t)0x00000200)
/** @brief Enabled when the laser is armed. */
#define MIRcatSDK_STATUS_MASK_LASER_ARMED               ((uint32_t)0x00000400)
/** @brief Reserved flag 3. */
#define MIRcatSDK_STATUS_MASK_RESERVED_3                ((uint32_t)0x00000800)
/** @brief Enabled when the laser is actively firing. */
#define MIRcatSDK_STATUS_MASK_LASER_FIRING              ((uint32_t)0x00001000)
/** @brief Enabled when the system initialization is complete. */
#define MIRcatSDK_STATUS_MASK_INIT_DONE                 ((uint32_t)0x00002000)
/** @brief Enabled when case temp 1 is faulty. */
#define MIRcatSDK_STATUS_MASK_BTEMP1_FAULTY             ((uint32_t)0x00004000)
/** @brief Enabled when case temp 2 is faulty. */
#define MIRcatSDK_STATUS_MASK_BTEMP2_FAULTY             ((uint32_t)0x00008000)
/** @brief Enabled when the PCB board temp is faulty. */
#define MIRcatSDK_STATUS_MASK_PCB_TEMP_FAULTY           ((uint32_t)0x00010000)
/** @brief Enabled when the red laser pointer is installed. */
#define MIRcatSDK_STATUS_MASK_POINTER_INSTALLED         ((uint32_t)0x00020000)
/** @brief Enabled when the red laser pointer is emitting. */
#define MIRcatSDK_STATUS_MASK_POINTER_ENABLED           ((uint32_t)0x00040000)
/** @brief Enabled when the zero-point hardware is installed. */
#define MIRcatSDK_STATUS_MASK_ZERO_POINT_INSTALLED      ((uint32_t)0x00080000)
/** @brief Enabled when the pointing calibration is disabled. */
#define MIRcatSDK_STATUS_MASK_POINTING_CAL_DISABLED     ((uint32_t)0x00100000)

/** @} */ // End of StatusMaskFlags group

//-----------------------------------------------------------//
//                 PARAMETERS                                //
//-----------------------------------------------------------//
/**
 * @defgroup Parameters Parameters
 * @brief Parameters used throughout the MIRcat system.
 * @{
 */

/**
 * @defgroup CommunicationParameters Communication Parameters
 * @brief Parameters used to configure communication with the MIRcat system.
 * @{
 */

/** @brief Communication via Serial port. */
#define MIRcatSDK_COMM_SERIAL                           ((uint8_t)1)
/** @brief Communication via UDP. */
#define MIRcatSDK_COMM_UDP                              ((uint8_t)2)
/** @brief Uses Serial Communication as the default. */
#define MIRcatSDK_COMM_DEFAULT                          MIRcatSDK_COMM_SERIAL

/** @} */ // End of CommunicationParameters group

/**
 * @defgroup SerialPortParameters Serial Port Parameters
 * @brief Parameters for configuring the serial port.
 * @{
 */

/** @brief Automatically find the device on the port. */
#define MIRcatSDK_SERIAL_PORT_AUTO                      ((uint16_t)0)
/** @brief Use default baud rate. */
#define MIRcatSDK_SERIAL_BAUD_USE_DEFAULT               ((uint32_t)0)
/** @brief Baud rate 115200. */
#define MIRcatSDK_SERIAL_BAUD1                          ((uint32_t)115200)
/** @brief Baud rate 921600. */
#define MIRcatSDK_SERIAL_BAUD2                          ((uint32_t)921600)

/** @} */ // End of SerialPortParameters group

/** @} */ // End of Parameters group

//-----------------------------------------------------------//
//                 UNITS                                     //
//-----------------------------------------------------------//
/**
 * @defgroup Units Units
 * @brief Units for functions that use wavelength values.
 * @{
 */

/** @brief Micrometers, 1 x 10^-6 meters. */
#define MIRcatSDK_UNITS_MICRONS                         ((uint8_t)1)
/**
 * @brief Wavenumbers in cm^-1 units.
 * @details This is the spatial frequency of the wavelength and is in cycles per cm.
 */
#define MIRcatSDK_UNITS_CM1                             ((uint8_t)2)

/** @} */ // End of Units group

//-----------------------------------------------------------//
//                 MODES                                     //
//-----------------------------------------------------------//
/**
 * @defgroup Modes Modes
 * @brief Constants for different modes.
 * @{
 */

/**
 * @defgroup LaserModes Laser Modes
 * @brief This is the mode the laser uses for emission. Not all modes are supported by all laser heads.
 * @{
 */

/** @brief Error code associated with the different laser modes */
#define MIRcatSDK_MODE_ERROR                            ((uint8_t)0)
/**
 * @brief Pulsed laser mode.
 * @details The laser pulses on/off at the set repetition rate and pulse width.
 */
#define MIRcatSDK_MODE_PULSED                           ((uint8_t)1)
/**
 * @brief Continuous Waveform Mode.
 * @details In this mode the laser emission is continuously on.
 */
#define MIRcatSDK_MODE_CW                               ((uint8_t)2)
/**
 * @brief Same as CW mode but with an analog modulation enable signal enabled.
 * @details This is only supported by laser heads that have a modulation enable input (such as MIRcat sleds).
 */
#define MIRcatSDK_MODE_CW_MOD                           ((uint8_t)3)
/**
 * @brief CW mode with MR
 * @attention currently not supported in firmware.
 */
#define MIRcatSDK_MODE_CW_MR                            ((uint8_t)6)
/**
 * @brief CW mode with MR and modulation,
 * @attention currently not supported in firmware.
 */
#define MIRcatSDK_MODE_CW_MR_MOD                        ((uint8_t)7)
/** @brief Continuous Waveform mode with filter 1. */
#define MIRcatSDK_MODE_CW_FLTR1                         ((uint8_t)8)
/** @brief Continuous Waveform mode with filter 2. */
#define MIRcatSDK_MODE_CW_FLTR2                         ((uint8_t)9)
/** @brief Continuous Waveform mode with filter 1 and modulation. */
#define MIRcatSDK_MODE_CW_FLTR1_MOD                     ((uint8_t)10)

/** @} */ // End of LaserModes group

/**
 * @defgroup PulseTriggeringModes Pulse Triggering Modes
 * @brief Laser triggering modes for controlling QCL on/off.
 * @{
 */

/** @brief The laser internally controls pulse triggering based on set parameters. */
#define MIRcatSDK_PULSE_MODE_INTERNAL                   ((uint8_t)1)
/** @brief The laser uses an external TTL trigger signal to control the start of a laser pulse. */
#define MIRcatSDK_PULSE_MODE_EXTERNAL_TRIGGER           ((uint8_t)2)
/** @brief The laser output follows the external TTL signal with limits. */
#define MIRcatSDK_PULSE_MODE_EXTERNAL_PASSTHRU          ((uint8_t)3)
/** @brief Wavelength-triggered mode. */
#define MIRcatSDK_PULSE_MODE_WAVELENGTH_TRIGGER         ((uint8_t)4)

/** @} */ // End of PulseTriggeringModes group

/**
 * @defgroup ProcessTriggeringModes Process Triggering Modes
 * @brief Modes for triggering process steps in step scan modes.
 * @{
 */

/** @brief Laser controller controls all timing for step scan modes. */
#define MIRcatSDK_PROC_TRIG_MODE_INTERNAL               ((uint8_t)1)
/** @brief External trigger on MIRcat 9-pin I/O connector must be provided to advance to the next step. */
#define MIRcatSDK_PROC_TRIG_MODE_EXTERNAL               ((uint8_t)2)
/** @brief Manual trigger command from PC must be sent to advance to the next step. */
#define MIRcatSDK_PROC_TRIG_MODE_MANUAL                 ((uint8_t)3)

/** @} */ // End of ProcessTriggeringModes group

/** @} */ // End of Modes group

/** @} */ // End of Constants group

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @defgroup Functions Functions
 * @brief Functions of the SDK.
 * @{
 */

/**
 * @defgroup CommunicationFunctions Communication Functions
 * @brief Functions whose main purpose is to communicate with the system.
 * @{
 */

/**
 * @brief Get the version of the API.
 *
 * @param[out] papiVersionMajor Major version of the MIRcat API.
 * @param[out] papiVersionMinor Minor version of the MIRcat API.
 * @param[out] papiVersionPatch Patch version of the MIRcat API.
 *
 * @return @ref ReturnCodes "Return Code" indicating the query status for the API version.
 * @retval #MIRcatSDK_RET_SUCCESS if querying the API is successful.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetAPIVersion(uint16_t *papiVersionMajor, uint16_t *papiVersionMinor,
                                            uint16_t *papiVersionPatch);

/**
 * @brief Set the communications type.
 *
 * @param[in] commType Communications Interface Type.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of setting the communication type.
 * @retval #MIRcatSDK_RET_SUCCESS if setting the communication type is successful.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the controller is not yet initialized.
 * @retval #MIRcatSDK_RET_UNSUPPORTED_TRANSPORT if the user-specified @p commType is invalid.
 *
 * @see CommunicationParameters
 */
MIRCAT_LIB uint32_t MIRcatSDK_SetCommType(uint8_t commType);

/**
 * @brief Set serial port parameters.
 *
 * @param[in] port COM port number.
 * @param[in] baud Baud Rate.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of setting the serial port.
 * @retval #MIRcatSDK_RET_SUCCESS if setting the serial port is successful.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the controller is not yet initialized.
 *
 * @see SerialPortParameters
 */
MIRCAT_LIB uint32_t MIRcatSDK_SetSerialParams(uint16_t port, uint32_t baud);

/**
 * @brief Creates a new MIRcat object.
 *
 * @deprecated In single MIRcat mode, use @ref MIRcatSDK_Initialize instead. In multi-MIRcat mode, use @ref
 * MIRcatSDK_ConnectToDevice instead.
 *
 * @note If a previous call has been made to MIRcatSDK_DeInitialize(), this function should be
 * called before trying to call other MIRcatSDK functions.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of creating the MIRcat object.
 * @retval #MIRcatSDK_RET_SUCCESS if creating a MIRcat object is successful.
 * @retval #MIRcatSDK_RET_ALREADY_CREATED if the user attempts to create a new MIRcatObject
 *         when an instance has already been initialized.
 */
MIRCAT_LIB uint32_t MIRcatSDK_CreateMIRcatObject();

/**
 * @brief Returns a boolean value indicating if a MIRcat object has been created.
 *
 * @deprecated SDK calls already check if there is an active controller, and if there are none, those SDK
 * functions return @ref MIRcatSDK_RET_NOT_INITIALIZED.
 *
 * @note The object is destroyed following a call to MIRcatSDK_DeInitialize(). If it is
 * destroyed, it must be created before any SDK function calls will be valid. A
 * call to MIRcatSDK_Initialize() will also create the object if it has been destroyed.
 *
 * @param[out] pbMIRcatObjectCreated True if the MIRcat object has been created; false otherwise.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of checking the MIRcat object creation status.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_IsMIRcatObjectCreated(bool *pbMIRcatObjectCreated);

/**
 * @brief Initializes the API and connects to the first system found.
 *
 * @note This function creates a new MIRcat controller object if it does not already exist.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of the initialization.
 * @retval #MIRcatSDK_RET_SUCCESS if the MIRcat controller is successfully initialized.
 * @retval #MIRcatSDK_RET_INITIALIZATION_FAILURE if MIRcat controller initialization failed.
 */
MIRCAT_LIB uint32_t MIRcatSDK_Initialize();

/**
 * @brief Disconnect and clean up ports, memory, and threads associated with
 * initializing the MIRcatSDK.
 *
 * @note In multi-MIRcat mode, use @ref MIRcatSDK_DisconnectFromDevice instead.
 *
 * @pre A call to this function requires a call to MIRcatSDK_CreateMIRcatObject() or MIRcatSDK_Initialize()
 * before any subsequent calls to any SDK functions.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of the de-initialization.
 * @retval #MIRcatSDK_RET_SUCCESS if de-initializing the MIRcat controller object was successful.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the user tries to de-initialize the MIRcat object before the
 * controller is initialized.
 */
MIRCAT_LIB uint32_t MIRcatSDK_DeInitialize();

/** @} */ // End of CommunicationFunctions Group

/**
 * @defgroup MultiMIRcat Multi-MIRcat Support
 * @brief Functions related to supporting multiple MIRcats
 * @{
 */

/**
 * @brief Searches for MIRcats that are physically connected to the host computer.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of the search.
 * @retval #MIRcatSDK_RET_SUCCESS if device(s) are successfully found.
 * @retval #MIRcatSDK_RET_NO_SYSTEM_FOUND if no devices were found.
 */
MIRCAT_LIB uint32_t MIRcatSDK_SearchForDevices(void);

/**
 * @brief Retrieves the number of discovered devices.
 *
 * @param[out] numDevices Number of current devices.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the number of devices.
 * @retval #MIRcatSDK_RET_SUCCESS if retrieving the number of devices is successful.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetNumMIRcatDevices(uint8_t *numDevices);

/**
 * @brief Get the list of MIRcat handles.
 *
 * @param[out] handles Pointer to a list that holds the current MIRcat handle values (the size of the list is
 * determined by @ref MIRcatSDK_GetNumMIRcatDevices).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the pointer to handles.
 * @retval #MIRcatSDK_RET_SUCCESS if retrieving the pointer to handles is successful.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetDeviceList(unsigned int **handles);

/**
 * @brief Attempts to connect to the device labeled by the handle.
 *
 * @param handle Handle of the device the user wants to connect to.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of the connection attempt.
 * @retval #MIRcatSDK_RET_SUCCESS if connecting to the device with the given handle is successful.
 * @retval #MIRcatSDK_RET_CONNECT_FAIL_AT_HANDLE if connecting to the device with the given handle is
 * unsuccessful.
 */
MIRCAT_LIB uint32_t MIRcatSDK_ConnectToDevice(unsigned int handle);

/**
 * @brief Attempts to set the MIRcat's active system to the system given by the handle.
 *
 * @param handle Handle of the system the user wants to connect to.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of setting the active system.
 * @retval #MIRcatSDK_RET_SUCCESS if connecting to the system given by the handle is successful.
 * @retval #MIRcatSDK_RET_NO_DEVICE_AT_HANDLE if finding the system by the handle is unsuccessful.
 * @retval #MIRcatSDK_RET_NO_CONTROLLER_AT_HANDLE if the system given by the handle currently doesn't have a
 * controller.
 */
MIRCAT_LIB uint32_t MIRcatSDK_SetActiveSystem(unsigned int handle);

/**
 * @brief Attempts to disconnect from the device given by the handle.
 *
 * @param handle Handle of the device the user wants to disconnect from.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of the disconnection attempt.
 * @retval #MIRcatSDK_RET_SUCCESS if disconnecting from the device is successful.
 * @retval #MIRcatSDK_RET_NO_DEVICE_AT_HANDLE if finding the device given by the handle is unsuccessful.
 * @retval #MIRcatSDK_RET_NO_CONTROLLER_AT_HANDLE if the device given by the handle currently doesn't have a
 * controller.
 * @retval #MIRcatSDK_RET_DISCONNECT_ERROR if disconnecting from the controller of the device given by the
 * handler is unsuccessful.
 */
MIRCAT_LIB uint32_t MIRcatSDK_DisconnectFromDevice(unsigned int handle);

/** @} End of MultiMIRcat */

//-------------------------------------------------------------------------------------------------------------------------------------------//

/**
 * @defgroup InformationFunctions Information Functions
 * @brief Functions that retrieve information
 * @{
 */

/**
 * @brief Gets the name and description of a return code.
 *
 * @param returnCode The return code for which information is requested.
 * @param[out] title Pointer to a character array that will contain the return code title. The buffer size
 * should be 255 bytes.
 * @param titleBufferLength Size of title in bytes.
 * @param[out] description Pointer to a character array that will contain the return code description. The
 * buffer size should be 255 bytes.
 * @param descriptionBufferLength Size of description in bytes.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the return code information.
 * @retval #MIRcatSDK_RET_SUCCESS if retrieving the return code information is successful.
 * @retval #MIRcatSDK_RET_BUFFER_TOO_SMALL if the user-specified buffer is too small for the character array.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 * @retval #MIRcatSDK_RET_INDEX_OUTOFBOUNDS if the returnCode parameter is invalid.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetReturnCodeInformation(uint32_t returnCode, char *title,
                                                       uint64_t titleBufferLength, char *description,
                                                       uint64_t descriptionBufferLength);

/**
 * @brief Gets the model number of the MIRcat system.
 *
 * @param[out] pszModelNumber Pointer to a character array that will contain the model number after calling
 * the function. This array should be at least 24 bytes.
 * @param bSize Size of pszModelNumber in bytes.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the model number.
 * @retval #MIRcatSDK_RET_SUCCESS if retrieving the model number is successful.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the controller is not yet initialized.
 * @retval #MIRcatSDK_RET_BUFFER_TOO_SMALL if the user-specified buffer is too small for the character array.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetModelNumber(char *pszModelNumber, uint8_t bSize);

/**
 * @brief Gets the serial number of the MIRcat system.
 *
 * @param[out] pszSerialNumber Pointer to a character array that will contain the serial number after calling
 * the function. This array should be at least 24 bytes.
 * @param bSize Size of pszSerialNumber in bytes.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the serial number.
 * @retval #MIRcatSDK_RET_SUCCESS if retrieving the serial number is successful.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the controller is not yet initialized.
 * @retval #MIRcatSDK_RET_BUFFER_TOO_SMALL if the user-specified buffer is too small for the character array.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetSerialNumber(char *pszSerialNumber, uint8_t bSize);

/**
 * @brief Gets the system firmware versions.
 *
 * @param[out] cbFwMaj Control Board Major FW Version Number.
 * @param[out] cbFwMin Control Board Minor FW Version Number.
 * @param[out] cbFwPatch Control Board Patch FW Version Number.
 * @param[out] mbFwMaj Motion Board Major FW Version Number.
 * @param[out] mbFwMin Motion Board Minor FW Version Number.
 * @param[out] mbFwPatch Motion Board Patch FW Version Number.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the firmware versions.
 * @retval #MIRcatSDK_RET_SUCCESS if retrieving the firmware versions is successful.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the controller is not yet initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetFirmwareVersions(uint8_t *cbFwMaj, uint8_t *cbFwMin, uint8_t *cbFwPatch,
                                                  uint8_t *mbFwMaj, uint8_t *mbFwMin, uint8_t *mbFwPatch);

/**
 * @brief Gets the tuning range of the MIRcat system.
 *
 * @param[out] pfMinRange Minimum wavelength of the MIRcat system.
 * @param[out] pfMaxRange Maximum wavelength of the MIRcat system.
 * @param[out] pbUnits Units for the min/max wavelength of the MIRcat system.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the tuning range.
 * @retval #MIRcatSDK_RET_SUCCESS if the controller is initialized.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the controller is not yet initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetTuningRange(float *pfMinRange, float *pfMaxRange, uint8_t *pbUnits);

/**
 * @brief Gets the number of QCLs installed in the MIRcat system.
 *
 * @param[out] pbNumQcls Number of installed QCLs.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the number of installed QCLs.
 * @retval #MIRcatSDK_RET_SUCCESS if the controller is initialized.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the controller is not yet initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetNumInstalledQcls(uint8_t *pbNumQcls);

/**
 * @brief Gets the tuning range of a particular QCL in the MIRcat system.
 *
 * @param bQcl QCL for which to get the tuning range, indexed 1-4.
 * @param[out] pfMinRange Minimum wavelength of the MIRcat system.
 * @param[out] pfMaxRange Maximum wavelength of the MIRcat system.
 * @param[out] pbUnits Units for the min/max wavelength of the MIRcat system.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the tuning range.
 * @retval #MIRcatSDK_RET_SUCCESS if the tuning range of the user-specified QCL is properly retrieved.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetQclTuningRange(uint8_t bQcl, float *pfMinRange, float *pfMaxRange,
                                                uint8_t *pbUnits);

/**
 * @brief Gets the hours of operation for the lasers in the system.
 *
 * @param[out] hours The summation of hours of operation for all laser channels.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the hours of operation.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetHoursOfOperation(float *hours);

/** @} End of InformationFunctions */

//-------------------------------------------------------------------------------------------------------------------------------------------//

/**
 * @defgroup StatusAPIFunctions Status API Functions
 * @brief Functions that handle the status APIs.
 * @{
 */

/**
 * @brief Get the MIRcat status mask.
 *
 * @param[out] status_mask Bit mask representing the current MIRcat status.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the status mask.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to query the status mask.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetStatusMask(uint32_t *status_mask);

/**
 * @brief Is there a valid connection to the laser?
 *
 * @param[out] pbConnected Bool value that indicates if the API is connected to the MIRcat system.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of the connection check.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the controller is not yet initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_IsConnectedToLaser(bool *pbConnected);

/**
 * @brief Is the interlock set?
 *
 * @param[out] pbSet Bool value that indicates if the interlock circuit is closed.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of the interlock check.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the controller is not yet initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_IsInterlockedStatusSet(bool *pbSet);

/**
 * @brief Is the key switch in the ON position?
 *
 * @param[out] pbSet Bool value that indicates if the key switch is in the ON position.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of the key switch check.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the controller is not yet initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_IsKeySwitchStatusSet(bool *pbSet);

/**
 * @brief Is the laser emission on?
 *
 * @param[out] pbIsOn Bool value that indicates if the laser is currently emitting light.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of the emission check.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read info regarding the light from
 * the system.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_IsEmissionOn(bool *pbIsOn);

/**
 * @brief Is the laser armed?
 *
 * @param[out] pbIsArmed Bool value that indicates if the laser is armed.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of the laser armed check.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to query the status mask.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_IsLaserArmed(bool *pbIsArmed);

/**
 * @brief Is there a system error?
 *
 * @param[out] pbIsError Bool value that indicates if there is a system error.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of the system error check.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to query the status mask.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_IsSystemError(bool *pbIsError);

/**
 * @brief Attempt to clear the system error.
 * @attention If the error cannot be cleared, it is likely a serious system error.
 *
 * @param[out] pbErrorCleared Bool value that indicates the error could be cleared.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of attempting to clear the system error.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_ClearSystemError(bool *pbErrorCleared);

/**
 * @brief Are all of the TECs at the set temperature?
 *
 * @param[out] pbIsAtSetTemperature Bool value that indicates if the TECs are at the set temperature.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of checking if TECs are at set temp.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to query the status mask.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_AreTECsAtSetTemperature(bool *pbIsAtSetTemperature);

/**
 * @brief Gets the system error word.
 *
 * @param[out] pwErrorWord 16-bit error code. See the user's manual for an exhaustive list of error codes.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the system error word.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to query the status mask.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetSystemErrorWord(uint16_t *pwErrorWord);

/**
 * @brief Gets the wavelength display units specified in the laser settings.
 *
 * @param[out] pbDisplayUnits Display units for wavelength in the laser settings.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the display units.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to query the display units.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetWWDisplayUnits(uint8_t *pbDisplayUnits);

/**
 * @brief Gets the status of the current scan/tune.
 *
 * @param[out] pbIsScanInProgress Bool value that indicates if the scan is in progress.
 * @param[out] pbIsScanActive Bool value that indicates if the scan is active.
 * @param[out] pbIsScanPaused Bool value that indicates if the scan is paused.
 * @param[out] pwCurScanNum Current scan number in repeated scan sequence.
 * @param[out] pwCurrentScanPercent Current scan percentage completed.
 * @param[out] pfCurrentWW Current wavelength of the laser.
 * @param[out] pbUnits Wavelength units.
 * @param[out] pbIsTECInProgress Bool value that indicates if the laser is waiting for a TEC to get to the
 * target temperature before firing.
 * @param[out] pbIsMotionInProgress Bool value that indicates if a QCL is currently tuning.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the scan status.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to query the scan progress.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetScanStatus(bool *pbIsScanInProgress, bool *pbIsScanActive,
                                            bool *pbIsScanPaused, uint16_t *pwCurScanNum,
                                            uint16_t *pwCurrentScanPercent, float *pfCurrentWW,
                                            uint8_t *pbUnits, bool *pbIsTECInProgress,
                                            bool *pbIsMotionInProgress);

/**
 * @brief Is the system waiting for a user trigger?
 *
 * @param[out] bWaitProcTrig Bool value that indicates whether the system is waiting for a user trigger.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of the user trigger check.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to query the scan progress.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetScanWaitingProcessTrigger(bool *bWaitProcTrig);

/**
 * @brief Gets the active QCL during a scan/tune.
 *
 * @param[out] pbActiveQcl The QCL that is active during this part of the scan/tune.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the active QCL.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to query the info light status.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetActiveQcl(uint8_t *pbActiveQcl);

/** @} End of StatusAPIFunctions */

//-------------------------------------------------------------------------------------------------------------------------------------------//

/**
 * @defgroup UtilityFunctions Utility Functions
 * @brief Helper functions for the SDK.
 * @{
 */

/**
 * @brief Converts the wavelength from cm-1 to microns and vice versa.
 *
 * @param fWW The wavelength to convert.
 * @param bcurrentUnits The units to convert from.
 * @param bnewUnits The units to convert to.
 * @param[out] pfConvertedWW The value of the converted units.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of the conversion.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_ConvertWW(float fWW, uint8_t bcurrentUnits, uint8_t bnewUnits,
                                        float *pfConvertedWW);

/** @} End of UtilityFunctions */

//-------------------------------------------------------------------------------------------------------------------------------------------//

/**
 * @defgroup ArmDisarmLaserFunctions Arm/Disarm Laser Functions
 * @brief Functions that are responsible for arming and disarming the laser/emissions
 * @{
 */

/**
 * @brief Arms the Laser.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of arming the laser.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully arms the laser.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_LASER_ALREADY_ARMED if the user attempts to arm the laser when it has already been
 * armed.
 * @retval #MIRcatSDK_RET_INTERLOCKS_KEYSWITCH_NOTSET if the interlock status is not set or the key switch is
 * not set.
 * @retval #MIRcatSDK_RET_ARMDISARM_FAILURE if the system fails to arm the laser.
 */
MIRCAT_LIB uint32_t MIRcatSDK_ArmLaser();

/**
 * @brief Disarm the Laser.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of disarming the laser.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully disarms the laser.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_LASER_ALREADY_ARMED if the user attempts to disarm the laser when it has already
 * been disarmed.
 * @retval #MIRcatSDK_RET_ARMDISARM_FAILURE if the system fails to disarm the laser.
 */
MIRCAT_LIB uint32_t MIRcatSDK_DisarmLaser();

/**
 * @brief Toggle the armed state of the laser based on the current state.
 * (i.e., if the laser is disarmed, this command will arm it and vice versa).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of toggling the armed state of the laser.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully toggled laser arming.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_INTERLOCKS_KEYSWITCH_NOTSET if the interlock status is not set or the key switch is
 * not set.
 * @retval #MIRcatSDK_RET_ARMDISARM_FAILURE if the system fails to toggle laser arming.
 */
MIRCAT_LIB uint32_t MIRcatSDK_ArmDisarmLaser();

/** @} End of ArmDisarmLaserFunctions */

//-------------------------------------------------------------------------------------------------------------------------------------------//

/**
 * @defgroup GeneralScanFunctions General Scan Functions
 * @brief General functions utilized for different scan modes.
 * @{
 */

/**
 * @brief Stops the current scan.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of stopping the scan.
 * @retval #MIRcatSDK_RET_SUCCESS if the scan is successfully stopped.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_STOP_SCAN_FAILURE if the system fails to successfully stop the scan in progress.
 * @retval #MIRcatSDK_RET_NO_SCAN_INPROGRESS if the user attempts to stop a scan when there is no current scan
 * in progress.
 */
MIRCAT_LIB uint32_t MIRcatSDK_StopScanInProgress();

/**
 * @brief Pauses the current scan.
 *
 * @attention This function sends a pause command to the
 * laser, but currently the laser does not support pausing of a scan.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of pausing the scan.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to pause the scan in progress.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_PAUSE_SCAN_FAILURE if the system fails to pause the scan in progress.
 * @retval #MIRcatSDK_RET_NO_SCAN_INPROGRESS if the user attempts to pause a scan when there is no current
 * scan in progress.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PauseScanInProgress();

/**
 * @brief Resumes the current scan.
 *
 * @attention This function sends a resume command to the
 * laser, but currently the laser does not support pausing of a scan, so will not
 * resume.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of resuming the scan.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to resume the scan in progress.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_RESUME_SCAN_FAILURE if the system fails to resume the scan in progress.
 * @retval #MIRcatSDK_RET_NO_SCAN_INPROGRESS if the user attempts to resume a scan when there is no current
 * scan in progress.
 */
MIRCAT_LIB uint32_t MIRcatSDK_ResumeScanInProgress();

/**
 * @brief Tells the laser to go to the next step in a step and measure or
 * multi-spectral scan if the process trigger mode is set to manual.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of moving to the next step.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully moves to the next step.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_MANUAL_STEP_SCAN_FAILURE if the system fails to manually move to the next step.
 * @retval #MIRcatSDK_RET_NO_SCAN_INPROGRESS if the user attempts to manually step a scan when there is no
 * current scan in progress.
 */
MIRCAT_LIB uint32_t MIRcatSDK_ManualStepScanInProgress();

/** @} End of GeneralScanFunctions */

//-------------------------------------------------------------------------------------------------------------------------------------------//

/**
 * @defgroup TuneFunctions Tune Functions
 * @brief Functions for tuning.
 * @{
 */

/**
 * @brief Gets the actual tuned wavelength.
 *
 * @details This can be used during a sweep or tune to indicate when the target is reached.
 *
 * @param[out] pfActualWW The actual wavelength the laser is currently tuned to.
 * @param[out] pbUnits The wavelength units for the tuning.
 * @param[out] pbLightValid Indicates if laser light is valid (tuned and emitting).
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the actual wavelength.
 * @retval #MIRcatSDK_RET_SUCCESS if the MIRcat controller successfully queries the actual wavelength.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read info regarding the light from
 * the system.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetActualWW(float *pfActualWW, uint8_t *pbUnits, bool *pbLightValid);

/**
 * @brief Gets the currently tuned target wavelength.
 *
 * @param[out] pfTuneWW The wavelength the laser is currently tuned to.
 * @param[out] pbUnits The wavelength units for the tuning.
 * @param[out] pbPreferredQcl The preferred QCL as specified in the last
 * TuneToWW command indexed 1-4. A value of 0 indicates no preferred QCL.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the tuned wavelength.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetTuneWW(float *pfTuneWW, uint8_t *pbUnits, uint8_t *pbPreferredQcl);

/**
 * @brief Tune the laser to the specified wavelength with a preferred QCL.
 *
 * @param fTuneWW The target wavelength to tune the laser to.
 * @param bUnits The wavelength units for tuning the laser.
 * @param bPreferredQcl The preferred QCL for this tune command indexed 1-4. A value of 0 indicates no
 * preferred QCL.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of tuning to the user-specified wavelength.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to tune to the user-specified wavelength.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_TECS_NOT_AT_SET_TEMPERATURE if the system is not operating at the set temperature.
 * @retval #MIRcatSDK_RET_STARTTUNE_FAILURE if the system fails to tune the laser to the user-specified
 * wavelength.
 * @retval #MIRcatSDK_RET_LASER_NOT_ARMED if the user attempts to tune the laser when the laser is not yet
 * armed.
 * @retval #MIRcatSDK_RET_WW_OUTOFTUNINGRANGE if the user-specified wavelength is out of the valid range.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system is unable to read admin params or admin qcl params or
 * unable to read status mask.
 */
MIRCAT_LIB uint32_t MIRcatSDK_TuneToWW(float fTuneWW, uint8_t bUnits, uint8_t bPreferredQcl);

/**
 * @brief Is the laser tuned?
 *
 * @param[out] pbIsTuned Bool value that indicates if the laser is currently tuned.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of checking if the laser is tuned.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to query the scan progress or the
 * status mask.
 */
MIRCAT_LIB uint32_t MIRcatSDK_IsTuned(bool *pbIsTuned);

/**
 * @brief Cancel the current single tune.
 *
 * @attention If the laser is tuned in single tune mode, this command must be sent before performing a scan.
 *
 * @see MIRcatSDK_StopScanInProgress()
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of cancelling the manual tune mode.
 */
MIRCAT_LIB uint32_t MIRcatSDK_CancelManualTuneMode();

/**
 * @brief Turns laser emission on.
 *
 * @pre Laser must have been tuned to a wavelength prior to sending this command.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of enabling the laser emission.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to enable the laser emission.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to query the status mask.
 * @retval #MIRcatSDK_RET_LASER_NOT_ARMED if the user attempts to enable laser emission before the laser is
 * armed.
 * @retval #MIRcatSDK_RET_EMISSION_ALREADY_ON if the user attempts to enable the laser emission while the
 * laser is already emitting.
 * @retval #MIRcatSDK_RET_LASER_NOT_TUNED if the user attempts to enable laser emission before tuning the
 * laser.
 * @retval #MIRcatSDK_RET_EMISSION_ON_FAILURE if the system fails to enable the laser emission.
 */
MIRCAT_LIB uint32_t MIRcatSDK_TurnEmissionOn();

/**
 * @brief Turns laser emission off.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of disabling the laser emission.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to disable the laser emission.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_EMISSION_ALREADY_OFF if the user attempts to disable laser emission when it is
 * already disabled.
 * @retval #MIRcatSDK_RET_EMISSION_OFF_FAILURE if the system fails to disable the laser emission.
 */
MIRCAT_LIB uint32_t MIRcatSDK_TurnEmissionOff();

/** @} End of TuneAPIFunctions */

//-------------------------------------------------------------------------------------------------------------------------------------------//

/**
 * @defgroup SweepFunctions Sweep Functions
 * @brief Functions for sweeping scans.
 * @{
 */

/**
 * @brief Gets the sweep start wavelength from the last sweep scan.
 *
 * @param[out] pfStartWW Start wavelength of the last scan.
 * @param[out] pbUnits Wavelength units.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the sweep start wavelength.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read sweep parameters from the
 * system.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetSweepStartWW(float *pfStartWW, uint8_t *pbUnits);

/**
 * @brief Gets the sweep stop wavelength from the last sweep scan.
 *
 * @param[out] pfStopWW Stop wavelength of the last scan.
 * @param[out] pbUnits Wavelength units.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the sweep stop wavelength.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read sweep parameters from the
 * system.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetSweepStopWW(float *pfStopWW, uint8_t *pbUnits);

/**
 * @brief Gets the sweep speed in the indicated units per second from the last sweep scan.
 *
 * @param[out] pfScanSpeed Scan speed in units per second.
 * @param[out] pbUnits Wavelength units.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the sweep scan speed.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read sweep parameters from the
 * system.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetSweepScanSpeed(float *pfScanSpeed, uint8_t *pbUnits);

/**
 * @brief Gets the number of iterations to be performed for this scan.
 *
 * @param[out] pwNumScans Number of scan iterations to be performed.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the number of iterations.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read sweep parameters from the
 * system.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetSweepNumScans(uint16_t *pwNumScans);

/**
 * @brief Is this scan bidirectional?
 *
 * @deprecated Firmware no longer supports bidirectional scans.
 *
 * @param[out] pbIsBidirectional Bool value indicating if this scan is bidirectional.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of checking the bidirectional scan.
 * @retval #MIRcatSDK_RET_WARNING_DEPRECATED_FUNCTION if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read sweep parameters from the
 * system.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_IsSweepBidirectional(bool *pbIsBidirectional);

/**
 * @brief Starts a sweep scan with the specified parameters.
 *
 * @param fStartWW Start wavelength for this scan.
 * @param fStopWW Stop wavelength for this scan.
 * @param fScanSpeed Scan speed in specified units per second.
 * @param bUnits Wavelength units for this scan.
 * @param wNumScans Number of iterations of this scan to perform.
 * @param bIsBiDirectional [deprecated] Bool value indicating if this scan is bidirectional.
 * The parameter is forced to `false` regardless of input.
 * @param u8PreferredQcl The preferred QCL for this sweep scan command
 * indexed 1-4. A value of 0 indicates no preferred QCL. If there is a
 * preferred QCL, the scan will switch to this QCL as soon as possible and stay
 * on this QCL as long as possible.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of starting the sweep scan.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully starts a Sweep Scan.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_LASER_NOT_ARMED if the user attempts to start the sweep scan before the laser is
 * armed.
 * @retval #MIRcatSDK_RET_WW_OUTOFTUNINGRANGE if the user-specified wavelength is out of the valid range.
 * @retval #MIRcatSDK_RET_START_SWEEPSCAN_FAILURE if the system fails to start a Sweep Scan.
 * @retval #MIRcatSDK_RET_TECS_NOT_AT_SET_TEMPERATURE if the system is not operating at the set temperature.
 * @retval #MIRcatSDK_RET_WARNING_DEPRECATED_PARAMETER if the user attempts to enable the bidirectional
 * parameter.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system is unable to read admin params or admin qcl params or
 * unable to read status mask.
 */
MIRCAT_LIB uint32_t MIRcatSDK_StartSweepScan(float fStartWW, float fStopWW, float fScanSpeed, uint8_t bUnits,
                                             uint16_t wNumScans, bool bIsBiDirectional,
                                             uint8_t u8PreferredQcl);

/** @} End of SweepFunctions */

//-------------------------------------------------------------------------------------------------------------------------------------------//

/**
 * @defgroup StepMeasureFunctions Step Measure Functions
 * @brief Functions related to configuration and execution of step and measure scans.
 * @{
 */

/**
 * @brief Gets the step and measure start wavelength from the last step and measure scan.
 *
 * @param[out] pfStartWW Start wavelength of the last scan.
 * @param[out] pbUnits Wavelength units.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the start wavelength.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read step-measure parameters from
 * the system.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetStepMeasureStartWW(float *pfStartWW, uint8_t *pbUnits);

/**
 * @brief Gets the step and measure stop wavelength from the last step and measure scan.
 *
 * @param[out] pfStopWW Stop wavelength of the last scan.
 * @param[out] pbUnits Wavelength units.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the stop wavelength.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read step-measure parameters from
 * the system.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetStepMeasureStopWW(float *pfStopWW, uint8_t *pbUnits);

/**
 * @brief Gets the step and measure step size from the last step and measure scan.
 *
 * @param[out] pfStepSize Step size in the specified units.
 * @param[out] pbUnits Wavelength units.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the step size.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read step-measure parameters from
 * the system.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetStepMeasureStepSizeWW(float *pfStepSize, uint8_t *pbUnits);

/**
 * @brief Gets the number of iterations for the step and measure scan.
 *
 * @param[out] pwNumScans Number of scan iterations.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the number of iterations.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read step-measure parameters from
 * the system.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetStepMeasureNumScans(uint16_t *pwNumScans);

/**
 * @brief Starts a step and measure scan with the specified parameters.
 *
 * @param fStart Start wavelength in the specified units.
 * @param fStop Stop wavelength in the specified units.
 * @param fStepSize Step size in the specified units.
 * @param bUnits Wavelength units.
 * @param wNumScans Number of iterations to be performed for this scan.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of starting the step and measure scan.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully starts a step and measure scan.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_LASER_NOT_ARMED if the user attempts to start a step and measure scan before the
 * laser is armed.
 * @retval #MIRcatSDK_RET_WW_OUTOFTUNINGRANGE if the user-specified wavelength is out of the valid range.
 * @retval #MIRcatSDK_RET_TECS_NOT_AT_SET_TEMPERATURE if the system is not operating at the set temperature.
 * @retval #MIRcatSDK_RET_START_STEPMEASURESCAN_FAILURE if the system fails to start a step and measure scan.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system is unable to read admin params or admin qcl params or
 * unable to read status mask.
 */
MIRCAT_LIB uint32_t MIRcatSDK_StartStepMeasureModeScan(float fStart, float fStop, float fStepSize,
                                                       uint8_t bUnits, uint16_t wNumScans);

/** @} End of StepMeasureFunctions */

//-------------------------------------------------------------------------------------------------------------------------------------------//

/**
 * @defgroup MultiSpectralFunctions Multi Spectral Functions
 * @brief Functions related to configuration and execution of multi-spectral scans
 * @{
 */

/**
 * @brief Gets the number of elements in the last multi-spectral scan.
 *
 * @param[out] pbNumElements Number of elements in the multi-spectral scan.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the number of elements.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read multi-spectral parameters from
 * the system.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetNumMultiSpectralElements(uint8_t *pbNumElements);

/**
 * @brief Gets the parameters for the specified element in a multi-spectral scan.
 *
 * @param bIndex Element index.
 * @param[out] pfScanWW Element wavelength.
 * @param[out] pdwDwellTime Element dwell time.
 * @param[out] pdwOffTime Element off time.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the parameters for the
 * user-specified element.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the parameters for the user-specified
 * element.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_INDEX_OUTOFBOUNDS if the user-specified element index (@p bIndex) is invalid and
 * out of index bounds.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read multi-spectral parameters from
 * the system.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetMultiSpectralElement(uint8_t bIndex, float *pfScanWW, uint32_t *pdwDwellTime,
                                                      uint32_t *pdwOffTime);

/**
 * @brief Gets the wavelength units for the last multi-spectral scan.
 *
 * @param[out] pbUnits Wavelength units for the multi-spectral scan.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the wavelength units.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read multi-spectral parameters from
 * the system.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetMultiSpectralWWUnits(uint8_t *pbUnits);

/**
 * @brief Gets the number of iterations for the last multi-spectral scan.
 *
 * @param[out] pwNumScans Number of scan iterations.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the number of iterations.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read multi-spectral parameters from
 * the system.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetMultiSpectralNumScans(uint16_t *pwNumScans);

/**
 * @brief Sets the number of elements for a multi-spectral scan.
 *
 * @param bNumElements Number of elements in a multi-spectral scan.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of setting the number of elements.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully sets the number of elements for a multi-spectral
 * scan.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_TOO_MANY_ELEMENTS if the user-specified number of elements is too large.
 */
MIRCAT_LIB uint32_t MIRcatSDK_SetNumMultiSpectralElements(uint8_t bNumElements);

/**
 * @brief Adds a multi-spectral scan element to the end of the element list.
 *
 * @param fScanWW Element wavelength.
 * @param bUnits Element wavelength units.
 * @param dwDwellTime Element dwell time.
 * @param dwOffTime Element off time.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of adding an element to the end of the element
 * list.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully adds an element to the end of the element list.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_INDEX_OUTOFBOUNDS if the user-specified element index (@p bIndex) is invalid and
 * out of index bounds.
 * @retval #MIRcatSDK_RET_WW_OUTOFTUNINGRANGE if the user-specified wavelength is out of the valid range.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system is unable to read admin params or admin qcl params or
 * unable to read status mask.
 */
MIRCAT_LIB uint32_t MIRcatSDK_AddMultiSpectralElement(float fScanWW, uint8_t bUnits, uint32_t dwDwellTime,
                                                      uint32_t dwOffTime);

/**
 * @brief Starts a multi-spectral scan with the specified number of iterations.
 *
 * @pre The elements for this scan must have been set up previously.
 *
 * @param wNumScans Number of iterations for this multi-spectral scan.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of starting the Multi-Spectral scan.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully starts a Multi-Spectral scan.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_LASER_NOT_ARMED if the user attempts to start a multi-spectral scan before the laser
 * is armed.
 * @retval #MIRcatSDK_RET_NOT_ENOUGH_ELEMENTS if the user does not define enough multi-spectral scan elements.
 * @retval #MIRcatSDK_RET_TECS_NOT_AT_SET_TEMPERATURE if the system is not operating at the set temperature.
 * @retval #MIRcatSDK_RET_START_MULTISPECTRALSCAN_FAILURE if the system fails to start a multi-spectral scan.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system is unable to read the status mask.
 */
MIRCAT_LIB uint32_t MIRcatSDK_StartMultiSpectralModeScan(uint16_t wNumScans);

/** @} End of MultiSpectralFunctions */

//-------------------------------------------------------------------------------------------------------------------------------------------//

/**
 * @defgroup FavoritesFunctions Favorites Functions
 * @brief Functions for the favorites section in MIRcat.
 * @{
 */

/**
 * @brief Gets the number of user favorites that have been saved in the laser memory.
 *
 * @param[out] pbNumFavorites Number of favorites saved in the laser memory.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the number of favorites.
 * @retval #MIRcatSDK_RET_SUCCESS if the system is successfully able to return a value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read favorites from the system.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetNumFavorites(uint8_t *pbNumFavorites);

/**
 * @brief Gets the name of the favorite at the specified index.
 *
 * @param bIndex Index of the favorite.
 * @param[out] pszFavoriteName Name of the favorite. This character array should be 32 bytes.
 * @param bSize Length in bytes of the favorite name.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the name of the favorite.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the name of the favorite at the
 * user-specified index.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_INDEX_OUTOFBOUNDS if the user-specified index is invalid and out of bounds.
 * @retval #MIRcatSDK_RET_BUFFER_TOO_SMALL if the user-specified buffer is too small for the character array.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetFavoriteName(uint8_t bIndex, char *pszFavoriteName, uint8_t bSize);

/**
 * @brief Recalls the favorite with the given name.
 *
 * @param[in] pszFavoriteName Name of the favorite to recall.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of recalling the favorite.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully recalls the favorite with the user-specified
 * name.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_FAVORITE_NAME_NOTRECOGNIZED if the user specifies an invalid favorite name.
 * @retval #MIRcatSDK_RET_FAVORITE_RECALL_FAILURE if the system fails to recall the favorite with the
 * user-specified name.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the in parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_RecallFavorite(char *pszFavoriteName);

/** @} End of FavoritesFunctions */

//-------------------------------------------------------------------------------------------------------------------------------------------//

/**
 * @defgroup SettingsFunctions Settings Functions
 * @brief Functions for laser settings.
 * @note All QCLs are indexed starting from 1.
 * @{
 */

/**
 * @brief Gets the pulse rate of the specified QCL in Hz.
 *
 * @param bQcl QCL number indexed from 1.
 * @param[out] pfPulseRateInHz Pulse Rate in Hz.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the pulse rate of the specified
 * QCL.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the pulse rate of the specified QCL.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetQCLPulseRate(uint8_t bQcl, float *pfPulseRateInHz);

/**
 * @brief Gets the pulse width of the specified QCL in nanoseconds (ns).
 *
 * @param bQcl QCL number indexed from 1.
 * @param[out] pfPulseWidthInNanoSec Pulse Width in nanoseconds (ns).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the pulse width of the specified
 * QCL.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the pulse width of the specified QCL.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetQCLPulseWidth(uint8_t bQcl, float *pfPulseWidthInNanoSec);

/**
 * @brief Gets the current setting of the specified QCL in milliAmps (mA).
 *
 * @param bQcl QCL number indexed from 1.
 * @param[out] pfCurrentInMilliAmps Current setting in milliAmps (mA).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the current setting of the
 * specified QCL.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the QCL current of the specified QCL.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetQCLCurrent(uint8_t bQcl, float *pfCurrentInMilliAmps);

/**
 * @brief Sets the operating parameters for the specified QCL.
 *
 * @param bQcl QCL number indexed from 1.
 * @param fPulseRateInHz Pulse rate in Hz.
 * @param fPulseWidthInNanoSec Pulse width in nanoseconds (ns).
 * @param fCurrentInMilliAmps Current in milliAmps (mA).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of setting the operating parameters for the
 * specified QCL.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully sets the operating parameters for the specified
 * QCL.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PULSERATE_OUTOFRANGE if the user-specified pulse rate is invalid and out of range.
 * @retval #MIRcatSDK_RET_PULSEWIDTH_OUTOFRANGE if the user-specified pulse width is invalid and out of range.
 * @retval #MIRcatSDK_RET_CURRENT_OUTOFRANGE if the user specifies a current that is out of range.
 * @retval #MIRcatSDK_RET_SAVE_SETTINGS_FAILURE if the system fails to save the QCL settings.
 */
MIRCAT_LIB uint32_t MIRcatSDK_SetQCLParams(uint8_t bQcl, float fPulseRateInHz, float fPulseWidthInNanoSec,
                                           float fCurrentInMilliAmps);

/**
 * @brief Gets the pulse limits for the specified QCL.
 *
 * @param bQcl QCL number indexed from 1-4.
 * @param[out] pfPulseRateMaxInHz Maximum pulse rate in Hz.
 * @param[out] pfPulseWidthMaxInNanoSec Maximum pulse width in nanoseconds (ns).
 * @param[out] pfDutyCycleMax Maximum pulsed duty cycle as a percentage.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the pulse limits for the
 * specified QCL.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the pulse limits of the specified QCL.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetQCLPulseLimits(uint8_t bQcl, float *pfPulseRateMaxInHz,
                                                float *pfPulseWidthMaxInNanoSec, float *pfDutyCycleMax);

/**
 * @brief Gets the QCL Duty Cycle as a percentage.
 *
 * @param bQcl QCL number indexed from 1-4.
 * @param[out] pfDutyCycle The duty cycle for the specified QCL as a percentage [0-100].
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the current duty cycle.
 * @retval #MIRcatSDK_RET_SUCCESS if the duty cycle was successfully calculated.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PULSERATE_OUTOFRANGE if the pulse rate is out of range (== 0.0f).
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetQCLDutyCycle(const uint8_t bQcl, float *pfDutyCycle);

/**
 * @brief Gets the max pulsed current setting of the specified QCL in milliAmps (mA).
 *
 * @param bQcl QCL number indexed from 1-4.
 * @param[out] pfCurrentInMilliAmps Maximum QCL current in milliAmps (mA).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the max pulsed current of the
 * specified QCL.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the max pulsed current of the specified QCL.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetQCLMaxPulsedCurrent(uint8_t bQcl, uint16_t *pfCurrentInMilliAmps);

/**
 * @brief Gets the min pulsed current setting of the specified QCL in milliAmps (mA).
 *
 * @param bQcl QCL number indexed from 1-4.
 * @param[out] pfCurrentInMilliAmps Minimum QCL current in milliAmps (mA).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the min pulsed current of the
 * specified QCL.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the min pulsed current of the specified QCL.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetQCLMinPulsedCurrent(uint8_t bQcl, uint16_t *pfCurrentInMilliAmps);

/**
 * @brief Gets the max CW current setting of the specified QCL in milliAmps (mA).
 *
 * @param bQcl QCL number indexed from 1-4.
 * @param[out] pfCurrentInMilliAmps Maximum QCL current in milliAmps (mA).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the max CW current of the
 * specified QCL.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the max CW current of the specified QCL.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetQCLMaxCwCurrent(uint8_t bQcl, uint16_t *pfCurrentInMilliAmps);

/**
 * @brief Gets the min CW current setting of the specified QCL in milliAmps (mA).
 *
 * @param bQcl QCL number indexed from 1-4.
 * @param[out] pfCurrentInMilliAmps Minimum QCL current in milliAmps (mA).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the min CW current of the
 * specified QCL.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the min CW current of the specified QCL.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetQCLMinCwCurrent(uint8_t bQcl, uint16_t *pfCurrentInMilliAmps);

/**
 * @brief Gets the status of CW being supported for the specified QCL.
 *
 * @param bQcl QCL number indexed from 1-4.
 * @param[out] pbCwAllowed Bool value that indicates if CW is supported on this channel.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of checking if CW is supported.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the status of CW being supported for the
 * specified QCL.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_isCwAllowed(uint8_t bQcl, bool *pbCwAllowed);

/**
 * @brief Gets the status of CW filters being supported for the specified QCL.
 *
 * @param bQcl QCL number indexed from 1-4.
 * @param[out] pbFiltersInstalled Bool value that indicates if CW filters are installed on this channel.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of checking if CW filters are installed.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the status of CW filters being supported for
 * the specified QCL.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_areCwFiltersInstalled(uint8_t bQcl, bool *pbFiltersInstalled);

/**
 * @brief Gets the TEC current for the specified channel.
 *
 * @param bTec TEC number indexed from 1-4.
 * @param[out] pfCurrentInMilliAmps TEC current in milliAmps (mA).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the TEC current for the
 * specified TEC.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the TEC current for the specified TEC.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetTecCurrent(uint8_t bTec, int16_t *pfCurrentInMilliAmps);

/**
 * @brief Gets the QCL temperature for the specified channel.
 *
 * @param bQcl QCL number indexed from 1-4.
 * @param[out] pfQclTemperature QCL temperature in degrees C.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the QCL temperature for the
 * specified QCL.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the QCL temperature for the specified QCL.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetQCLTemperature(uint8_t bQcl, float *pfQclTemperature);

/**
 * @brief Gets the QCL operating mode for the specified channel.
 *
 * @param bQcl QCL number indexed from 1-4.
 * @param[out] pbMode QCL operating mode.
 *
 * @see LaserModes
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the QCL operating mode for the
 * specified QCL.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the QCL operating mode for the specified
 * channel.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetQCLOperatingMode(uint8_t bQcl, uint8_t *pbMode);

/**
 * @brief Gets the QCL set temperature for the specified channel in degrees C.
 *
 * @param bQcl QCL number indexed from 1-4.
 * @param[out] pfQclSetTemperature QCL set temperature.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the QCL set temperature for the
 * specified QCL.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the QCL set temperature for the specified
 * channel.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetQclSetTemperature(uint8_t bQcl, float *pfQclSetTemperature);

/**
 * @brief Gets the QCL temperature range for the specified channel in degrees C.
 *
 * @param bQcl QCL number indexed from 1-4.
 * @param[out] pfQclNominalTemperature QCL nominal factory temperature (degrees C).
 * @param[out] pfQclMinTemperature QCL minimum temperature (degrees C).
 * @param[out] pfQclMaxTemperature QCL maximum temperature (degrees C).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the QCL temperature range for
 * the specified QCL.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the QCL temperature range for the specified
 * channel.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetQCLTemperatureRange(uint8_t bQcl, float *pfQclNominalTemperature,
                                                     float *pfQclMinTemperature, float *pfQclMaxTemperature);

/**
 * @brief Sets the operating parameters for the specified QCL.
 *
 * @param bQcl QCL number indexed from 1-4.
 * @param fPulseRate Pulse rate in Hz.
 * @param fPulseWidth Pulse width in nanoseconds (ns).
 * @param fCurrentInMilliAmps Current in milliAmps (mA).
 * @param fTemperature Temperature in degrees Celsius.
 * @param u8laserMode Laser Mode (Pulsed, CW, or CW+Mod).
 * @param checkParams If true, checks if the parameters are within range before setting them.
 *
 * @see LaserModes
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of setting and saving the operating parameters
 * for the specified QCL.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully sets and saves the operating parameters for the
 * specified QCL.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the user-specified QCL is out of range. Must be 1-4.
 * @retval #MIRcatSDK_RET_PULSERATE_OUTOFRANGE if the user-specified pulse rate is invalid and out of range.
 * @retval #MIRcatSDK_RET_PULSEWIDTH_OUTOFRANGE if the user-specified pulse width is invalid and out of range.
 * @retval #MIRcatSDK_RET_CW_NOT_ALLOWED_ON_QCL if the user-specified QCL does not support CW.
 * @retval #MIRcatSDK_RET_INVALID_LASER_MODE if the user specifies an invalid laser mode.
 * @retval #MIRcatSDK_RET_CURRENT_OUTOFRANGE if the user specifies a current that is out of range.
 * @retval #MIRcatSDK_RET_TEMPERATURE_OUT_OF_RANGE if the user specifies a temperature that is out of range.
 * @retval #MIRcatSDK_RET_SAVE_SETTINGS_FAILURE if the system fails to save the QCL settings.
 */
MIRCAT_LIB uint32_t MIRcatSDK_SetAllQclParams(uint8_t bQcl, float fPulseRate, float fPulseWidth,
                                              float fCurrentInMilliAmps, float fTemperature,
                                              uint8_t u8laserMode, bool checkParams = true);

/**
 * @brief Sends command to power the system off.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of powering off the system.
 * @retval #MIRcatSDK_RET_SUCCESS if the system has successfully powered off.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_LASER_POWER_OFF_ERROR if the laser was unable to power off.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PowerOffSystem(void);

/** @} End of SettingsFunctions */

//-------------------------------------------------------------------------------------------------------------------------------------------//

/**
 * @defgroup WavelengthTriggersFunctions Wavelength Triggers Functions
 * @brief Functions for setting/getting wavelength triggers during/for scans.
 * @{
 */

/**
 * @brief Gets the current wavelength trigger parameters in the laser settings.
 *
 * @param[out] pbPulseMode Pulse Triggering Mode.
 * @param[out] pbProcTrigMode Process Triggering Mode.
 * @param[out] pfWlTrigStart Wavelength Trigger Start Wavelength.
 * @param[out] pfWlTrigStop Wavelength Trigger Stop Wavelength.
 * @param[out] pfWlTrigInterval Wavelength Trigger Interval.
 * @param[out] pbUnits Wavelength Units for trigger parameters.
 * @param[out] pDwellTime The amount of time (in microseconds) to remain on a wavelength during a step and
 * measure scan.
 * @param[out] pAfterOffTime Interval of time (in microseconds) for the timer that controls the delay between
 * steps.
 *
 * @see PulseTriggeringModes
 * @see ProcessTriggeringModes
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the wavelength trigger
 * parameters.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully gets the wavelength trigger parameters.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system fails to communicate with the MIRcat laser.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetWlTrigParams(uint8_t *pbPulseMode, uint8_t *pbProcTrigMode,
                                              float *pfWlTrigStart, float *pfWlTrigStop,
                                              float *pfWlTrigInterval, uint8_t *pbUnits, uint32_t *pDwellTime,
                                              uint32_t *pAfterOffTime);

/**
 * @brief Sets the current wavelength trigger parameters in the laser settings.
 *
 * @param pbPulseMode Pulse Triggering Mode.
 * @param pbProcTrigMode Process Triggering Mode.
 * @param pfWlTrigStart Wavelength Trigger Start Wavelength.
 * @param pfWlTrigStop Wavelength Trigger Stop Wavelength.
 * @param pfWlTrigInterval Wavelength Trigger Interval.
 * @param pbUnits Microns or Wavenumbers. See Units
 * @param pDwellTime The amount of time (in microseconds) to remain on a wavelength during a step and measure
 * scan.
 * @param pAfterOffTime Interval of time (in microseconds) for the timer that controls the delay between
 * steps.
 *
 * @see PulseTriggeringModes
 * @see ProcessTriggeringModes
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of setting the wavelength trigger parameters.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully sets the wavelength trigger parameters.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system fails to communicate with the MIRcat laser.
 */
MIRCAT_LIB uint32_t MIRcatSDK_SetWlTrigParams(uint8_t pbPulseMode, uint8_t pbProcTrigMode,
                                              float pfWlTrigStart, float pfWlTrigStop, float pfWlTrigInterval,
                                              uint8_t pbUnits, uint32_t pDwellTime, uint32_t pAfterOffTime);

/**
 * @brief Read the wavelength trigger parameters for a specified channel.
 *
 * @param bChan QCL Channel indexed from 1.
 * @param[out] units Microns or Wavenumbers. See Units
 * @param[out] start_ww Starting Wavelength.
 * @param[out] stop_ww Stopping Wavelength.
 * @param[out] spacing Trigger Spacing.
 * @param[out] numTrigs Number of Triggers.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of reading the wavelength trigger parameters.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully reads the wavelength trigger parameters for the
 * specified channel.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system fails to communicate with the MIRcat laser.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetWlTrigChanParams(uint8_t bChan, uint8_t *units, float *start_ww,
                                                  float *stop_ww, float *spacing, uint16_t *numTrigs);

/**
 * @brief Gets the system temperatures.
 *
 * @param[out] pfBenchTemp1 Bench Temperature Sensor 1 (degrees C)
 * @param[out] pfBenchTemp2 Bench Temperature Sensor 2 (degrees C)
 * @param[out] pfPcbTemp PCB Temperature (degrees C)
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of reading the system temperatures.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully reads the system temperatures.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system fails to communicate with the MIRcat laser.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetSystemTemperatures(float *pfBenchTemp1, float *pfBenchTemp2,
                                                    float *pfPcbTemp);

/**
 * @brief Allows users to read/write parameters for the advanced sweep.
 *
 * @attention Users must use the ReadWrite function to read/write in hardware. The Set and Get functions alone
 * are not enough.
 *
 * @param fWrite Determines whether the user is reading or writing. (Writing being true; reading being false)
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of reading/writing parameters for the advanced
 * sweep.
 * @retval #MIRcatSDK_RET_SUCCESS if the system can successfully read/write parameters for the sweep-advanced
 * scan.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_START_SWEEP_ADVANCED_SCAN_FAILURE if the system fails to start/access a
 * sweep-advanced scan.
 */
MIRCAT_LIB uint32_t MIRcatSDK_ReadWriteAdvancedSweepParams(bool fWrite);

/**
 * @brief Sets the parameters for the advanced sweep on the controller.
 *
 * @attention This function doesn't set the values in hardware.
 * Use MIRcatSDK_ReadWriteAdvancedSweepParams(true) to set in hardware.
 *
 * @param pbUnits Units for either wavelength (#MIRcatSDK_UNITS_MICRONS) or wavenumber (#MIRcatSDK_UNITS_CM1).
 * @param pfStartWave Beginning of the sweep (same units as pbUnits).
 * @param pfStopWave End of the sweep (same units as pbUnits).
 * @param pfSpeed Speed of sweep (same units as pbUnits / second).
 * @param psNumScans How many times to repeat the sweep.
 * @param pbBidirectional Deprecated.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of setting the advanced sweep parameters.
 * @retval #MIRcatSDK_RET_SUCCESS if the system can successfully find the controller.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 */
MIRCAT_LIB uint32_t MIRcatSDK_SetAdvancedSweepParams(uint8_t pbUnits, float pfStartWave, float pfStopWave,
                                                     float pfSpeed, uint16_t psNumScans,
                                                     bool pbBidirectional);

/**
 * @brief Retrieves the parameters for the advanced sweep on the controller.
 *
 * @attention Use MIRcatSDK_ReadWriteAdvancedSweepParams(false) to query the latest values from hardware.
 *
 * @param[out] pbUnits Units for either wavelength (#MIRcatSDK_UNITS_MICRONS) or wavenumber
 * (#MIRcatSDK_UNITS_CM1).
 * @param[out] pfStartWave Beginning of the sweep (same units as pbUnits).
 * @param[out] pfStopWave End of the sweep (same units as pbUnits).
 * @param[out] pfSpeed Speed of sweep (same units as pbUnits / second).
 * @param[out] psNumScans How many times to repeat the sweep.
 * @param[out] pbBidirectional Deprecated.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the advanced sweep parameters.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully read and set parameters.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read sweep parameters from the
 * system.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetAdvancedSweepParams(uint8_t *pbUnits, float *pfStartWave, float *pfStopWave,
                                                     float *pfSpeed, uint16_t *psNumScans,
                                                     bool *pbBidirectional);

/**
 * @brief Sets the parameters for an advanced sweep for a specific QCL channel.
 *
 * @attention This function doesn't set the values in hardware.
 * Use MIRcatSDK_ReadWriteAdvancedSweepParams(true) to set in hardware.
 *
 * @param bQcl The QCL channel (indexed from 1).
 * @param chStartWave The start wavelength/wavenumber (same units as in MIRcatSDK_GetAdvancedSweepParams()).
 * @param chStopWave The stop wavelength/wavenumber (same units as in MIRcatSDK_GetAdvancedSweepParams()).
 * @param useChannel Determines whether or not the channel is used during the sweep.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of setting the advanced sweep channel
 * parameters.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully sets channel parameters.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the inputted bQcl value is out of scope of the number of
 * channels available.
 */
MIRCAT_LIB uint32_t MIRcatSDK_SetAdvancedSweepChanParams(uint8_t bQcl, float chStartWave, float chStopWave,
                                                         bool useChannel);

/**
 * @brief Retrieves the parameters for an advanced sweep for a specific QCL channel.
 *
 * @attention Use MIRcatSDK_ReadWriteAdvancedSweepParams(false) to query the latest values from hardware.
 *
 * @param bQcl The QCL channel (indexed from 1).
 * @param[out] chStartWave The start wavelength/wavenumber (same units as in
 * MIRcatSDK_GetAdvancedSweepParams).
 * @param[out] chStopWave The stop wavelength/wavenumber (same units as in MIRcatSDK_GetAdvancedSweepParams).
 * @param[out] useChannel Determines whether the channel is used during the sweep.
 *
 * @see Units
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the advanced sweep channel
 * parameters.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully read and retrieved channel parameters.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the MIRcat controller is unable to read sweep parameters from the
 * system.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the inputted bQcl value is out of scope of the number of
 * channels available.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetAdvancedSweepChanParams(uint8_t bQcl, float *chStartWave, float *chStopWave,
                                                         bool *useChannel);

/**
 * @brief Starts Sweep Advanced Scan.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of starting the scan.
 * @retval #MIRcatSDK_RET_SUCCESS if the controller is initialized.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the controller is not yet initialized.
 */
MIRCAT_LIB uint32_t MIRcatSDK_StartSweepAdvancedScan(void);

/**
 * @brief Inject a manual process into the system for scans when in manual process trigger mode.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of injecting the process trigger.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully injects a process trigger.
 * @retval #MIRcatSDK_RET_INJECT_PROC_TRIG_ERROR if the system fails to inject a process trigger.
 */
MIRCAT_LIB uint32_t MIRcatSDK_InjectProcessTrigger(void);

/**
 * @brief Gets the read back parameters from the specified QCL.
 *
 * @param bQcl The QCL channel (indexed from 1).
 * @param[out] actualQclCurrent QCL current in milliAmps (mA).
 * @param[out] actualQclVoltage QCL voltage in volts (V).
 * @param[out] actualVsrc VSRC voltage in volts (V).
 * @param[out] actualVfet Vfet voltage in volts (V).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the read back parameters.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully retrieves readback parameters.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system is not properly able to read QCL data.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the index for bQcl is outside range.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetReadbackParameters(uint8_t bQcl, float *actualQclCurrent,
                                                    float *actualQclVoltage, float *actualVsrc,
                                                    float *actualVfet);

/**
 * @brief Gets the TEC parameters.
 *
 * @param bTec The QCL channel with the TEC (indexed from 1).
 * @param[out] voltage TEC voltage in volts (V).
 * @param[out] current TEC current in amps (A).
 * @param[out] resistance TEC resistance in Ohms.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the TEC parameters.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully retrieves TEC parameters.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat controller is not yet initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the index for bTec is outside range.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system is not properly able to read TEC data.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetAllTecParams(uint8_t bTec, float *voltage, float *current,
                                              float *resistance);

/**
 * @brief Retrieves the trigger pulse's wavelength width.
 *
 * @param[out] wlTrigWidth_us Value of the width in microseconds (us).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the wavelength trigger pulse
 * width.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully retrieves the wavelength trigger pulse width.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system is unable to read the wavelength trigger pulse width.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetWlTrigPulseWidth(uint16_t *wlTrigWidth_us);

/**
 * @brief Sets the trigger pulse's wavelength width.
 *
 * @param wlTrigWidth_us Value of the width in microseconds (us).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of setting the wavelength trigger pulse width.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully sets the wavelength trigger pulse width.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system is unable to set the wavelength trigger pulse width.
 */
MIRCAT_LIB uint32_t MIRcatSDK_SetWlTrigPulseWidth(uint16_t wlTrigWidth_us);

/**
 * @brief Toggles whether the red laser pointer is enabled or not.
 *
 * @param enable Determines whether the laser pointer is on (enable == true) or off (enable == false).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of toggling the red laser pointer.
 * @retval #MIRcatSDK_RET_SUCCESS if the laser has been successfully toggled.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system is unable to communicate with the red laser pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_EnableRedLaserPointer(bool enable);

/**
 * @brief Retrieves the original/factory crossover values for a certain QCL channel.
 *
 * @param chan Channel to get crossover value from (starting index 1).
 * @param[out] wlCrossover_um The wavelength value at the crossover in micrometers (um).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the factory crossover value.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully retrieves the factory crossover value.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if wlCrossover_um is a null pointer.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the chan value is out of range of the channels.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system is unable to read the factory crossover value.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetFactoryCrossover(uint8_t chan, float *wlCrossover_um);

/**
 * @brief Retrieves the user set crossover values for a certain QCL channel.
 *
 * @param chan The QCL channel to get crossover from (indexed from 1).
 * @param[out] wlCrossover_um The wavelength value at the crossover in micrometers (um).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the user crossover value.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully retrieves the user crossover value.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if wlCrossover_um is a null pointer.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the chan value is out of range of the channels.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system is unable to read user crossover.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetUserCrossover(uint8_t chan, float *wlCrossover_um);

/**
 * @brief Sets user crossover values for a certain channel
 *
 * @param chan The QCL channel to get crossover from (indexed from 1).
 * @param wlCrossover_um The wavelength value at the crossover in micrometers (um)
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of setting user crossover values.
 * @retval #MIRcatSDK_RET_SUCCESS if the system successfully set the user crossover value.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the chan value is out of range of the channels.
 * @retval #MIRcatSDK_RET_COMM_ERROR if the system is unable to set user crossover.
 */
MIRCAT_LIB uint32_t MIRcatSDK_SetUserCrossover(uint8_t chan, float wlCrossover_um);

/** @} End of WavelengthTriggersFunctions */

//-------------------------------------------------------------------------------------------------------------------------------------------//
//-------------------------------------------------------------------------------------------------------------------------------------------//
//-------------------------------------------------------------------------------------------------------------------------------------------//

/**
 * @defgroup PointingControlFunctions Pointing Control Functions
 * @brief Functions that help control laser position/angles.
 * @{
 */

/** @brief Maximum tables per channel */
#define MIRCATSDK_POINTING_MAX_TABLES_PER_CHANNEL 8
/** @brief Maximum table name length */
#define MIRCATSDK_POINTING_TABLE_NAME_LEN_MAX     32
/** @brief Maximum calibration entries per table */
#define MIRCATSDK_MAX_CAL_ENTRIES_PER_TABLE       1024

/**
 * @brief Checks if the system supports MIRcat-QT-Z pointing controls.
 *
 * @param[out] enabled Indicates if the system supports pointing controls (MIRcat-QT-Z).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of checking whether pointing controls are
 * supported.
 * @retval #MIRcatSDK_RET_SUCCESS if the system supports pointing controls.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER *[User Error]* if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingControlsSupported(bool *enabled);

// Get/Set Pointing Compensation Enabled

/**
 * @brief Checks if pointing compensation is enabled.
 *
 * @note If pointing compensation is enabled, it will use the pointing calibration table to "flatten" out the
 * pointing vs. wavelength.
 *
 * @param[out] xEnabled Indicates if the X axis pointing compensation is enabled.
 * @param[out] yEnabled Indicates if the Y axis pointing compensation is enabled.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of getting whether compensation is enabled.
 * @retval #MIRcatSDK_RET_SUCCESS if the pointing compensation status is successfully retrieved.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER *[User Error]* if any of the out parameters are null pointers.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingGetCompensationEnabled(bool *xEnabled, bool *yEnabled);

/**
 * @brief Enables or disables pointing compensation.
 *
 * @note If pointing compensation is enabled, it will use the pointing calibration table to "flatten" out the
 * pointing vs. wavelength.
 *
 * @param enableX Used to enable/disable X axis pointing compensation.
 * @param enableY Used to enable/disable Y axis pointing compensation.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of enabling pointing compensation.
 * @retval #MIRcatSDK_RET_SUCCESS if the pointing compensation status is successfully set.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingCompensationEnable(bool enableX, bool enableY);

/**
 * @brief Commands MIRcat-QT-Z pointing system to go to X/Y position.
 *
 * @attention Pointing compensation should be disabled prior to commanding positions with this function.
 *
 * @param xCounts Target x position in counts.
 * @param yCounts Target y position in counts.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of positioning.
 * @retval #MIRcatSDK_RET_SUCCESS if the position is successfully set.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingGoToPosition(int xCounts, int yCounts);

/**
 * @brief Gets the current position of the pointing system.
 *
 * @param[out] xCounts Current x position in counts.
 * @param[out] yCounts Current y position in counts.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the position.
 * @retval #MIRcatSDK_RET_SUCCESS if the position is successfully retrieved.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingGetPosition(int *xCounts, int *yCounts);

/**
 * @brief Gets the laser channel that the pointing system is outputting.
 *
 * @param[out] chan Laser channel for which the pointing system is outputting (indexed at 0).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the active channel.
 * @retval #MIRcatSDK_RET_SUCCESS if the active channel is successfully retrieved.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingGetActiveChannel(uint8_t *chan);

/**
 * @brief Sets the laser channel that the pointing system is outputting.
 *
 * @param chan Laser channel to output with the pointing system (indexed at 0).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of setting the active channel.
 * @retval #MIRcatSDK_RET_SUCCESS if the active channel is successfully set.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the channel value is out of range of the channels.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingSetActiveChannel(uint8_t chan);

/**
 * @brief Gets the active base position for the given laser channel in counts.
 *
 * @param chan Laser channel to query the base position of (indexed at 0).
 * @param[out] baseX X position in counts of the base position for this channel.
 * @param[out] baseY Y position in counts of the base position for this channel.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the active base position.
 * @retval #MIRcatSDK_RET_SUCCESS if the base position is successfully retrieved.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the channel value is out of range of the channels.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 * @retval #MIRcatSDK_RET_POINTING_NOT_SUPPORTED if pointing is not supported.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingGetActiveBasePosition(uint8_t chan, int *baseX, int *baseY);

/**
 * @brief Sets the active base position for the given laser channel in counts.
 *
 * @param chan Laser channel to set the base position for (indexed at 0).
 * @param baseX X position in counts of the base position for this channel.
 * @param baseY Y position in counts of the base position for this channel.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of setting the active base position.
 * @retval #MIRcatSDK_RET_SUCCESS if the base position is successfully set.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the channel value is out of range of the channels.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 * @retval #MIRcatSDK_RET_POINTING_NOT_SUPPORTED if pointing is not supported.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingSetActiveBasePosition(uint8_t chan, int baseX, int baseY);

/**
 * @brief Gets the active base position for the given laser channel in milliRadians (mRad).
 *
 * @param chan Laser channel to query the base position of (indexed at 0).
 * @param[out] baseX X position in mRads of the angle offset for this channel.
 * @param[out] baseY Y position in mRads of the angle offset for this channel.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of getting the active base position in mRad.
 * @retval #MIRcatSDK_RET_SUCCESS if the base position is successfully retrieved.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the channel value is out of range of the channels.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 * @retval #MIRcatSDK_RET_POINTING_NOT_SUPPORTED if pointing is not supported.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingGetActiveBasePositionMilliRadians(uint8_t chan, float *baseX,
                                                                        float *baseY);

/**
 * @brief Sets the active base position for the given laser.
 *
 * @param chan Laser channel to query the base position of (indexed at 0).
 * @param baseX X position in mRads of the angle offset for this channel.
 * @param baseY Y position in mRads of the angle offset for this channel.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of setting the active base position in
 * milliRadians (mRad).
 * @retval #MIRcatSDK_RET_SUCCESS if the base position is successfully set.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the channel value is out of range of the channels.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 * @retval #MIRcatSDK_RET_POINTING_NOT_SUPPORTED if pointing is not supported.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingSetActiveBasePositionMilliRadians(uint8_t chan, float baseX,
                                                                        float baseY);

/**
 * @brief Gets the factory base position for the given laser channel.
 *
 * @param chan Laser channel to query the base position of.
 * @param[out] baseX X position in counts of the base position for this channel.
 * @param[out] baseY Y position in counts of the base position for this channel.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of getting the factory base position.
 * @retval #MIRcatSDK_RET_SUCCESS if the factory base position is successfully retrieved.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the channel value is out of range of the channels.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 * @retval #MIRcatSDK_RET_POINTING_NOT_SUPPORTED if pointing is not supported.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingGetFactoryBasePosition(uint8_t chan, int *baseX, int *baseY);

/**
 * @brief Reads the calibration table information for the requested calibration table.
 *
 * @param chan Laser channel for this calibration table.
 * @param tableNum Table number for this calibration table. There are up to 8 tables per channel (indexed
 * 0-7).
 * @param[out] tableExists Indicates if a calibration table exists for this channel/table number.
 * @param[out] numEntries The number of calibration entries in this calibration table.
 * @param[out] wlUnits Wavelength units used for this calibration table (see cal table format for wavelength
 * units).
 * @param[out] laserMode Laser mode used for this calibration table (see cal table format for laser mode).
 * @param[out] tableName Table name for this table. tableName should point to a char array of at least 32
 * characters.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of reading the calibration table information.
 * @retval #MIRcatSDK_RET_SUCCESS if the calibration table information is successfully read.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the channel value is out of range of the channels.
 * @retval #MIRcatSDK_RET_TABLE_NUM_OUT_OF_RANGE if the table number is out of range.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 * @retval #MIRcatSDK_RET_STRCPY_ERROR if there is a string copy error.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingReadCalTableInfo(uint8_t chan, uint8_t tableNum, bool *tableExists,
                                                       uint16_t *numEntries, uint8_t *wlUnits,
                                                       uint8_t *laserMode, char *tableName);

/**
 * @brief Exports the calibration table for a specified channel/table number.
 *
 * @param chan Laser channel for this calibration table.
 * @param tableNum Table number for this calibration table. There are up to 8 tables per channel (indexed
 * 0-7).
 * @param[out] numEntries The number of calibration entries in this calibration table.
 * @param[out] wavelengths Array of wavelengths for this calibration table. Caller should allocate an array of
 * 1024 elements (max table entries) to pass in.
 * @param[out] xCal Array of x calibration offsets for this calibration table. Caller should allocate an array
 * of 1024 elements (max table entries) to pass in.
 * @param[out] yCal Array of y calibration offsets for this calibration table. Caller should allocate an array
 * of 1024 elements (max table entries) to pass in.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of exporting the calibration table.
 * @retval #MIRcatSDK_RET_SUCCESS if the calibration table is successfully exported.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the channel value is out of range of the channels.
 * @retval #MIRcatSDK_RET_TABLE_NUM_OUT_OF_RANGE if the table number is out of range.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingExportCalTable(uint8_t chan, uint8_t tableNum, uint16_t *numEntries,
                                                     float *wavelengths, int32_t *xCal, int32_t *yCal);

/**
 * @brief Imports the calibration table for a specified channel/table number.
 *
 * @attention Table number 0 is typically used as the factory calibration table. This function does not allow
 * the user to import a calibration table as table number 0 to prevent the factory calibration from being
 * overwritten.
 *
 * @param chan Laser channel for this calibration table (index starting at 1).
 * @param tableNum Table number for this calibration table. There are up to
 * #MIRCATSDK_POINTING_MAX_TABLES_PER_CHANNEL tables per channel (indexed 0-7).
 * @param numEntries The number of calibration entries in this calibration table.
 * @param wlUnits The wavelength units used for this calibration table (see cal table format for wavelength
 * units; #MIRcatSDK_UNITS_MICRONS and #MIRcatSDK_UNITS_CM1).
 * @param laserMode Laser mode for this calibration table (see cal table format for laser mode units).
 * @param tableName A name for the calibration table (max character length of 31).
 * @param wavelengths Array of wavelengths for this calibration table. The size of the array should match @p
 * numEntries.
 * @param xCal Array of x calibration offsets for this calibration table. The size of the array should match
 * @p numEntries.
 * @param yCal Array of y calibration offsets for this calibration table. The size of the array should match
 * @p numEntries.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of importing the calibration table.
 * @retval #MIRcatSDK_RET_SUCCESS if the calibration table is successfully imported.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the in parameters are null pointers.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the channel value is out of range of the channels.
 * @retval #MIRcatSDK_RET_TABLE_NUM_OUT_OF_RANGE if the table number is out of range.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingImportCalTable(uint8_t chan, uint8_t tableNum, uint16_t numEntries,
                                                     uint8_t wlUnits, uint8_t laserMode, char *tableName,
                                                     float *wavelengths, int32_t *xCal, int32_t *yCal);

/**
 * @brief Activates a specific pointing calibration table.
 *
 * @param chan Laser channel for this calibration table.
 * @param tableNum Table number for this calibration table. There are up to
 * MIRCATSDK_POINTING_MAX_TABLES_PER_CHANNEL tables per channel (indexed 0-7).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of activating the calibration table.
 * @retval #MIRcatSDK_RET_SUCCESS if the calibration table is successfully activated.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the channel value is out of range of the channels.
 * @retval #MIRcatSDK_RET_TABLE_NUM_OUT_OF_RANGE if the table number is out of range.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingActivateCalTable(uint8_t chan, uint8_t tableNum);

/**
 * @brief Gets the active pointing calibration table for a given channel.
 *
 * If no table has been activated, this will return MIRCATSDK_POINTING_MAX_TABLES_PER_CHANNEL.
 *
 * @param chan Laser channel for this calibration table.
 * @param[out] tableNum Table number for this calibration table. There are up to
 * MIRCATSDK_POINTING_MAX_TABLES_PER_CHANNEL tables per channel (indexed 0-7). If no table is active, this
 * will return MIRCATSDK_POINTING_MAX_TABLES_PER_CHANNEL.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of getting the active calibration table.
 * @retval #MIRcatSDK_RET_SUCCESS if the active calibration table is successfully retrieved.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_POINTING_NOT_SUPPORTED if pointing is not supported.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if any of the out parameters are null pointers.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the channel value is out of range of the channels.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingGetActiveCalTable(uint8_t chan, uint8_t *tableNum);

/**
 * @brief Deletes a specific pointing calibration table.
 *
 * @attention Table number 0 is typically used as the factory calibration table. This function does not allow
 * the user to delete calibration table 0.
 *
 * @param chan Laser channel for this calibration table.
 * @param tableNum Table number for this calibration table. There are up to
 * MIRCATSDK_POINTING_MAX_TABLES_PER_CHANNEL tables per channel (indexed 0-7).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of deleting the calibration table.
 * @retval #MIRcatSDK_RET_SUCCESS if the calibration table is successfully deleted.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the system is not initialized.
 * @retval #MIRcatSDK_RET_QCL_NUM_OUTOFRANGE if the channel value is out of range of the channels.
 * @retval #MIRcatSDK_RET_TABLE_NUM_OUT_OF_RANGE if the table number is out of range.
 * @retval #MIRcatSDK_RET_COMM_ERROR if there is a communication error.
 */
MIRCAT_LIB uint32_t MIRcatSDK_PointingDeleteCalTable(uint8_t chan, uint8_t tableNum);

/**
 * @brief Converts encoder counts to milliradians (mRad).
 *
 * @param counts The count that will be converted.
 * @param[out] milliRadians The converted count to milliradians value.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of the conversion.
 * @retval #MIRcatSDK_RET_SUCCESS if the counts are successfully converted to milliradians.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_ConvertCountsToMilliRadians(int32_t counts, float *milliRadians);

/**
 * @brief Converts milliradians (mRad) to encoder counts.
 *
 * @param milliRadians The milliradians that will be converted.
 * @param[out] counts The converted milliradians to encoder counts.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of the conversion.
 * @retval #MIRcatSDK_RET_SUCCESS if the milliradians are successfully converted to counts.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_ConvertMilliRadiansToCounts(float milliRadians, int32_t *counts);

/**
 * @brief Retrieves the current admin mode.
 *
 * @param[out] adminMode Boolean flag indicating whether the user is in admin mode.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of retrieving the admin mode.
 * @retval #MIRcatSDK_RET_SUCCESS if the admin mode is successfully retrieved.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the out parameter is a null pointer.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetAdminMode(bool *adminMode);

/**
 * @brief Sets admin mode. Admin mode is required for deleting factory pointing calibrations.
 *
 * @param password User's inputted password.
 * @param adminMode Boolean that sets the current adminMode (true to enable adminMode).
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of setting the admin mode.
 * @retval #MIRcatSDK_RET_SUCCESS if the password is correct and successfully toggled the adminMode.
 * @retval #MIRcatSDK_RET_ADMIN_PASSWORD_INCORRECT if the admin password is incorrect.
 */
MIRCAT_LIB uint32_t MIRcatSDK_SetAdminMode(int32_t password, bool adminMode);

/**
 * @brief Gets the external pre-triggering state.
 *
 * @param[out] enabled Boolean flag denoting whether external pre-trigger mode is enabled.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of getting the external pre-triggering state.
 * @retval #MIRcatSDK_RET_SUCCESS if the external pre-trigger mode is successfully retrieved.
 * @retval #MIRcatSDK_RET_PASSED_NULL_POINTER if the enabled parameter is a null pointer.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat system is not initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if unable to read the current external pre trigger mode.
 */
MIRCAT_LIB uint32_t MIRcatSDK_GetExtPreTrigMode(bool *enabled);

/**
 * @brief Sets the External Pre Trigger mode.
 *
 * if (enabled == true): Pre-trigger is the inverse to trigger (pre-trigger on whilst trigger is off;
 * pre-trigger off whilst trigger is on). if (enabled == false): Pre-trigger acts accordingly to internal
 * laser settings.
 *
 * @param enabled Boolean flag indicating whether external pre-trigger mode should be enabled.
 *
 * @return @ref ReturnCodes "Return Code" indicating the status of setting the external pre-trigger mode.
 * @retval #MIRcatSDK_RET_SUCCESS if the external pre-trigger mode is successfully set.
 * @retval #MIRcatSDK_RET_NOT_INITIALIZED if the MIRcat system is not initialized.
 * @retval #MIRcatSDK_RET_COMM_ERROR if unable to write the current external pre trigger mode.
 */
MIRCAT_LIB uint32_t MIRcatSDK_SetExtPreTrigMode(bool enabled);

/** @} End of PointingControlFunctions */

/** @} End of Functions */

#ifdef __cplusplus
}
#endif

#endif // _MIRcatSDK_H_
