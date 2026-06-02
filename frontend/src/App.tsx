import { Routes, Route } from 'react-router-dom'
import Layout from './components/common/Layout'
import Home from './pages/Home'
import AnalyzeRepo from './pages/AnalyzeRepo'
import Overview from './pages/Overview'
import MainFlow from './pages/MainFlow'
import Showcase from './pages/Showcase'
import Takeaway from './pages/Takeaway'
import Evolution from './pages/Evolution'
import LearningPathView from './pages/LearningPathView'
import AgentTrace from './pages/AgentTrace'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/map" element={<LearningPathView />} />
        <Route path="/analyze" element={<AnalyzeRepo />} />
        {/* 4 stations: spec §9.1 */}
        <Route path="/overview" element={<Overview />} />
        <Route path="/mainflow" element={<MainFlow />} />
        <Route path="/showcase" element={<Showcase />} />
        <Route path="/takeaway" element={<Takeaway />} />
        {/* Advanced */}
        <Route path="/evolution" element={<Evolution />} />
        <Route path="/agent-trace" element={<AgentTrace />} />
      </Routes>
    </Layout>
  )
}
