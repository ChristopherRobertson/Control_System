import React, { useState } from 'react'
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
  Grid
} from '@mui/material'
import { Tune as TuneIcon } from '@mui/icons-material'
import { MIRcatAPI } from '../api'

interface TuningControlsProps {
  deviceStatus: any
  onStatusUpdate: () => void
}

function TuningControls({ deviceStatus, onStatusUpdate }: TuningControlsProps) {
  const [wavenumber, setWavenumber] = useState(1850.0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleTune = async () => {
    setLoading(true)
    setError(null)
    try {
      await MIRcatAPI.tuneToWavenumber(wavenumber)
      onStatusUpdate()
    } catch (err) {
      setError('Failed to tune laser')
      console.error('Tune error:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleManualTune = () => {
    // Manual tune mode
    handleTune()
  }

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
        <Grid item xs={12}>
          <Card variant="outlined">
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Typography variant="body1">
                  Wavenumber:
                </Typography>
                <TextField
                  type="number"
                  value={wavenumber}
                  onChange={(e) => setWavenumber(parseFloat(e.target.value))}
                  inputProps={{
                    min: 1638.81,
                    max: 2077.27,
                    step: 0.01
                  }}
                  sx={{ width: 120 }}
                />
                <FormControl sx={{ minWidth: 80 }}>
                  <InputLabel>Units</InputLabel>
                  <Select
                    value="cm-1"
                    label="Units"
                  >
                    <MenuItem value="cm-1">cm-1</MenuItem>
                    <MenuItem value="μm">μm</MenuItem>
                  </Select>
                </FormControl>
              </Box>

              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                  variant="contained"
                  startIcon={<TuneIcon />}
                  onClick={handleTune}
                  disabled={!deviceStatus?.connected || loading}
                  color="primary"
                >
                  Tune to {wavenumber} cm-1
                </Button>
                <Button
                  variant="outlined"
                  onClick={() => setWavenumber(1850)}
                  disabled={loading}
                >
                  Cancel
                </Button>
                <Button
                  variant="outlined"
                  onClick={handleManualTune}
                  disabled={!deviceStatus?.connected || loading}
                >
                  Manual Tune
                </Button>
                <Button
                  variant="outlined"
                  disabled={loading}
                >
                  Extended Info
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6" gutterBottom>
                QCL Information
              </Typography>
              <Box sx={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                gap: 2,
                mt: 1
              }}>
                <Box sx={{ textAlign: 'center', p: 2, border: '1px solid', borderColor: 'divider' }}>
                  <Typography variant="body2" color="text.secondary">QCL 1</Typography>
                  <Typography variant="body1">2077.3 to 1638.8 cm-1</Typography>
                </Box>
                <Box sx={{ textAlign: 'center', p: 2, border: '1px solid', borderColor: 'divider', opacity: 0.5 }}>
                  <Typography variant="body2" color="text.secondary">QCL 2</Typography>
                  <Typography variant="body1">Future</Typography>
                </Box>
                <Box sx={{ textAlign: 'center', p: 2, border: '1px solid', borderColor: 'divider', opacity: 0.5 }}>
                  <Typography variant="body2" color="text.secondary">QCL 3</Typography>
                  <Typography variant="body1">Future</Typography>
                </Box>
                <Box sx={{ textAlign: 'center', p: 2, border: '1px solid', borderColor: 'divider', opacity: 0.5 }}>
                  <Typography variant="body2" color="text.secondary">QCL 4</Typography>
                  <Typography variant="body1">Future</Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6" gutterBottom>
                QCL Information Table
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
                <Typography variant="body2" fontWeight="bold">TEMP (C)</Typography>
                <Typography variant="body2" fontWeight="bold">ACTIVE</Typography>
                <Typography variant="body2" fontWeight="bold">TEC mA</Typography>
                <Typography variant="body2" fontWeight="bold">TEC V</Typography>
                <Typography variant="body2" fontWeight="bold"></Typography>
                
                <Typography variant="body2">{deviceStatus?.status.case_temp_1 || '19.160'}</Typography>
                <Typography variant="body2">N</Typography>
                <Typography variant="body2">9</Typography>
                <Typography variant="body2">-0.19</Typography>
                <Typography variant="body2">1</Typography>
                
                <Typography variant="body2" color="text.disabled">--</Typography>
                <Typography variant="body2" color="text.disabled">--</Typography>
                <Typography variant="body2" color="text.disabled">--</Typography>
                <Typography variant="body2" color="text.disabled">--</Typography>
                <Typography variant="body2">2</Typography>
                
                <Typography variant="body2" color="text.disabled">--</Typography>
                <Typography variant="body2" color="text.disabled">--</Typography>
                <Typography variant="body2" color="text.disabled">--</Typography>
                <Typography variant="body2" color="text.disabled">--</Typography>
                <Typography variant="body2">3</Typography>
                
                <Typography variant="body2" color="text.disabled">--</Typography>
                <Typography variant="body2" color="text.disabled">--</Typography>
                <Typography variant="body2" color="text.disabled">--</Typography>
                <Typography variant="body2" color="text.disabled">--</Typography>
                <Typography variant="body2">4</Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {!deviceStatus?.connected && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Connect to device to enable tuning controls
        </Typography>
      )}
    </Box>
  )
}

export default TuningControls