import { useEffect, useRef, useState } from 'react'
import { api, type PicoScopeStatus, type ChannelName, type TriggerSource } from './api'
import {
  Box, Grid, Card, CardContent, Typography, Button, Chip, Divider, TextField,
  FormControlLabel, Switch, MenuItem, Select, FormControl, InputLabel, Alert, IconButton
} from '@mui/material'
import { PlayArrow, Stop, Refresh } from '@mui/icons-material'
import { Popover, RadioGroup, FormLabel, Radio, ButtonGroup } from '@mui/material'

const ranges = [
  '±10mV','±20mV','±50mV',
  '±100mV','±200mV','±500mV',
  '±1V','±2V','±5V','±10V','±20V'
]
const couplings = ['DC', 'AC']
const timePerDivOptions = [
  '1ns/div','2ns/div','5ns/div',
  '10ns/div','20ns/div','50ns/div',
  '100ns/div','200ns/div','500ns/div',
  '1µs/div','2µs/div','5µs/div',
  '10µs/div','20µs/div','50µs/div',
  '100µs/div','200µs/div','500µs/div',
  '1ms/div','2ms/div','5ms/div',
  '10ms/div','20ms/div','50ms/div',
  '100ms/div','200ms/div','500ms/div',
  '1s/div','2s/div','5s/div','10s/div','20s/div','50s/div',
  '100s/div','200s/div','500s/div',
  '1000s/div','2000s/div','5000s/div'
]

function parseRangeToVolts(rangeLabel?: string): number {
  if (!rangeLabel) return 2
  // Expect labels like '±2V', '±500mV'
  const m = rangeLabel.match(/^±\s*(\d+(?:\.\d+)?)(m?V)$/i)
  if (!m) return 2
  let val = parseFloat(m[1])
  const unit = m[2].toLowerCase()
  if (unit === 'mv') val /= 1000
  return val // this is the ± full-scale for one polarity
}

function parseTimePerDiv(label?: string): number {
  if (!label) return 0.001 // default 1ms/div
  // Accept ps, ns, µs, us, ms, s (case-insensitive), optional spaces before /div
  const m = label.trim().match(/^(\d+(?:\.\d+)?)\s*(ps|ns|µs|us|ms|s)\s*\/\s*div$/i)
  if (!m) return 0.001
  const val = parseFloat(m[1])
  const unit = m[2].toLowerCase()
  const mult: Record<string, number> = { s: 1, ms: 1e-3, us: 1e-6, 'µs': 1e-6, ns: 1e-9, ps: 1e-12 }
  return val * (mult[unit] ?? 1e-3)
}

function WaveformCanvas({ dataA, dataB, status, showGrid=true }: { dataA?: number[], dataB?: number[], status?: PicoScopeStatus | null, showGrid?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const dpr = window.devicePixelRatio || 1
    const cssW = canvas.clientWidth
    const cssH = canvas.clientHeight
    if (canvas.width !== Math.floor(cssW*dpr) || canvas.height !== Math.floor(cssH*dpr)) {
      canvas.width = Math.floor(cssW*dpr)
      canvas.height = Math.floor(cssH*dpr)
    }
    const ctx = canvas.getContext('2d')!
    const w = canvas.width
    const h = canvas.height
    // Background
    ctx.fillStyle = '#0c0c0c'
    ctx.fillRect(0,0,w,h)
    // Grid (10x10)
    if (showGrid) {
      ctx.strokeStyle = '#222'
      ctx.lineWidth = 1
      for (let i=0;i<=10;i++) {
        const x = (i/10)*w
        const y = (i/10)*h
        ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,h); ctx.stroke()
        ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(w,y); ctx.stroke()
      }
      // Axes highlights at center
      ctx.strokeStyle = '#333'
      ctx.beginPath(); ctx.moveTo(0,h/2); ctx.lineTo(w,h/2); ctx.stroke()
      ctx.beginPath(); ctx.moveTo(w/2,0); ctx.lineTo(w/2,h); ctx.stroke()
    }
    // Axis labels (time and voltage)
    // Use configured time/div from status for stable labeling
    const tPerDiv = parseTimePerDiv(status?.timebase?.time_per_div)
    const fmtTime = (s: number) => {
      const abs = Math.abs(s)
      if (abs >= 1) return `${s.toFixed(2)} s`
      if (abs >= 1e-3) return `${(s*1e3).toFixed(2)} ms`
      if (abs >= 1e-6) return `${(s*1e6).toFixed(2)} µs`
      if (abs >= 1e-9) return `${(s*1e9).toFixed(2)} ns`
      return `${(s*1e12).toFixed(2)} ps`
    }
    ctx.fillStyle = '#999'
    ctx.font = `${Math.max(10, Math.floor(12*dpr))}px sans-serif`
    // Time labels along bottom
    for (let i=0;i<=10;i++) {
      const x = (i/10)*w
      const t = i * tPerDiv
      const label = fmtTime(t)
      ctx.fillText(label, Math.max(2, Math.min(w-50, x+2)), h - 4)
    }
    // Voltage scale labels for A (left) and B (right)
    const rangeA = parseRangeToVolts(status?.channels?.A?.range)
    const rangeB = parseRangeToVolts(status?.channels?.B?.range)
    const vPerDivA = (rangeA*2)/10
    const vPerDivB = (rangeB*2)/10
    for (let i=0;i<=10;i++) {
      const y = (i/10)*h
      const vA = (5 - i) * vPerDivA
      const vB = (5 - i) * vPerDivB
      ctx.fillText(`${vA.toFixed(2)} V`, 4, Math.max(10, Math.min(h-2, y+4)))
      const text = `${vB.toFixed(2)} V`
      const tw = ctx.measureText(text).width
      ctx.fillText(text, Math.max(2, w - tw - 4), Math.max(10, Math.min(h-2, y+4)))
    }

    // Waveforms
    const drawTrace = (data: number[]|undefined, color: string) => {
      if (!data || data.length === 0) return
      ctx.strokeStyle = color
      ctx.lineWidth = 1.5
      ctx.beginPath()
      const n = data.length
      const cmax = (status?.adc_max_counts && status.adc_max_counts > 0) ? status.adc_max_counts : 32767
      for (let i=0;i<n;i++) {
        const x = (i/(n-1))*w
        let norm = (data[i]/cmax)
        if (norm > 1) norm = 1; else if (norm < -1) norm = -1
        const y = h/2 - norm*(h/2)
        if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y)
      }
      ctx.stroke()
    }
    drawTrace(dataA, '#00bcd4')
    drawTrace(dataB, '#ff9800')
  }, [dataA, dataB, status, showGrid])
  return <canvas ref={canvasRef} style={{ width: '100%', height: 420, background: '#0c0c0c', borderRadius: 6 }} />
}

function ChannelCard({ name, status, onUpdate }: { name: ChannelName, status: PicoScopeStatus, onUpdate: (cfg: any) => void }) {
  const cfg = status.channels[name]
  const [offsetStr, setOffsetStr] = useState<string>(String(cfg.offset ?? 0))
  useEffect(() => { setOffsetStr(String(cfg.offset ?? 0)) }, [cfg.offset])
  return (
    <Card>
      <CardContent>
        <Box sx={{ display:'flex', alignItems:'center', justifyContent:'space-between', mb:2 }}>
          <Typography variant="h6">Channel {name}</Typography>
          <FormControlLabel
            control={<Switch checked={cfg.enabled} onChange={(e)=> onUpdate({ enabled: e.target.checked })} disabled={!status.connected} />}
            label={cfg.enabled ? 'Enabled' : 'Disabled'}
          />
        </Box>
        <Grid container spacing={2}>
          <Grid item xs={6}>
            <FormControl fullWidth size="small" disabled={!status.connected}>
              <InputLabel>Range</InputLabel>
              <Select value={cfg.range} label="Range" onChange={(e)=> onUpdate({ range: e.target.value })}>
                {ranges.map(r => <MenuItem key={r} value={r}>{r}</MenuItem>)}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={6}>
            <FormControl fullWidth size="small" disabled={!status.connected}>
              <InputLabel>Coupling</InputLabel>
              <Select value={cfg.coupling} label="Coupling" onChange={(e)=> onUpdate({ coupling: e.target.value })}>
                {couplings.map(c => <MenuItem key={c} value={c}>{c}</MenuItem>)}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12}>
            <TextField label="Offset (V)" type="number" size="small" fullWidth value={offsetStr}
              onChange={(e)=> setOffsetStr(e.target.value)}
              onBlur={()=> {
                const v = parseFloat(offsetStr)
                if (!Number.isFinite(v)) { setOffsetStr(String(cfg.offset ?? 0)); return }
                onUpdate({ offset: v })
              }}
              onKeyDown={(e)=> { if (e.key === 'Enter') (e.currentTarget as HTMLInputElement).blur() }}
              disabled={!status.connected} />
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  )
}

export default function PicoScope5244DView() {
  const [status, setStatus] = useState<PicoScopeStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [previewA, setPreviewA] = useState<number[] | undefined>(undefined)
  const [previewB, setPreviewB] = useState<number[] | undefined>(undefined)
  const [anchor, setAnchor] = useState<{key: string, el: HTMLElement|null}>({key:'', el: null})
  const runLoopRef = useRef<number | null>(null)
  const previewBusyRef = useRef(false)
  // reserved for future use if we switch to dynamic labels based on capture timing

  const refresh = async () => {
    try { setStatus(await api.status()); } catch (e:any) { setError(e.message) }
  }

  const connect = async () => { setBusy(true); try { setStatus((await api.connect())); } catch(e:any){ setError(e.message) } finally { setBusy(false) } }
  const disconnect = async () => { setBusy(true); try { setStatus((await api.disconnect())); } catch(e:any){ setError(e.message) } finally { setBusy(false) } }
  const startRun = async () => {
    if (!status?.connected) return
    setBusy(true)
    try {
      setStatus((await api.run()))
      // pull frames at ~5 Hz (200 ms)
      if (runLoopRef.current) window.clearInterval(runLoopRef.current)
      runLoopRef.current = window.setInterval(async () => {
        if (previewBusyRef.current) return
        previewBusyRef.current = true
        try {
          const res = await api.acquirePreview()
          setStatus(res)
          setPreviewA(res.result.waveforms['A'])
          setPreviewB(res.result.waveforms['B'])
        } catch (e:any) {
          setError(e.message)
        } finally {
          previewBusyRef.current = false
        }
      }, 200)
    } catch(e:any){ setError(e.message) } finally { setBusy(false) }
  }
  const stopRun = async () => {
    setBusy(true)
    try {
      if (runLoopRef.current) { window.clearInterval(runLoopRef.current); runLoopRef.current = null }
      setStatus((await api.stop()))
    } catch(e:any){ setError(e.message) } finally { setBusy(false) }
  }

  useEffect(() => { refresh() }, [])

  const wsRef = useRef<WebSocket | null>(null)
  useEffect(() => {
    // Live status updates
    const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/picoscope_5244d`)
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg?.type === 'status') setStatus(msg.payload)
      } catch {}
    }
    ws.onerror = () => {}
    wsRef.current = ws
    return () => { ws.close() }
  }, [])

  const s = status
  return (
    <Box>
      <Box sx={{ display:'flex', alignItems:'center', gap:2, mb:2 }}>
        <Typography variant="h4">PicoScope 5244D</Typography>
        <Chip label={s?.connected ? 'Connected' : 'Disconnected'} color={s?.connected ? 'success' : 'default'} />
        {s && (
          <>
            <Chip label={`Samples: ${s.timebase?.n_samples ?? '-'}`} />
            <Chip label={`Rate: ${s.timebase?.sample_rate_hz ?? '-'} Hz`} />
          </>
        )}
        <Box sx={{ ml:'auto', display:'flex', gap:1 }}>
          {s?.connected ? (
            <Button variant="outlined" color="secondary" onClick={disconnect} disabled={busy}>Disconnect</Button>
          ) : (
            <Button variant="contained" onClick={connect} disabled={busy}>Connect</Button>
          )}
          <IconButton onClick={refresh} disabled={busy} title="Refresh status"><Refresh/></IconButton>
        </Box>
      </Box>

      {/* Top action bar similar to vendor UI */}
      <Box sx={{ display:'flex', gap:1, mb:2, flexWrap:'wrap' }}>
        <ButtonGroup variant='outlined' size='small'>
          <Button onClick={(e)=> setAnchor({key:'scope', el: e.currentTarget})} disabled={!s?.connected}>Scope</Button>
          <Button onClick={(e)=> setAnchor({key:'trigger', el: e.currentTarget})} disabled={!s?.connected}>Trigger</Button>
          <Button onClick={(e)=> setAnchor({key:'res', el: e.currentTarget})} disabled={!s?.connected}>Hardware resolution</Button>
          <Button onClick={async ()=> setStatus(await api.autosetup())} disabled={!s?.connected}>Auto setup</Button>
          <Button onClick={()=> { setPreviewA(undefined); setPreviewB(undefined) }} disabled={!previewA && !previewB}>Clear</Button>
        </ButtonGroup>
      </Box>

      {/* Scope popover */}
      <Popover open={anchor.key==='scope'} anchorEl={anchor.el} onClose={()=> setAnchor({key:'', el:null})} anchorOrigin={{vertical:'bottom',horizontal:'left'}}>
        <Box sx={{ p:2, minWidth:260 }}>
          <FormLabel>Time / division</FormLabel>
          <FormControl fullWidth size='small'>
            <InputLabel>Time/Div</InputLabel>
            <Select label='Time/Div' value={s?.timebase?.time_per_div || '1ms/div'} onChange={async (e)=> setStatus(await api.setTimebase({ time_per_div: e.target.value }))}>
              {timePerDivOptions.map(op => <MenuItem key={op} value={op}>{op}</MenuItem>)}
            </Select>
          </FormControl>
        </Box>
      </Popover>

      {/* Trigger popover */}
      <Popover open={anchor.key==='trigger'} anchorEl={anchor.el} onClose={()=> setAnchor({key:'', el:null})} anchorOrigin={{vertical:'bottom',horizontal:'left'}}>
        <Box sx={{ p:2, minWidth:320 }}>
          <FormLabel>Mode</FormLabel>
          <RadioGroup row value={s?.trigger?.mode || 'None'} onChange={(_e,val)=> {
            setStatus(prev => prev ? { ...prev, trigger: { ...prev.trigger, mode: val as any } } : prev)
            api.setTrigger({ mode: val as any }).then(setStatus).catch((e:any)=> setError(e.message))
          }}>
            <FormControlLabel value='None' control={<Radio/>} label='None' />
            <FormControlLabel value='Auto' control={<Radio/>} label='Auto' />
            <FormControlLabel value='Single' control={<Radio/>} label='Single' />
          </RadioGroup>
          <Box sx={{ display:'flex', gap:2, mt:1 }}>
            <FormControl fullWidth size='small'>
              <InputLabel>Source</InputLabel>
              <Select label='Source' value={s?.trigger?.source || 'A'} onChange={(e)=> {
                const v = e.target.value as TriggerSource
                setStatus(prev => prev ? { ...prev, trigger: { ...prev.trigger, source: v } } : prev)
                api.setTrigger({ source: v }).then(setStatus).catch((err:any)=> setError(err.message))
              }}>
                <MenuItem value='A'>A</MenuItem>
                <MenuItem value='B'>B</MenuItem>
                <MenuItem value='Ext'>Ext</MenuItem>
              </Select>
            </FormControl>
            <FormControl fullWidth size='small'>
              <InputLabel>Edge</InputLabel>
              <Select label='Edge' value={s?.trigger?.edge || 'Rising'} onChange={(e)=> {
                const v = e.target.value as 'Rising'|'Falling'
                setStatus(prev => prev ? { ...prev, trigger: { ...prev.trigger, edge: v } } : prev)
                api.setTrigger({ edge: v }).then(setStatus).catch((err:any)=> setError(err.message))
              }}>
                <MenuItem value='Rising'>Rising</MenuItem>
                <MenuItem value='Falling'>Falling</MenuItem>
              </Select>
            </FormControl>
          </Box>
          <TextField sx={{ mt:2 }} fullWidth size='small' type='number' label='Threshold (V)'
            value={s?.trigger?.level_v ?? 0} onChange={(e)=> {
              const v = parseFloat(e.target.value)
              setStatus(prev => prev ? { ...prev, trigger: { ...prev.trigger, level_v: v } } : prev)
              api.setTrigger({ level_v: v }).then(setStatus).catch((err:any)=> setError(err.message))
            }} />
        </Box>
      </Popover>

      {/* Resolution popover */}
      <Popover open={anchor.key==='res'} anchorEl={anchor.el} onClose={()=> setAnchor({key:'', el:null})} anchorOrigin={{vertical:'bottom',horizontal:'left'}}>
        <Box sx={{ p:2, minWidth:220 }}>
          <FormControl fullWidth size='small'>
            <InputLabel>Resolution</InputLabel>
            <Select label='Resolution' value={s?.resolution_bits ?? 8} onChange={async (e)=> setStatus(await api.setResolution(Number(e.target.value)))}>
              {[8,12,14,15].map(r => <MenuItem key={r} value={r}>{r}-bit</MenuItem>)}
            </Select>
          </FormControl>
        </Box>
      </Popover>


      {error && <Alert severity='error' sx={{ mb:2 }} onClose={()=> setError(null)}>{error}</Alert>}

      <Grid container spacing={2}>
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box sx={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
                <Typography variant="h6">Acquisition</Typography>
                <Box sx={{ display:'flex', gap:1 }}>
                  <Button startIcon={<PlayArrow/>} variant='contained' onClick={startRun} disabled={!s?.connected || busy}>Run</Button>
                  <Button startIcon={<Stop/>} variant='outlined' onClick={stopRun} disabled={!s?.connected || busy}>Stop</Button>
                </Box>
              </Box>
              <Divider sx={{ my:2 }}/>
              <WaveformCanvas dataA={previewA} dataB={previewB} status={s} />
            </CardContent>
          </Card>
        </Grid>

        {s ? (
          <>
            <Grid item xs={12} md={6}>
              <ChannelCard name='A' status={s} onUpdate={async (cfg)=> setStatus(await api.setChannel('A', cfg))} />
            </Grid>
            <Grid item xs={12} md={6}>
              <ChannelCard name='B' status={s} onUpdate={async (cfg)=> setStatus(await api.setChannel('B', cfg))} />
            </Grid>
          </>
        ) : (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant='body2' color='text.secondary'>
                  Connect to the PicoScope to configure channels.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </Box>
  )
}
