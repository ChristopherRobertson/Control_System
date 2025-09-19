import { useEffect, useMemo, useState } from 'react'
import { Box, Typography, Chip, Button, Grid, Card, CardHeader, CardContent, TextField, Switch, FormControlLabel, Snackbar, Alert, Divider } from '@mui/material'
import HF2API, { HF2Status } from './api'

function SectionCard({ title, children }: { title: string; children: any }) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardHeader title={title} />
      <CardContent>{children}</CardContent>
    </Card>
  )
}

function useHF2Nodes(connected: boolean) {
  const [values, setValues] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(false)

  const refresh = async (paths: string[]) => {
    if (!connected) return
    setLoading(true)
    try {
      const res = await HF2API.getNodes(paths)
      setValues(prev => ({ ...prev, ...res }))
    } finally {
      setLoading(false)
    }
  }

  const set = async (path: string, value: any) => {
    await HF2API.setNodes([{ path, value }])
    setValues(prev => ({ ...prev, [path]: value }))
  }

  return { values, refresh, set, loading }
}

// Default node paths for the main controls we expose in Phase 1.
// Update device id at runtime once we know it.
const makeNodeMap = (deviceId: string) => ({
  // Signal inputs
  in1: {
    ac: `/${deviceId}/sigins/0/ac`,
    imp50: `/${deviceId}/sigins/0/imp50`,
    diff: `/${deviceId}/sigins/0/diff`,
    range: `/${deviceId}/sigins/0/range`,
    scale: `/${deviceId}/sigins/0/scale`,
  },
  in2: {
    ac: `/${deviceId}/sigins/1/ac`,
    imp50: `/${deviceId}/sigins/1/imp50`,
    diff: `/${deviceId}/sigins/1/diff`,
    range: `/${deviceId}/sigins/1/range`,
    scale: `/${deviceId}/sigins/1/scale`,
  },
  // Oscillators
  oscs: [
    { freq: `/${deviceId}/oscs/0/freq` },
    { freq: `/${deviceId}/oscs/1/freq` },
  ],
  // Demodulators (first two to keep UI compact)
  demods: [
    {
      enable: `/${deviceId}/demods/0/enable`,
      adcselect: `/${deviceId}/demods/0/adcselect`,
      oscselect: `/${deviceId}/demods/0/oscselect`,
      order: `/${deviceId}/demods/0/order`,
      tc: `/${deviceId}/demods/0/timeconstant`,
      rate: `/${deviceId}/demods/0/rate`,
      sinc: `/${deviceId}/demods/0/sinc`,
    },
    {
      enable: `/${deviceId}/demods/1/enable`,
      adcselect: `/${deviceId}/demods/1/adcselect`,
      oscselect: `/${deviceId}/demods/1/oscselect`,
      order: `/${deviceId}/demods/1/order`,
      tc: `/${deviceId}/demods/1/timeconstant`,
      rate: `/${deviceId}/demods/1/rate`,
      sinc: `/${deviceId}/demods/1/sinc`,
    }
  ],
  // Outputs
  out1: {
    on: `/${deviceId}/sigouts/0/on`,
    range: `/${deviceId}/sigouts/0/range`,
    offset: `/${deviceId}/sigouts/0/offset`,
    add: `/${deviceId}/sigouts/0/add`,
    amp: `/${deviceId}/sigouts/0/amplitudes/0`,
  },
  out2: {
    on: `/${deviceId}/sigouts/1/on`,
    range: `/${deviceId}/sigouts/1/range`,
    offset: `/${deviceId}/sigouts/1/offset`,
    add: `/${deviceId}/sigouts/1/add`,
    amp: `/${deviceId}/sigouts/1/amplitudes/0`,
  },
})

function ZurichHF2LIView() {
  const [status, setStatus] = useState<HF2Status | null>(null)
  const [loading, setLoading] = useState(false)
  const [snack, setSnack] = useState<{open: boolean; msg: string; severity: 'success'|'error'|'info'}>({open: false, msg: '', severity: 'info'})

  const connected = !!status?.connected && !!status?.server_connected
  const deviceId = status?.device_id || 'devXXXX'

  const nodes = useMemo(() => makeNodeMap(deviceId), [deviceId])
  const { values, refresh, set } = useHF2Nodes(connected)

  async function loadInitial() {
    const s = await HF2API.status()
    setStatus(s)
    if (s?.connected && s?.device_id) {
      const paths: string[] = []
      paths.push(...Object.values(nodes.in1))
      paths.push(...Object.values(nodes.in2))
      nodes.oscs.forEach(o => paths.push(o.freq))
      nodes.demods.forEach(d => { paths.push(d.enable, d.adcselect, d.oscselect, d.order, d.tc, d.rate, d.sinc) })
      paths.push(...Object.values(nodes.out1))
      paths.push(...Object.values(nodes.out2))
      await refresh(paths)
    }
  }

  useEffect(() => { loadInitial() }, [])

  const toggleConnect = async () => {
    setLoading(true)
    try {
      const res = !connected ? await HF2API.connect() : await HF2API.disconnect()
      setStatus(await HF2API.status())
      setSnack({ open: true, msg: res?.message || (!connected ? 'Connected' : 'Disconnected'), severity: 'success' })
      if (!connected && res?.device_id) {
        // Freshly connected; fetch values.
        await loadInitial()
      }
    } catch (e: any) {
      setSnack({ open: true, msg: e?.response?.data?.detail || e?.message || String(e), severity: 'error' })
    } finally {
      setLoading(false)
    }
  }

  const fmt = (v: any) => v === undefined || v === null ? '' : String(v)

  return (
    <Box>
      <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box>
          <Typography variant="h4">Zurich Instruments HF2LI</Typography>
          <Typography variant="body2" color="text.secondary">{`Host: ${status?.host ?? 'n/a'} | Data Server: ${status?.data_server_port ?? 'n/a'} | API: ${status?.api_level ?? '6'}`}</Typography>
          {!!status?.server_version && (
            <Typography variant="body2" color="text.secondary">{`LabOne Server: ${status.server_version}`}</Typography>
          )}
        </Box>
        <Chip label={connected ? 'Connected' : 'Disconnected'} color={connected ? 'success' : 'default'} />
        <Button variant="contained" onClick={toggleConnect} disabled={loading} color={connected ? 'secondary' : 'primary'}>
          {connected ? 'Disconnect' : 'Connect'}
        </Button>
      </Box>

      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <SectionCard title="Signal Inputs">
            <Typography variant="subtitle2">Input 1</Typography>
            <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
              <TextField size="small" label="Range (V)" type="number" value={fmt(values[nodes.in1.range])}
                onChange={e => set(nodes.in1.range, parseFloat(e.target.value))} />
              <TextField size="small" label="Scaling" type="number" value={fmt(values[nodes.in1.scale])}
                onChange={e => set(nodes.in1.scale, parseFloat(e.target.value))} />
            </Box>
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <FormControlLabel control={<Switch checked={!!values[nodes.in1.ac]} onChange={e => set(nodes.in1.ac, e.target.checked)} />} label="AC" />
              <FormControlLabel control={<Switch checked={!!values[nodes.in1.imp50]} onChange={e => set(nodes.in1.imp50, e.target.checked)} />} label="50 Ω" />
              <FormControlLabel control={<Switch checked={!!values[nodes.in1.diff]} onChange={e => set(nodes.in1.diff, e.target.checked)} />} label="Diff" />
            </Box>
            <Divider sx={{ my: 1 }} />
            <Typography variant="subtitle2">Input 2</Typography>
            <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
              <TextField size="small" label="Range (V)" type="number" value={fmt(values[nodes.in2.range])}
                onChange={e => set(nodes.in2.range, parseFloat(e.target.value))} />
              <TextField size="small" label="Scaling" type="number" value={fmt(values[nodes.in2.scale])}
                onChange={e => set(nodes.in2.scale, parseFloat(e.target.value))} />
            </Box>
            <Box sx={{ display: 'flex', gap: 2 }}>
              <FormControlLabel control={<Switch checked={!!values[nodes.in2.ac]} onChange={e => set(nodes.in2.ac, e.target.checked)} />} label="AC" />
              <FormControlLabel control={<Switch checked={!!values[nodes.in2.imp50]} onChange={e => set(nodes.in2.imp50, e.target.checked)} />} label="50 Ω" />
              <FormControlLabel control={<Switch checked={!!values[nodes.in2.diff]} onChange={e => set(nodes.in2.diff, e.target.checked)} />} label="Diff" />
            </Box>
          </SectionCard>
        </Grid>

        <Grid item xs={12} md={8}>
          <SectionCard title="Oscillators & Demodulators">
            <Typography variant="subtitle2" sx={{ mb: 1 }}>Oscillators</Typography>
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <TextField size="small" label="Osc 1 Freq (Hz)" type="number" value={fmt(values[nodes.oscs[0].freq])}
                onChange={e => set(nodes.oscs[0].freq, parseFloat(e.target.value))} />
              <TextField size="small" label="Osc 2 Freq (Hz)" type="number" value={fmt(values[nodes.oscs[1].freq])}
                onChange={e => set(nodes.oscs[1].freq, parseFloat(e.target.value))} />
            </Box>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>Demod 1</Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1 }}>
              <FormControlLabel control={<Switch checked={!!values[nodes.demods[0].enable]} onChange={e => set(nodes.demods[0].enable, e.target.checked)} />} label="Enable" />
              <TextField size="small" label="Input (0=In1,1=In2)" type="number" value={fmt(values[nodes.demods[0].adcselect])}
                onChange={e => set(nodes.demods[0].adcselect, parseInt(e.target.value))} />
              <TextField size="small" label="Osc (0/1)" type="number" value={fmt(values[nodes.demods[0].oscselect])}
                onChange={e => set(nodes.demods[0].oscselect, parseInt(e.target.value))} />
              <TextField size="small" label="Order" type="number" value={fmt(values[nodes.demods[0].order])}
                onChange={e => set(nodes.demods[0].order, parseInt(e.target.value))} />
              <TextField size="small" label="Time Const (s)" type="number" value={fmt(values[nodes.demods[0].tc])}
                onChange={e => set(nodes.demods[0].tc, parseFloat(e.target.value))} />
              <TextField size="small" label="Rate (Sa/s)" type="number" value={fmt(values[nodes.demods[0].rate])}
                onChange={e => set(nodes.demods[0].rate, parseFloat(e.target.value))} />
              <FormControlLabel control={<Switch checked={!!values[nodes.demods[0].sinc]} onChange={e => set(nodes.demods[0].sinc, e.target.checked)} />} label="Sinc" />
            </Box>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>Demod 2</Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              <FormControlLabel control={<Switch checked={!!values[nodes.demods[1].enable]} onChange={e => set(nodes.demods[1].enable, e.target.checked)} />} label="Enable" />
              <TextField size="small" label="Input (0=In1,1=In2)" type="number" value={fmt(values[nodes.demods[1].adcselect])}
                onChange={e => set(nodes.demods[1].adcselect, parseInt(e.target.value))} />
              <TextField size="small" label="Osc (0/1)" type="number" value={fmt(values[nodes.demods[1].oscselect])}
                onChange={e => set(nodes.demods[1].oscselect, parseInt(e.target.value))} />
              <TextField size="small" label="Order" type="number" value={fmt(values[nodes.demods[1].order])}
                onChange={e => set(nodes.demods[1].order, parseInt(e.target.value))} />
              <TextField size="small" label="Time Const (s)" type="number" value={fmt(values[nodes.demods[1].tc])}
                onChange={e => set(nodes.demods[1].tc, parseFloat(e.target.value))} />
              <TextField size="small" label="Rate (Sa/s)" type="number" value={fmt(values[nodes.demods[1].rate])}
                onChange={e => set(nodes.demods[1].rate, parseFloat(e.target.value))} />
              <FormControlLabel control={<Switch checked={!!values[nodes.demods[1].sinc]} onChange={e => set(nodes.demods[1].sinc, e.target.checked)} />} label="Sinc" />
            </Box>
          </SectionCard>
        </Grid>

        <Grid item xs={12} md={6}>
          <SectionCard title="Signal Output 1">
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
              <FormControlLabel control={<Switch checked={!!values[nodes.out1.on]} onChange={e => set(nodes.out1.on, e.target.checked)} />} label="On" />
              <FormControlLabel control={<Switch checked={!!values[nodes.out1.add]} onChange={e => set(nodes.out1.add, e.target.checked)} />} label="Add" />
              <TextField size="small" label="Range (V)" type="number" value={fmt(values[nodes.out1.range])}
                onChange={e => set(nodes.out1.range, parseFloat(e.target.value))} />
              <TextField size="small" label="Offset (V)" type="number" value={fmt(values[nodes.out1.offset])}
                onChange={e => set(nodes.out1.offset, parseFloat(e.target.value))} />
              <TextField size="small" label="Amp (Vpk)" type="number" value={fmt(values[nodes.out1.amp])}
                onChange={e => set(nodes.out1.amp, parseFloat(e.target.value))} />
            </Box>
          </SectionCard>
        </Grid>
        <Grid item xs={12} md={6}>
          <SectionCard title="Signal Output 2">
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
              <FormControlLabel control={<Switch checked={!!values[nodes.out2.on]} onChange={e => set(nodes.out2.on, e.target.checked)} />} label="On" />
              <FormControlLabel control={<Switch checked={!!values[nodes.out2.add]} onChange={e => set(nodes.out2.add, e.target.checked)} />} label="Add" />
              <TextField size="small" label="Range (V)" type="number" value={fmt(values[nodes.out2.range])}
                onChange={e => set(nodes.out2.range, parseFloat(e.target.value))} />
              <TextField size="small" label="Offset (V)" type="number" value={fmt(values[nodes.out2.offset])}
                onChange={e => set(nodes.out2.offset, parseFloat(e.target.value))} />
              <TextField size="small" label="Amp (Vpk)" type="number" value={fmt(values[nodes.out2.amp])}
                onChange={e => set(nodes.out2.amp, parseFloat(e.target.value))} />
            </Box>
          </SectionCard>
        </Grid>
      </Grid>

      <Snackbar open={snack.open} autoHideDuration={2500} onClose={() => setSnack(s => ({...s, open:false}))}>
        <Alert severity={snack.severity} variant="filled">{snack.msg}</Alert>
      </Snackbar>
    </Box>
  )
}

export default ZurichHF2LIView

