import { Box, Typography, Chip } from '@mui/material'
import { styled } from '@mui/material/styles'

const StatusBox = styled(Box)(({ theme }) => ({
  backgroundColor: theme.palette.background.paper,
  borderTop: `1px solid ${theme.palette.divider}`,
  padding: theme.spacing(1, 2),
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
}))

function Statusbar() {
  return (
    <StatusBox>
      <Typography variant="body2" color="text.secondary">
        System Status: Running
      </Typography>
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Chip label="Backend: Connected" color="success" size="small" />
        <Chip label="Devices: 0/6 Connected" color="warning" size="small" />
      </Box>
    </StatusBox>
  )
}

export default Statusbar