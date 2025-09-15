export type ChannelName = 'A' | 'B'

export interface ChannelConfig {
  enabled: boolean
  range: string
  coupling: 'AC' | 'DC'
  offset: number
  bandwidth_limiter?: boolean
  invert?: boolean
}

export interface TimebaseConfig {
  time_per_div: string
  n_samples: number
  sample_rate_hz: number
}

export type TriggerSource = ChannelName | 'Ext'

export interface TriggerConfig {
  mode?: 'None' | 'Auto' | 'Single'
  source: TriggerSource
  level_v: number
  edge: 'Rising' | 'Falling'
  enabled: boolean
}

export interface AwgConfig {
  enabled: boolean
  shape: 'Sine' | 'Square' | 'Triangle' | 'DC'
  frequency_hz: number
  amplitude_vpp: number
  offset_v: number
}

export interface PicoScopeStatus {
  connected: boolean
  acquiring: boolean
  resolution_bits: number
  waveform_count: number
  channels: Record<ChannelName, ChannelConfig>
  timebase: TimebaseConfig
  trigger: TriggerConfig
  awg: AwgConfig
  model?: string
  serial?: string
  driver_version?: string
  transport?: string
  last_error?: string | null
  last_error_code?: number | null
}

const base = '/api/picoscope_5244d'

async function http<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${base}${path}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  connect: () => http<PicoScopeStatus & { message: string }>(`/connect`, { method: 'POST' }),
  disconnect: () => http<PicoScopeStatus & { message: string }>(`/disconnect`, { method: 'POST' }),
  status: () => http<PicoScopeStatus>(`/status`),
  setResolution: (bits: number) => http<PicoScopeStatus & { message: string }>(`/resolution`, { method: 'POST', body: JSON.stringify({ bits }) }),
  setWaveformCount: (count: number) => http<PicoScopeStatus & { message: string }>(`/waveform_count`, { method: 'POST', body: JSON.stringify({ count }) }),
  setChannel: (channel: ChannelName, config: Partial<ChannelConfig>) => http<PicoScopeStatus & { message: string }>(`/channel`, { method: 'POST', body: JSON.stringify({ channel, config }) }),
  setTimebase: (config: Partial<TimebaseConfig>) => http<PicoScopeStatus & { message: string }>(`/timebase`, { method: 'POST', body: JSON.stringify({ config }) }),
  setTrigger: (config: Partial<TriggerConfig>) => http<PicoScopeStatus & { message: string }>(`/trigger`, { method: 'POST', body: JSON.stringify({ config }) }),
  setAwg: (config: Partial<AwgConfig>) => http<PicoScopeStatus & { message: string }>(`/awg`, { method: 'POST', body: JSON.stringify({ config }) }),
  zeroOffset: (channel: ChannelName) => http<PicoScopeStatus & { message: string }>(`/channel/zero_offset`, { method: 'POST', body: JSON.stringify({ channel }) }),
  autosetup: () => http<PicoScopeStatus & { message: string }>(`/autosetup`, { method: 'POST' }),
  run: () => http<PicoScopeStatus & { message: string }>(`/run`, { method: 'POST' }),
  stop: () => http<PicoScopeStatus & { message: string }>(`/stop`, { method: 'POST' }),
  acquirePreview: () => http<PicoScopeStatus & { message: string; result: { samples: number; time_interval_ns: number; waveforms: Record<string, number[]> } }>(`/acquire_preview`, { method: 'POST' }),
}
