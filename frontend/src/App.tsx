import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ResearchPage from './pages/ResearchPage'
import RunsPage from './pages/RunsPage'
import RunDetailPage from './pages/RunDetailPage'
import ComparePage from './pages/ComparePage'
import EvaluationPage from './pages/EvaluationPage'
import SettingsPage from './pages/SettingsPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<ResearchPage />} />
        <Route path="/research" element={<ResearchPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/runs/:runId" element={<RunDetailPage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="/evaluation" element={<EvaluationPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </Layout>
  )
}

export default App
