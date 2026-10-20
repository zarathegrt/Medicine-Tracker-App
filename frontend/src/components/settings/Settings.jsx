import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Settings as SettingsIcon,
  Bell,
  Clock,
  Globe,
  Download,
  Upload,
  Activity,
  CheckCircle2,
  AlertCircle,
  Save,
  RotateCw,
  Sun,
  Moon,
  BellRing,
  Info,
  ShieldCheck,
  AlertTriangle,
} from 'lucide-react';
import api from '../../services/api';
import notificationService from '../../services/notificationService';
import { useToast } from '../common/ToastContext';
import ConfirmDialog from '../common/ConfirmDialog';
import LoadingSkeleton from '../common/LoadingSkeleton';
import './Settings.css';

export default function Settings() {
  const toast = useToast();
  const fileInputRef = useRef(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [healthStatus, setHealthStatus] = useState(null);
  const [notifPermission, setNotifPermission] = useState(() => notificationService.getPermissionStatus());
  const [confirmConfig, setConfirmConfig] = useState({ isOpen: false });

  const [settings, setSettings] = useState({
    notifications_enabled: 'true',
    snooze_duration: '10',
    reminder_lead_time: '5',
    language: 'en',
    theme: localStorage.getItem('curavit_theme') || 'light',
  });

  const loadSettingsAndHealth = useCallback(async () => {
    try {
      const [settingsRes, healthRes] = await Promise.all([
        api.getSettings().catch(() => ({})),
        api.checkHealth().catch((e) => ({ status: 'error', error: e.message })),
      ]);

      if (settingsRes && Object.keys(settingsRes).length > 0) {
        setSettings((prev) => ({
          ...prev,
          ...settingsRes,
          theme: settingsRes.theme || localStorage.getItem('curavit_theme') || 'light',
        }));
      }
      setHealthStatus(healthRes);
      setNotifPermission(notificationService.getPermissionStatus());
    } catch {
      toast.error('Failed to load settings');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadSettingsAndHealth();
  }, [loadSettingsAndHealth]);

  const handleChange = (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    if (key === 'theme') {
      document.documentElement.setAttribute('data-theme', value);
      localStorage.setItem('curavit_theme', value);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.updateSettings(settings);
      toast.success('Preferences saved successfully!');
    } catch (err) {
      toast.error(err.message || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  // Notification permission handlers
  const handleRequestPermission = async () => {
    const perm = await notificationService.requestPermission();
    setNotifPermission(perm);
    if (perm === 'granted') {
      toast.success('Browser notification permissions granted!');
    } else if (perm === 'denied') {
      toast.warning('Permission was denied. Please unblock notifications in your browser address bar.');
    } else {
      toast.info('Notification permission prompt dismissed.');
    }
  };

  const handleTestNotification = () => {
    if (notifPermission !== 'granted') {
      toast.warning('Please enable browser notification permissions first');
      return;
    }
    const success = notificationService.sendTestNotification();
    if (success) {
      toast.success('Test notification dispatched!');
    } else {
      toast.error('Could not send notification. Check operating system Focus or Do Not Disturb settings.');
    }
  };

  // Export JSON Backup
  const handleExportData = async () => {
    try {
      const exportJson = await api.getExportData();
      const blob = new Blob([JSON.stringify(exportJson, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `curavit_backup_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success('Database export downloaded successfully');
    } catch (err) {
      toast.error(err.message || 'Failed to export database');
    }
  };

  // Validated Restore Workflow
  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsed = JSON.parse(event.target.result);
        if (!parsed.medicines || !Array.isArray(parsed.medicines) || !parsed.logs || !Array.isArray(parsed.logs)) {
          toast.error('Invalid backup file: missing medicines or dose logs arrays');
          return;
        }

        const medCount = parsed.medicines.length;
        const logCount = parsed.logs.length;

        // Prompt confirmation dialog
        setConfirmConfig({
          isOpen: true,
          title: 'Restore Database Backup?',
          message: `This will restore ${medCount} medication(s) and ${logCount} dose log(s). An automatic safety snapshot of your current database will be saved before restoring. Are you sure you want to proceed?`,
          confirmLabel: 'Restore Database',
          isDestructive: true,
          onConfirm: async () => {
            try {
              const res = await api.restoreData(parsed);
              toast.success(`Restored ${res.restored_medicines} medicines and ${res.restored_logs} dose logs!`);
              setConfirmConfig({ isOpen: false });
              await loadSettingsAndHealth();
              window.dispatchEvent(new CustomEvent('curavit:medicine-added'));
            } catch (err) {
              toast.error(err.message || 'Failed to restore database');
            }
          },
          onCancel: () => setConfirmConfig({ isOpen: false }),
        });
      } catch (err) {
        toast.error('Failed to parse JSON file. Please ensure it is a valid Curavit export.');
      } finally {
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      }
    };
    reader.readAsText(file);
  };

  if (loading) {
    return (
      <div className="settings-page">
        <LoadingSkeleton variant="card" count={3} />
      </div>
    );
  }

  const limitations = notificationService.getLimitationsNotice();

  return (
    <div className="settings-page">
      <div className="page-header-row">
        <div>
          <h1 className="page-main-title">Application Settings</h1>
          <p className="page-main-subtitle">
            Configure reminder durations, browser notification permissions, themes, and database recovery
          </p>
        </div>

        <button
          type="button"
          className="btn btn-secondary"
          onClick={loadSettingsAndHealth}
          title="Reload settings"
          aria-label="Reload settings"
        >
          <RotateCw size={15} />
          <span>Reload</span>
        </button>
      </div>

      <form onSubmit={handleSave} className="settings-form-layout">
        {/* Reminders & Browser Alerts Section */}
        <div className="settings-section-card">
          <div className="section-title-wrap">
            <div className="section-icon-pill">
              <Bell size={18} />
            </div>
            <div>
              <h3>Reminders & Notifications</h3>
              <p>Configure reminder lead times, snooze intervals, and browser alert permissions</p>
            </div>
          </div>

          {/* Browser Permission Status Row */}
          <div className="notif-permission-row">
            <div className="setting-label-col">
              <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>Browser Push Notifications</span>
              <span className="setting-desc">Status of OS/browser notification permission</span>
            </div>

            <div className="notif-action-btns">
              <span className={`permission-status-pill ${notifPermission}`}>
                {notifPermission === 'granted' && <CheckCircle2 size={13} />}
                {notifPermission === 'denied' && <AlertCircle size={13} />}
                {notifPermission === 'default' && <BellRing size={13} />}
                {notifPermission === 'unsupported' && <Info size={13} />}
                <span>
                  {notifPermission === 'granted'
                    ? 'Allowed'
                    : notifPermission === 'denied'
                    ? 'Blocked'
                    : notifPermission === 'unsupported'
                    ? 'Unsupported'
                    : 'Not Requested'}
                </span>
              </span>

              {notifPermission !== 'granted' && notifPermission !== 'unsupported' && (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={handleRequestPermission}
                >
                  <BellRing size={14} />
                  <span>Request Permission</span>
                </button>
              )}

              {notifPermission === 'granted' && (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={handleTestNotification}
                  title="Dispatch a test browser notification"
                >
                  <span>Test Notification</span>
                </button>
              )}
            </div>
          </div>

          <div className="settings-fields-group">
            <div className="setting-row">
              <div className="setting-label-col">
                <label htmlFor="notifications-toggle">In-App Dose Alerts</label>
                <span className="setting-desc">
                  Highlight scheduled and overdue doses within the daily dashboard
                </span>
              </div>
              <div className="setting-control-col">
                <select
                  id="notifications-toggle"
                  value={settings.notifications_enabled}
                  onChange={(e) => handleChange('notifications_enabled', e.target.value)}
                >
                  <option value="true">Enabled</option>
                  <option value="false">Disabled</option>
                </select>
              </div>
            </div>

            <div className="setting-row">
              <div className="setting-label-col">
                <label htmlFor="snooze-duration">Snooze Duration</label>
                <span className="setting-desc">
                  Default duration to defer a dose when clicking "Snooze" on the dashboard
                </span>
              </div>
              <div className="setting-control-col">
                <select
                  id="snooze-duration"
                  value={settings.snooze_duration}
                  onChange={(e) => handleChange('snooze_duration', e.target.value)}
                >
                  <option value="5">5 minutes</option>
                  <option value="10">10 minutes</option>
                  <option value="15">15 minutes</option>
                  <option value="30">30 minutes</option>
                </select>
              </div>
            </div>

            <div className="setting-row">
              <div className="setting-label-col">
                <label htmlFor="lead-time">Reminder Lead Time</label>
                <span className="setting-desc">
                  Display upcoming dose notices ahead of scheduled time
                </span>
              </div>
              <div className="setting-control-col">
                <select
                  id="lead-time"
                  value={settings.reminder_lead_time}
                  onChange={(e) => handleChange('reminder_lead_time', e.target.value)}
                >
                  <option value="5">5 minutes before</option>
                  <option value="10">10 minutes before</option>
                  <option value="15">15 minutes before</option>
                </select>
              </div>
            </div>
          </div>

          {/* Transparent Browser Limitations Notice */}
          <div className="notif-limitations-notice">
            <h5>{limitations.title}</h5>
            <ul>
              {limitations.points.map((pt, idx) => (
                <li key={idx}>{pt}</li>
              ))}
            </ul>
          </div>
        </div>

        {/* Display & Localization Section */}
        <div className="settings-section-card">
          <div className="section-title-wrap">
            <div className="section-icon-pill">
              <Sun size={18} />
            </div>
            <div>
              <h3>Display & Appearance</h3>
              <p>Personalize the visual theme and language preferences</p>
            </div>
          </div>

          <div className="settings-fields-group">
            <div className="setting-row">
              <div className="setting-label-col">
                <label htmlFor="theme-select">Color Theme</label>
                <span className="setting-desc">
                  Choose between calming sage light mode and dark contrast mode
                </span>
              </div>
              <div className="setting-control-col">
                <select
                  id="theme-select"
                  value={settings.theme}
                  onChange={(e) => handleChange('theme', e.target.value)}
                >
                  <option value="light">Warm Off-White & Sage (Light)</option>
                  <option value="dark">Charcoal & Slate (Dark)</option>
                </select>
              </div>
            </div>

            <div className="setting-row">
              <div className="setting-label-col">
                <label htmlFor="language-select">Interface Language</label>
                <span className="setting-desc">Preferred language for application labels</span>
              </div>
              <div className="setting-control-col">
                <select
                  id="language-select"
                  value={settings.language}
                  onChange={(e) => handleChange('language', e.target.value)}
                >
                  <option value="en">English (US)</option>
                  <option value="es">Español</option>
                  <option value="fr">Français</option>
                  <option value="de">Deutsch</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Save Bar */}
        <div className="settings-actions-bar">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            <Save size={16} />
            <span>{saving ? 'Saving...' : 'Save Preferences'}</span>
          </button>
        </div>
      </form>

      {/* Data Management & System Status Card */}
      <div className="settings-section-card data-management-card">
        <div className="section-title-wrap">
          <div className="section-icon-pill box-primary">
            <Download size={18} />
          </div>
          <div>
            <h3>Data Management & Safe Recovery</h3>
            <p>Export JSON backups, restore verified medication records, and check backend connectivity</p>
          </div>
        </div>

        <div className="data-management-content">
          <div className="data-export-col">
            <h4>Backup & Restore Records</h4>
            <p>
              Download a complete JSON snapshot containing all your active medicines, dose history logs, and user preferences, or restore from a previously saved backup file.
            </p>

            <div className="data-actions-row">
              <button
                type="button"
                className="btn btn-secondary export-btn"
                onClick={handleExportData}
              >
                <Download size={16} />
                <span>Export JSON Backup</span>
              </button>

              <button
                type="button"
                className="btn btn-secondary export-btn"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload size={16} />
                <span>Restore Backup</span>
              </button>

              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                style={{ display: 'none' }}
                onChange={handleFileChange}
              />
            </div>
          </div>

          <div className="server-health-col">
            <h4>Backend Status</h4>
            <div className="health-status-badge">
              {healthStatus?.status === 'healthy' ? (
                <>
                  <CheckCircle2 size={16} className="health-icon healthy" />
                  <div>
                    <span className="health-title">Server Online & Healthy</span>
                    <span className="health-time">
                      API responding at http://localhost:5000 (v{healthStatus?.version || '2.0.0'})
                    </span>
                  </div>
                </>
              ) : (
                <>
                  <AlertCircle size={16} className="health-icon unhealthy" />
                  <div>
                    <span className="health-title">Server Unavailable</span>
                    <span className="health-time">Check your Flask server console</span>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Confirmation Dialog for Restore */}
      <ConfirmDialog {...confirmConfig} />
    </div>
  );
}
