import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ToastProvider } from './components/common/ToastContext';
import { AuthProvider } from './services/authContext';
import AppLayout from './components/layout/AppLayout';
import Dashboard from './components/dashboard/Dashboard';
import MyMedicines from './components/medicines/MyMedicines';
import DoseHistory from './components/history/DoseHistory';
import Analytics from './components/analytics/Analytics';
import Settings from './components/settings/Settings';
import CareTeam from './components/careteam/CareTeam';
import CaregiverDashboard from './components/caregiver/CaregiverDashboard';
import AcceptInvite from './components/caregiver/AcceptInvite';
import AuthPage from './components/auth/AuthPage';
import NotFound from './components/common/NotFound';

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Standalone Acceptance & Login Pages */}
            <Route path="/accept-invite" element={<AcceptInvite />} />
            <Route path="/login" element={<AuthPage initialMode="login" />} />
            <Route path="/register" element={<AuthPage initialMode="register" />} />

            {/* Main Application Layout */}
            <Route path="/" element={<AppLayout />}>
              <Route index element={<Dashboard />} />
              <Route path="medicines" element={<MyMedicines />} />
              <Route path="history" element={<DoseHistory />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="care-team" element={<CareTeam />} />
              <Route path="caregiver" element={<CaregiverDashboard />} />
              <Route path="settings" element={<Settings />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ToastProvider>
  );
}
