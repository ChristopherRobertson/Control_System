import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Switch,
  FormControlLabel,
  Chip,
  Alert,
  Tabs,
  Tab,
  Divider
} from '@mui/material'
import {
  PlayArrow as StartIcon,
  Stop as StopIcon,
  Settings as SettingsIcon,
  Timeline as SignalIcon
} from '@mui/icons-material'

function QuantumComposers9524View() {
  const [connected, setConnected] = useState(false)
  const [running, setRunning] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState(0)
  
  const [systemSettings, setSystemSettings] = useState({
    pulseMode: 'Continuous',
    period: '0.000,100,00',
    burstCount: 10,
    autoStart: false
  })

  const [selectedChannel, setSelectedChannel] = useState('A')
  const [channelSettings, setChannelSettings] = useState({
    A: { enabled: true, delay: '0.000,000,000,00', width: '0.000,001,000,00' },
    B: { enabled: false, delay: '0.000,000,000,00', width: '0.000,001,000,00' },
    C: { enabled: false, delay: '0.000,000,000,00', width: '0.000,001,000,00' },
    D: { enabled: false, delay: '0.000,000,000,00', width: '0.000,001,000,00' }
  })

  const handleConnect = async () => {
    setLoading(true)
    try {
      // TODO: Implement API call
      setConnected(true)
      setError(null)
    } catch (err) {
      setError('Failed to connect to Quantum Composers')
    } finally {
      setLoading(false)
    }
  }

  const handleStart = async () => {
    setLoading(true)
    try {
      // TODO: Implement API call
      setRunning(true)
      setError(null)
    } catch (err) {
      setError('Failed to start signal generation')
    } finally {
      setLoading(false)
    }
  }

  const handleStop = async () => {
    setLoading(true)
    try {
      // TODO: Implement API call
      setRunning(false)
      setError(null)
    } catch (err) {
      setError('Failed to stop signal generation')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          Quantum Composers Model 9524
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          SW Version: 1.0.3.13 | ComPort: 6 | Baud: 115200
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Chip 
            label={connected ? 'Connected' : 'Disconnected'} 
            color={connected ? 'success' : 'default'}
            icon={<SignalIcon />}
          />
          <Button
            variant="contained"
            onClick={connected ? () => setConnected(false) : handleConnect}
            disabled={loading}
            color={connected ? 'secondary' : 'primary'}
          >
            {connected ? 'Disconnect' : 'Connect'}
          </Button>
          <Button
            variant="contained"
            onClick={running ? handleStop : handleStart}
            disabled={!connected || loading}
            startIcon={running ? <StopIcon /> : <StartIcon />}
            color={running ? 'error' : 'success'}
            size="large"
            sx={{ ml: 'auto', minWidth: 120 }}
          >
            {running ? 'STOP' : 'RUN'}
          </Button>
        </Box>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
          <Tab label="System Options" />
          <Tab label="Additional Options" />
        </Tabs>
      </Box>

      {/* System Options Tab */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          {/* System Settings */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  System
                </Typography>
                
                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" gutterBottom>Pulse Mode</Typography>
                  <FormControl fullWidth size="small" disabled={!connected}>
                    <Select
                      value={systemSettings.pulseMode}
                      onChange={(e) => setSystemSettings(prev => ({ ...prev, pulseMode: e.target.value }))}
                    >
                      <MenuItem value="Continuous">Continuous</MenuItem>
                      <MenuItem value="Burst">Burst</MenuItem>
                      <MenuItem value="Single">Single</MenuItem>
                    </Select>
                  </FormControl>
                </Box>

                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" gutterBottom>Period</Typography>
                  <TextField
                    fullWidth
                    size="small"
                    value={systemSettings.period}
                    onChange={(e) => setSystemSettings(prev => ({ ...prev, period: e.target.value }))}
                    disabled={!connected}
                  />
                </Box>

                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" gutterBottom>Burst Count</Typography>
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    value={systemSettings.burstCount}
                    onChange={(e) => setSystemSettings(prev => ({ ...prev, burstCount: parseInt(e.target.value) }))}
                    disabled={!connected}
                  />
                </Box>

                <FormControlLabel
                  control={
                    <Switch
                      checked={systemSettings.autoStart}
                      onChange={(e) => setSystemSettings(prev => ({ ...prev, autoStart: e.target.checked }))}
                      disabled={!connected}
                    />
                  }
                  label="Auto Start"
                />
              </CardContent>
            </Card>
          </Grid>

          {/* Duty Cycle & External Trigger */}
          <Grid item xs={12} md={6}>
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Duty Cycle
                </Typography>
                <Box sx={{ display: 'flex', gap: 2 }}>
                  <Box>
                    <Typography variant="body2" gutterBottom>On Counts</Typography>
                    <TextField size="small" defaultValue="4" disabled={!connected} />
                  </Box>
                  <Box>
                    <Typography variant="body2" gutterBottom>Off Counts</Typography>
                    <TextField size="small" defaultValue="2" disabled={!connected} />
                  </Box>
                </Box>
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  External Trigger/Gate
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Typography variant="body2" gutterBottom>Trigger Mode</Typography>
                    <FormControl fullWidth size="small" disabled={!connected}>
                      <Select defaultValue="Disabled">
                        <MenuItem value="Disabled">Disabled</MenuItem>
                        <MenuItem value="Enabled">Enabled</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" gutterBottom>Gate Mode</Typography>
                    <FormControl fullWidth size="small" disabled={!connected}>
                      <Select defaultValue="Disabled">
                        <MenuItem value="Disabled">Disabled</MenuItem>
                        <MenuItem value="Enabled">Enabled</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" gutterBottom>Trigger Edge</Typography>
                    <FormControl fullWidth size="small" disabled={!connected}>
                      <Select defaultValue="Rising">
                        <MenuItem value="Rising">Rising</MenuItem>
                        <MenuItem value="Falling">Falling</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" gutterBottom>Gate Logic</Typography>
                    <FormControl fullWidth size="small" disabled={!connected}>
                      <Select defaultValue="High">
                        <MenuItem value="High">High</MenuItem>
                        <MenuItem value="Low">Low</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" gutterBottom>Threshold (V)</Typography>
                    <TextField size="small" defaultValue="2.50" disabled={!connected} />
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" gutterBottom>Threshold (V)</Typography>
                    <TextField size="small" defaultValue="2.50" disabled={!connected} />
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>

          {/* Channels */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Channels
                </Typography>
                
                {/* Channel Tabs */}
                <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                  {['A', 'B', 'C', 'D'].map((channel) => (
                    <Button
                      key={channel}
                      variant={selectedChannel === channel ? 'contained' : 'outlined'}
                      onClick={() => setSelectedChannel(channel)}
                      size="small"
                      disabled={!connected}
                    >
                      Ch {channel}
                    </Button>
                  ))}
                </Box>

                {/* Selected Channel Settings */}
                <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={channelSettings[selectedChannel].enabled}
                        onChange={(e) => setChannelSettings(prev => ({
                          ...prev,
                          [selectedChannel]: { ...prev[selectedChannel], enabled: e.target.checked }
                        }))}
                        disabled={!connected}
                      />
                    }
                    label="Enabled"
                    sx={{ mb: 2 }}
                  />

                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography variant="body2" gutterBottom>Delay</Typography>
                      <TextField
                        fullWidth
                        size="small"
                        value={channelSettings[selectedChannel].delay}
                        onChange={(e) => setChannelSettings(prev => ({
                          ...prev,
                          [selectedChannel]: { ...prev[selectedChannel], delay: e.target.value }
                        }))}
                        disabled={!connected || !channelSettings[selectedChannel].enabled}
                      />
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="body2" gutterBottom>Width</Typography>
                      <TextField
                        fullWidth
                        size="small"
                        value={channelSettings[selectedChannel].width}
                        onChange={(e) => setChannelSettings(prev => ({
                          ...prev,
                          [selectedChannel]: { ...prev[selectedChannel], width: e.target.value }
                        }))}
                        disabled={!connected || !channelSettings[selectedChannel].enabled}
                      />
                    </Grid>
                    <Grid item xs={4}>
                      <Typography variant="body2" gutterBottom>Channel Mode</Typography>
                      <FormControl fullWidth size="small" disabled={!connected || !channelSettings[selectedChannel].enabled}>
                        <Select defaultValue="Normal">
                          <MenuItem value="Normal">Normal</MenuItem>
                          <MenuItem value="Invert">Invert</MenuItem>
                        </Select>
                      </FormControl>
                    </Grid>
                    <Grid item xs={4}>
                      <Typography variant="body2" gutterBottom>Sync Source</Typography>
                      <FormControl fullWidth size="small" disabled={!connected || !channelSettings[selectedChannel].enabled}>
                        <Select defaultValue="T0">
                          <MenuItem value="T0">T0</MenuItem>
                          <MenuItem value="T1">T1</MenuItem>
                        </Select>
                      </FormControl>
                    </Grid>
                    <Grid item xs={4}>
                      <Typography variant="body2" gutterBottom>Duty Cycle On</Typography>
                      <TextField size="small" defaultValue="2" disabled={!connected || !channelSettings[selectedChannel].enabled} />
                    </Grid>
                  </Grid>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* System Information */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  System Information
                </Typography>
                <Typography variant="body2">Serial Number: 11496</Typography>
                <Typography variant="body2">Firmware Ver: 3.0.0.13</Typography>
                <Typography variant="body2">FPGA Ver: 2.0.2.8</Typography>
              </CardContent>
            </Card>
          </Grid>

          {/* Command Terminal */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Command Terminal
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <TextField
                    fullWidth
                    size="small"
                    placeholder="Enter command..."
                    disabled={!connected}
                  />
                  <Button variant="contained" disabled={!connected}>
                    Send
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Additional Options Tab */}
      {activeTab === 1 && (
        <Box>
          <Typography variant="h6">Additional Options</Typography>
          <Typography color="text.secondary">
            Additional configuration options will be available here...
          </Typography>
        </Box>
      )}
    </Box>
  )
}

export default QuantumComposers9524View