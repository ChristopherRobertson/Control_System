import { useEffect, useRef, useState } from 'react'
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
import { MIRcatAPI } from '../api'

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
  
  // MultiSpectral table data - start with NO entries; add via form below
  const [multiSpectralEntries, setMultiSpectralEntries] = useState<MultiSpectralEntry[]>([])
  const [nextId, setNextId] = useState(1)
  const [numberOfScans, setNumberOfScans] = useState(1)
  const [keepLaserOnBetweenSteps, setKeepLaserOnBetweenSteps] = useState(false)
  const [infiniteScans, setInfiniteScans] = useState(false)

  // New-entry draft fields (use strings to avoid numeric input UX quirks)
  const [draftWn, setDraftWn] = useState<string>('')
  const [draftDwell, setDraftDwell] = useState<string>('')
  const [draftOff, setDraftOff] = useState<string>('')
  
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [manualStepEnabled, setManualStepEnabled] = useState(false)
  // Get scan status from backend instead of local state
  const scanInProgress = deviceStatus?.scan_in_progress || false

  const canInteract = deviceStatus?.connected && deviceStatus?.armed

  // Derived scan loop counter based on percent resets (SDK cur_scan may be misleading)
  const [loopCount, setLoopCount] = useState<number>(0)
  const prevPercentRef = useRef<number | null>(null)
  const prevInProgressRef = useRef<boolean>(false)
  const msBaselineScanNumRef = useRef<number | null>(null)
  const msElementsRef = useRef<number>(0)
  const prevModeRef = useRef<string | null>(null)
  useEffect(() => {
    const curInProgress = !!scanInProgress
    const curPercent = typeof deviceStatus?.current_scan_percent === 'number' ? (deviceStatus.current_scan_percent as number) : null
    const curScanNum = typeof deviceStatus?.current_scan_number === 'number' ? (deviceStatus.current_scan_number as number) : null
    const activeMode = deviceStatus?.current_scan_mode || null

    // Reset loop count on scan stop or mode change
    if (!curInProgress || (prevModeRef.current && activeMode && prevModeRef.current !== activeMode)) {
      setLoopCount(0)
      prevPercentRef.current = null
      msBaselineScanNumRef.current = null
    }

    if (curInProgress) {
      // On scan start
      if (!prevInProgressRef.current) {
        setLoopCount(1)
        // Capture multispectral baseline if applicable
        if (activeMode === 'multispectral') {
          msBaselineScanNumRef.current = curScanNum ?? 0
          msElementsRef.current = multiSpectralEntries.length || 1
        }
      } else {
        // Heuristic 1: Detect percent wrap-around with relaxed thresholds
        if (prevPercentRef.current != null && curPercent != null) {
          const prevP = prevPercentRef.current
          const drop = prevP - curPercent
          if ((prevP > 80 && curPercent < 30) || drop > 50) {
            setLoopCount(v => v + 1)
          }
        }

        // Heuristic 2: For multispectral, derive loops from scan number delta vs elements
        if (activeMode === 'multispectral' && curScanNum != null) {
          const base = msBaselineScanNumRef.current ?? curScanNum
          const elems = Math.max(1, msElementsRef.current || multiSpectralEntries.length || 1)
          if (msBaselineScanNumRef.current == null) {
            msBaselineScanNumRef.current = base
          }
          if (curScanNum >= base) {
            const loopsByIdx = Math.floor((curScanNum - base) / elems) + 1
            if (loopsByIdx > loopCount) setLoopCount(loopsByIdx)
          }
        }
      }
    }

    prevInProgressRef.current = curInProgress
    if (curPercent != null) prevPercentRef.current = curPercent
    prevModeRef.current = activeMode
  }, [scanInProgress, deviceStatus?.current_scan_percent, deviceStatus?.current_scan_number, deviceStatus?.current_scan_mode, multiSpectralEntries.length])

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
      // Reset draft inputs when changing units to avoid confusion
      setDraftWn('')
      setDraftDwell('')
      setDraftOff('')
    }
  }

  const addMultiSpectralEntry = () => {
    // Validate inputs and add to list
    const wnVal = parseFloat(draftWn)
    const dwellVal = parseInt(draftDwell)
    const offVal = parseInt(draftOff)
    if (!isFinite(wnVal)) return
    if (!isFinite(dwellVal as any) || dwellVal <= 0) return
    if (!isFinite(offVal as any) || offVal <= 0) return

    // Clamp to valid wn range in current units then add
    const correctedWn = validateAndCorrectValue(wnVal, 'wavenumber')

    const newEntry: MultiSpectralEntry = {
      id: nextId,
      wavenumber: correctedWn,
      dwellTime: dwellVal,
      offTime: offVal
    }
    setMultiSpectralEntries(prev => [...prev, newEntry])
    setNextId(prev => prev + 1)
    // Clear drafts
    setDraftWn('')
    setDraftDwell('')
    setDraftOff('')
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

  useEffect(() => {
    (async () => {
      try {
        const data = await MIRcatAPI.getUserSettings()
        const mode = data?.processTriggerMode
        setManualStepEnabled(mode === 'manual' || mode === 'Use Manual Step Mode')
      } catch {}
    })()
  }, [])

  const handleManualStep = async () => {
    setLoading(true)
    try {
      await MIRcatAPI.manualStep()
      await onStatusUpdate()
    } catch (err: any) {
      console.error('Manual step error:', err)
      setError(err.response?.data?.detail || err.message || 'Manual step failed')
    } finally {
      setLoading(false)
    }
  }

  const handleStartScan = async () => {
    setLoading(true)
    setError(null)
    try {
      let result
      
      if (selectedScanMode === 'sweep') {
        result = await MIRcatAPI.startSweepScan({
          start_wavenumber: scanSettings.startWavenumber,
          end_wavenumber: scanSettings.endWavenumber,
          scan_speed: scanSettings.scanSpeed,
          number_of_scans: scanSettings.infiniteScans ? 0 : scanSettings.numberOfScans,
          bidirectional_scanning: scanSettings.bidirectionalScanning
        })
      } else if (selectedScanMode === 'step') {
        result = await MIRcatAPI.startStepScan({
          start_wavenumber: scanSettings.startWavenumber,
          end_wavenumber: scanSettings.endWavenumber,
          step_size: scanSettings.stepSize,
          dwell_time: scanSettings.dwellTime,
          number_of_scans: scanSettings.numberOfScans
        })
      } else if (selectedScanMode === 'multispectral') {
        // Ensure any focused input commits onBlur before reading state
        try { (document.activeElement as HTMLElement | null)?.blur() } catch {}

        // Require at least two elements as per UI rule
        if (multiSpectralEntries.length < 2) {
          throw new Error('Add at least two entries before starting a multispectral scan')
        }

        const wavelengthList = multiSpectralEntries.map(entry => ({
          wavenumber: units === 'μm' ? convertToWavenumber(entry.wavenumber) : entry.wavenumber,
          dwell_time: entry.dwellTime,
          off_time: entry.offTime
        }))
        const scans = infiniteScans ? 0 : (Number.isFinite(numberOfScans) && numberOfScans > 0 ? numberOfScans : 1)
        result = await MIRcatAPI.startMultispectralScan({
          wavelength_list: wavelengthList,
          number_of_scans: scans,
          keep_laser_on_between_steps: keepLaserOnBetweenSteps
        })
      }
      
      console.log('Scan started successfully:', result?.message)
      
      // Update status from backend instead of setting local state
      await onStatusUpdate()
      
    } catch (err: any) {
      console.error('Start scan error:', err)
      setError(err.response?.data?.detail || err.message || 'Failed to start scan')
    } finally {
      setLoading(false)
    }
  }

  const handleStopScan = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await MIRcatAPI.stopScan()
      console.log('Scan stopped successfully:', result.message)
      
      // Update status from backend instead of setting local state
      await onStatusUpdate()
      
    } catch (err: any) {
      console.error('Stop scan error:', err)
      setError(err.response?.data?.detail || err.message || 'Failed to stop scan')
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
                  {/* Dwell time controlled by Laser Settings (Internal Trigger Step Time) */}
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

            {/* Add-entry form */}
            <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
              <TextField
                label={units === 'cm-1' ? 'Wavenumber (cm-1)' : 'Wavelength (μm)'}
                placeholder={units === 'cm-1' ? 'e.g. 1850.0' : 'e.g. 5.405'}
                value={draftWn}
                onChange={(e) => setDraftWn(e.target.value)}
                onBlur={() => {
                  const v = parseFloat(draftWn)
                  if (isFinite(v)) setDraftWn(validateAndCorrectValue(v).toString())
                }}
                inputMode="decimal"
                disabled={!canInteract}
                size="small"
                sx={{ minWidth: 180 }}
              />
              <TextField
                label="Dwell Time (ms)"
                placeholder="e.g. 5000"
                value={draftDwell}
                onChange={(e) => setDraftDwell(e.target.value.replace(/[^0-9]/g, ''))}
                inputMode="numeric"
                disabled={!canInteract}
                size="small"
                sx={{ width: 140 }}
              />
              <TextField
                label="Off Time (ms)"
                placeholder="e.g. 100"
                value={draftOff}
                onChange={(e) => setDraftOff(e.target.value.replace(/[^0-9]/g, ''))}
                inputMode="numeric"
                disabled={!canInteract}
                size="small"
                sx={{ width: 140 }}
              />
              <Button
                startIcon={<AddIcon />}
                onClick={addMultiSpectralEntry}
                disabled={!canInteract || !draftWn || !draftDwell || !draftOff}
                variant="outlined"
                size="small"
              >
                Add Entry
              </Button>
            </Box>

            {/* Entries table */}
            <TableContainer component={Paper} sx={{ mb: 2 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell align="center">{units === 'cm-1' ? 'Wavenumber (cm-1)' : 'Wavelength (μm)'}</TableCell>
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
                          type="text"
                          defaultValue={entry.wavenumber}
                          onBlur={(e) => {
                            const v = parseFloat(e.target.value)
                            const correctedValue = isFinite(v) ? validateAndCorrectValue(v) : (units === 'cm-1' ? 1850.0 : convertToMicrons(1850.0))
                            updateMultiSpectralEntry(entry.id, 'wavenumber', correctedValue)
                            // Normalize displayed value
                            e.currentTarget.value = String(correctedValue)
                          }}
                          inputMode="decimal"
                          disabled={!canInteract}
                          size="small"
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

            {/* Removed old Add button (replaced by add-entry form above) */}
            <Box sx={{ display: 'flex', gap: 2, mb: 2, alignItems: 'center' }}></Box>

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
                disabled={!canInteract || loading || scanInProgress || multiSpectralEntries.length < (selectedScanMode === 'multispectral' ? 2 : 0)}
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

              {selectedScanMode === 'step' && manualStepEnabled && (
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
                Scan Progress: {scanInProgress ? `${deviceStatus?.current_scan_percent ?? 0}%` : 'Ready'} {scanInProgress && loopCount > 0 ? (
                  selectedScanMode === 'multispectral'
                    ? `(Scan ${loopCount}${infiniteScans ? ' of ∞' : ` of ${numberOfScans || 1}`})`
                    : `(Scan ${loopCount})`
                ) : ''}
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
