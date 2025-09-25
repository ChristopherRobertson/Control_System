import { useCallback, useEffect, useMemo, useState } from 'react'
import { Box, Typography, Chip, Button, Grid, Card, CardHeader, CardContent, TextField, Switch, FormControlLabel, Snackbar, Alert, Divider, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, MenuItem } from '@mui/material'
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

  const refresh = useCallback(async (paths: string[], options: { force?: boolean } = {}) => {
    if (!paths?.length) return
    if (!connected && !options.force) return
    setLoading(true)
    try {
      const res = await HF2API.getNodes(paths)
      setValues(prev => ({ ...prev, ...res }))
    } finally {
      setLoading(false)
    }
  }, [connected])

  const set = useCallback(async (path: string, value: any) => {
    await HF2API.setNodes([{ path, value }])
    setValues(prev => ({ ...prev, [path]: value }))
  }, [])

  const setMany = useCallback(async (settings: { path: string; value: any }[]) => {
    if (!settings.length) return
    await HF2API.setNodes(settings)
    setValues(prev => {
      const next = { ...prev }
      settings.forEach(({ path: settingPath, value }) => {
        next[settingPath] = value
      })
      return next
    })
  }, [])

  return { values, refresh, set, setMany, loading }
}

// Default node paths for the main controls we expose.
// Update device id at runtime once we know it.
const OSC_COUNT = 2
const DEMOD_COUNT = 8

const SIGNAL_RANGE_MIN = 0
const SIGNAL_RANGE_MAX = 2
const OSC_FREQ_MIN = 0
const OSC_FREQ_MAX = 100_000_000
const HARMONIC_MIN = 1
const HARMONIC_MAX = 1023
const PHASE_MIN = -180
const PHASE_MAX = 180
const LP_TC_MIN = 7.832e-7
const LP_TC_MAX = 5.829e2
const LP_BW3_MIN = 1.757e-4
const LP_BW3_MAX = 1.388e5
const LP_BWNEP_MIN = 2.144e-4
const LP_BWNEP_MAX = 1.596e5
const DATA_RATE_MIN = 2.196e-1
const DATA_RATE_MAX = 1.842e6
const REF_MODE_OPTIONS = [
  { value: 'manual', label: 'Manual' },
  { value: 'external', label: 'External Reference' },
] as const
type RefMode = (typeof REF_MODE_OPTIONS)[number]['value']

const FILTER_MODE_OPTIONS = [
  { value: 'TC', label: 'TC', min: LP_TC_MIN, max: LP_TC_MAX },
  { value: 'BW_NEP', label: 'BW NEP', min: LP_BWNEP_MIN, max: LP_BWNEP_MAX },
  { value: 'BW_3_DB', label: 'BW 3 dB', min: LP_BW3_MIN, max: LP_BW3_MAX },
] as const
type FilterMode = (typeof FILTER_MODE_OPTIONS)[number]['value']

type TriggerSource = 'continuous' | 'dio0' | 'dio1' | 'dio01'
type TriggerMode = 'continuous' | 'rise' | 'fall' | 'both' | 'high' | 'low'

const TRIGGER_SOURCE_OPTIONS: Array<{ value: TriggerSource; label: string }> = [
  { value: 'continuous', label: 'Continuous' },
  { value: 'dio0', label: 'DIO 0' },
  { value: 'dio1', label: 'DIO 1' },
  { value: 'dio01', label: 'DIO 0|1' },
]

const TRIGGER_MODE_OPTIONS: Array<{ value: TriggerMode; label: string }> = [
  { value: 'continuous', label: 'Continuous' },
  { value: 'rise', label: 'Rise' },
  { value: 'fall', label: 'Fall' },
  { value: 'both', label: 'Both' },
  { value: 'high', label: 'High' },
  { value: 'low', label: 'Low' },
]

const TRIGGER_VALUE_MAP: Record<TriggerSource, Partial<Record<TriggerMode, number>>> = {
  continuous: { continuous: 0 },
  dio0: { rise: 1, fall: 2, both: 3, high: 16, low: 32 },
  dio1: { rise: 4, fall: 8, both: 12, high: 64, low: 128 },
  dio01: { rise: 5, fall: 10, both: 15, high: 80, low: 160 },
}

const TRIGGER_DEFAULT_MODE: Record<TriggerSource, TriggerMode> = {
  continuous: 'continuous',
  dio0: 'rise',
  dio1: 'rise',
  dio01: 'rise',
}

const FIXED_INPUT_ASSIGNMENTS: Record<number, number> = {
  0: 0,
  1: 0,
  2: 0,
  3: 1,
  4: 1,
  5: 1,
}

const INPUT_OPTION_LABELS: Record<number, string> = {
  0: 'Signal 1 In',
  1: 'Signal 2 In',
  2: 'Auxillary 1 In',
  3: 'Auxillary 2 In',
  4: 'DIO D0',
  5: 'DIO D1',
}

const EXT_INPUT_OPTIONS = [0, 1, 2, 3, 4, 5].map(value => ({ value, label: INPUT_OPTION_LABELS[value] }))
const FIXED_REF_DEMOD_INDICES = [6, 7]
const FIXED_OSC_ASSIGNMENTS: Partial<Record<number, number>> = {
  6: 0,
  7: 1,
}
const DEMOD_GROUPS = [
  { label: 'Demodulators 1-3', options: [0, 1, 2] as const },
  { label: 'Demodulators 4-6', options: [3, 4, 5] as const },
] as const
const INDIVIDUAL_DEMODS = [6, 7] as const


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
  oscs: Array.from({ length: OSC_COUNT }, (_, idx) => ({
    freq: `/${deviceId}/oscs/${idx}/freq`,
  })),
  // PLLs tie oscillator references to demodulators 7 and 8
  plls: Array.from({ length: OSC_COUNT }, (_, idx) => ({
    enable: `/${deviceId}/plls/${idx}/enable`,
    demodselect: `/${deviceId}/plls/${idx}/demodselect`,
  })),
  // Demodulators
  demods: Array.from({ length: DEMOD_COUNT }, (_, idx) => ({
    enable: `/${deviceId}/demods/${idx}/enable`,
    adcselect: `/${deviceId}/demods/${idx}/adcselect`,
    oscselect: `/${deviceId}/demods/${idx}/oscselect`,
    harmonic: `/${deviceId}/demods/${idx}/harmonic`,
    phase: `/${deviceId}/demods/${idx}/phaseshift`,
    order: `/${deviceId}/demods/${idx}/order`,
    timeconstant: `/${deviceId}/demods/${idx}/timeconstant`,
    rate: `/${deviceId}/demods/${idx}/rate`,
    trigger: `/${deviceId}/demods/${idx}/trigger`,
    sinc: `/${deviceId}/demods/${idx}/sinc`,
  })),
})

function ZurichHF2LIView() {
  const [status, setStatus] = useState<HF2Status | null>(null)
  const [loading, setLoading] = useState(false)
  const [snack, setSnack] = useState<{open: boolean; msg: string; severity: 'success'|'error'|'info'}>({open: false, msg: '', severity: 'info'})

  const connected = !!status?.connected && !!status?.server_connected
  const deviceId = status?.device_id || 'devXXXX'

  const nodes = useMemo(() => makeNodeMap(deviceId), [deviceId])
  const { values, refresh, set, setMany } = useHF2Nodes(connected)
  const controlsDisabled = !connected
  const [selectedDemodIndices, setSelectedDemodIndices] = useState<number[]>(() => DEMOD_GROUPS.map(group => group.options[0]))

  const loadInitial = useCallback(async (statusOverride?: HF2Status) => {
    const nextStatus = statusOverride ?? await HF2API.status()
    setStatus(nextStatus)
    const resolvedId = nextStatus?.device_id
    if (nextStatus?.connected && resolvedId) {
      const dynamicNodes = makeNodeMap(resolvedId)
      const paths: string[] = []
      paths.push(...Object.values(dynamicNodes.in1))
      paths.push(...Object.values(dynamicNodes.in2))
      dynamicNodes.oscs.forEach(o => paths.push(o.freq))
      dynamicNodes.plls?.forEach(pll => {
        paths.push(pll.enable, pll.demodselect)
      })
      dynamicNodes.demods.forEach(d => {
        paths.push(
          d.enable,
          d.adcselect,
          d.oscselect,
          d.harmonic,
          d.phase,
          d.order,
          d.timeconstant,
          d.rate,
          d.trigger,
          d.sinc,
        )
      })
      await refresh(paths, { force: true })
    }
  }, [refresh])

  useEffect(() => { void loadInitial() }, [loadInitial])

  const toggleConnect = async () => {
    setLoading(true)
    try {
      const res = !connected ? await HF2API.connect() : await HF2API.disconnect()
      const nextStatus = await HF2API.status()
      await loadInitial(nextStatus)
      setSnack({ open: true, msg: res?.message || (!connected ? 'Connected' : 'Disconnected'), severity: 'success' })
    } catch (e: any) {
      setSnack({ open: true, msg: e?.response?.data?.detail || e?.message || String(e), severity: 'error' })
    } finally {
      setLoading(false)
    }
  }

  const fmt = (v: any) => {
    if (v === undefined || v === null) return ''
    if (Array.isArray(v)) {
      return v.length ? String(v[0]) : ''
    }
    if (typeof v === 'object') {
      if ('value' in v && Array.isArray((v as any).value) && (v as any).value.length) {
        return String((v as any).value[0])
      }
      if ('vector' in v && Array.isArray((v as any).vector) && (v as any).vector.length) {
        return String((v as any).vector[0])
      }
      return ''
    }
    return String(v)
  }
  const asNumber = (v: any, fallback = 0) => {
    if (typeof v === 'number') return v
    if (typeof v === 'string') {
      const parsed = Number(v)
      return Number.isFinite(parsed) ? parsed : fallback
    }
    if (Array.isArray(v) && v.length > 0) {
      const parsed = Number(v[0])
      return Number.isFinite(parsed) ? parsed : fallback
    }
    return fallback
  }

  const asBool = (v: any) => {
    if (typeof v === 'boolean') return v
    if (typeof v === 'number') return v !== 0
    if (typeof v === 'string') {
      const parsed = Number(v)
      if (!Number.isNaN(parsed)) return parsed !== 0
    }
    return Boolean(v)
  }

  const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

  const wrapPhase = (value: number) => {
    if (!Number.isFinite(value)) return 0
    let wrapped = ((value + 180) % 360 + 360) % 360 - 180
    if (wrapped === -180 && value >= PHASE_MIN && value <= PHASE_MAX) {
      wrapped = value
    }
    return wrapped
  }

  const convertTimeConstantToModeValue = (tc: number, mode: FilterMode) => {
    if (!Number.isFinite(tc) || tc <= 0) return 0
    switch (mode) {
      case 'TC':
        return tc
      case 'BW_3_DB':
        return 1 / (2 * Math.PI * tc)
      case 'BW_NEP':
        return 1 / (4 * tc)
      default:
        return tc
    }
  }

  const convertModeValueToTimeConstant = (value: number, mode: FilterMode) => {
    if (!Number.isFinite(value) || value <= 0) return value
    switch (mode) {
      case 'TC':
        return value
      case 'BW_3_DB':
        return 1 / (2 * Math.PI * value)
      case 'BW_NEP':
        return 1 / (4 * value)
      default:
        return value
    }
  }

  const [filterModes, setFilterModes] = useState<FilterMode[]>(() => Array(DEMOD_COUNT).fill('TC'))

  const getFilterMode = (idx: number): FilterMode => filterModes[idx] ?? 'TC'

  const updateFilterMode = (idx: number, mode: FilterMode) => {
    setFilterModes(prev => {
      const next = [...prev]
      next[idx] = mode
      return next
    })
  }

  const getFilterOption = (mode: FilterMode) => FILTER_MODE_OPTIONS.find(opt => opt.value === mode) ?? FILTER_MODE_OPTIONS[0]

  const getFilterDisplayValue = (idx: number) => {
    const demod = nodes.demods[idx]
    const tc = asNumber(values[demod.timeconstant])
    const mode = getFilterMode(idx)
    return convertTimeConstantToModeValue(tc, mode)
  }

  const applyFilterValue = (idx: number, rawValue: number) => {
    if (controlsDisabled) return
    const demod = nodes.demods[idx]
    const mode = getFilterMode(idx)
    const option = getFilterOption(mode)
    const clamped = clamp(rawValue, option.min, option.max)
    let tc = convertModeValueToTimeConstant(clamped, mode)
    tc = clamp(tc, LP_TC_MIN, LP_TC_MAX)
    void set(demod.timeconstant, tc)
  }

  const handleFilterModeSelection = (idx: number, mode: FilterMode) => {
    if (controlsDisabled) return
    updateFilterMode(idx, mode)
    const demod = nodes.demods[idx]
    const tc = asNumber(values[demod.timeconstant])
    const option = getFilterOption(mode)
    const converted = convertTimeConstantToModeValue(tc, mode)
    const clamped = clamp(converted, option.min, option.max)
    if (!Number.isFinite(converted)) return
    if (Math.abs(clamped - converted) > Number.EPSILON) {
      let tcAdjusted = convertModeValueToTimeConstant(clamped, mode)
      tcAdjusted = clamp(tcAdjusted, LP_TC_MIN, LP_TC_MAX)
      void set(demod.timeconstant, tcAdjusted)
    }
  }

  const handlePhaseZero = async (idx: number) => {
    if (!connected) return
    try {
      const { phase } = await HF2API.zeroPhase(idx)
      const phaseLabel = Number.isFinite(phase) ? ` ({phase.toFixed(2)}\u00B0)` : ''
      setSnack({ open: true, msg: `Demod ${idx + 1} phase zeroed${phaseLabel}`, severity: 'success' })
      await refresh([nodes.demods[idx].phase])
    } catch (error: any) {
      const message = error?.response?.data?.detail ?? error?.message ?? String(error)
      setSnack({ open: true, msg: message, severity: 'error' })
    }
  }

  const handleDemodSelectionChange = (groupIdx: number, demodIdx: number) => {
    setSelectedDemodIndices(prev => {
      const next = [...prev]
      next[groupIdx] = demodIdx
      return next
    })
  }

  const oscOptions = nodes.oscs.map((_, idx) => ({ value: idx, label: `${idx + 1}` }))
  const orderOptions = [1, 2, 3, 4, 5, 6, 7, 8]

  const decodeTriggerValue = (value: any): { source: TriggerSource; mode: TriggerMode } => {
    const numeric = asNumber(value, 0)
    if (numeric === 0) {
      return { source: 'continuous', mode: 'continuous' }
    }
    const sources = Object.keys(TRIGGER_VALUE_MAP) as TriggerSource[]
    for (const source of sources) {
      const modeMap = TRIGGER_VALUE_MAP[source]
      for (const [modeKey, val] of Object.entries(modeMap)) {
        if (val === numeric) {
          return { source, mode: modeKey as TriggerMode }
        }
      }
    }
    return { source: 'continuous', mode: 'continuous' }
  }

  const encodeTriggerValue = (source: TriggerSource, mode: TriggerMode) => {
    const modeMap = TRIGGER_VALUE_MAP[source]
    if (modeMap?.[mode] !== undefined) {
      return modeMap[mode] as number
    }
    const fallback = TRIGGER_DEFAULT_MODE[source]
    const fallbackValue = modeMap?.[fallback]
    return fallbackValue !== undefined ? fallbackValue : 0
  }

  const handleTriggerSourceChange = (demodIdx: number, source: TriggerSource) => {
    if (controlsDisabled) return
    const demod = nodes.demods[demodIdx]
    const current = decodeTriggerValue(values[demod.trigger])
    const mode = source === 'continuous' || !TRIGGER_VALUE_MAP[source]?.[current.mode]
      ? TRIGGER_DEFAULT_MODE[source]
      : current.mode
    const encoded = encodeTriggerValue(source, mode)
    void set(demod.trigger, encoded)
  }

  const handleTriggerModeChange = (demodIdx: number, mode: TriggerMode) => {
    if (controlsDisabled) return
    const demod = nodes.demods[demodIdx]
    const current = decodeTriggerValue(values[demod.trigger])
    if (current.source === 'continuous') return
    const encoded = encodeTriggerValue(current.source, mode)
    void set(demod.trigger, encoded)
  }

  const getRefModeForDemod = (demodIdx: number): RefMode => {
    if (!FIXED_REF_DEMOD_INDICES.includes(demodIdx)) {
      return 'manual'
    }
    const oscIdx = demodIdx - 6
    const pll = nodes.plls?.[oscIdx]
    if (!pll) return 'manual'
    return asBool(values[pll.enable]) ? 'external' : 'manual'
  }

  const handleRefModeChange = async (demodIdx: number, mode: RefMode) => {
    if (controlsDisabled) return
    const oscIdx = demodIdx - 6
    const pll = nodes.plls?.[oscIdx]
    const demod = nodes.demods[demodIdx]
    if (!pll || !demod) return
    const enable = mode === 'external'
    const updates: { path: string; value: any }[] = [{ path: pll.enable, value: enable }]
    if (enable) {
      updates.push({ path: pll.demodselect, value: demodIdx })
      const expectedOsc = FIXED_OSC_ASSIGNMENTS[demodIdx]
      if (expectedOsc !== undefined && asNumber(values[demod.oscselect], expectedOsc) !== expectedOsc) {
        updates.push({ path: demod.oscselect, value: expectedOsc })
      }
    }
    await setMany(updates)
  }

  const renderDash = () => <Typography variant="body2" color="text.secondary">{'\u2014'}</Typography>

  const getFixedInputAssignment = (demodIdx: number) => {
    const assignments = FIXED_INPUT_ASSIGNMENTS as Record<string, number>
    const key = String(demodIdx)
    return assignments[key]
  }

  const renderDemodRow = (demodIdx: number, label: string, selectorProps?: { groupIdx: number; options: readonly number[] }) => {
    const demod = nodes.demods[demodIdx]
    if (!demod) return null

    const isRefDemod = FIXED_REF_DEMOD_INDICES.includes(demodIdx)
    const assignedInput = getFixedInputAssignment(demodIdx)
    const expectedOsc = FIXED_OSC_ASSIGNMENTS[demodIdx]
    const oscValue = expectedOsc !== undefined ? expectedOsc : asNumber(values[demod.oscselect])
    const refModeValue = isRefDemod ? getRefModeForDemod(demodIdx) : 'manual'
    const triggerState = decodeTriggerValue(values[demod.trigger])
    const triggerSource = triggerState.source
    const triggerMode = triggerState.mode
    const triggerModeChoices = triggerSource === 'continuous'
      ? TRIGGER_MODE_OPTIONS.filter(opt => opt.value === 'continuous')
      : TRIGGER_MODE_OPTIONS
    const showFullControls = demodIdx < 6
    const inputLabel = assignedInput !== undefined ? INPUT_OPTION_LABELS[assignedInput] : undefined

    return (
      <TableRow key={`${label}-${demodIdx}`} hover>
        <TableCell>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
            <Typography variant="body2" color="text.secondary">{label}</Typography>
            {selectorProps && (
              <TextField
                select
                size="small"
                value={demodIdx}
                disabled={controlsDisabled}
                onChange={event => {
                  const parsed = Number(event.target.value)
                  if (!Number.isFinite(parsed)) return
                  if (!selectorProps.options.includes(parsed)) return
                  handleDemodSelectionChange(selectorProps.groupIdx, parsed)
                }}
                sx={{ minWidth: 140 }}
              >
                {selectorProps.options.map(option => (
                  <MenuItem key={option} value={option}>{'Demod ' + (option + 1)}</MenuItem>
                ))}
              </TextField>
            )}
          </Box>
        </TableCell>
        <TableCell>
          {isRefDemod ? (
            <TextField
              select
              size="small"
              value={refModeValue}
              disabled={controlsDisabled}
              onChange={event => {
                const mode = event.target.value as RefMode
                void handleRefModeChange(demodIdx, mode)
              }}
              sx={{ minWidth: 170 }}
            >
              {REF_MODE_OPTIONS.map(opt => (
                <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
              ))}
            </TextField>
          ) : (
            <Chip label="Manual" size="small" />
          )}
        </TableCell>
        <TableCell>
          {expectedOsc !== undefined ? (
            <Chip label={`Osc ${expectedOsc + 1}`} size="small" color={isRefDemod && refModeValue === 'external' ? 'primary' : 'default'} />
          ) : (
            <TextField
              select
              size="small"
              value={oscValue}
              disabled={controlsDisabled}
              onChange={event => {
                if (controlsDisabled) return
                const parsed = Number(event.target.value)
                if (!Number.isFinite(parsed)) return
                const clamped = clamp(Math.round(parsed), 0, oscOptions.length - 1)
                void set(demod.oscselect, clamped)
              }}
              sx={{ minWidth: 80 }}
            >
              {oscOptions.map(opt => (
                <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
              ))}
            </TextField>
          )}
        </TableCell>
        <TableCell>
          {showFullControls ? (
            <TextField
              size="small"
              type="number"
              value={fmt(values[demod.harmonic])}
              disabled={controlsDisabled}
              onChange={event => {
                if (controlsDisabled) return
                const parsed = Number(event.target.value)
                if (!Number.isFinite(parsed)) return
                const clamped = clamp(Math.round(parsed), HARMONIC_MIN, HARMONIC_MAX)
                void set(demod.harmonic, clamped)
              }}
              sx={{ minWidth: 80 }}
            />
          ) : (
            renderDash()
          )}
        </TableCell>
        <TableCell>
          {showFullControls ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TextField
                size="small"
                type="number"
                value={fmt(values[demod.phase])}
                disabled={controlsDisabled}
                onChange={event => {
                  if (controlsDisabled) return
                  const parsed = Number(event.target.value)
                  if (!Number.isFinite(parsed)) return
                  const wrapped = wrapPhase(parsed)
                  void set(demod.phase, wrapped)
                }}
                sx={{ minWidth: 110 }}
              />
              <Button variant="outlined" size="small" onClick={() => handlePhaseZero(demodIdx)} disabled={controlsDisabled}>Zero</Button>
            </Box>
          ) : (
            renderDash()
          )}
        </TableCell>
        <TableCell>
          {inputLabel !== undefined ? (
            <Chip label={inputLabel} size="small" />
          ) : (
            <TextField
              select
              size="small"
              value={asNumber(values[demod.adcselect])}
              disabled={controlsDisabled}
              onChange={event => {
                if (controlsDisabled) return
                const parsed = Number(event.target.value)
                if (!Number.isFinite(parsed)) return
                const clamped = clamp(Math.round(parsed), EXT_INPUT_OPTIONS[0].value, EXT_INPUT_OPTIONS[EXT_INPUT_OPTIONS.length - 1].value)
                void set(demod.adcselect, clamped)
              }}
              sx={{ minWidth: 140 }}
            >
              {EXT_INPUT_OPTIONS.map(opt => (
                <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
              ))}
            </TextField>
          )}
        </TableCell>
        <TableCell>
          {showFullControls ? (
            <TextField
              select
              size="small"
              value={asNumber(values[demod.order], 1) || 1}
              disabled={controlsDisabled}
              onChange={event => {
                if (controlsDisabled) return
                const parsed = Number(event.target.value)
                if (!Number.isFinite(parsed)) return
                const clamped = clamp(Math.round(parsed), orderOptions[0], orderOptions[orderOptions.length - 1])
                void set(demod.order, clamped)
              }}
              sx={{ minWidth: 80 }}
            >
              {orderOptions.map(val => (
                <MenuItem key={val} value={val}>{val}</MenuItem>
              ))}
            </TextField>
          ) : (
            renderDash()
          )}
        </TableCell>
        <TableCell>
          {showFullControls ? (
            <TextField
              select
              size="small"
              value={getFilterMode(demodIdx)}
              disabled={controlsDisabled}
              onChange={event => handleFilterModeSelection(demodIdx, event.target.value as FilterMode)}
              sx={{ minWidth: 120 }}
            >
              {FILTER_MODE_OPTIONS.map(opt => (
                <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
              ))}
            </TextField>
          ) : (
            renderDash()
          )}
        </TableCell>
        <TableCell>
          {showFullControls ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              {(() => {
                const mode = getFilterMode(demodIdx)
                const label = mode === 'TC' ? 'TC (s)' : mode === 'BW_3_DB' ? 'BW 3 dB (Hz)' : 'BW NEP (Hz)'
                return (
                  <TextField
                    size="small"
                    type="number"
                    label={label}
                    disabled={controlsDisabled}
                    value={(() => {
                      const displayValue = getFilterDisplayValue(demodIdx)
                      return Number.isFinite(displayValue) ? displayValue : ''
                    })()}
                    onChange={event => {
                      if (controlsDisabled) return
                      const parsed = Number(event.target.value)
                      if (!Number.isFinite(parsed)) return
                      applyFilterValue(demodIdx, parsed)
                    }}
                    sx={{ minWidth: 140 }}
                  />
                )
              })()}
            </Box>
          ) : (
            renderDash()
          )}
        </TableCell>
        <TableCell align="center">
          {showFullControls ? (
            <Switch
              checked={asBool(values[demod.enable])}
              disabled={controlsDisabled}
              onChange={event => {
                if (controlsDisabled) return
                void set(demod.enable, event.target.checked)
              }}
              inputProps={{ 'aria-label': `Demod ${demodIdx + 1} enable` }}
            />
          ) : (
            renderDash()
          )}
        </TableCell>
        <TableCell>
          {showFullControls ? (
            <TextField
              size="small"
              type="number"
              value={fmt(values[demod.rate])}
              disabled={controlsDisabled}
              onChange={event => {
                if (controlsDisabled) return
                const parsed = Number(event.target.value)
                if (!Number.isFinite(parsed)) return
                const clamped = clamp(parsed, DATA_RATE_MIN, DATA_RATE_MAX)
                void set(demod.rate, clamped)
              }}
              sx={{ minWidth: 110 }}
            />
          ) : (
            renderDash()
          )}
        </TableCell>
        <TableCell>
          {showFullControls ? (
            <TextField
              select
              size="small"
              value={triggerSource}
              disabled={controlsDisabled}
              onChange={event => handleTriggerSourceChange(demodIdx, event.target.value as TriggerSource)}
              sx={{ minWidth: 140 }}
            >
              {TRIGGER_SOURCE_OPTIONS.map(opt => (
                <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
              ))}
            </TextField>
          ) : (
            renderDash()
          )}
        </TableCell>
        <TableCell>
          {showFullControls ? (
            <TextField
              select
              size="small"
              value={triggerMode}
              disabled={controlsDisabled || triggerSource === 'continuous'}
              onChange={event => handleTriggerModeChange(demodIdx, event.target.value as TriggerMode)}
              sx={{ minWidth: 140 }}
            >
              {triggerModeChoices.map(opt => (
                <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
              ))}
            </TextField>
          ) : (
            renderDash()
          )}
        </TableCell>
      </TableRow>
    )
  }

  useEffect(() => {
    if (!connected) return
    nodes.demods.forEach((demod, idx) => {
      const assigned = getFixedInputAssignment(idx)
      if (assigned === undefined) return
      const current = asNumber(values[demod.adcselect], assigned)
      if (current !== assigned) {
        void set(demod.adcselect, assigned)
      }
    })
  }, [connected, nodes.demods, set, values])

  useEffect(() => {
    if (!connected) return
    const updates: { path: string; value: number }[] = []
    FIXED_REF_DEMOD_INDICES.forEach(idx => {
      const demod = nodes.demods[idx]
      const expectedOsc = FIXED_OSC_ASSIGNMENTS[idx]
      if (!demod || expectedOsc === undefined) return
      const current = asNumber(values[demod.oscselect], expectedOsc)
      if (current !== expectedOsc) {
        updates.push({ path: demod.oscselect, value: expectedOsc })
      }
    })
    if (updates.length) {
      void setMany(updates)
    }
  }, [connected, nodes.demods, setMany, values])

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
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <SectionCard title="Signal Inputs">
              <Typography variant="subtitle2">Input 1</Typography>
              <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                <TextField size="small" label="Range (V)" type="number" value={fmt(values[nodes.in1.range])}
                disabled={controlsDisabled}
                onChange={e => {
                  if (controlsDisabled) return
                  const parsed = Number(e.target.value)
                  if (!Number.isFinite(parsed)) return
                  const clamped = clamp(parsed, SIGNAL_RANGE_MIN, SIGNAL_RANGE_MAX)
                  void set(nodes.in1.range, clamped)
                }} />
                <TextField size="small" label="Scaling" type="number" value={fmt(values[nodes.in1.scale])}
                disabled={controlsDisabled}
                onChange={e => {
                  if (controlsDisabled) return
                  void set(nodes.in1.scale, parseFloat(e.target.value))
                }} />
              </Box>
              <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                <FormControlLabel disabled={controlsDisabled} control={<Switch checked={asBool(values[nodes.in1.ac])} disabled={controlsDisabled} onChange={e => { if (controlsDisabled) return; void set(nodes.in1.ac, e.target.checked) }} />} label="AC" />
                <FormControlLabel disabled={controlsDisabled} control={<Switch checked={asBool(values[nodes.in1.imp50])} disabled={controlsDisabled} onChange={e => { if (controlsDisabled) return; void set(nodes.in1.imp50, e.target.checked) }} />} label="50 Ohm" />
                <FormControlLabel disabled={controlsDisabled} control={<Switch checked={asBool(values[nodes.in1.diff])} disabled={controlsDisabled} onChange={e => { if (controlsDisabled) return; void set(nodes.in1.diff, e.target.checked) }} />} label="Diff" />
              </Box>
              <Divider sx={{ my: 1 }} />
              <Typography variant="subtitle2">Input 2</Typography>
              <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                <TextField size="small" label="Range (V)" type="number" value={fmt(values[nodes.in2.range])}
                disabled={controlsDisabled}
                onChange={e => {
                  if (controlsDisabled) return
                  const parsed = Number(e.target.value)
                  if (!Number.isFinite(parsed)) return
                  const clamped = clamp(parsed, SIGNAL_RANGE_MIN, SIGNAL_RANGE_MAX)
                  void set(nodes.in2.range, clamped)
                }} />
                <TextField size="small" label="Scaling" type="number" value={fmt(values[nodes.in2.scale])}
                  disabled={controlsDisabled}
                  onChange={e => {
                    if (controlsDisabled) return
                    void set(nodes.in2.scale, parseFloat(e.target.value))
                  }} />
              </Box>
              <Box sx={{ display: 'flex', gap: 2 }}>
                <FormControlLabel disabled={controlsDisabled} control={<Switch checked={asBool(values[nodes.in2.ac])} disabled={controlsDisabled} onChange={e => { if (controlsDisabled) return; void set(nodes.in2.ac, e.target.checked) }} />} label="AC" />
                <FormControlLabel disabled={controlsDisabled} control={<Switch checked={asBool(values[nodes.in2.imp50])} disabled={controlsDisabled} onChange={e => { if (controlsDisabled) return; void set(nodes.in2.imp50, e.target.checked) }} />} label="50 Ohm" />
                <FormControlLabel disabled={controlsDisabled} control={<Switch checked={asBool(values[nodes.in2.diff])} disabled={controlsDisabled} onChange={e => { if (controlsDisabled) return; void set(nodes.in2.diff, e.target.checked) }} />} label="Diff" />
              </Box>
            </SectionCard>
            <SectionCard title="Oscillators">
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {nodes.oscs.map((osc, idx) => {
                  const refMode = getRefModeForDemod(idx + 6)
                  const modeLabel = refMode === 'external' ? 'External Reference' : 'Manual'
                  return (
                    <Box key={osc.freq} sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      <Typography variant="subtitle2">{`Osc ${idx + 1}`}</Typography>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                        <TextField
                          size="small"
                          label="Frequency (Hz)"
                          type="number"
                          value={fmt(values[osc.freq])}
                          disabled={controlsDisabled || refMode === 'external'}
                          onChange={e => {
                            if (controlsDisabled || refMode === 'external') return
                            const parsed = Number(e.target.value)
                            if (!Number.isFinite(parsed)) return
                            const clamped = clamp(parsed, OSC_FREQ_MIN, OSC_FREQ_MAX)
                            void set(osc.freq, clamped)
                          }}
                        />
                        <Chip label={modeLabel} color={refMode === 'external' ? 'primary' : 'default'} size="small" />
                      </Box>
                    </Box>
                  )
                })}
              </Box>
            </SectionCard>
          </Box>
        </Grid>

        <Grid item xs={12} md={8}>
          <SectionCard title="Demodulators">
            <TableContainer>
              <Table size="small" sx={{ minWidth: 900 }}>
                <TableHead>
                  <TableRow>
                    <TableCell rowSpan={2}>#</TableCell>
                    <TableCell rowSpan={2}>Ref Mode</TableCell>
                    <TableCell rowSpan={2}>Osc</TableCell>
                    <TableCell rowSpan={2}>Harm</TableCell>
                    <TableCell rowSpan={2}>Phase (deg)</TableCell>
                    <TableCell rowSpan={2}>Input Signal</TableCell>
                    <TableCell align="center" colSpan={3}>Low-Pass Filters</TableCell>
                    <TableCell align="center" colSpan={2}>Data Transfer</TableCell>
                    <TableCell align="center" colSpan={2}>Trigger</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Order</TableCell>
                    <TableCell>Mode</TableCell>
                    <TableCell>Value</TableCell>
                    <TableCell>Enable</TableCell>
                    <TableCell>Rate (Sa/s)</TableCell>
                    <TableCell>Source</TableCell>
                    <TableCell>Mode</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {DEMOD_GROUPS.map((group, groupIdx) => {
                    const options = group.options
                    const candidate = selectedDemodIndices[groupIdx]
                    const selectedIdx = candidate !== undefined && options.includes(candidate)
                      ? candidate
                      : options[0]
                    return renderDemodRow(selectedIdx, group.label, { groupIdx, options })
                  })}
                  {INDIVIDUAL_DEMODS.map(demodIdx => renderDemodRow(demodIdx, 'Demod ' + (demodIdx + 1)))}
                </TableBody>
              </Table>
            </TableContainer>
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

