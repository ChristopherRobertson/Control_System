import { Grid, Card, CardContent, Typography, Box, FormControl, Select, MenuItem, TextField, Switch, FormControlLabel } from '@mui/material'
import { QCStatus } from '../api'

interface Props {
  status: QCStatus
  disabled?: boolean
  onChange: (patch: any) => Promise<void> | void
}

function SystemPanel({ status, disabled, onChange }: Props) {
  const sys = status.system_settings
  const info = status.device_info || {}
  const ranges = status.ranges || {}
  return (
    <Grid container spacing={3}>
      <Grid item xs={12} md={6}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>System</Typography>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" gutterBottom>Pulse Mode</Typography>
              <FormControl fullWidth size="small" disabled={disabled}>
                <Select value={sys.pulse_mode} onChange={(e) => onChange({ pulse_mode: e.target.value })}>
                  <MenuItem value="Continuous">Continuous</MenuItem>
                  <MenuItem value="Burst">Burst</MenuItem>
                  <MenuItem value="Single">Single</MenuItem>
                </Select>
              </FormControl>
            </Box>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" gutterBottom>Period (s)</Typography>
              <TextField fullWidth size="small" type="number" value={sys.period_s}
                inputProps={{ step: 0.00000001, min: ranges.period_min_s, max: ranges.period_max_s }}
                helperText={`min ${ranges.period_min_s ?? ''}  max ${ranges.period_max_s ?? ''}`}
                onBlur={(e) => onChange({ period_s: Number(e.target.value) })} disabled={disabled} />
            </Box>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Typography variant="body2" gutterBottom>Burst Count</Typography>
                <TextField fullWidth size="small" type="number" value={sys.burst_count}
                  inputProps={{ min: ranges.burst_count_min, max: ranges.burst_count_max }}
                  helperText={`min ${ranges.burst_count_min ?? ''}  max ${ranges.burst_count_max ?? ''}`}
                  onBlur={(e) => onChange({ burst_count: Number(e.target.value) })} disabled={disabled} />
              </Grid>
              <Grid item xs={6}>
                <FormControlLabel control={<Switch checked={sys.auto_start} onChange={(e) => onChange({ auto_start: e.target.checked })} disabled={disabled} />} label="Auto Start" />
              </Grid>
            </Grid>
            <Grid container spacing={2} sx={{ mt: 1 }}>
              <Grid item xs={6}>
                <Typography variant="body2" gutterBottom>Duty On (counts)</Typography>
                <TextField size="small" type="number" value={sys.duty_cycle_on_counts}
                  inputProps={{ min: ranges.duty_cycle_on_min, max: ranges.duty_cycle_on_max }}
                  helperText={`min ${ranges.duty_cycle_on_min ?? ''}  max ${ranges.duty_cycle_on_max ?? ''}`}
                  onBlur={(e) => onChange({ duty_cycle_on_counts: Number(e.target.value) })} disabled={disabled} />
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" gutterBottom>Duty Off (counts)</Typography>
                <TextField size="small" type="number" value={sys.duty_cycle_off_counts}
                  inputProps={{ min: ranges.duty_cycle_off_min, max: ranges.duty_cycle_off_max }}
                  helperText={`min ${ranges.duty_cycle_off_min ?? ''}  max ${ranges.duty_cycle_off_max ?? ''}`}
                  onBlur={(e) => onChange({ duty_cycle_off_counts: Number(e.target.value) })} disabled={disabled} />
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      </Grid>
      <Grid item xs={12} md={6}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>System Info</Typography>
            <Typography variant="body2">Model: {info.model || 'QC 9524'}</Typography>
            <Typography variant="body2">Serial: {info.serial_number || 'n/a'}</Typography>
            <Typography variant="body2">Firmware: {info.firmware_version || 'n/a'}</Typography>
            <Typography variant="body2">FPGA: {info.fpga_version || 'n/a'}</Typography>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  )
}

export default SystemPanel

