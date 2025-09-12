import axios from 'axios'

const API_BASE = '/api/quantum_composers_9524'

export interface DeviceStatus {
  connected: boolean
  running: boolean
  system_settings: Record<string, any>
  channels: Record<string, any>
  external_trigger: Record<string, any>
  device_info: Record<string, any>
}

export class QuantumComposersAPI {
  static async connect() {
    const response = await axios.post(`${API_BASE}/connect`)
    return response.data
  }

  static async disconnect() {
    const response = await axios.post(`${API_BASE}/disconnect`)
    return response.data
  }

  static async start() {
    const response = await axios.post(`${API_BASE}/start`)
    return response.data
  }

  static async stop() {
    const response = await axios.post(`${API_BASE}/stop`)
    return response.data
  }

  static async setSystemConfig(config: Record<string, any>) {
    const response = await axios.post(`${API_BASE}/system`, { config })
    return response.data
  }

  static async setChannelConfig(channel: string, config: Record<string, any>) {
    const response = await axios.post(`${API_BASE}/channel`, { channel, config })
    return response.data
  }

  static async setExternalTriggerConfig(config: Record<string, any>) {
    const response = await axios.post(`${API_BASE}/external-trigger`, { config })
    return response.data
  }

  static async sendCommand(command: string) {
    const response = await axios.post(`${API_BASE}/command`, { command })
    return response.data
  }

  static async getStatus(): Promise<DeviceStatus> {
    const response = await axios.get(`${API_BASE}/status`)
    return response.data
  }
}

export default QuantumComposersAPI
