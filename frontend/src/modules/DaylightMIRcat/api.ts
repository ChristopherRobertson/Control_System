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
  tuned: boolean
  temperature_stable: boolean
  scan_in_progress: boolean
  current_scan_mode: string | null
  last_error: string | null
  last_error_code: number | null
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
    tuned: boolean
    armed: boolean
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

export interface SweepScanRequest {
  start_wavenumber: number
  end_wavenumber: number
  scan_speed: number
  number_of_scans: number
  bidirectional_scanning: boolean
}

export interface StepScanRequest {
  start_wavenumber: number
  end_wavenumber: number
  step_size: number
  dwell_time: number
  number_of_scans: number
}

export interface MultispectralEntry {
  wavenumber: number
  dwell_time: number
  off_time: number
}

export interface MultispectralScanRequest {
  wavelength_list: MultispectralEntry[]
  number_of_scans: number
  keep_laser_on_between_steps: boolean
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

  /**
   * Start sweep scan
   */
  static async startSweepScan(params: SweepScanRequest): Promise<{ message: string; scan_mode: string; parameters: any }> {
    const response = await axios.post(`${API_BASE}/scan/sweep/start`, params)
    return response.data
  }

  /**
   * Start step scan
   */
  static async startStepScan(params: StepScanRequest): Promise<{ message: string; scan_mode: string; parameters: any }> {
    const response = await axios.post(`${API_BASE}/scan/step/start`, params)
    return response.data
  }

  /**
   * Start multispectral scan
   */
  static async startMultispectralScan(params: MultispectralScanRequest): Promise<{ message: string; scan_mode: string; parameters: any }> {
    const response = await axios.post(`${API_BASE}/scan/multispectral/start`, params)
    return response.data
  }

  /**
   * Stop any active scan
   */
  static async stopScan(): Promise<{ message: string; scan_in_progress: boolean }> {
    const response = await axios.post(`${API_BASE}/scan/stop`)
    return response.data
  }
}