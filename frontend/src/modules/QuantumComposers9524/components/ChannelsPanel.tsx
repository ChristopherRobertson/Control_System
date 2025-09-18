import { Card, CardContent, Typography, Box, Grid, FormControlLabel, Switch, TextField, FormControl, Select, MenuItem, Button } from '@mui/material'
import { QCChannelKey, QCStatus } from '../api'

interface Props {
  status: QCStatus
  selected: QCChannelKey
  onSelect: (ch: QCChannelKey) => void
  onSystemChange: (patch: any) => Promise<void> | void
  onChange: (patch: any) => Promise<void> | void
  disabled?: boolean
}

function ChannelsPanel({ status, selected, onSelect, onSystemChange, onChange, disabled }: Props) {
  const sys = status.system_settings
  const ch = status.channels[selected]
  const ranges = status.ranges || {}

  const normalize = (value: string | undefined) => (value || '').replace(/\s+/g, '').toLowerCase()

  const systemMode = normalize(sys.pulse_mode)
  const channelMode = normalize(ch.channel_mode)

  const showSystemBurst = systemMode === 'burst'
  const showSystemDuty = systemMode === 'dutycycle'
  const showChannelBurst = showSystemBurst || channelMode === 'burst'
  const showChannelDuty = showSystemDuty || channelMode === 'dutycycle'

  const channelControlsDisabled = !!disabled || !ch.enabled

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>System Settings</Typography>
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} md={4}>
            <Typography variant="body2" gutterBottom>Pulse Mode</Typography>
            <FormControl fullWidth size="small" disabled={disabled}>
              <Select
                value={sys.pulse_mode || 'Continuous'}
                onChange={(e) => onSystemChange({ pulse_mode: e.target.value })}
              >
                <MenuItem value="Continuous">Continuous</MenuItem>
                <MenuItem value="Burst">Burst</MenuItem>
                <MenuItem value="Single">Single</MenuItem>
                <MenuItem value="DutyCycle">Duty Cycle</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={4} sx={{ display: 'flex', alignItems: 'center' }}>
            <FormControlLabel
              control={<Switch checked={!!sys.auto_start} onChange={(e) => onSystemChange({ auto_start: e.target.checked })} disabled={disabled} />}
              label="Auto Start"
            />
          </Grid>
          {showSystemBurst && (
            <Grid item xs={12} md={4}>
              <Typography variant="body2" gutterBottom>System Burst Count</Typography>
              <TextField
                fullWidth
                size="small"
                type="number"
                value={sys.burst_count}
                inputProps={{ min: ranges.burst_count_min, max: ranges.burst_count_max }}
                helperText={`min ${ranges.burst_count_min ?? ''}  max ${ranges.burst_count_max ?? ''}`}
                onBlur={(e) => onSystemChange({ burst_count: Number(e.target.value) })}
                disabled={disabled}
              />
            </Grid>
          )}
          {showSystemDuty && (
            <>
              <Grid item xs={12} md={4}>
                <Typography variant="body2" gutterBottom>Duty On (counts)</Typography>
                <TextField
                  fullWidth
                  size="small"
                  type="number"
                  value={sys.duty_cycle_on_counts}
                  inputProps={{ min: ranges.duty_cycle_on_min, max: ranges.duty_cycle_on_max }}
                  helperText={`min ${ranges.duty_cycle_on_min ?? ''}  max ${ranges.duty_cycle_on_max ?? ''}`}
                  onBlur={(e) => onSystemChange({ duty_cycle_on_counts: Number(e.target.value) })}
                  disabled={disabled}
                />
              </Grid>
              <Grid item xs={12} md={4}>
                <Typography variant="body2" gutterBottom>Duty Off (counts)</Typography>
                <TextField
                  fullWidth
                  size="small"
                  type="number"
                  value={sys.duty_cycle_off_counts}
                  inputProps={{ min: ranges.duty_cycle_off_min, max: ranges.duty_cycle_off_max }}
                  helperText={`min ${ranges.duty_cycle_off_min ?? ''}  max ${ranges.duty_cycle_off_max ?? ''}`}
                  onBlur={(e) => onSystemChange({ duty_cycle_off_counts: Number(e.target.value) })}
                  disabled={disabled}
                />
              </Grid>
            </>
          )}
        </Grid>

        <Typography variant="h6" gutterBottom>Channels</Typography>
        <Box sx={{ display: 'flex', gap: 1, mb: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          {( ['A','B','C','D'] as QCChannelKey[]).map((key) => (
            <Button key={key} variant={selected === key ? 'contained' : 'outlined'} size="small" onClick={() => onSelect(key)} disabled={disabled}>Ch {key}</Button>
          ))}
        </Box>

        <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
          <FormControlLabel control={<Switch checked={!!ch.enabled} onChange={(e) => onChange({ enabled: e.target.checked })} disabled={disabled} />} label="Enabled" />

          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} md={6}>
              <Typography variant="body2" gutterBottom>Delay (s)</Typography>
              <TextField fullWidth size="small" type="number" value={ch.delay_s}
                inputProps={{ step: 0.00000001, min: ranges.delay_min_s, max: ranges.delay_max_s }}
                helperText={`min ${ranges.delay_min_s ?? ''}  max ${ranges.delay_max_s ?? ''}`}
                onBlur={(e) => onChange({ delay_s: Number(e.target.value) })} disabled={channelControlsDisabled} />
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="body2" gutterBottom>Width (s)</Typography>
              <TextField fullWidth size="small" type="number" value={ch.width_s}
                inputProps={{ step: 0.00000001, min: ranges.width_min_s, max: ranges.width_max_s }}
                helperText={`min ${ranges.width_min_s ?? ''}  max ${ranges.width_max_s ?? ''}`}
                onBlur={(e) => onChange({ width_s: Number(e.target.value) })} disabled={channelControlsDisabled} />
            </Grid>
            <Grid item xs={12} md={4}>
              <Typography variant="body2" gutterBottom>Channel Mode</Typography>
              <FormControl fullWidth size="small" disabled={channelControlsDisabled}>
                <Select value={ch.channel_mode || 'Normal'} onChange={(e) => onChange({ channel_mode: e.target.value })}>
                  <MenuItem value="Normal">Normal</MenuItem>
                  <MenuItem value="Invert">Invert</MenuItem>
                  <MenuItem value="Burst">Burst</MenuItem>
                  <MenuItem value="DutyCycle">Duty Cycle</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={4}>
              <Typography variant="body2" gutterBottom>Sync Source</Typography>
              <FormControl fullWidth size="small" disabled={channelControlsDisabled}>
                <Select value={ch.sync_source || 'T0'} onChange={(e) => onChange({ sync_source: e.target.value })}>
                  <MenuItem value="T0">T0</MenuItem>
                  <MenuItem value="T1">T1</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={4}>
              <Typography variant="body2" gutterBottom>Amplitude (V)</Typography>
              <TextField size="small" type="number" value={ch.amplitude_v}
                inputProps={{ min: ranges.amplitude_min_v, max: ranges.amplitude_max_v, step: 0.1 }}
                helperText={`min ${ranges.amplitude_min_v ?? ''}  max ${ranges.amplitude_max_v ?? ''}`}
                onBlur={(e) => onChange({ amplitude_v: Number(e.target.value) })}
                disabled={channelControlsDisabled}
              />
            </Grid>
            {showChannelBurst && (
              <Grid item xs={12} md={4}>
                <Typography variant="body2" gutterBottom>Channel Burst Count</Typography>
                <TextField size="small" type="number" value={ch.burst_count} onBlur={(e) => onChange({ burst_count: Number(e.target.value) })} disabled={channelControlsDisabled} />
              </Grid>
            )}
            {showChannelDuty && (
              <>
                <Grid item xs={12} md={4}>
                  <Typography variant="body2" gutterBottom>Duty On</Typography>
                  <TextField size="small" type="number" value={ch.duty_on} onBlur={(e) => onChange({ duty_on: Number(e.target.value) })} disabled={channelControlsDisabled} />
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography variant="body2" gutterBottom>Duty Off</Typography>
                  <TextField size="small" type="number" value={ch.duty_off} onBlur={(e) => onChange({ duty_off: Number(e.target.value) })} disabled={channelControlsDisabled} />
                </Grid>
              </>
            )}
          </Grid>

          <Typography variant="body2" sx={{ mt: 2 }} gutterBottom>Multiplexer</Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            {( ['A','B','C','D'] as QCChannelKey[]).map((k) => (
              <FormControlLabel key={k} control={<Switch checked={!!ch.multiplexer?.[k]} onChange={(e) => onChange({ multiplexer: { ...(ch.multiplexer || {}), [k]: e.target.checked } })} disabled={channelControlsDisabled} />} label={k} />
            ))}
          </Box>
        </Box>
      </CardContent>
    </Card>
  )
}

export default ChannelsPanel
