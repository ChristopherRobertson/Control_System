import { Grid, Card, CardContent, Typography, Chip, Box } from '@mui/material'
import { 
  Science as ScienceIcon,
  Memory as MemoryIcon,
  PowerSettingsNew as PowerIcon,
  Sync as SyncIcon,
  Thermostat as ThermostatIcon,
  Computer as ComputerIcon
} from '@mui/icons-material'

const devices = [
  {
    name: 'Daylight MIRcat',
    type: 'Mid-IR Probe Laser',
    status: 'Disconnected',
    icon: <ScienceIcon />,
    path: '/daylight_mircat'
  },
  {
    name: 'PicoScope 5244D',
    type: 'Oscilloscope',
    status: 'Disconnected',
    icon: <MemoryIcon />,
    path: '/picoscope_5244d'
  },
  {
    name: 'Quantum Composers 9524',
    type: 'Signal Generator',
    status: 'Disconnected',
    icon: <SyncIcon />,
    path: '/quantum_composers_9524'
  },
  {
    name: 'Zurich HF2LI',
    type: 'Lock-in Amplifier',
    status: 'Disconnected',
    icon: <PowerIcon />,
    path: '/zurich_hf2li'
  },
  {
    name: 'Arduino MUX',
    type: 'Sample Positioning',
    status: 'Disconnected',
    icon: <ComputerIcon />,
    path: '/arduino_mux'
  },
  {
    name: 'Continuum Nd:YAG',
    type: 'Pump Laser',
    status: 'TTL Controlled',
    icon: <ThermostatIcon />,
    path: '/continuum_ndyag'
  }
]

function DashboardView() {
  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        IR Pump-Probe Spectroscopy Control Dashboard
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
        Unified control interface for all system components
      </Typography>
      
      <Grid container spacing={3}>
        {devices.map((device) => (
          <Grid item xs={12} md={6} lg={4} key={device.name}>
            <Card 
              sx={{ 
                cursor: 'pointer',
                '&:hover': { 
                  backgroundColor: 'action.hover' 
                }
              }}
              onClick={() => window.location.pathname = device.path}
            >
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  {device.icon}
                  <Typography variant="h6" component="div" sx={{ ml: 1 }}>
                    {device.name}
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  {device.type}
                </Typography>
                <Chip 
                  label={device.status} 
                  color={device.status === 'Connected' ? 'success' : 
                         device.status === 'TTL Controlled' ? 'info' : 'default'} 
                  size="small" 
                />
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  )
}

export default DashboardView