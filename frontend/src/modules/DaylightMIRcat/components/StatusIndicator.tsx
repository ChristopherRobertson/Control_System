// import { useState, useEffect } from 'react'
import { Box, Typography } from '@mui/material'
import { CheckCircle, Error, RadioButtonUnchecked } from '@mui/icons-material'

interface StatusIndicatorProps {
  label: string
  status: boolean
  connected?: boolean
  invert?: boolean // For cases where false means good (like "System Fault")
}

function StatusIndicator({ label, status, connected = true, invert = false }: StatusIndicatorProps) {
  // Show grey when disconnected, except for System Fault which only shows red when there's an actual fault
  if (!connected) {
    if (label === 'System Fault') {
      // System Fault should be grey when disconnected (no fault state)
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="body2" color="text.secondary">
            {label}:
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <RadioButtonUnchecked sx={{ color: 'grey.500', fontSize: 16 }} />
            <Typography variant="body2" color="grey.500">
              --
            </Typography>
          </Box>
        </Box>
      )
    } else {
      // All other indicators show grey when disconnected
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="body2" color="text.secondary">
            {label}:
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <RadioButtonUnchecked sx={{ color: 'grey.500', fontSize: 16 }} />
            <Typography variant="body2" color="grey.500">
              --
            </Typography>
          </Box>
        </Box>
      )
    }
  }

  const isGood = invert ? !status : status
  
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
      <Typography variant="body2" color="text.secondary">
        {label}:
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        {isGood ? (
          <CheckCircle sx={{ color: 'success.main', fontSize: 16 }} />
        ) : (
          <Error sx={{ color: 'error.main', fontSize: 16 }} />
        )}
        <Typography variant="body2" color={isGood ? 'success.main' : 'error.main'}>
          {isGood ? 'OK' : 'ERROR'}
        </Typography>
      </Box>
    </Box>
  )
}

export default StatusIndicator