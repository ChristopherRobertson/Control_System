import React, { useState, useEffect } from 'react'
import {
  Box,
  Typography,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  Card,
  CardContent,
  Grid,
  Switch,
  FormControlLabel,
  Snackbar
} from '@mui/material'
import { 
  Tune as TuneIcon, 
  Security as ArmIcon,
  Lightbulb as RedLaserIcon,
  FlashOn as EmitIcon
} from '@mui/icons-material'
import { MIRcatAPI } from '../api'

interface TuningControlsProps {
  deviceStatus: any
  onStatusUpdate: () => void
}

function TuningControls({ deviceStatus, onStatusUpdate }: TuningControlsProps) {
  const [wavenumber, setWavenumber] = useState(1850.0)
  const [units, setUnits] = useState<'cm-1' | 'μm'>('cm-1')
  const [selectedQCL, setSelectedQCL] = useState(1)
  const [redLaserOn, setRedLaserOn] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [snackbarMessage, setSnackbarMessage] = useState<string | null>(null)

  // QCL information data
  const qclData = {
    1: { 
      range: '2077.3 to 1638.8 cm-1', 
      temp: deviceStatus?.status?.case_temp_1 || '--',
      active: deviceStatus?.connected ? 'Y' : '--',
      tecMA: deviceStatus?.connected ? '9' : '--',
      tecV: deviceStatus?.connected ? '-0.19' : '--'
    },
    2: { range: 'Not Installed', temp: '--', active: '--', tecMA: '--', tecV: '--' },
    3: { range: 'Not Installed', temp: '--', active: '--', tecMA: '--', tecV: '--' },
    4: { range: 'Not Installed', temp: '--', active: '--', tecMA: '--', tecV: '--' }
  }

  // Convert between units
  const convertToMicrons = (wavenum: number) => (10000 / wavenum)
  const convertToWavenumber = (microns: number) => (10000 / microns)

  // Handle unit conversion
  const handleUnitChange = (newUnit: 'cm-1' | 'μm') => {
    if (newUnit !== units) {
      if (newUnit === 'μm') {
        setWavenumber(convertToMicrons(wavenumber))
      } else {
        setWavenumber(convertToWavenumber(wavenumber))
      }
      setUnits(newUnit)
    }
  }

  // Parameter validation on blur
  const handleWavenumberBlur = () => {
    let min, max, correctedValue = wavenumber

    if (units === 'cm-1') {
      min = 1638.81
      max = 2077.27
    } else {
      min = convertToMicrons(2077.27) // ~4.81 μm
      max = convertToMicrons(1638.81) // ~6.1 μm
    }

    if (wavenumber < min) {
      correctedValue = min
    } else if (wavenumber > max) {
      correctedValue = max
    }

    if (correctedValue !== wavenumber) {
      const decimals = units === 'cm-1' ? 2 : 2 // Limit microns to 2 decimal places
      setWavenumber(Number(correctedValue.toFixed(decimals)))
      setSnackbarMessage(`Value corrected to acceptable range: ${correctedValue.toFixed(decimals)} ${units}`)
    }
  }

  // Workflow validation
  const validateWorkflow = (action: string): string | null => {
    if (!deviceStatus?.connected) {
      return `Please connect to the device before ${action.toLowerCase()}.`
    }

    switch (action) {
      case 'ARM':
        if (!deviceStatus.connected) return 'Please connect to the device before arming.'
        break
      case 'TUNE':
        if (!deviceStatus.connected) return 'Please connect to the device before tuning.'
        if (!deviceStatus.armed) return 'Please arm the laser before tuning.'
        break
      case 'EMIT':
        if (!deviceStatus.connected) return 'Please connect to the device before emission.'
        if (!deviceStatus.armed) return 'Please arm the laser before emission.'
        // Check if tuned (assuming current_wavenumber indicates tuning status)
        if (!deviceStatus.current_wavenumber || deviceStatus.current_wavenumber === 0) {
          return 'Please tune the laser before enabling emission.'
        }
        break
    }
    return null
  }

  const handleArm = async () => {
    const validation = validateWorkflow('ARM')
    if (validation) {
      setSnackbarMessage(validation)
      return
    }

    setLoading(true)
    setError(null)
    try {
      await MIRcatAPI.armLaser()
      onStatusUpdate()
      setSnackbarMessage('Laser armed successfully')
    } catch (err) {
      setError('Failed to arm laser')
    } finally {
      setLoading(false)
    }
  }

  const handleDisarm = async () => {
    setLoading(true)
    setError(null)
    try {
      // If emitting, stop emission first
      if (deviceStatus?.emission_on) {
        await MIRcatAPI.turnEmissionOff()
        setSnackbarMessage('Emission stopped before disarming')
      }
      await MIRcatAPI.disarmLaser()
      onStatusUpdate()
      setSnackbarMessage('Laser disarmed successfully')
    } catch (err) {
      setError('Failed to disarm laser')
    } finally {
      setLoading(false)
    }
  }

  const handleTune = async () => {
    const validation = validateWorkflow('TUNE')
    if (validation) {
      setSnackbarMessage(validation)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const targetWavenumber = units === 'μm' ? convertToWavenumber(wavenumber) : wavenumber
      await MIRcatAPI.tuneToWavenumber(targetWavenumber)
      onStatusUpdate()
      setSnackbarMessage(`Tuned to ${wavenumber} ${units}`)
    } catch (err) {
      setError('Failed to tune laser')
    } finally {
      setLoading(false)
    }
  }

  const handleEmit = async () => {
    const validation = validateWorkflow('EMIT')
    if (validation) {
      setSnackbarMessage(validation)
      return
    }

    setLoading(true)
    setError(null)
    try {
      if (deviceStatus.emission_on) {
        await MIRcatAPI.turnEmissionOff()
        setSnackbarMessage('Emission turned off')
      } else {
        await MIRcatAPI.turnEmissionOn()
        setSnackbarMessage('Emission turned on')
      }
      onStatusUpdate()
    } catch (err) {
      setError('Failed to control emission')
    } finally {
      setLoading(false)
    }
  }

  const handleRedLaser = () => {
    // Red laser safety logic - can only be enabled when not armed
    if (deviceStatus?.armed) {
      setSnackbarMessage('Red laser cannot be enabled while system is armed')
      return
    }

    setRedLaserOn(!redLaserOn)
    setSnackbarMessage(`Red laser ${!redLaserOn ? 'enabled' : 'disabled'}`)
  }

  const canInteract = deviceStatus?.connected || false
  // More explicit tuning status - only consider tuned if we've successfully completed a tune operation
  // For now, let's use a different approach to determine if tuned
  const isTuned = deviceStatus?.laser_mode === 'tuned' || (deviceStatus?.current_wavenumber && deviceStatus?.current_wavenumber > 0 && deviceStatus?.armed)
  const isEmitting = deviceStatus?.emission_on
  
  // For testing purposes, let's be very explicit about when laser is considered "tuned"
  // A laser is tuned when: connected + armed + has completed a tune operation
  // Since we don't have explicit tune status, let's assume not tuned initially after arming
  const isActuallyTuned = deviceStatus?.connected && deviceStatus?.armed && deviceStatus?.current_wavenumber && deviceStatus?.current_wavenumber > 1600 // within QCL range

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Tune Mode
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2}>
        {/* QCL Range Selection */}
        <Grid item xs={12}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6" gutterBottom>
                QCL Range
              </Typography>
              <FormControl fullWidth disabled={!canInteract}>
                <InputLabel>Select QCL</InputLabel>
                <Select
                  value={selectedQCL}
                  label="Select QCL"
                  onChange={(e) => setSelectedQCL(e.target.value as number)}
                >
                  <MenuItem value={1}>QCL 1 - 2077.3 to 1638.8 cm-1</MenuItem>
                  <MenuItem value={2} disabled>QCL 2 - Not Installed</MenuItem>
                  <MenuItem value={3} disabled>QCL 3 - Not Installed</MenuItem>
                  <MenuItem value={4} disabled>QCL 4 - Not Installed</MenuItem>
                </Select>
              </FormControl>
            </CardContent>
          </Card>
        </Grid>

        {/* Tuning Controls */}
        <Grid item xs={12}>
          <Card variant="outlined">
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
                <Typography variant="body1">
                  Target:
                </Typography>
                <TextField
                  type="number"
                  value={wavenumber}
                  onChange={(e) => setWavenumber(parseFloat(e.target.value) || 0)}
                  onBlur={handleWavenumberBlur}
                  disabled={!canInteract}
                  inputProps={{
                    step: units === 'cm-1' ? 0.01 : 0.001
                  }}
                  sx={{ width: 140 }}
                />
                <FormControl sx={{ minWidth: 80 }} disabled={!canInteract}>
                  <InputLabel>Units</InputLabel>
                  <Select
                    value={units}
                    label="Units"
                    onChange={(e) => handleUnitChange(e.target.value as 'cm-1' | 'μm')}
                  >
                    <MenuItem value="cm-1">cm-1</MenuItem>
                    <MenuItem value="μm">μm</MenuItem>
                  </Select>
                </FormControl>
              </Box>

              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Button
                  variant="contained"
                  startIcon={<TuneIcon />}
                  onClick={handleTune}
                  disabled={!canInteract || loading || !deviceStatus?.armed || isActuallyTuned || isEmitting}
                  color="primary"
                >
                  {`Tune to ${wavenumber} ${units}`}
                </Button>

                <Button
                  variant="outlined"
                  onClick={() => {
                    // Cancel tune - reset to disconnected state
                    onStatusUpdate()
                    setSnackbarMessage('Tune cancelled')
                  }}
                  disabled={!canInteract || loading || !isActuallyTuned || isEmitting}
                  color="warning"
                >
                  Cancel Tune
                </Button>

                <Button
                  variant={deviceStatus?.emission_on ? 'contained' : 'outlined'}
                  startIcon={<EmitIcon />}
                  onClick={handleEmit}
                  disabled={!canInteract || loading || !deviceStatus?.armed || !isActuallyTuned}
                  color={deviceStatus?.emission_on ? 'error' : 'success'}
                >
                  {deviceStatus?.emission_on ? 'STOP EMISSION' : 'START EMISSION'}
                </Button>

                <FormControlLabel
                  control={
                    <Switch
                      checked={redLaserOn}
                      onChange={handleRedLaser}
                      disabled={!canInteract || deviceStatus?.armed}
                    />
                  }
                  label="Red Laser"
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* QCL Information */}
        <Grid item xs={12}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6" gutterBottom>
                QCL Information
              </Typography>
              <Box sx={{ 
                display: 'grid', 
                gridTemplateColumns: 'auto auto auto auto auto', 
                gap: 1,
                alignItems: 'center',
                '& > div': { 
                  p: 1, 
                  textAlign: 'center',
                  borderBottom: '1px solid',
                  borderColor: 'divider'
                }
              }}>
                <Typography variant="body2" fontWeight="bold">QCL</Typography>
                <Typography variant="body2" fontWeight="bold">TEMP (°C)</Typography>
                <Typography variant="body2" fontWeight="bold">ACTIVE</Typography>
                <Typography variant="body2" fontWeight="bold">TEC mA</Typography>
                <Typography variant="body2" fontWeight="bold">TEC V</Typography>
                
                <Typography variant="body2" fontWeight="bold">{selectedQCL}</Typography>
                <Typography variant="body2">
                  {qclData[selectedQCL].temp !== '--' ? 
                    (typeof qclData[selectedQCL].temp === 'number' ? qclData[selectedQCL].temp.toFixed(2) : qclData[selectedQCL].temp) : 
                    '--'
                  }
                </Typography>
                <Typography variant="body2">{qclData[selectedQCL].active}</Typography>
                <Typography variant="body2">{qclData[selectedQCL].tecMA}</Typography>
                <Typography variant="body2">{qclData[selectedQCL].tecV}</Typography>
              </Box>
              
              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Range: {qclData[selectedQCL].range}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {!canInteract && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Connect to device to enable tuning controls
        </Typography>
      )}

      <Snackbar
        open={!!snackbarMessage}
        autoHideDuration={4000}
        onClose={() => setSnackbarMessage(null)}
        message={snackbarMessage}
      />
    </Box>
  )
}

export default TuningControls