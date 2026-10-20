import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import {
  HeartHandshake,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Clock,
  ArrowRight,
  UserCheck,
  Lock
} from 'lucide-react';
import api from '../../services/api';
import { useAuth } from '../../services/authContext';
import { useToast } from '../common/ToastContext';
import './AcceptInvite.css';

export default function AcceptInvite() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');
  const { user, isAuthenticated, login, register, fetchCaregiverPatients } = useAuth();
  const { showToast } = useToast();

  const [loading, setLoading] = useState(true);
  const [invitation, setInvitation] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [accepting, setAccepting] = useState(false);

  // Quick inline auth state if user is not logged in
  const [authMode, setAuthMode] = useState('login'); // 'login' or 'register'
  const [authEmail, setAuthEmail] = useState('');
  const [authName, setAuthName] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [submittingAuth, setSubmittingAuth] = useState(false);

  useEffect(() => {
    if (!token) {
      setErrorMsg('No invitation token provided in the URL.');
      setLoading(false);
      return;
    }

    api.verifyInvitation(token)
      .then((data) => {
        setInvitation(data.invitation);
        if (data.invitation?.invited_email) {
          setAuthEmail(data.invitation.invited_email);
        }
      })
      .catch((err) => {
        setErrorMsg(err.message || 'Invalid or expired invitation token.');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [token]);

  const handleAccept = async () => {
    if (!token) return;
    setAccepting(true);
    try {
      await api.acceptInvitation(token);
      await fetchCaregiverPatients();
      showToast('Invitation accepted! You have joined the patient care team.', 'success');
      navigate('/caregiver', { replace: true });
    } catch (err) {
      setErrorMsg(err.message || 'Failed to accept invitation.');
    } finally {
      setAccepting(false);
    }
  };

  const handleInlineAuth = async (e) => {
    e.preventDefault();
    setAuthError('');
    setSubmittingAuth(true);

    try {
      if (authMode === 'login') {
        await login(authEmail, authPassword);
      } else {
        await register({
          name: authName,
          email: authEmail,
          password: authPassword,
          role: 'caregiver',
        });
      }
      showToast('Authenticated! Now accepting your invitation...', 'success');
      // After login/register, automatically accept
      await api.acceptInvitation(token);
      await fetchCaregiverPatients();
      showToast('Invitation accepted! Welcome to the Caregiver Portal.', 'success');
      navigate('/caregiver', { replace: true });
    } catch (err) {
      setAuthError(err.message || 'Authentication failed. Please check your credentials.');
    } finally {
      setSubmittingAuth(false);
    }
  };

  if (loading) {
    return (
      <div className="accept-invite-page">
        <div className="accept-invite-card">
          <div className="invite-spinner" />
          <p>Verifying invitation details...</p>
        </div>
      </div>
    );
  }

  if (errorMsg || !invitation) {
    return (
      <div className="accept-invite-page">
        <div className="accept-invite-card error">
          <div className="error-icon-box">
            <AlertCircle size={36} />
          </div>
          <h2>Invitation Unusable</h2>
          <p>{errorMsg || 'This invitation could not be verified.'}</p>
          <Link to="/" className="btn-return">Return to Curavit Home</Link>
        </div>
      </div>
    );
  }

  if (invitation.status !== 'pending') {
    return (
      <div className="accept-invite-page">
        <div className="accept-invite-card">
          <div className="status-icon-box">
            <Clock size={36} />
          </div>
          <h2>Invitation No Longer Pending</h2>
          <p>This invitation has already been <strong>{invitation.status}</strong>.</p>
          <Link to="/" className="btn-return">Return to Curavit Home</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="accept-invite-page">
      <div className="accept-invite-card">
        {/* Header */}
        <div className="accept-header">
          <div className="invite-badge-icon">
            <HeartHandshake size={32} />
          </div>
          <span className="invite-kicker">Care Team Invitation</span>
          <h1 className="invite-patient-title">
            {invitation.patient_name}
          </h1>
          <p className="invite-desc">
            has invited you to join their Curavit Care Team as an authorized caregiver.
          </p>
        </div>

        {/* Permissions Overview */}
        <div className="invited-permissions-box">
          <h3 className="perms-heading">
            <ShieldCheck size={16} />
            <span>Permissions You Will Receive:</span>
          </h3>
          <ul className="perms-summary-list">
            {(invitation.permissions || []).map((perm) => (
              <li key={perm} className="perm-summary-item">
                <CheckCircle2 size={16} className="perm-check-icon" />
                <span>{perm.replace('view_', 'View ').replace('_', ' ')}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Acceptance Action or Inline Auth */}
        {isAuthenticated ? (
          <div className="auth-acceptance-box">
            <div className="logged-in-user-banner">
              <UserCheck size={18} />
              <span>
                Logged in as <strong>{user?.name}</strong> ({user?.email})
              </span>
            </div>

            <button
              type="button"
              className="accept-submit-btn"
              onClick={handleAccept}
              disabled={accepting}
            >
              {accepting ? (
                <span>Accepting Access...</span>
              ) : (
                <>
                  <span>Accept Invitation & Open Dashboard</span>
                  <ArrowRight size={18} />
                </>
              )}
            </button>
          </div>
        ) : (
          <div className="inline-auth-box">
            <p className="inline-auth-intro">
              Please sign in or create your caregiver account to accept this invitation:
            </p>

            <div className="inline-auth-tabs">
              <button
                type="button"
                className={`inline-tab ${authMode === 'login' ? 'active' : ''}`}
                onClick={() => setAuthMode('login')}
              >
                Sign In
              </button>
              <button
                type="button"
                className={`inline-tab ${authMode === 'register' ? 'active' : ''}`}
                onClick={() => setAuthMode('register')}
              >
                Create Account
              </button>
            </div>

            {authError && (
              <div className="inline-alert error">
                <AlertCircle size={16} />
                <span>{authError}</span>
              </div>
            )}

            <form onSubmit={handleInlineAuth} className="inline-auth-form">
              {authMode === 'register' && (
                <div className="form-group">
                  <label className="form-label">Full Name</label>
                  <input
                    type="text"
                    required
                    placeholder="Your Name"
                    value={authName}
                    onChange={(e) => setAuthName(e.target.value)}
                    className="auth-input"
                  />
                </div>
              )}

              <div className="form-group">
                <label className="form-label">Email Address</label>
                <input
                  type="email"
                  required
                  placeholder="you@example.com"
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                  className="auth-input"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Password</label>
                <input
                  type="password"
                  required
                  placeholder="Min. 8 characters"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  className="auth-input"
                />
              </div>

              <button
                type="submit"
                className="accept-submit-btn"
                disabled={submittingAuth}
              >
                {submittingAuth ? (
                  <span>Processing...</span>
                ) : (
                  <>
                    <span>
                      {authMode === 'login' ? 'Sign In & Accept' : 'Register & Accept'}
                    </span>
                    <ArrowRight size={18} />
                  </>
                )}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
