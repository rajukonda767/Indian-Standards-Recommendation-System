import { Routes, Route, Navigate } from 'react-router-dom'
import { LandingPage } from '@/pages/LandingPage'
import { RecommendPage } from '@/pages/RecommendPage'
import { StandardsPage } from '@/pages/StandardsPage'
import { TenderAuditPage } from '@/pages/TenderAuditPage'
import { PreviousPage } from '@/pages/PreviousPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/recommend" element={<RecommendPage />} />
      <Route path="/standards" element={<StandardsPage />} />
      <Route path="/tender-audit" element={<TenderAuditPage />} />
      <Route path="/previous" element={<PreviousPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
