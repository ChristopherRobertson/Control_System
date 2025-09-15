import { useState } from 'react'
import { Box, Button, TextField, Typography } from '@mui/material'
import QuantumComposersAPI from '../api'

interface Props {
  connected: boolean
}

function Terminal({ connected }: Props) {
  const [cmd, setCmd] = useState('')
  const [resp, setResp] = useState('')
  const [busy, setBusy] = useState(false)

  const send = async () => {
    if (!cmd.trim()) return
    setBusy(true)
    try {
      const r = await QuantumComposersAPI.sendCommand(cmd)
      setResp(String(r.response ?? ''))
    } catch (e: any) {
      setResp(`Error: ${e?.response?.data?.detail || e?.message || String(e)}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>Command Terminal</Typography>
      <Box sx={{ display: 'flex', gap: 1 }}>
        <TextField fullWidth size="small" placeholder="Enter command..." value={cmd} onChange={(e) => setCmd(e.target.value)} disabled={!connected || busy} />
        <Button variant="contained" onClick={send} disabled={!connected || busy}>Send</Button>
      </Box>
      {resp && (
        <Box sx={{ mt: 1 }}>
          <TextField fullWidth size="small" multiline minRows={2} value={resp} disabled />
        </Box>
      )}
    </Box>
  )
}

export default Terminal

