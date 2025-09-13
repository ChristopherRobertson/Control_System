import { useEffect, useRef, useState } from 'react'
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Chip,
  Alert
} from '@mui/material'
import {
  PlayArrow as StartIcon,
  Stop as StopIcon,
  SettingsApplications as AutoSetupIcon,
  Memory as ScopeIcon
} from '@mui/icons-material'
import PicoScopeAPI, { ChannelConfig } from './api'

type ChannelsState = Record<'A' | 'B' | 'C' | 'D', ChannelConfig>

function PicoScope5244DView() {
  const [connected, setConnected] = useState(false)
  const [acquiring, setAcquiring] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [channels, setChannels] = useState<ChannelsState>({
    A: { enabled: true, range: '±2V', coupling: 'DC' },
    B: { enabled: true, range: '±2V', coupling: 'DC' },
    C: { enabled: false, range: '±2V', coupling: 'DC' },
    D: { enabled: false, range: '±2V', coupling: 'DC' }
  })
  const wsRef = useRef<WebSocket | null>(null)
  const [deviceInfo, setDeviceInfo] = useState<{ model?: string; serial?: string; driver_version?: string } | null>(null)

  const handleConnect = async () => {
    setLoading(true)
    try {
      const status = await PicoScopeAPI.connect()
      setConnected(status.connected)
      setAcquiring(status.acquiring)
      setDeviceInfo({ model: status.model, serial: status.serial, driver_version: status.driver_version })
      setError(null)
    } catch (err) {
      setError('Failed to connect to PicoScope')
    } finally {
      setLoading(false)
    }
  }

  const handleDisconnect = async () => {
    setLoading(true)
    try {
      const status = await PicoScopeAPI.disconnect()
      setConnected(status.connected)
      setAcquiring(status.acquiring)
      setDeviceInfo(null)
      setError(null)
    } catch (err) {
      setError('Failed to disconnect from PicoScope')
    } finally {
      setLoading(false)
    }
  }

  const handleAutoSetup = async () => {
    setLoading(true)
    try {
      await PicoScopeAPI.autoSetup()
      setError(null)
    } catch (err) {
      setError('Auto setup failed')
    } finally {
      setLoading(false)
    }
  }

  const handleStartAcquisition = async () => {
    setLoading(true)
    try {
      const status = await PicoScopeAPI.startAcquisition()
      setAcquiring(status.acquiring)
      setError(null)
    } catch (err) {
      setError('Failed to start acquisition')
    } finally {
      setLoading(false)
    }
  }

  const handleStopAcquisition = async () => {
    setLoading(true)
    try {
      const status = await PicoScopeAPI.stopAcquisition()
      setAcquiring(status.acquiring)
      setError(null)
    } catch (err) {
      setError('Failed to stop acquisition')
    } finally {
      setLoading(false)
    }
  }

  // Helpers to call backend on UI changes
  const updateChannel = async (ch: 'A'|'B'|'C'|'D', cfg: Partial<ChannelConfig>) => {
    if (!connected) return
    setLoading(true)
    try {
      const status = await PicoScopeAPI.setChannelConfig(ch, cfg)
      setChannels(prev => ({ ...prev, [ch]: { ...prev[ch], ...cfg } }))
      setConnected(status.connected)
      setAcquiring(status.acquiring)
      setDeviceInfo({ model: status.model, serial: status.serial, driver_version: status.driver_version })
    } catch (e) {
      setError(`Failed to configure channel ${ch}`)
    } finally {
      setLoading(false)
    }
  }

  const setTimebase = async (cfg: Record<string, any>) => {
    if (!connected) return
    setLoading(true)
    try {
      const status = await PicoScopeAPI.setTimebaseConfig(cfg)
      setConnected(status.connected)
      setAcquiring(status.acquiring)
      setDeviceInfo({ model: status.model, serial: status.serial, driver_version: status.driver_version })
    } catch (e) {
      setError('Failed to set timebase')
    } finally {
      setLoading(false)
    }
  }

  const setTrigger = async (cfg: Record<string, any>) => {
    if (!connected) return
    setLoading(true)
    try {
      const status = await PicoScopeAPI.setTriggerConfig(cfg)
      setConnected(status.connected)
      setAcquiring(status.acquiring)
      setDeviceInfo({ model: status.model, serial: status.serial, driver_version: status.driver_version })
    } catch (e) {
      setError('Failed to set trigger')
    } finally {
      setLoading(false)
    }
  }

  // WebSocket subscription for live status
  useEffect(() => {
    if (!connected) {
      if (wsRef.current) { try { wsRef.current.close() } catch {} wsRef.current = null }
      return
    }
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    const ws = new WebSocket(`${scheme}://${host}/ws/picoscope_5244d`)
    wsRef.current = ws
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data)
        if (msg?.type === 'status' && msg?.payload) {
          const st = msg.payload
          setConnected(!!st.connected)
          setAcquiring(!!st.acquiring)
          setDeviceInfo({ model: st.model, serial: st.serial, driver_version: st.driver_version })
          if (st.channels) setChannels(st.channels)
        }
      } catch {}
    }
    ws.onerror = () => { /* errors surfaced via HTTP paths */ }
    return () => { try { ws.close() } catch {} }
  }, [connected])

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          PicoScope 5244D MSO Control Panel
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Chip 
            label={connected ? (deviceInfo?.serial ? `Connected (${deviceInfo.serial})` : 'Connected') : 'Disconnected'} 
            color={connected ? 'success' : 'default'}
            icon={<ScopeIcon />}
          />
          <Button
            variant="contained"
            onClick={connected ? handleDisconnect : handleConnect}
            disabled={loading}
            color={connected ? 'secondary' : 'primary'}
          >
            {connected ? 'Disconnect' : 'Connect'}
          </Button>
          <Button
            variant="outlined"
            startIcon={<AutoSetupIcon />}
            onClick={handleAutoSetup}
            disabled={!connected || loading}
          >
            Auto Setup
          </Button>
        </Box>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Channel Controls */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Channel Configuration
              </Typography>
              {Object.entries(channels).map(([channel, config]) => (
                <Box key={channel} sx={{ mb: 2, p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="subtitle1">Channel {channel}</Typography>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={config.enabled}
                          onChange={(e) => updateChannel(channel as 'A'|'B'|'C'|'D', { enabled: e.target.checked })}
                          disabled={!connected}
                        />
                      }
                      label="Enabled"
                    />
                  </Box>
                  <Box sx={{ display: 'flex', gap: 2 }}>
                    <FormControl size="small" disabled={!connected || !config.enabled}>
                      <InputLabel>Range</InputLabel>
                      <Select value={config.range} label="Range" onChange={(e) => updateChannel(channel as 'A'|'B'|'C'|'D', { range: e.target.value as string })}>
                        <MenuItem value="±10V">±10V</MenuItem>
                        <MenuItem value="±5V">±5V</MenuItem>
                        <MenuItem value="±2V">±2V</MenuItem>
                        <MenuItem value="±1V">±1V</MenuItem>
                        <MenuItem value="±500mV">±500mV</MenuItem>
                      </Select>
                    </FormControl>
                    <FormControl size="small" disabled={!connected || !config.enabled}>
                      <InputLabel>Coupling</InputLabel>
                      <Select value={config.coupling} label="Coupling" onChange={(e) => updateChannel(channel as 'A'|'B'|'C'|'D', { coupling: e.target.value as string })}>
                        <MenuItem value="DC">DC</MenuItem>
                        <MenuItem value="AC">AC</MenuItem>
                      </Select>
                    </FormControl>
                  </Box>
                </Box>
              ))}
            </CardContent>
          </Card>
        </Grid>

        {/* Acquisition Controls */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Acquisition Control
              </Typography>
              
              <Box sx={{ mb: 3 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Status: {acquiring ? 'Acquiring' : 'Stopped'}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Button
                    variant="contained"
                    startIcon={<StartIcon />}
                    onClick={handleStartAcquisition}
                    disabled={!connected || acquiring || loading}
                    color="success"
                  >
                    Start
                  </Button>
                  <Button
                    variant="contained"
                    startIcon={<StopIcon />}
                    onClick={handleStopAcquisition}
                    disabled={!connected || !acquiring || loading}
                    color="error"
                  >
                    Stop
                  </Button>
                </Box>
              </Box>

              <Typography variant="h6" gutterBottom>
                Timebase
              </Typography>
              <FormControl fullWidth size="small" disabled={!connected}>
                <InputLabel>Time/Division</InputLabel>
                <Select defaultValue="1ms/div" label="Time/Division" onChange={(e) => setTimebase({ scale: e.target.value })}>
                  <MenuItem value="10ns/div">10ns/div</MenuItem>
                  <MenuItem value="100ns/div">100ns/div</MenuItem>
                  <MenuItem value="1µs/div">1µs/div</MenuItem>
                  <MenuItem value="10µs/div">10µs/div</MenuItem>
                  <MenuItem value="100µs/div">100µs/div</MenuItem>
                  <MenuItem value="1ms/div">1ms/div</MenuItem>
                  <MenuItem value="10ms/div">10ms/div</MenuItem>
                  <MenuItem value="100ms/div">100ms/div</MenuItem>
                  <MenuItem value="1s/div">1s/div</MenuItem>
                </Select>
              </FormControl>

              <Typography variant="h6" sx={{ mt: 3, mb: 1 }}>
                Trigger
              </Typography>
              <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                <FormControl size="small" disabled={!connected}>
                  <InputLabel>Source</InputLabel>
                  <Select defaultValue="Channel A" label="Source" onChange={(e) => setTrigger({ source: e.target.value })}>
                    <MenuItem value="Channel A">Channel A</MenuItem>
                    <MenuItem value="Channel B">Channel B</MenuItem>
                    <MenuItem value="Channel C">Channel C</MenuItem>
                    <MenuItem value="Channel D">Channel D</MenuItem>
                    <MenuItem value="External">External</MenuItem>
                  </Select>
                </FormControl>
                <FormControl size="small" disabled={!connected}>
                  <InputLabel>Edge</InputLabel>
                  <Select defaultValue="Rising" label="Edge" onChange={(e) => setTrigger({ direction: e.target.value })}>
                    <MenuItem value="Rising">Rising</MenuItem>
                    <MenuItem value="Falling">Falling</MenuItem>
                  </Select>
                </FormControl>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Waveform Display Placeholder */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Waveform Display
              </Typography>
              <Box 
                sx={{ 
                  height: 300, 
                  backgroundColor: 'background.default',
                  border: '1px solid',
                  borderColor: 'divider',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <Typography color="text.secondary">
                  {connected ? 'Waveform display will appear here' : 'Connect to device to view waveforms'}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  )
}

export default PicoScope5244DView

