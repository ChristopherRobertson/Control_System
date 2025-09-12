import { AppBar, Toolbar, Typography, Button, Box } from '@mui/material'
import { NavLink } from 'react-router-dom'
import { styled } from '@mui/material/styles'

const NavButton = styled(Button)(({ theme }) => ({
  color: 'white',
  textTransform: 'none',
  '&.active': {
    backgroundColor: theme.palette.primary.main,
    color: theme.palette.primary.contrastText,
  },
}))

function Navbar() {
  const deviceLinks = [
    { path: '/', label: 'Dashboard' },
    { path: '/daylight_mircat', label: 'MIRcat' },
    { path: '/picoscope_5244d', label: 'PicoScope' },
    { path: '/quantum_composers_9524', label: 'QC 9524' },
    { path: '/zurich_hf2li', label: 'HF2LI' },
    { path: '/arduino_mux', label: 'Arduino MUX' },
    { path: '/continuum_ndyag', label: 'Nd:YAG' },
  ]

  return (
    <AppBar position="static">
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ mr: 4 }}>
          IR Spectroscopy Control
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          {deviceLinks.map((link) => (
            <NavLink
              key={link.path}
              to={link.path}
              className={({ isActive }) => (isActive ? 'active' : '')}
              style={{ textDecoration: 'none' }} // prevent underline
            >
              <NavButton>{link.label}</NavButton>
            </NavLink>
          ))}
        </Box>
      </Toolbar>
    </AppBar>
  )
}

export default Navbar
