import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './Layout';
import SettingsAI from './pages/SettingsAI';
import JobHunt from './pages/JobHunt';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/agents/jobshunt" replace />} />
          <Route path="agents/jobshunt" element={<JobHunt />} />
          <Route path="settings/ai" element={<SettingsAI />} />
        </Route>
        <Route path="*" element={<Navigate to="/agents/jobshunt" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
