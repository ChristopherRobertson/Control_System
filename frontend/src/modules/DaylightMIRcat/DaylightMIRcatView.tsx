import React, { useState, useEffect } from 'react'
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Chip,
  Divider,
  Alert,
  LinearProgress
} from '@mui/material'
import {
  PowerSettingsNew as PowerIcon,
  Security as SecurityIcon,
  Thermostat as ThermostatIcon,
  RadioButtonChecked as LaserIcon,
  Tune as TuneIcon
} from '@mui/icons-material'
import { MIRcatAPI } from './api'
import StatusIndicator from './components/StatusIndicator'
import LaserControls from './components/LaserControls'
import TuningControls from './components/TuningControls'
import LaserSettingsPanel from './components/LaserSettingsPanel'

interface DeviceStatus {
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

function DaylightMIRcatView() {
  const [deviceStatus, setDeviceStatus] = useState<DeviceStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('tune')

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

  // Initial status fetch
  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 2000) // Poll every 2 seconds
    return () => clearInterval(interval)
  }, [])

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
        {/* Left Navigation Panel */}
        <Grid item xs={12} md={3}>
          <Card sx={{ height: 'fit-content' }}>
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
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Main Control Area */}
        <Grid item xs={12} md={6}>
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
                  <Typography color="text.secondary" sx={{ mb: 2 }}>
                    Select scan type and configure parameters:
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                    <Button variant="outlined" disabled={!deviceStatus?.connected}>
                      Sweep Scan
                    </Button>
                    <Button variant="outlined" disabled={!deviceStatus?.connected}>
                      Step Scan
                    </Button>
                    <Button variant="outlined" disabled={!deviceStatus?.connected}>
                      Multi-Spectral Scan
                    </Button>
                  </Box>
                  <Typography color="text.secondary">
                    {deviceStatus?.connected ? 'Select a scan mode to configure parameters' : 'Connect to device to enable scan modes'}
                  </Typography>
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

        {/* Right Status Panel */}
        <Grid item xs={12} md={3}>
          <Card sx={{ height: 'fit-content' }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Laser Status
              </Typography>
              
              {deviceStatus && (
                <>
                  <StatusIndicator
                    label="Interlocks"
                    status={deviceStatus.status.interlocks}
                  />
                  <StatusIndicator
                    label="Key Switch Status"
                    status={deviceStatus.status.key_switch}
                  />
                  <StatusIndicator
                    label="Temperature"
                    status={deviceStatus.status.temperature}
                  />
                  <StatusIndicator
                    label="Connected"
                    status={deviceStatus.status.connected}
                  />
                  <StatusIndicator
                    label="Emission"
                    status={deviceStatus.status.emission}
                  />
                  <StatusIndicator
                    label="Pointing Correction"
                    status={deviceStatus.status.pointing_correction}
                  />
                  <StatusIndicator
                    label="System Fault"
                    status={!deviceStatus.status.system_fault}
                    invert
                  />

                  <Divider sx={{ my: 2 }} />

                  <Box sx={{ mb: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      Case Temp 1 (C): {deviceStatus.connected ? deviceStatus.status.case_temp_1 : 'N/A'}
                    </Typography>
                  </Box>
                  <Box sx={{ mb: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      Case Temp 2 (C): {deviceStatus.connected ? deviceStatus.status.case_temp_2 : 'N/A'}
                    </Typography>
                  </Box>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      PCB Temperature (C): {deviceStatus.connected ? deviceStatus.status.pcb_temperature : 'N/A'}
                    </Typography>
                  </Box>

                  <Divider sx={{ my: 2 }} />
                  
                  <LaserControls
                    deviceStatus={deviceStatus}
                    onStatusUpdate={fetchStatus}
                  />
                </>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  )
}

export default DaylightMIRcatView