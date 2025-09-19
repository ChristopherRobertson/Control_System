import { useEffect, useState } from 'react'
import { Box, Typography, Chip, Button, Tabs, Tab, Snackbar, Alert } from '@mui/material'
import { PlayArrow as StartIcon, Stop as StopIcon, Timeline as SignalIcon } from '@mui/icons-material'
import QuantumComposersAPI, { QCStatus, QCChannelKey, QCSystemSettings } from './api'
import TriggerPanel from './components/TriggerPanel'
import ChannelsPanel from './components/ChannelsPanel'
import Terminal from './components/Terminal'

function QuantumComposers9524View() {
  const [status, setStatus] = useState<QCStatus | null>(null)
  const [activeTab, setActiveTab] = useState(0)
  const [selectedChannel, setSelectedChannel] = useState<QCChannelKey>('A')
  const [loading, setLoading] = useState(false)
  const [snack, setSnack] = useState<{open: boolean; msg: string; severity: 'success'|'error'|'info'}>({open: false, msg: '', severity: 'info'})

  const connected = !!status?.connected
  const running = !!status?.running
  const info = status?.device_info || {}

  async function refresh() {
    const s = await QuantumComposersAPI.getStatus()
    setStatus(s)
  }

  useEffect(() => { refresh() }, [])

  const toggleConnect = async () => {
    setLoading(true)
    try {
      const res = connected ? await QuantumComposersAPI.disconnect() : await QuantumComposersAPI.connect()
      await refresh()
      setSnack({open: true, msg: res.message || (connected ? 'Disconnected' : 'Connected'), severity: 'success'})
    } catch (e: any) {
      setSnack({open: true, msg: e?.response?.data?.detail || e?.message || String(e), severity: 'error'})
    } finally {
      setLoading(false)
    }
  }

  const toggleRun = async () => {
    if (!status) return
    const nextRunning = !running
    const previousStatus = status
    setLoading(true)
    setStatus(prev => {
      if (!prev) return prev
      const updated = { ...prev, running: nextRunning, channels: { ...prev.channels } }
      if (!nextRunning) {
        const newChannels = {} as typeof prev.channels
        (Object.keys(prev.channels) as QCChannelKey[]).forEach((key) => {
          newChannels[key] = { ...prev.channels[key], enabled: false }
        })
        updated.channels = newChannels
      }
      return updated
    })
    try {
      const res = nextRunning ? await QuantumComposersAPI.start() : await QuantumComposersAPI.stop()
      const { message: responseMessage, ...statusPayload } = res || {}
      if (statusPayload && Object.keys(statusPayload).length > 0) {
        setStatus(statusPayload as QCStatus)
      } else {
        await refresh()
      }
      setSnack({open: true, msg: responseMessage || (nextRunning ? 'Started' : 'Stopped'), severity: 'success'})
    } catch (e: any) {
      setStatus(prev => previousStatus ? { ...previousStatus, channels: { ...previousStatus.channels } } : prev)
      setSnack({open: true, msg: e?.response?.data?.detail || e?.message || String(e), severity: 'error'})
    } finally {
      setLoading(false)
    }
  }

  const updateSystem = async (patch: Partial<QCSystemSettings>) => {
    setLoading(true)
    try {
      const res = await QuantumComposersAPI.setSystem(patch)
      await refresh()
      setSnack({open: true, msg: res?.message || 'System updated', severity: 'success'})
    } catch (e: any) {
      setSnack({open: true, msg: e?.response?.data?.detail || e?.message || String(e), severity: 'error'})
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box>
          <Typography variant="h4" gutterBottom>Quantum Composers 9524</Typography>
          <Typography variant="body2" color="text.secondary">{`Port: ${info.port ?? 'n/a'} | Baud: ${info.baud_rate ?? 'n/a'}`}</Typography>
          {!!info.identity && (
            <Typography variant="body2" color="text.secondary">{String(info.identity)}</Typography>
          )}
        </Box>
        <Chip label={connected ? 'Connected' : 'Disconnected'} color={connected ? 'success' : 'default'} icon={<SignalIcon />} />
        <Button variant="contained" onClick={toggleConnect} disabled={loading} color={connected ? 'secondary' : 'primary'}>{connected ? 'Disconnect' : 'Connect'}</Button>
        <Button variant="contained" onClick={toggleRun} disabled={!connected || loading} startIcon={running ? <StopIcon /> : <StartIcon />} color={running ? 'error' : 'success'} sx={{ ml: 'auto' }}>{running ? 'STOP' : 'RUN'}</Button>
      </Box>

      <Tabs value={activeTab} onChange={(_e, v) => setActiveTab(v)} sx={{ mb: 2 }}>
        <Tab label="Channels" />
        <Tab label="Triggers" />
      </Tabs>

      {activeTab === 0 && status && (
        <ChannelsPanel
          status={status}
          selected={selectedChannel}
          onSelect={setSelectedChannel}
          onSystemChange={updateSystem}
          onChange={async (patch) => { setLoading(true); try { await QuantumComposersAPI.setChannel(selectedChannel, patch); await refresh(); } finally { setLoading(false) } }}
          disabled={!connected || loading}
        />
      )}
      {activeTab === 1 && status && (
        <TriggerPanel status={status} onChange={async (patch) => { setLoading(true); try { await QuantumComposersAPI.setExternal(patch); await refresh(); } finally { setLoading(false) } }} disabled={!connected || loading} />
      )}
      <Box sx={{ mt: 3 }}>
        <Terminal connected={!!status?.connected} />
      </Box>

      <Snackbar open={snack.open} autoHideDuration={2500} onClose={() => setSnack(s => ({...s, open:false}))}>
        <Alert severity={snack.severity} variant="filled">{snack.msg}</Alert>
      </Snackbar>
    </Box>
  )
}

export default QuantumComposers9524View
