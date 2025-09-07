import React from 'react'
import { Box, Typography, Chip } from '@mui/material'
import { CheckCircle, Error, RadioButtonUnchecked } from '@mui/icons-material'

interface StatusIndicatorProps {
  label: string
  status: boolean
  invert?: boolean // For cases where false means good (like "System Fault")
}

function StatusIndicator({ label, status, invert = false }: StatusIndicatorProps) {
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