import { Routes, Route } from 'react-router-dom'
import MainLayout from './components/global/MainLayout'
import DashboardView from './components/DashboardView'
import DaylightMIRcatView from './modules/DaylightMIRcat/DaylightMIRcatView'

function App() {
  return (
    <MainLayout>
      <Routes>
        <Route path="/" element={<DashboardView />} />
        <Route path="/daylight_mircat" element={<DaylightMIRcatView />} />
        <Route path="/picoscope_5244d" element={<div>PicoScope Control Panel (Coming Soon)</div>} />
        <Route path="/quantum_composers_9524" element={<div>Quantum Composers Control Panel (Coming Soon)</div>} />
        <Route path="/zurich_hf2li" element={<div>Zurich HF2LI Control Panel (Coming Soon)</div>} />
        <Route path="/arduino_mux" element={<div>Arduino MUX Control Panel (Coming Soon)</div>} />
        <Route path="/continuum_ndyag" element={<div>Continuum Nd:YAG Control Panel (Coming Soon)</div>} />
      </Routes>
    </MainLayout>
  )
}

export default App