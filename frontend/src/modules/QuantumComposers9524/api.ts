import axios from 'axios'

export const API_BASE = '/api/quantum_composers_9524'

export type QCChannelKey = 'A' | 'B' | 'C' | 'D'

export interface QCSystemSettings {
  pulse_mode: 'Continuous' | 'Burst' | 'Single'
  burst_count: number
  auto_start: boolean
  duty_cycle_on_counts: number
  duty_cycle_off_counts: number
}

export interface QCChannelSettings {
  enabled: boolean
  delay_s: number
  width_s: number
  channel_mode: 'Normal' | 'Invert'
  sync_source: string
  duty_on: number
  duty_off: number
  burst_count: number
  polarity: 'Normal' | 'Invert'
  output_mode: string
  amplitude_v: number
  wait_count: number
  multiplexer: Record<QCChannelKey, boolean>
  gate_mode: 'Disabled' | 'Enabled'
}

export interface QCExternalTrigger {
  trigger_mode: 'Disabled' | 'Enabled'
  trigger_edge: 'Rising' | 'Falling'
  trigger_threshold_v: number
  gate_mode: 'Disabled' | 'Enabled'
  gate_logic: 'High' | 'Low'
  gate_threshold_v: number
}

export interface QCStatus {
  connected: boolean
  running: boolean
  system_settings: QCSystemSettings
  channels: Record<QCChannelKey, QCChannelSettings>
  external_trigger: QCExternalTrigger
  device_info: Record<string, any>
  ranges?: Record<string, number>
  last_error?: string | null
}

export class QuantumComposersAPI {
  static async connect() {
    return (await axios.post(`${API_BASE}/connect`)).data as any
  }
  static async disconnect() {
    return (await axios.post(`${API_BASE}/disconnect`)).data as any
  }
  static async start() {
    return (await axios.post(`${API_BASE}/start`)).data as any
  }
  static async stop() {
    return (await axios.post(`${API_BASE}/stop`)).data as any
  }
  static async setSystem(config: Partial<QCSystemSettings>) {
    return (await axios.post(`${API_BASE}/system`, { config })).data as any
  }
  static async setChannel(channel: QCChannelKey, config: Partial<QCChannelSettings>) {
    return (await axios.post(`${API_BASE}/channel`, { channel, config })).data as any
  }
  static async setExternal(config: Partial<QCExternalTrigger>) {
    return (await axios.post(`${API_BASE}/external-trigger`, { config })).data as any
  }
  static async sendCommand(command: string) {
    return (await axios.post(`${API_BASE}/command`, { command })).data as any
  }
  static async getStatus(): Promise<QCStatus> {
    return (await axios.get(`${API_BASE}/status`)).data as QCStatus
  }
  static async getConfig() {
    return (await axios.get(`${API_BASE}/config`)).data as any
  }
}

export default QuantumComposersAPI
