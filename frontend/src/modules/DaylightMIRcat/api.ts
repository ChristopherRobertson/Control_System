/**
 * API client for Daylight MIRcat device communication
 */

import axios from 'axios'

const API_BASE = '/api/daylight_mircat'

export interface DeviceStatus {
  connected: boolean
  armed: boolean
  emission_on: boolean
  current_wavenumber: number
  current_qcl: number
  laser_mode: string
  status: {
    interlocks: boolean
    key_switch: boolean
    temperature: boolean
    connected: boolean
    emission: boolean
    pointing_correction: boolean
    system_fault: boolean
    case_temp_1: number
    case_temp_2: number
    pcb_temperature: number
  }
}

export interface TuneRequest {
  wavenumber: number
}

export interface LaserModeRequest {
  mode: string
}

export interface PulseParametersRequest {
  pulse_rate: number
  pulse_width: number
}

export class MIRcatAPI {
  /**
   * Connect to MIRcat device
   */
  static async connect(): Promise<{ message: string; connected: boolean }> {
    const response = await axios.post(`${API_BASE}/connect`)
    return response.data
  }

  /**
   * Disconnect from MIRcat device
   */
  static async disconnect(): Promise<{ message: string; connected: boolean }> {
    const response = await axios.post(`${API_BASE}/disconnect`)
    return response.data
  }

  /**
   * Arm the laser for operation
   */
  static async armLaser(): Promise<{ message: string; armed: boolean }> {
    const response = await axios.post(`${API_BASE}/arm`)
    return response.data
  }

  /**
   * Disarm the laser
   */
  static async disarmLaser(): Promise<{ message: string; armed: boolean }> {
    const response = await axios.post(`${API_BASE}/disarm`)
    return response.data
  }

  /**
   * Turn laser emission on
   */
  static async turnEmissionOn(): Promise<{ message: string; emission_on: boolean }> {
    const response = await axios.post(`${API_BASE}/emission/on`)
    return response.data
  }

  /**
   * Turn laser emission off
   */
  static async turnEmissionOff(): Promise<{ message: string; emission_on: boolean }> {
    const response = await axios.post(`${API_BASE}/emission/off`)
    return response.data
  }

  /**
   * Tune laser to specific wavenumber
   */
  static async tuneToWavenumber(wavenumber: number): Promise<{ message: string; wavenumber: number }> {
    const response = await axios.post(`${API_BASE}/tune`, { wavenumber })
    return response.data
  }

  /**
   * Set laser operation mode
   */
  static async setLaserMode(mode: string): Promise<{ message: string; mode: string }> {
    const response = await axios.post(`${API_BASE}/mode`, { mode })
    return response.data
  }

  /**
   * Set pulse parameters for pulsed mode
   */
  static async setPulseParameters(pulse_rate: number, pulse_width: number): Promise<{ message: string; pulse_rate: number; pulse_width: number }> {
    const response = await axios.post(`${API_BASE}/pulse-parameters`, { pulse_rate, pulse_width })
    return response.data
  }

  /**
   * Get current device status
   */
  static async getStatus(): Promise<DeviceStatus> {
    const response = await axios.get(`${API_BASE}/status`)
    return response.data
  }

  /**
   * Get device configuration parameters
   */
  static async getConfig(): Promise<any> {
    const response = await axios.get(`${API_BASE}/config`)
    return response.data
  }
}