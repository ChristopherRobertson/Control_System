import axios from 'axios'

export const API_BASE = '/api/zurich_hf2li'

export interface HF2Status {
  connected: boolean
  server_connected: boolean
  host?: string
  data_server_port?: number
  api_level?: number
  device_id?: string
  server_version?: string
  device_present?: boolean
  last_error?: string | null
}

export class HF2API {
  static async status(): Promise<HF2Status> {
    return (await axios.get(`${API_BASE}/status`)).data as HF2Status
  }
  static async connect() {
    return (await axios.post(`${API_BASE}/connect`)).data as any
  }
  static async disconnect() {
    return (await axios.post(`${API_BASE}/disconnect`)).data as any
  }
  static async getNodes(paths: string[]): Promise<Record<string, any>> {
    return (await axios.post(`${API_BASE}/nodes/get`, { paths })).data as any
  }
  static async setNodes(settings: { path: string, value: any }[]): Promise<Record<string, any>> {
    return (await axios.post(`${API_BASE}/nodes/set`, { settings })).data as any
  }
}

export default HF2API

