import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import {
  HeartPulse,
  User,
  Mail,
  Lock,
  ShieldCheck,
  HeartHandshake,
  ArrowRight,
  Database,
  CheckCircle2,
  AlertCircle,
  Eye,
  EyeOff
} from 'lucide-react';
import { useAuth } from '../../services/authContext';
import { useToast } from '../common/ToastContext';
import './AuthPage.css';

export default function AuthPage({ initialMode = 'login' }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, register, setupStatus } = useAuth();
  const { showToast } = useToast();

  const [mode, setMode] = useState(initialMode); // 'login' or 'register'
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    role: 'patient',
    claimLegacy: true,
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const redirectPath = location.state?.from || '/';

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
    setErrorMsg('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setLoading(true);

    try {
      if (mode === 'login') {
        if (!formData.email || !formData.password) {
          throw new Error('Please fill in both email and password.');
        }
        await login(formData.email, formData.password);
        showToast('Welcome back to Curavit!', 'success');
        navigate(redirectPath, { replace: true });
      } else {
        if (!formData.name || !formData.email || !formData.password) {
          throw new Error('Please fill in all required fields.');
        }
        if (formData.password.length < 8) {
          throw new Error('Password must be at least 8 characters long.');
        }
        await register({
          name: formData.name,
          email: formData.email,
          password: formData.password,
          role: formData.role,
          claim_legacy: formData.claimLegacy,
        });
        showToast('Account created successfully!', 'success');
        navigate(redirectPath, { replace: true });
      }
    } catch (err) {
      setErrorMsg(err.message || 'Authentication failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const hasLegacy = setupStatus?.has_legacy_data;
  const legacyCount = setupStatus?.legacy_medicines_count || 0;

  return (
    <div className="auth-page-container">
      <div className="auth-card">
        {/* Brand Header */}
        <div className="auth-brand-header">
          <div className="auth-brand-icon">
            <HeartPulse size={30} />
          </div>
          <h1 className="auth-brand-title">Curavit</h1>
          <p className="auth-brand-subtitle">
            Secure Personal & Family Medication Management
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="auth-tabs" role="tablist">
          <button
            type="button"
            className={`auth-tab ${mode === 'login' ? 'active' : ''}`}
            onClick={() => {
              setMode('login');
              setErrorMsg('');
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            className={`auth-tab ${mode === 'register' ? 'active' : ''}`}
            onClick={() => {
              setMode('register');
              setErrorMsg('');
            }}
          >
            Create Account
          </button>
        </div>

        {errorMsg && (
          <div className="auth-alert error" role="alert">
            <AlertCircle size={18} className="alert-icon" />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          {mode === 'register' && (
            <div className="form-group">
              <label htmlFor="auth-name" className="form-label">Full Name</label>
              <div className="input-with-icon">
                <User size={18} className="input-icon" />
                <input
                  id="auth-name"
                  type="text"
                  name="name"
                  value={formData.name}
                  onChange={handleChange}
                  placeholder="e.g. Eleanor Vance"
                  className="auth-input"
                  required={mode === 'register'}
                  autoComplete="name"
                />
              </div>
            </div>
          )}

          <div className="form-group">
            <label htmlFor="auth-email" className="form-label">Email Address</label>
            <div className="input-with-icon">
              <Mail size={18} className="input-icon" />
              <input
                id="auth-email"
                type="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="you@example.com"
                className="auth-input"
                required
                autoComplete="email"
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="auth-password" className="form-label">Password</label>
            <div className="input-with-icon">
              <Lock size={18} className="input-icon" />
              <input
                id="auth-password"
                type={showPassword ? 'text' : 'password'}
                name="password"
                value={formData.password}
                onChange={handleChange}
                placeholder={mode === 'register' ? 'Min. 8 characters' : 'Enter password'}
                className="auth-input"
                required
                autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              />
              <button
                type="button"
                className="password-toggle-btn"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {mode === 'register' && (
            <>
              {/* Role Selector */}
              <div className="form-group">
                <label className="form-label">Account Purpose</label>
                <div className="role-selector-grid">
                  <label className={`role-card ${formData.role === 'patient' ? 'selected' : ''}`}>
                    <input
                      type="radio"
                      name="role"
                      value="patient"
                      checked={formData.role === 'patient'}
                      onChange={handleChange}
                      className="sr-only"
                    />
                    <div className="role-icon-wrap">
                      <ShieldCheck size={20} />
                    </div>
                    <div className="role-info">
                      <span className="role-title">Patient</span>
                      <span className="role-desc">Manage my own medications & invite caregivers</span>
                    </div>
                  </label>

                  <label className={`role-card ${formData.role === 'caregiver' ? 'selected' : ''}`}>
                    <input
                      type="radio"
                      name="role"
                      value="caregiver"
                      checked={formData.role === 'caregiver'}
                      onChange={handleChange}
                      className="sr-only"
                    />
                    <div className="role-icon-wrap">
                      <HeartHandshake size={20} />
                    </div>
                    <div className="role-info">
                      <span className="role-title">Caregiver</span>
                      <span className="role-desc">Care for a family member or patient</span>
                    </div>
                  </label>
                </div>
              </div>

              {/* Legacy Records Migration Box */}
              {hasLegacy && (
                <div className="legacy-claim-box">
                  <div className="legacy-header">
                    <Database size={18} className="legacy-icon" />
                    <span className="legacy-title">Existing Local Records Detected</span>
                  </div>
                  <p className="legacy-text">
                    We found <strong>{legacyCount} medication(s)</strong> already stored on this device.
                    Link them to this account so your existing schedule and history are preserved.
                  </p>
                  <label className="legacy-checkbox-label">
                    <input
                      type="checkbox"
                      name="claimLegacy"
                      checked={formData.claimLegacy}
                      onChange={handleChange}
                    />
                    <span>Import and link my existing medication data</span>
                  </label>
                </div>
              )}
            </>
          )}

          <button
            type="submit"
            className="auth-submit-btn"
            disabled={loading}
          >
            {loading ? (
              <span className="spinner-text">Processing...</span>
            ) : (
              <>
                <span>{mode === 'login' ? 'Sign In to Curavit' : 'Complete Registration'}</span>
                <ArrowRight size={18} />
              </>
            )}
          </button>
        </form>

        <div className="auth-footer-note">
          <ShieldCheck size={14} className="security-icon" />
          <span>Protected with PBKDF2 password encryption & zero unauthorized disclosure.</span>
        </div>
      </div>
    </div>
  );
}
