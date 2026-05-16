import { Routes, Route } from 'react-router-dom'
import Layout from './components/common/Layout'
import GraphExplorer from './pages/GraphExplorer'
import QueryConsole from './pages/QueryConsole'
import DocumentIngest from './pages/DocumentIngest'
import ConflictDashboard from './pages/ConflictDashboard'
import Timeline from './pages/Timeline'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<GraphExplorer />} />
        <Route path="/query" element={<QueryConsole />} />
        <Route path="/documents" element={<DocumentIngest />} />
        <Route path="/conflicts" element={<ConflictDashboard />} />
        <Route path="/timeline" element={<Timeline />} />
      </Routes>
    </Layout>
  )
}
