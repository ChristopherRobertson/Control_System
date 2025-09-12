import { useState } from 'react'
import { Box, Button, Typography, Alert } from '@mui/material'
import { 
  PowerSettingsNew as PowerIcon,
  Security as SecurityIcon,
  FlashOn as EmissionIcon
} from '@mui/icons-material'
import { MIRcatAPI } from '../api'

interface LaserControlsProps {
  deviceStatus: any
  onStatusUpdate: () => void
}

function LaserControls({ deviceStatus, onStatusUpdate }: LaserControlsProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleArmLaser = async () => {
    setLoading(true)
    setError(null)
    try {
      await MIRcatAPI.armLaser()
      onStatusUpdate()
    } catch (err) {
      setError('Failed to arm laser')
      console.error('Arm laser error:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleDisarmLaser = async () => {
    setLoading(true)
    setError(null)
    try {
      await MIRcatAPI.disarmLaser()
      onStatusUpdate()
    } catch (err) {
      setError('Failed to disarm laser')
      console.error('Disarm laser error:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleEmissionOn = async () => {
    setLoading(true)
    setError(null)
    try {
      await MIRcatAPI.turnEmissionOn()
      onStatusUpdate()
    } catch (err) {
      setError('Failed to turn emission on')
      console.error('Emission on error:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleEmissionOff = async () => {
    setLoading(true)
    setError(null)
    try {
      await MIRcatAPI.turnEmissionOff()
      onStatusUpdate()
    } catch (err) {
      setError('Failed to turn emission off')
      console.error('Emission off error:', err)
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

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {/* Red Laser On Button (placeholder) */}
        <Button
          variant="contained"
          color="error"
          startIcon={<PowerIcon />}
          disabled={!deviceStatus?.connected}
          sx={{ justifyContent: 'flex-start' }}
        >
          RED LASER ON
        </Button>

        {/* Arm/Disarm Laser Button */}
        <Button
          variant="contained"
          color={deviceStatus?.armed ? 'secondary' : 'success'}
          startIcon={<SecurityIcon />}
          onClick={deviceStatus?.armed ? handleDisarmLaser : handleArmLaser}
          disabled={!deviceStatus?.connected || loading}
          sx={{ justifyContent: 'flex-start' }}
        >
          {deviceStatus?.armed ? 'DISARM LASER' : 'ARM LASER'}
        </Button>

        {/* Turn Emission On/Off Button */}
        <Button
          variant="contained"
          color={deviceStatus?.emission_on ? 'warning' : 'primary'}
          startIcon={<EmissionIcon />}
          onClick={deviceStatus?.emission_on ? handleEmissionOff : handleEmissionOn}
          disabled={!deviceStatus?.armed || loading}
          sx={{ justifyContent: 'flex-start' }}
        >
          {deviceStatus?.emission_on ? 'TURN EMISSION OFF' : 'TURN EMISSION ON'}
        </Button>
      </Box>
      
      {!deviceStatus?.connected && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Connect to device to enable controls
        </Typography>
      )}
      
      {!deviceStatus?.armed && deviceStatus?.connected && (
        <Typography variant="body2" color="warning.main" sx={{ mt: 1 }}>
          Arm laser to enable emission controls
        </Typography>
      )}
    </Box>
  )
}

export default LaserControls