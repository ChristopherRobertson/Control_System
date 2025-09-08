import React, { useState } from 'react'
import {
  Box,
  Typography,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Card,
  CardContent,
  Grid,
  Switch,
  FormControlLabel,
  Alert
} from '@mui/material'
import { PlayArrow as PlayIcon, Stop as StopIcon } from '@mui/icons-material'

interface ScanModePanelProps {
  deviceStatus: any
  onStatusUpdate: () => void
}

function ScanModePanel({ deviceStatus, onStatusUpdate }: ScanModePanelProps) {
  const [selectedScanMode, setSelectedScanMode] = useState<string>('')
  const [scanSettings, setScanSettings] = useState({
    startWavenumber: 1850.0,
    endWavenumber: 1900.0,
    stepSize: 1.0,
    dwellTime: 1000,
    sweepRate: 10,
    numPoints: 50,
    autoStart: false
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canInteract = deviceStatus?.connected && deviceStatus?.armed

  const handleScanModeSelect = (mode: string) => {
    setSelectedScanMode(mode)
  }

  const handleManualStep = () => {
    // Implement manual step for step scan
    console.log('Manual step executed')
  }

  const handleStartScan = async () => {
    setLoading(true)
    setError(null)
    try {
      // TODO: Implement scan start API call
      console.log('Starting scan:', selectedScanMode, scanSettings)
      onStatusUpdate()
    } catch (err) {
      setError('Failed to start scan')
    } finally {
      setLoading(false)
    }
  }

  const handleStopScan = async () => {
    setLoading(true)
    setError(null)
    try {
      // TODO: Implement scan stop API call
      console.log('Stopping scan')
      onStatusUpdate()
    } catch (err) {
      setError('Failed to stop scan')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Scan Mode Selection */}
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Scan Type Selection
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            <Button 
              variant={selectedScanMode === 'sweep' ? 'contained' : 'outlined'}
              onClick={() => handleScanModeSelect('sweep')}
              disabled={!canInteract}
            >
              Sweep Scan
            </Button>
            <Button 
              variant={selectedScanMode === 'step' ? 'contained' : 'outlined'}
              onClick={() => handleScanModeSelect('step')}
              disabled={!canInteract}
            >
              Step Scan
            </Button>
            <Button 
              variant={selectedScanMode === 'multispectral' ? 'contained' : 'outlined'}
              onClick={() => handleScanModeSelect('multispectral')}
              disabled={!canInteract}
            >
              Multi-Spectral Scan
            </Button>
          </Box>
          
          {!canInteract && (
            <Typography color="text.secondary">
              {!deviceStatus?.connected ? 'Connect to device and arm laser to enable scan modes' : 'Arm laser to enable scan modes'}
            </Typography>
          )}
        </CardContent>
      </Card>

      {/* Scan Settings - Dynamic based on selected mode */}
      {selectedScanMode && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              {selectedScanMode === 'sweep' && 'Sweep Scan Settings'}
              {selectedScanMode === 'step' && 'Step Scan Settings'}
              {selectedScanMode === 'multispectral' && 'Multi-Spectral Scan Settings'}
            </Typography>

            <Grid container spacing={2}>
              <Grid item xs={6} md={3}>
                <TextField
                  fullWidth
                  label="Start (cm-1)"
                  type="number"
                  value={scanSettings.startWavenumber}
                  onChange={(e) => setScanSettings(prev => ({ ...prev, startWavenumber: parseFloat(e.target.value) }))}
                  disabled={!canInteract}
                  inputProps={{ min: 1638.81, max: 2077.27, step: 0.01 }}
                />
              </Grid>
              <Grid item xs={6} md={3}>
                <TextField
                  fullWidth
                  label="End (cm-1)"
                  type="number"
                  value={scanSettings.endWavenumber}
                  onChange={(e) => setScanSettings(prev => ({ ...prev, endWavenumber: parseFloat(e.target.value) }))}
                  disabled={!canInteract}
                  inputProps={{ min: 1638.81, max: 2077.27, step: 0.01 }}
                />
              </Grid>

              {selectedScanMode === 'step' && (
                <>
                  <Grid item xs={6} md={3}>
                    <TextField
                      fullWidth
                      label="Step Size (cm-1)"
                      type="number"
                      value={scanSettings.stepSize}
                      onChange={(e) => setScanSettings(prev => ({ ...prev, stepSize: parseFloat(e.target.value) }))}
                      disabled={!canInteract}
                      inputProps={{ min: 0.01, max: 10, step: 0.01 }}
                    />
                  </Grid>
                  <Grid item xs={6} md={3}>
                    <TextField
                      fullWidth
                      label="Dwell Time (ms)"
                      type="number"
                      value={scanSettings.dwellTime}
                      onChange={(e) => setScanSettings(prev => ({ ...prev, dwellTime: parseInt(e.target.value) }))}
                      disabled={!canInteract}
                      inputProps={{ min: 100, max: 10000, step: 100 }}
                    />
                  </Grid>
                </>
              )}

              {selectedScanMode === 'sweep' && (
                <>
                  <Grid item xs={6} md={3}>
                    <TextField
                      fullWidth
                      label="Sweep Rate (cm-1/s)"
                      type="number"
                      value={scanSettings.sweepRate}
                      onChange={(e) => setScanSettings(prev => ({ ...prev, sweepRate: parseFloat(e.target.value) }))}
                      disabled={!canInteract}
                      inputProps={{ min: 0.1, max: 100, step: 0.1 }}
                    />
                  </Grid>
                  <Grid item xs={6} md={3}>
                    <TextField
                      fullWidth
                      label="Number of Points"
                      type="number"
                      value={scanSettings.numPoints}
                      onChange={(e) => setScanSettings(prev => ({ ...prev, numPoints: parseInt(e.target.value) }))}
                      disabled={!canInteract}
                      inputProps={{ min: 10, max: 1000, step: 10 }}
                    />
                  </Grid>
                </>
              )}

              <Grid item xs={12}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={scanSettings.autoStart}
                      onChange={(e) => setScanSettings(prev => ({ ...prev, autoStart: e.target.checked }))}
                      disabled={!canInteract}
                    />
                  }
                  label="Auto Start on Parameter Change"
                />
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Scan Control Buttons */}
      {selectedScanMode && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Scan Control
            </Typography>
            
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <Button
                variant="contained"
                startIcon={<PlayIcon />}
                onClick={handleStartScan}
                disabled={!canInteract || loading}
                color="success"
              >
                Start Scan
              </Button>
              
              <Button
                variant="contained"
                startIcon={<StopIcon />}
                onClick={handleStopScan}
                disabled={!canInteract || loading}
                color="error"
              >
                Stop Scan
              </Button>

              {selectedScanMode === 'step' && (
                <Button
                  variant="outlined"
                  onClick={handleManualStep}
                  disabled={!canInteract || loading}
                >
                  Manual Step
                </Button>
              )}
            </Box>

            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Scan Progress: {loading ? 'In Progress...' : 'Ready'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Current Position: {deviceStatus?.current_wavenumber?.toFixed(2) || '--'} cm-1
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  )
}

export default ScanModePanel