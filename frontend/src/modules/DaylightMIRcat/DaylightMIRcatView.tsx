import { useState, useEffect, useRef } from 'react'
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  // TextField,
  // FormControl,
  // InputLabel,
  // Select,
  // MenuItem,
  // Switch,
  // FormControlLabel,
  Chip,
  Divider,
  Alert,
  LinearProgress
} from '@mui/material'
import {
  // PowerSettingsNew as PowerIcon,
  Security as SecurityIcon,
  // Thermostat as ThermostatIcon,
  RadioButtonChecked as LaserIcon,
  Tune as TuneIcon
} from '@mui/icons-material'
import { MIRcatAPI, type DeviceStatus as APIDeviceStatus } from './api'
import StatusIndicator from './components/StatusIndicator'
import TuningControls from './components/TuningControls'
import LaserSettingsPanel from './components/LaserSettingsPanel'
import ScanModePanel from './components/ScanModePanel'

// Mirror API DeviceStatus but allow optional last_error fields to reconcile types
// Note: Using `APIDeviceStatus` directly for state; keep local aliasing minimal.

function DaylightMIRcatView() {
  const [deviceStatus, setDeviceStatus] = useState<APIDeviceStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('tune')
  const [wsConnected, setWsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  // Fetch device status
  const fetchStatus = async () => {
    try {
      const status = await MIRcatAPI.getStatus()
      setDeviceStatus(status)
      setError(null)
    } catch (err) {
      setError('Failed to fetch device status')
      console.error('Status fetch error:', err)
    }
  }

  // Connect to device
  const handleConnect = async () => {
    setLoading(true)
    try {
      await MIRcatAPI.connect()
      await fetchStatus()
      setError(null)
    } catch (err) {
      setError('Failed to connect to device')
      console.error('Connect error:', err)
    } finally {
      setLoading(false)
    }
  }

  // Disconnect from device
  const handleDisconnect = async () => {
    setLoading(true)
    try {
      await MIRcatAPI.disconnect()
      await fetchStatus()
      setError(null)
    } catch (err) {
      setError('Failed to disconnect from device')
      console.error('Disconnect error:', err)
    } finally {
      setLoading(false)
    }
  }

  // Arm laser
  const handleArm = async () => {
    setLoading(true)
    setError(null)
    try {
      await MIRcatAPI.armLaser()
      await fetchStatus()
    } catch (err) {
      setError('Failed to arm laser')
      console.error('Arm error:', err)
    } finally {
      setLoading(false)
    }
  }

  // Disarm laser
  const handleDisarm = async () => {
    setLoading(true)
    setError(null)
    try {
      // If emitting, stop emission first
      if (deviceStatus?.emission_on) {
        await MIRcatAPI.turnEmissionOff()
      }
      await MIRcatAPI.disarmLaser()
      await fetchStatus()
    } catch (err) {
      setError('Failed to disarm laser')
      console.error('Disarm error:', err)
    } finally {
      setLoading(false)
    }
  }

  // WebSocket live updates
  useEffect(() => {
    try {
      const isSecure = window.location.protocol === 'https:'
      const host = window.location.hostname
      const port = window.location.port === '5000' ? '8000' : window.location.port || (isSecure ? '443' : '80')
      const wsUrl = `${isSecure ? 'wss' : 'ws'}://${host}:${port}/ws/daylight_mircat`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws
      ws.onopen = () => setWsConnected(true)
      ws.onclose = () => setWsConnected(false)
      ws.onerror = () => setWsConnected(false)
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg?.type === 'status' && msg?.payload) {
            setDeviceStatus(msg.payload)
          }
        } catch {}
      }
      return () => {
        try { ws.close() } catch {}
      }
    } catch {
      setWsConnected(false)
    }
  }, [])

  // Fallback polling when WS not connected
  useEffect(() => {
    if (wsConnected) return
    fetchStatus()
    const intervalMs = deviceStatus?.connected ? 500 : 3000
    const interval = setInterval(fetchStatus, intervalMs)
    return () => clearInterval(interval)
  }, [deviceStatus?.connected, wsConnected])

  const navigationTabs = [
    { id: 'tune', label: 'Tune', icon: <TuneIcon /> },
    { id: 'scan', label: 'Scan', icon: <TuneIcon /> },
    { id: 'settings', label: 'Laser Settings', icon: <LaserIcon /> },
  ]

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          Daylight MIRcat QCL Control Panel
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Chip 
            label={deviceStatus?.connected ? 'Connected to MIRcat S/N 10524' : 'Disconnected'} 
            color={deviceStatus?.connected ? 'success' : 'default'}
            icon={<SecurityIcon />}
          />
          {deviceStatus?.connected && (
            <Typography variant="body2" color="success.main">
              Connected Devices: MIRcat QCL System
            </Typography>
          )}
          <Button
            variant="contained"
            onClick={deviceStatus?.connected ? handleDisconnect : handleConnect}
            disabled={loading}
            color={deviceStatus?.connected ? 'secondary' : 'primary'}
          >
            {loading ? 'Working...' : (deviceStatus?.connected ? 'Disconnect' : 'Connect')}
          </Button>
        </Box>
        {loading && <LinearProgress sx={{ mt: 1 }} />}
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3} sx={{ flexGrow: 1 }}>
        {/* Left Column - Navigation + Status */}
        <Grid item xs={12} md={3}>
          {/* Navigation Panel */}
          <Card sx={{ height: 'fit-content', mb: 2 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Navigation
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {navigationTabs.map((tab) => (
                  <Button
                    key={tab.id}
                    variant={activeTab === tab.id ? 'contained' : 'outlined'}
                    startIcon={tab.icon}
                    onClick={() => setActiveTab(tab.id)}
                    sx={{ justifyContent: 'flex-start' }}
                  >
                    {tab.label}
                  </Button>
                ))}
                
                <Divider sx={{ my: 1 }} />
                
                {/* Arm/Disarm Button - Present on all pages */}
                <Button
                  variant={deviceStatus?.armed ? 'contained' : 'outlined'}
                  startIcon={<SecurityIcon />}
                  onClick={deviceStatus?.armed ? handleDisarm : handleArm}
                  disabled={!deviceStatus?.connected || loading}
                  color={deviceStatus?.armed ? 'warning' : 'primary'}
                  sx={{ justifyContent: 'flex-start' }}
                >
                  {deviceStatus?.armed ? 'DISARM LASER' : 'ARM LASER'}
                </Button>
              </Box>
            </CardContent>
          </Card>

          {/* Status Panel - Below Navigation */}
          <Card sx={{ height: 'fit-content' }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Laser Status
              </Typography>
              
              {deviceStatus && (
                <>
                  {/* Error Reporting Section */}
                  {deviceStatus.last_error && (
                    <Box sx={{ mb: 2 }}>
                      <Alert
                        severity="error"
                        sx={{ mb: 1 }}
                        action={
                          <Button color="inherit" size="small" onClick={async () => {
                            try {
                              const { MIRcatAPI } = await import('./api')
                              await MIRcatAPI.clearError()
                              await fetchStatus()
                            } catch {}
                          }}>
                            Clear
                          </Button>
                        }
                      >
                        <Typography variant="subtitle2" fontWeight="bold">
                          MIRcat Error {deviceStatus.last_error_code ? `(Code ${deviceStatus.last_error_code})` : ''}
                        </Typography>
                        <Typography variant="body2">
                          {deviceStatus.last_error}
                        </Typography>
                      </Alert>
                    </Box>
                  )}

                  <StatusIndicator
                    label="Interlocks"
                    status={deviceStatus.status.interlocks}
                    connected={deviceStatus.connected}
                  />
                  <StatusIndicator
                    label="Key Switch"
                    status={deviceStatus.status.key_switch}
                    connected={deviceStatus.connected}
                  />
                  {/* Replaced temperature indicators with mode and pulse details */}
                  <StatusIndicator
                    label="Pointing Correction"
                    status={deviceStatus.status.pointing_correction}
                    connected={deviceStatus.connected}
                  />
                  <StatusIndicator
                    label="System Fault"
                    status={deviceStatus.status.system_fault}
                    connected={deviceStatus.connected}
                    invert={true}
                  />
                  <StatusIndicator
                    label="Emission"
                    status={deviceStatus.status.emission}
                    connected={deviceStatus.connected}
                    neutralFalse={true}
                  />

                  <Divider sx={{ my: 2 }} />

                  <Box sx={{ mb: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      Laser Mode: {deviceStatus.connected ? (deviceStatus.laser_mode || '-') : '-'}
                    </Typography>
                  </Box>
                  <Box sx={{ mb: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      Wavenumber (cm-1): {deviceStatus.connected && deviceStatus.current_wavenumber ? deviceStatus.current_wavenumber.toFixed(2) : '-'}
                    </Typography>
                  </Box>
                  <Box sx={{ mb: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      Wavelength (µm): {deviceStatus.connected && deviceStatus.current_wavenumber ? (10000 / deviceStatus.current_wavenumber).toFixed(4) : '-'}
                    </Typography>
                  </Box>
                  {deviceStatus?.laser_mode === 'Pulsed' && (
                    <>
                      <Box sx={{ mb: 1 }}>
                        <Typography variant="body2" color="text.secondary">
                          Pulse Rate (Hz): {deviceStatus.connected && deviceStatus.pulse_rate ? deviceStatus.pulse_rate.toFixed(0) : '-'}
                        </Typography>
                      </Box>
                      <Box sx={{ mb: 1 }}>
                        <Typography variant="body2" color="text.secondary">
                          Pulse Width (ns): {deviceStatus.connected && deviceStatus.pulse_width ? deviceStatus.pulse_width.toFixed(0) : '-'}
                        </Typography>
                      </Box>
                    </>
                  )}

                </>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Main Control Area - Right Side */}
        <Grid item xs={12} md={9}>
          <Card sx={{ height: 'fit-content' }}>
            <CardContent>
              {activeTab === 'tune' && (
                <TuningControls 
                  deviceStatus={deviceStatus}
                  onStatusUpdate={fetchStatus}
                />
              )}
              {activeTab === 'scan' && (
                <Box>
                  <Typography variant="h6" gutterBottom>
                    Scan Mode
                  </Typography>
                  
                  <ScanModePanel 
                    deviceStatus={deviceStatus}
                    onStatusUpdate={fetchStatus}
                  />
                </Box>
              )}
              {activeTab === 'settings' && (
                <LaserSettingsPanel 
                  deviceStatus={deviceStatus}
                  onStatusUpdate={fetchStatus}
                />
              )}
            </CardContent>
          </Card>
        </Grid>

      </Grid>
    </Box>
  )
}

export default DaylightMIRcatView
