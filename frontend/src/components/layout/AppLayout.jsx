import React, { useState, useEffect } from 'react';
import { NavLink, useLocation, useNavigate, Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  Pill,
  History,
  BarChart3,
  Settings,
  Users,
  HeartHandshake,
  Sun,
  Moon,
  Plus,
  HeartPulse,
  Clock,
  LogOut,
  Shield,
  User
} from 'lucide-react';
import PillNav from '../reactbits/PillNav';
import AddMedicineModal from '../medicines/AddMedicineModal';
import AuthPage from '../auth/AuthPage';
import api from '../../services/api';
import { useAuth } from '../../services/authContext';
import './AppLayout.css';

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, isAuthenticated, loading, logout, caregiverPatients } = useAuth();

  const [theme, setTheme] = useState(() => localStorage.getItem('curavit_theme') || 'light');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());

  // Apply theme to html root
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('curavit_theme', theme);
  }, [theme]);

  // Live clock
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 30000);
    return () => clearInterval(timer);
  }, []);

  const toggleTheme = async () => {
    const nextTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(nextTheme);
    try {
      await api.updateSettings({ theme: nextTheme });
    } catch {
      // Non-blocking
    }
  };

  // Compute navigation items based on user role and authorized relationships
  const isCaregiverEligible = user?.role === 'caregiver' || user?.role === 'both' || (caregiverPatients && caregiverPatients.length > 0);
  const isPatientEligible = user?.role !== 'caregiver';

  const navItems = [
    ...(isPatientEligible ? [{ path: '/', label: 'Dashboard', icon: LayoutDashboard }] : []),
    ...(isCaregiverEligible ? [{ path: '/caregiver', label: 'Caregiver Portal', icon: HeartHandshake }] : []),
    ...(isPatientEligible ? [
      { path: '/medicines', label: 'My Medicines', icon: Pill },
      { path: '/history', label: 'Dose History', icon: History },
      { path: '/analytics', label: 'Analytics', icon: BarChart3 },
      { path: '/care-team', label: 'Care Team', icon: Users },
    ] : []),
    { path: '/settings', label: 'Settings', icon: Settings },
  ];

  // Mobile pill nav handler
  const currentPath = location.pathname;
  const activeNavItem = navItems.find((item) => 
    item.path === '/' ? currentPath === '/' : currentPath.startsWith(item.path)
  ) || navItems[0] || { path: '/', label: 'Dashboard' };

  const handleMobileNavChange = (path) => {
    navigate(path);
  };

  // Loading Splash Screen
  if (loading) {
    return (
      <div className="curavit-splash-screen">
        <div className="splash-icon-box">
          <HeartPulse size={36} className="splash-pulse" />
        </div>
        <h2 className="splash-title">Curavit</h2>
        <p className="splash-sub">Verifying secure session...</p>
      </div>
    );
  }

  // Not authenticated: render AuthPage
  if (!isAuthenticated) {
    return <AuthPage />;
  }

  return (
    <div className="app-shell">
      {/* Desktop Sidebar */}
      <aside className="app-sidebar">
        <div className="sidebar-brand">
          <div className="brand-logo-icon">
            <HeartPulse size={22} />
          </div>
          <div className="brand-titles">
            <span className="brand-name">Curavit</span>
            <span className="brand-tagline">Medicine Tracker</span>
          </div>
        </div>

        {/* User Profile Badge */}
        <div className="sidebar-user-badge">
          <div className="user-avatar-circle">
            {(user?.name || 'U').charAt(0).toUpperCase()}
          </div>
          <div className="user-details-wrap">
            <span className="user-name-display">{user?.name}</span>
            <div className="user-role-badge-row">
              <span className={`user-role-chip ${user?.role}`}>
                {user?.role === 'both' ? 'Patient & Caregiver' : user?.role}
              </span>
            </div>
          </div>
          <button
            type="button"
            className="user-logout-btn"
            onClick={logout}
            title="Sign Out"
            aria-label="Sign Out"
          >
            <LogOut size={16} />
          </button>
        </div>

        {/* Add Medicine Action (Patients only) */}
        {isPatientEligible && (
          <div className="sidebar-action-wrap">
            <button
              type="button"
              className="sidebar-add-btn"
              onClick={() => setIsAddModalOpen(true)}
            >
              <Plus size={17} />
              <span>Add Medicine</span>
            </button>
          </div>
        )}

        <nav className="sidebar-nav">
          <div className="nav-group-title">NAVIGATION</div>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
                end={item.path === '/'}
              >
                <Icon size={18} className="sidebar-link-icon" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-clock-card">
            <div className="clock-header">
              <Clock size={14} className="clock-icon" />
              <span>{currentTime.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}</span>
            </div>
            <div className="clock-time">
              {currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </div>
          </div>

          <div className="sidebar-bottom-actions">
            <button
              type="button"
              className="theme-toggle-btn"
              onClick={toggleTheme}
              aria-label="Toggle light and dark mode"
              title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} mode`}
            >
              {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
              <span>{theme === 'light' ? 'Dark Mode' : 'Light Mode'}</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="app-main-wrapper">
        {/* Mobile Header */}
        <header className="mobile-header">
          <div className="mobile-brand">
            <HeartPulse size={20} className="mobile-brand-icon" />
            <span className="mobile-brand-name">Curavit</span>
          </div>

          <div className="mobile-header-actions">
            <span className="mobile-user-name">{user?.name?.split(' ')[0]}</span>
            <button
              type="button"
              className="theme-toggle-btn-compact"
              onClick={toggleTheme}
              aria-label="Toggle theme"
            >
              {theme === 'light' ? <Moon size={17} /> : <Sun size={17} />}
            </button>
            <button
              type="button"
              className="mobile-logout-btn"
              onClick={logout}
              aria-label="Sign out"
              title="Sign Out"
            >
              <LogOut size={16} />
            </button>
            {isPatientEligible && (
              <button
                type="button"
                className="mobile-add-btn"
                onClick={() => setIsAddModalOpen(true)}
                aria-label="Add medicine"
              >
                <Plus size={18} />
              </button>
            )}
          </div>
        </header>

        {/* Mobile Horizontal Pill Navigation */}
        <div className="mobile-pill-bar">
          <PillNav
            items={navItems.map((item) => ({
              id: item.path,
              label: item.label,
              icon: item.icon,
            }))}
            activeId={activeNavItem.path}
            onChange={handleMobileNavChange}
          />
        </div>

        {/* Dynamic Route Content */}
        <main className="app-content-body">
          <Outlet context={{ openAddModal: () => setIsAddModalOpen(true) }} />
        </main>
      </div>

      {/* Global Add Medicine Modal */}
      {isPatientEligible && (
        <AddMedicineModal
          isOpen={isAddModalOpen}
          onClose={() => setIsAddModalOpen(false)}
          onSuccess={() => {
            window.dispatchEvent(new CustomEvent('curavit:medicine-added'));
          }}
        />
      )}
    </div>
  );
}
