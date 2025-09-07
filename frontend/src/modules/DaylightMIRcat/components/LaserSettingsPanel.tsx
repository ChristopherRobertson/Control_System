import React, { useState } from 'react'
import {
  Box,
  Typography,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Grid,
  Card,
  CardContent,
  Button,
  Divider,
  Alert
} from '@mui/material'
import { Save as SaveIcon } from '@mui/icons-material'
import { MIRcatAPI } from '../api'

interface LaserSettingsPanelProps {
  deviceStatus: any
  onStatusUpdate: () => void
}

function LaserSettingsPanel({ deviceStatus, onStatusUpdate }: LaserSettingsPanelProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Laser Parameters State
  const [laserParams, setLaserParams] = useState({
    displayUnits: 'Wavenumber',
    selectQCL: 1,
    laserMode: 'Pulsed',
    pulseRate: 2000000,
    pulseWidth: 150,
    dutyCycle: 30,
    pulsedCurrent: 1000,
    cwCurrent: 775,
    temperature: 19,
    reInitTuning: 2.36
  })

  // Process Trigger Parameters
  const [processTrigger, setProcessTrigger] = useState({
    mode: 'Use Internal Step Mode',
    internalStepTime: 1000,
    internalStepDelay: 0
  })

  // Pulse Mode Parameters
  const [pulseMode, setPulseMode] = useState({
    mode: 'Use Internal Pulse Mode',
    wlTrigInterval: 1.0,
    wlTrigStart: 2077.27,
    wlTrigStop: 1638.81,
    wlTrigPulseWidth: 100
  })

  // Global Options
  const [globalOptions, setGlobalOptions] = useState({
    alwaysUseCrossover: false,
    enableParameterLogging: false,
    disableAudioNotification: false,
    flashLEDWhenFires: true,
    disableChannel: false
  })

  // Crossover Points
  const [crossoverPoints, setCrossoverPoints] = useState([
    { channel: 1, wavelength: 0.000 },
    { channel: 2, wavelength: 0.000 },
    { channel: 3, wavelength: 0.000 },
    { channel: 4, wavelength: 0.000 }
  ])

  const handleSaveSettings = async () => {
    setLoading(true)
    setError(null)
    try {
      // TODO: Implement actual settings save via API
      await new Promise(resolve => setTimeout(resolve, 1000)) // Simulate API call
      onStatusUpdate()
    } catch (err) {
      setError('Failed to save laser settings')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Laser Settings
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Display Units & Notifications */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Display Units</Typography>
              <FormControl fullWidth size="small" sx={{ mb: 2 }}>
                <InputLabel>Units</InputLabel>
                <Select
                  value={laserParams.displayUnits}
                  label="Units"
                  onChange={(e) => setLaserParams(prev => ({ ...prev, displayUnits: e.target.value }))}
                  disabled={!deviceStatus?.connected}
                >
                  <MenuItem value="Wavenumber">Wavenumber</MenuItem>
                  <MenuItem value="Wavelength">Wavelength</MenuItem>
                </Select>
              </FormControl>

              <Typography variant="h6" gutterBottom>Notifications</Typography>
              <FormControlLabel
                control={
                  <Switch
                    checked={globalOptions.disableAudioNotification}
                    onChange={(e) => setGlobalOptions(prev => ({ ...prev, disableAudioNotification: e.target.checked }))}
                    disabled={!deviceStatus?.connected}
                  />
                }
                label="Disable Audio Notification When Laser Fires"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={globalOptions.flashLEDWhenFires}
                    onChange={(e) => setGlobalOptions(prev => ({ ...prev, flashLEDWhenFires: e.target.checked }))}
                    disabled={!deviceStatus?.connected}
                  />
                }
                label="Flash LED When Laser Fires"
              />
            </CardContent>
          </Card>
        </Grid>

        {/* Global Options */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Global Options</Typography>
              <FormControlLabel
                control={
                  <Switch
                    checked={globalOptions.alwaysUseCrossover}
                    onChange={(e) => setGlobalOptions(prev => ({ ...prev, alwaysUseCrossover: e.target.checked }))}
                    disabled={!deviceStatus?.connected}
                  />
                }
                label="Always Use Crossover in Single Tune"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={globalOptions.enableParameterLogging}
                    onChange={(e) => setGlobalOptions(prev => ({ ...prev, enableParameterLogging: e.target.checked }))}
                    disabled={!deviceStatus?.connected}
                  />
                }
                label="Enable Parameter Logging"
              />
              <Button variant="outlined" size="small" sx={{ ml: 2 }}>
                Set Fault Log Directory
              </Button>
            </CardContent>
          </Card>
        </Grid>

        {/* Laser Parameters */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Laser Parameters</Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={6} md={3}>
                  <Typography variant="body2" gutterBottom>Select QCL:</Typography>
                  <FormControl fullWidth size="small">
                    <Select
                      value={laserParams.selectQCL}
                      onChange={(e) => setLaserParams(prev => ({ ...prev, selectQCL: e.target.value as number }))}
                      disabled={!deviceStatus?.connected}
                    >
                      <MenuItem value={1}>QCL 1</MenuItem>
                      <MenuItem value={2}>QCL 2</MenuItem>
                      <MenuItem value={3}>QCL 3</MenuItem>
                      <MenuItem value={4}>QCL 4</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={6} md={3}>
                  <Typography variant="body2" gutterBottom>Laser Mode:</Typography>
                  <FormControl fullWidth size="small">
                    <Select
                      value={laserParams.laserMode}
                      onChange={(e) => setLaserParams(prev => ({ ...prev, laserMode: e.target.value }))}
                      disabled={!deviceStatus?.connected}
                    >
                      <MenuItem value="Pulsed">Pulsed</MenuItem>
                      <MenuItem value="CW">CW</MenuItem>
                      <MenuItem value="CW + Modulation">CW + Modulation</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={6} md={3}>
                  <Typography variant="body2" gutterBottom>Re-Init Tuning:</Typography>
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    value={laserParams.reInitTuning}
                    onChange={(e) => setLaserParams(prev => ({ ...prev, reInitTuning: parseFloat(e.target.value) }))}
                    disabled={!deviceStatus?.connected}
                    inputProps={{ step: 0.01, min: 0, max: 100 }}
                  />
                  <Typography variant="caption">WL: %</Typography>
                </Grid>

                <Grid item xs={6} md={3}>
                  <Typography variant="body2" gutterBottom>Temperature:</Typography>
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    value={laserParams.temperature}
                    onChange={(e) => setLaserParams(prev => ({ ...prev, temperature: parseFloat(e.target.value) }))}
                    disabled={!deviceStatus?.connected}
                    inputProps={{ step: 0.1, min: 17, max: 23 }}
                  />
                  <Typography variant="caption">°C</Typography>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={globalOptions.disableChannel}
                        onChange={(e) => setGlobalOptions(prev => ({ ...prev, disableChannel: e.target.checked }))}
                        disabled={!deviceStatus?.connected}
                      />
                    }
                    label="Disable Channel"
                    sx={{ ml: 1 }}
                  />
                </Grid>

                <Grid item xs={6} md={3}>
                  <Typography variant="body2" gutterBottom>Pulse Rate:</Typography>
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    value={laserParams.pulseRate}
                    onChange={(e) => setLaserParams(prev => ({ ...prev, pulseRate: parseInt(e.target.value) }))}
                    disabled={!deviceStatus?.connected || laserParams.laserMode !== 'Pulsed'}
                    inputProps={{ min: 10, max: 3000000 }}
                  />
                  <Typography variant="caption">Hz</Typography>
                </Grid>

                <Grid item xs={6} md={3}>
                  <Typography variant="body2" gutterBottom>Pulse Width:</Typography>
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    value={laserParams.pulseWidth}
                    onChange={(e) => setLaserParams(prev => ({ ...prev, pulseWidth: parseInt(e.target.value) }))}
                    disabled={!deviceStatus?.connected || laserParams.laserMode !== 'Pulsed'}
                    inputProps={{ min: 20, max: 1000 }}
                  />
                  <Typography variant="caption">ns</Typography>
                </Grid>

                <Grid item xs={6} md={3}>
                  <Typography variant="body2" gutterBottom>Current:</Typography>
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    value={laserParams.laserMode === 'Pulsed' ? laserParams.pulsedCurrent : laserParams.cwCurrent}
                    onChange={(e) => {
                      const value = parseInt(e.target.value)
                      if (laserParams.laserMode === 'Pulsed') {
                        setLaserParams(prev => ({ ...prev, pulsedCurrent: value }))
                      } else {
                        setLaserParams(prev => ({ ...prev, cwCurrent: value }))
                      }
                    }}
                    disabled={!deviceStatus?.connected}
                    inputProps={{ 
                      min: 100, 
                      max: laserParams.laserMode === 'Pulsed' ? 1000 : 775 
                    }}
                  />
                  <Typography variant="caption">mA</Typography>
                </Grid>

                <Grid item xs={6} md={3}>
                  <Typography variant="body2" gutterBottom>Duty Cycle (%):</Typography>
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    value={laserParams.dutyCycle}
                    onChange={(e) => setLaserParams(prev => ({ ...prev, dutyCycle: parseFloat(e.target.value) }))}
                    disabled={!deviceStatus?.connected || laserParams.laserMode !== 'Pulsed'}
                    inputProps={{ step: 0.1, min: 1, max: 30 }}
                  />
                  <Typography variant="caption">60.0%</Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Process Trigger Modes */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Process Trigger Modes</Typography>
              
              <FormControl component="fieldset">
                {['Use Internal Step Mode', 'Use External Step Mode', 'Use Manual Step Mode'].map((mode) => (
                  <FormControlLabel
                    key={mode}
                    control={
                      <Switch
                        checked={processTrigger.mode === mode}
                        onChange={() => setProcessTrigger(prev => ({ ...prev, mode }))}
                        disabled={!deviceStatus?.connected}
                      />
                    }
                    label={mode}
                  />
                ))}
              </FormControl>

              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" gutterBottom>Internal Trigger Step Time (ms):</Typography>
                <TextField
                  fullWidth
                  size="small"
                  type="number"
                  value={processTrigger.internalStepTime}
                  onChange={(e) => setProcessTrigger(prev => ({ ...prev, internalStepTime: parseInt(e.target.value) }))}
                  disabled={!deviceStatus?.connected || processTrigger.mode !== 'Use Internal Step Mode'}
                  inputProps={{ min: 0, max: 4000000 }}
                />
              </Box>

              <Box sx={{ mt: 1 }}>
                <Typography variant="body2" gutterBottom>Internal Trigger Step Delay (ms):</Typography>
                <TextField
                  fullWidth
                  size="small"
                  type="number"
                  value={processTrigger.internalStepDelay}
                  onChange={(e) => setProcessTrigger(prev => ({ ...prev, internalStepDelay: parseInt(e.target.value) }))}
                  disabled={!deviceStatus?.connected || processTrigger.mode !== 'Use Internal Step Mode'}
                  inputProps={{ min: 0, max: 4000000 }}
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Pulse Modes */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Pulse Modes</Typography>
              
              <FormControl component="fieldset">
                {[
                  'Use Internal Pulse Mode',
                  'Use External Trigger Mode', 
                  'Use External Pulse Mode',
                  'Use Wavelength Trigger Pulse Mode'
                ].map((mode) => (
                  <FormControlLabel
                    key={mode}
                    control={
                      <Switch
                        checked={pulseMode.mode === mode}
                        onChange={() => setPulseMode(prev => ({ ...prev, mode }))}
                        disabled={!deviceStatus?.connected}
                      />
                    }
                    label={mode}
                  />
                ))}
              </FormControl>

              {pulseMode.mode === 'Use Wavelength Trigger Pulse Mode' && (
                <Box sx={{ mt: 2 }}>
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography variant="body2" gutterBottom>Wavelength Trigger Interval:</Typography>
                      <TextField
                        fullWidth
                        size="small"
                        type="number"
                        value={pulseMode.wlTrigInterval}
                        onChange={(e) => setPulseMode(prev => ({ ...prev, wlTrigInterval: parseFloat(e.target.value) }))}
                        inputProps={{ step: 0.01, min: 0.01, max: 100 }}
                      />
                      <Typography variant="caption">cm-1</Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="body2" gutterBottom>Wavelength Trigger Pulse Width:</Typography>
                      <TextField
                        fullWidth
                        size="small"
                        type="number"
                        value={pulseMode.wlTrigPulseWidth}
                        onChange={(e) => setPulseMode(prev => ({ ...prev, wlTrigPulseWidth: parseInt(e.target.value) }))}
                        inputProps={{ min: 1, max: 500 }}
                      />
                      <Typography variant="caption">μs</Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="body2" gutterBottom>Wavelength Trigger Start:</Typography>
                      <TextField
                        fullWidth
                        size="small"
                        type="number"
                        value={pulseMode.wlTrigStart}
                        onChange={(e) => setPulseMode(prev => ({ ...prev, wlTrigStart: parseFloat(e.target.value) }))}
                        inputProps={{ step: 0.01, min: 1638.81, max: 2077.27 }}
                      />
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="body2" gutterBottom>Wavelength Trigger Stop:</Typography>
                      <TextField
                        fullWidth
                        size="small"
                        type="number"
                        value={pulseMode.wlTrigStop}
                        onChange={(e) => setPulseMode(prev => ({ ...prev, wlTrigStop: parseFloat(e.target.value) }))}
                        inputProps={{ step: 0.01, min: 1638.81, max: 2077.27 }}
                      />
                    </Grid>
                  </Grid>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Crossover Points */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Crossover Points</Typography>
              
              <Grid container spacing={2}>
                {crossoverPoints.map((point, index) => (
                  <Grid item xs={6} md={3} key={index}>
                    <Typography variant="body2" gutterBottom>Channel {point.channel}:</Typography>
                    <TextField
                      fullWidth
                      size="small"
                      type="number"
                      value={point.wavelength}
                      onChange={(e) => {
                        const newPoints = [...crossoverPoints]
                        newPoints[index].wavelength = parseFloat(e.target.value)
                        setCrossoverPoints(newPoints)
                      }}
                      disabled={!deviceStatus?.connected}
                      inputProps={{ step: 0.001, min: 0 }}
                    />
                  </Grid>
                ))}
              </Grid>
              
              <Box sx={{ mt: 2 }}>
                <Button variant="outlined" size="small">
                  Restore to Factory
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Save Settings */}
        <Grid item xs={12}>
          <Box sx={{ display: 'flex', justifyContent: 'flex-start' }}>
            <Button
              variant="contained"
              startIcon={<SaveIcon />}
              onClick={handleSaveSettings}
              disabled={!deviceStatus?.connected || loading}
              color="primary"
            >
              Save Settings
            </Button>
          </Box>
        </Grid>
      </Grid>
    </Box>
  )
}

export default LaserSettingsPanel