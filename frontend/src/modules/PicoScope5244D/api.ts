/**
 * API client for PicoScope 5244D oscilloscope
 */

import axios from 'axios'

const API_BASE = '/api/picoscope_5244d'

export interface ChannelConfig {
  enabled: boolean
  range: string
  coupling: string
  offset?: number
}

export interface DeviceStatus {
  connected: boolean
  acquiring: boolean
  channels: Record<string, ChannelConfig>
  timebase: Record<string, any>
  trigger: Record<string, any>
}

export class PicoScopeAPI {
  static async connect(): Promise<DeviceStatus> {
    const response = await axios.post(`${API_BASE}/connect`)
    return response.data
  }

  static async disconnect(): Promise<DeviceStatus> {
    const response = await axios.post(`${API_BASE}/disconnect`)
    return response.data
  }

  static async startAcquisition(): Promise<DeviceStatus> {
    const response = await axios.post(`${API_BASE}/start`)
    return response.data
  }

  static async stopAcquisition(): Promise<DeviceStatus> {
    const response = await axios.post(`${API_BASE}/stop`)
    return response.data
  }

  static async autoSetup(): Promise<DeviceStatus> {
    const response = await axios.post(`${API_BASE}/auto-setup`)
    return response.data
  }

  static async setChannelConfig(channel: string, config: Partial<ChannelConfig>): Promise<DeviceStatus> {
    const response = await axios.post(`${API_BASE}/channel`, { channel, config })
    return response.data
  }

  static async setTimebaseConfig(config: Record<string, any>): Promise<DeviceStatus> {
    const response = await axios.post(`${API_BASE}/timebase`, { config })
    return response.data
  }

  static async setTriggerConfig(config: Record<string, any>): Promise<DeviceStatus> {
    const response = await axios.post(`${API_BASE}/trigger`, { config })
    return response.data
  }

  static async getStatus(): Promise<DeviceStatus> {
    const response = await axios.get(`${API_BASE}/status`)
    return response.data
  }
}

export default PicoScopeAPI
