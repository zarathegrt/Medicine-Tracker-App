import React, { useState, useEffect } from 'react';
import { NavLink, useLocation, useNavigate, Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  Pill,
  History,
  BarChart3,
  Settings,
  Sun,
  Moon,
  Plus,
  HeartPulse,
  Menu,
  X,
  Clock,
} from 'lucide-react';
import PillNav from '../reactbits/PillNav';
import AddMedicineModal from '../medicines/AddMedicineModal';
import api from '../../services/api';
import './AppLayout.css';

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/medicines', label: 'My Medicines', icon: Pill },
  { path: '/history', label: 'Dose History', icon: History },
  { path: '/analytics', label: 'Analytics', icon: BarChart3 },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [theme, setTheme] = useState(() => localStorage.getItem('curavit_theme') || 'light');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
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
      // Non-blocking setting update
    }
  };

  // Mobile pill nav handler
  const currentPath = location.pathname;
  const activeNavItem = NAV_ITEMS.find((item) => 
    item.path === '/' ? currentPath === '/' : currentPath.startsWith(item.path)
  ) || NAV_ITEMS[0];

  const handleMobileNavChange = (path) => {
    navigate(path);
  };

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

        <nav className="sidebar-nav">
          <div className="nav-group-title">MAIN MENU</div>
          {NAV_ITEMS.map((item) => {
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
              className="mobile-add-btn"
              onClick={() => setIsAddModalOpen(true)}
              aria-label="Add medicine"
            >
              <Plus size={18} />
            </button>
          </div>
        </header>

        {/* Mobile Horizontal Pill Navigation */}
        <div className="mobile-pill-bar">
          <PillNav
            items={NAV_ITEMS.map((item) => ({
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
      <AddMedicineModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSuccess={() => {
          // Triggers window custom event so open views can refresh
          window.dispatchEvent(new CustomEvent('curavit:medicine-added'));
        }}
      />
    </div>
  );
}
