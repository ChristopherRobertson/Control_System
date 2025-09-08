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
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Checkbox,
  FormControlLabel
} from '@mui/material'
import { 
  PlayArrow as PlayIcon, 
  Stop as StopIcon, 
  Add as AddIcon,
  Delete as DeleteIcon 
} from '@mui/icons-material'

interface ScanModePanelProps {
  deviceStatus: any
  onStatusUpdate: () => void
}

interface MultiSpectralEntry {
  id: number
  wavenumber: number
  dwellTime: number
  offTime: number
}

function ScanModePanel({ deviceStatus, onStatusUpdate }: ScanModePanelProps) {
  const [selectedScanMode, setSelectedScanMode] = useState<string>('')
  const [units, setUnits] = useState<'cm-1' | 'μm'>('cm-1')
  const [scanSettings, setScanSettings] = useState({
    startWavenumber: 1850.0,
    endWavenumber: 1900.0,
    stepSize: 1.0,
    dwellTime: 1000,
    scanSpeed: 10,
    numberOfScans: 1,
    infiniteScans: false,
    bidirectionalScanning: false,
    manualStepMode: false
  })
  
  // MultiSpectral table data
  const [multiSpectralEntries, setMultiSpectralEntries] = useState<MultiSpectralEntry[]>([
    { id: 1, wavenumber: 1638.8, dwellTime: 3997, offTime: 2000 }
  ])
  const [nextId, setNextId] = useState(2)
  const [numberOfScans, setNumberOfScans] = useState(1)
  const [keepLaserOnBetweenSteps, setKeepLaserOnBetweenSteps] = useState(false)
  const [infiniteScans, setInfiniteScans] = useState(false)
  
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [scanInProgress, setScanInProgress] = useState(false)

  const canInteract = deviceStatus?.connected && deviceStatus?.armed

  // Convert between units
  const convertToMicrons = (wavenum: number) => (10000 / wavenum)
  const convertToWavenumber = (microns: number) => (10000 / microns)

  // Validate and correct input values to QCL range
  const validateAndCorrectValue = (value: number, field: 'wavenumber' | 'stepSize' = 'wavenumber') => {
    let min, max, correctedValue = value
    
    if (field === 'wavenumber') {
      if (units === 'cm-1') {
        min = 1638.81
        max = 2077.27
      } else {
        min = convertToMicrons(2077.27) // ~4.81 μm
        max = convertToMicrons(1638.81) // ~6.1 μm
      }
      
      if (value < min) correctedValue = min
      if (value > max) correctedValue = max
      
      // Limit decimals for microns
      if (units === 'μm') {
        correctedValue = Number(correctedValue.toFixed(2))
      }
    }
    
    return correctedValue
  }

  const handleScanModeSelect = (mode: string) => {
    setSelectedScanMode(mode)
  }

  const handleUnitChange = (newUnit: 'cm-1' | 'μm') => {
    if (newUnit !== units) {
      if (newUnit === 'μm') {
        setScanSettings(prev => ({
          ...prev,
          startWavenumber: convertToMicrons(prev.startWavenumber),
          endWavenumber: convertToMicrons(prev.endWavenumber)
        }))
        setMultiSpectralEntries(prev => prev.map(entry => ({
          ...entry,
          wavenumber: convertToMicrons(entry.wavenumber)
        })))
      } else {
        setScanSettings(prev => ({
          ...prev,
          startWavenumber: convertToWavenumber(prev.startWavenumber),
          endWavenumber: convertToWavenumber(prev.endWavenumber)
        }))
        setMultiSpectralEntries(prev => prev.map(entry => ({
          ...entry,
          wavenumber: convertToWavenumber(entry.wavenumber)
        })))
      }
      setUnits(newUnit)
    }
  }

  const addMultiSpectralEntry = () => {
    const newEntry: MultiSpectralEntry = {
      id: nextId,
      wavenumber: units === 'cm-1' ? 1850.0 : convertToMicrons(1850.0),
      dwellTime: 3997,
      offTime: 2000
    }
    setMultiSpectralEntries(prev => [...prev, newEntry])
    setNextId(prev => prev + 1)
  }

  const removeMultiSpectralEntry = (id: number) => {
    setMultiSpectralEntries(prev => prev.filter(entry => entry.id !== id))
  }

  const updateMultiSpectralEntry = (id: number, field: keyof MultiSpectralEntry, value: number) => {
    let correctedValue = value
    
    // Auto-revert to QCL range if invalid
    if (field === 'wavenumber') {
      const min = units === 'cm-1' ? 1638.81 : convertToMicrons(2077.27)
      const max = units === 'cm-1' ? 2077.27 : convertToMicrons(1638.81)
      
      if (value < min) correctedValue = min
      if (value > max) correctedValue = max
      
      // Limit decimals for microns
      if (units === 'μm') {
        correctedValue = Number(correctedValue.toFixed(2))
      }
    }
    
    setMultiSpectralEntries(prev => prev.map(entry => 
      entry.id === id ? { ...entry, [field]: correctedValue } : entry
    ))
  }

  const handleManualStep = () => {
    console.log('Manual step executed')
  }

  const handleStartScan = async () => {
    setLoading(true)
    setError(null)
    try {
      console.log('Starting scan:', selectedScanMode, scanSettings)
      setScanInProgress(true)
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
      console.log('Stopping scan')
      setScanInProgress(false)
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
      {selectedScanMode && selectedScanMode !== 'multispectral' && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              {selectedScanMode === 'sweep' && 'Sweep Scan Settings'}
              {selectedScanMode === 'step' && 'Step Scan Settings'}
            </Typography>

            <Grid container spacing={2} alignItems="center">
              <Grid item xs={12} md={3}>
                <FormControl fullWidth disabled={!canInteract}>
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
              </Grid>
              
              <Grid item xs={6} md={3}>
                <TextField
                  fullWidth
                  label={`Start (${units})`}
                  type="number"
                  value={scanSettings.startWavenumber}
                  onChange={(e) => setScanSettings(prev => ({ ...prev, startWavenumber: parseFloat(e.target.value) || 0 }))}
                  onBlur={(e) => {
                    const correctedValue = validateAndCorrectValue(parseFloat(e.target.value) || 0)
                    setScanSettings(prev => ({ ...prev, startWavenumber: correctedValue }))
                  }}
                  disabled={!canInteract}
                  inputProps={{ step: units === 'cm-1' ? 0.01 : 0.001 }}
                />
              </Grid>
              <Grid item xs={6} md={3}>
                <TextField
                  fullWidth
                  label={`End (${units})`}
                  type="number"
                  value={scanSettings.endWavenumber}
                  onChange={(e) => setScanSettings(prev => ({ ...prev, endWavenumber: parseFloat(e.target.value) || 0 }))}
                  onBlur={(e) => {
                    const correctedValue = validateAndCorrectValue(parseFloat(e.target.value) || 0)
                    setScanSettings(prev => ({ ...prev, endWavenumber: correctedValue }))
                  }}
                  disabled={!canInteract}
                  inputProps={{ step: units === 'cm-1' ? 0.01 : 0.001 }}
                />
              </Grid>

              {selectedScanMode === 'step' && (
                <>
                  <Grid item xs={6} md={3}>
                    <TextField
                      fullWidth
                      label={`Step Size (${units})`}
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
                  <Grid item xs={12}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={scanSettings.manualStepMode}
                          onChange={(e) => setScanSettings(prev => ({ ...prev, manualStepMode: e.target.checked }))}
                          disabled={!canInteract}
                        />
                      }
                      label="Manual Step Mode"
                    />
                  </Grid>
                </>
              )}

              {selectedScanMode === 'sweep' && (
                <>
                  <Grid item xs={6} md={3}>
                    <TextField
                      fullWidth
                      label={`Scan Speed (${units}/s)`}
                      type="number"
                      value={scanSettings.scanSpeed}
                      onChange={(e) => setScanSettings(prev => ({ ...prev, scanSpeed: parseFloat(e.target.value) }))}
                      disabled={!canInteract}
                      inputProps={{ min: 0.1, max: 100, step: 0.1 }}
                    />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
                      <TextField
                        label="Number of Scans"
                        type="number"
                        value={scanSettings.numberOfScans}
                        onChange={(e) => setScanSettings(prev => ({ ...prev, numberOfScans: parseInt(e.target.value) }))}
                        disabled={!canInteract || scanSettings.infiniteScans}
                        inputProps={{ min: 1, max: 999, step: 1 }}
                        sx={{ width: 140 }}
                      />
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={scanSettings.infiniteScans}
                            onChange={(e) => setScanSettings(prev => ({ ...prev, infiniteScans: e.target.checked }))}
                            disabled={!canInteract}
                          />
                        }
                        label="Infinite"
                      />
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={scanSettings.bidirectionalScanning}
                            onChange={(e) => setScanSettings(prev => ({ ...prev, bidirectionalScanning: e.target.checked }))}
                            disabled={!canInteract}
                          />
                        }
                        label="Bi-directional"
                      />
                    </Box>
                  </Grid>
                </>
              )}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Multi-Spectral Scan Settings */}
      {selectedScanMode === 'multispectral' && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Multi-Spectral Scan Settings
            </Typography>
            
            <Box sx={{ mb: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
              <Typography>Scan Mode:</Typography>
              <Typography fontWeight="bold">Multi-Spectral Mode</Typography>
              
              <Typography sx={{ ml: 4 }}>Multi-Spectral Mode Units:</Typography>
              <FormControl size="small" disabled={!canInteract}>
                <Select
                  value={units}
                  onChange={(e) => handleUnitChange(e.target.value as 'cm-1' | 'μm')}
                >
                  <MenuItem value="cm-1">cm-1</MenuItem>
                  <MenuItem value="μm">μm</MenuItem>
                </Select>
              </FormControl>
            </Box>

            <TableContainer component={Paper} sx={{ mb: 2 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell align="center">Wave number</TableCell>
                    <TableCell align="center">Dwell Time (ms)</TableCell>
                    <TableCell align="center">Off Time (ms)</TableCell>
                    <TableCell align="center">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {multiSpectralEntries.map((entry) => (
                    <TableRow key={entry.id}>
                      <TableCell>
                        <TextField
                          type="number"
                          value={entry.wavenumber || ''}
                          onChange={(e) => updateMultiSpectralEntry(entry.id, 'wavenumber', parseFloat(e.target.value) || 0)}
                          onBlur={(e) => {
                            const correctedValue = validateAndCorrectValue(parseFloat(e.target.value) || 0)
                            updateMultiSpectralEntry(entry.id, 'wavenumber', correctedValue)
                          }}
                          disabled={!canInteract}
                          size="small"
                          inputProps={{ step: units === 'cm-1' ? 0.1 : 0.001 }}
                        />
                      </TableCell>
                      <TableCell>
                        <TextField
                          type="number"
                          value={entry.dwellTime}
                          onChange={(e) => updateMultiSpectralEntry(entry.id, 'dwellTime', parseInt(e.target.value))}
                          disabled={!canInteract}
                          size="small"
                          inputProps={{ min: 100, step: 1 }}
                        />
                      </TableCell>
                      <TableCell>
                        <TextField
                          type="number"
                          value={entry.offTime}
                          onChange={(e) => updateMultiSpectralEntry(entry.id, 'offTime', parseInt(e.target.value))}
                          disabled={!canInteract}
                          size="small"
                          inputProps={{ min: 100, step: 1 }}
                        />
                      </TableCell>
                      <TableCell>
                        <IconButton 
                          onClick={() => removeMultiSpectralEntry(entry.id)}
                          disabled={!canInteract || multiSpectralEntries.length <= 1}
                          size="small"
                        >
                          <DeleteIcon />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            <Box sx={{ display: 'flex', gap: 2, mb: 2, alignItems: 'center' }}>
              <Button
                startIcon={<AddIcon />}
                onClick={addMultiSpectralEntry}
                disabled={!canInteract}
                variant="outlined"
                size="small"
              >
                Add
              </Button>
            </Box>

            <Box sx={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={keepLaserOnBetweenSteps}
                    onChange={(e) => setKeepLaserOnBetweenSteps(e.target.checked)}
                    disabled={!canInteract}
                  />
                }
                label="Keep Laser On Between Steps"
              />
              
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography>Number of Scans:</Typography>
                <TextField
                  type="number"
                  value={numberOfScans}
                  onChange={(e) => setNumberOfScans(parseInt(e.target.value))}
                  disabled={!canInteract || infiniteScans}
                  size="small"
                  sx={{ width: 80 }}
                  inputProps={{ min: 1, max: 999 }}
                />
                <Typography>- Or -</Typography>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={infiniteScans}
                      onChange={(e) => setInfiniteScans(e.target.checked)}
                      disabled={!canInteract}
                    />
                  }
                  label="Infinite"
                />
              </Box>
            </Box>
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
                disabled={!canInteract || loading || !scanInProgress}
                color="error"
              >
                Stop Scan
              </Button>

              {selectedScanMode === 'step' && scanSettings.manualStepMode && (
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
                Scan Progress: {scanInProgress ? 'In Progress...' : 'Ready'}
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