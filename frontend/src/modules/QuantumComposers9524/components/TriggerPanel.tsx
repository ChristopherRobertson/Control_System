import { Card, CardContent, Typography, Grid, FormControl, Select, MenuItem, TextField } from '@mui/material'
import { QCStatus } from '../api'

interface Props {
  status: QCStatus
  disabled?: boolean
  onChange: (patch: any) => Promise<void> | void
}

function TriggerPanel({ status, disabled, onChange }: Props) {
  const ext = status.external_trigger
  const ranges = status.ranges || {}
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>External Trigger / Gate</Typography>
        <Grid container spacing={2}>
          <Grid item xs={6}>
            <Typography variant="body2" gutterBottom>Trigger Mode</Typography>
            <FormControl fullWidth size="small" disabled={disabled}>
              <Select value={ext.trigger_mode} onChange={(e) => onChange({ trigger_mode: e.target.value })}>
                <MenuItem value="Disabled">Disabled</MenuItem>
                <MenuItem value="Enabled">Enabled</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={6}>
            <Typography variant="body2" gutterBottom>Gate Mode</Typography>
            <FormControl fullWidth size="small" disabled={disabled}>
              <Select value={ext.gate_mode} onChange={(e) => onChange({ gate_mode: e.target.value })}>
                <MenuItem value="Disabled">Disabled</MenuItem>
                <MenuItem value="Enabled">Enabled</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={6}>
            <Typography variant="body2" gutterBottom>Trigger Edge</Typography>
            <FormControl fullWidth size="small" disabled={disabled}>
              <Select value={ext.trigger_edge} onChange={(e) => onChange({ trigger_edge: e.target.value })}>
                <MenuItem value="Rising">Rising</MenuItem>
                <MenuItem value="Falling">Falling</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={6}>
            <Typography variant="body2" gutterBottom>Gate Logic</Typography>
            <FormControl fullWidth size="small" disabled={disabled}>
              <Select value={ext.gate_logic} onChange={(e) => onChange({ gate_logic: e.target.value })}>
                <MenuItem value="High">High</MenuItem>
                <MenuItem value="Low">Low</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={6}>
            <Typography variant="body2" gutterBottom>Trigger Threshold (V)</Typography>
            <TextField size="small" type="number" value={ext.trigger_threshold_v}
              inputProps={{ min: ranges.trigger_threshold_min_v, max: ranges.trigger_threshold_max_v, step: 0.01 }}
              helperText={`min ${ranges.trigger_threshold_min_v ?? ''}  max ${ranges.trigger_threshold_max_v ?? ''}`}
              onBlur={(e) => onChange({ trigger_threshold_v: Number(e.target.value) })}
              disabled={disabled}
            />
          </Grid>
          <Grid item xs={6}>
            <Typography variant="body2" gutterBottom>Gate Threshold (V)</Typography>
            <TextField size="small" type="number" value={ext.gate_threshold_v}
              inputProps={{ min: ranges.gate_threshold_min_v, max: ranges.gate_threshold_max_v, step: 0.01 }}
              helperText={`min ${ranges.gate_threshold_min_v ?? ''}  max ${ranges.gate_threshold_max_v ?? ''}`}
              onBlur={(e) => onChange({ gate_threshold_v: Number(e.target.value) })}
              disabled={disabled}
            />
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  )
}

export default TriggerPanel

