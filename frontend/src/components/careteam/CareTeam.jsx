import React, { useState, useEffect, useCallback } from 'react';
import {
  Users,
  UserPlus,
  Shield,
  ShieldCheck,
  ShieldAlert,
  Clock,
  CheckCircle2,
  XCircle,
  Copy,
  Check,
  Trash2,
  Settings2,
  AlertTriangle,
  History,
  Lock,
  Eye,
  RefreshCw,
  ExternalLink,
  ChevronRight
} from 'lucide-react';
import api from '../../services/api';
import { useAuth } from '../../services/authContext';
import { useToast } from '../common/ToastContext';
import './CareTeam.css';

const PERMISSION_DEFINITIONS = [
  {
    id: 'view_medicines',
    label: 'View Medicines',
    description: 'Can see your prescription names, dosages, and instructions.',
    defaultSelected: true,
  },
  {
    id: 'view_schedule',
    label: 'View Today\'s Schedule',
    description: 'Can see scheduled dose times and current status.',
    defaultSelected: true,
  },
  {
    id: 'view_history',
    label: 'View Dose History',
    description: 'Can inspect past taken, skipped, and missed logs.',
    defaultSelected: false,
  },
  {
    id: 'view_adherence',
    label: 'View Adherence Analytics',
    description: 'Can monitor weekly adherence rate and trend charts.',
    defaultSelected: false,
  },
  {
    id: 'record_doses',
    label: 'Record Doses',
    description: 'Can log doses as taken or skipped on your behalf.',
    defaultSelected: false,
  },
  {
    id: 'correct_doses',
    label: 'Correct Dose Mistakes',
    description: 'Can adjust previously logged doses with a mandatory recorded reason (requires Record Doses).',
    defaultSelected: false,
  },
];

export default function CareTeam() {
  const { user } = useAuth();
  const { showToast } = useToast();

  const [caregivers, setCaregivers] = useState([]);
  const [invitations, setInvitations] = useState([]);
  const [activityLogs, setActivityLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Invite Modal State
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [selectedPermissions, setSelectedPermissions] = useState(['view_medicines', 'view_schedule']);
  const [submittingInvite, setSubmittingInvite] = useState(false);
  const [inviteResult, setInviteResult] = useState(null);
  const [copiedToken, setCopiedToken] = useState(false);

  // Edit Permissions Modal State
  const [editingCaregiver, setEditingCaregiver] = useState(null);
  const [editPermissionsList, setEditPermissionsList] = useState([]);
  const [savingPermissions, setSavingPermissions] = useState(false);

  // Revoke Confirm Modal State
  const [revokingCaregiver, setRevokingCaregiver] = useState(null);
  const [submittingRevoke, setSubmittingRevoke] = useState(false);

  const fetchTeamData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const data = await api.getCaregiverTeam();
      setCaregivers(data.caregivers || []);
      setInvitations(data.invitations || []);
      setActivityLogs(data.recent_activity || []);
    } catch (err) {
      showToast(err.message || 'Failed to load care team data', 'error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [showToast]);

  useEffect(() => {
    fetchTeamData();
  }, [fetchTeamData]);

  // Handle permission toggle in invite modal
  const handlePermissionToggle = (permId) => {
    setSelectedPermissions((prev) => {
      let updated;
      if (prev.includes(permId)) {
        updated = prev.filter((p) => p !== permId);
        // If unchecking record_doses, also uncheck correct_doses
        if (permId === 'record_doses') {
          updated = updated.filter((p) => p !== 'correct_doses');
        }
      } else {
        updated = [...prev, permId];
        // If checking correct_doses, also ensure record_doses is enabled
        if (permId === 'correct_doses' && !updated.includes('record_doses')) {
          updated.push('record_doses');
        }
      }
      return updated;
    });
  };

  // Submit new invitation
  const handleSendInvite = async (e) => {
    e.preventDefault();
    if (!inviteEmail) return;

    setSubmittingInvite(true);
    try {
      const res = await api.inviteCaregiver({
        email: inviteEmail,
        permissions: selectedPermissions,
      });
      setInviteResult(res);
      showToast(`Invitation created for ${inviteEmail}!`, 'success');
      fetchTeamData();
    } catch (err) {
      showToast(err.message || 'Failed to send invitation', 'error');
    } finally {
      setSubmittingInvite(false);
    }
  };

  const handleCopyInviteLink = (token) => {
    const link = `${window.location.origin}/accept-invite?token=${token}`;
    navigator.clipboard.writeText(link);
    setCopiedToken(true);
    showToast('Invitation link copied to clipboard!', 'success');
    setTimeout(() => setCopiedToken(false), 2500);
  };

  // Cancel pending invitation
  const handleCancelInvite = async (invId) => {
    try {
      await api.cancelInvitation(invId);
      showToast('Invitation cancelled successfully', 'info');
      fetchTeamData();
    } catch (err) {
      showToast(err.message || 'Failed to cancel invitation', 'error');
    }
  };

  // Edit Permissions Dialog
  const openEditPermissions = (cg) => {
    setEditingCaregiver(cg);
    setEditPermissionsList(cg.permissions || []);
  };

  const handleEditPermissionToggle = (permId) => {
    setEditPermissionsList((prev) => {
      let updated;
      if (prev.includes(permId)) {
        updated = prev.filter((p) => p !== permId);
        if (permId === 'record_doses') {
          updated = updated.filter((p) => p !== 'correct_doses');
        }
      } else {
        updated = [...prev, permId];
        if (permId === 'correct_doses' && !updated.includes('record_doses')) {
          updated.push('record_doses');
        }
      }
      return updated;
    });
  };

  const handleSavePermissions = async () => {
    if (!editingCaregiver) return;
    setSavingPermissions(true);
    try {
      await api.updateCaregiverPermissions(editingCaregiver.id || editingCaregiver.relationship_id, editPermissionsList);
      showToast(`Permissions updated for ${editingCaregiver.caregiver_name}`, 'success');
      setEditingCaregiver(null);
      fetchTeamData();
    } catch (err) {
      showToast(err.message || 'Failed to update permissions', 'error');
    } finally {
      setSavingPermissions(false);
    }
  };

  // Revoke Caregiver Access
  const handleConfirmRevoke = async () => {
    if (!revokingCaregiver) return;
    setSubmittingRevoke(true);
    try {
      await api.revokeCaregiver(revokingCaregiver.id || revokingCaregiver.relationship_id);
      showToast(`Access revoked for ${revokingCaregiver.caregiver_name}`, 'info');
      setRevokingCaregiver(null);
      fetchTeamData();
    } catch (err) {
      showToast(err.message || 'Failed to revoke access', 'error');
    } finally {
      setSubmittingRevoke(false);
    }
  };

  const pendingInvites = invitations.filter((inv) => inv.status === 'pending');
  const pastInvites = invitations.filter((inv) => inv.status !== 'pending');

  return (
    <div className="care-team-container">
      {/* Page Header */}
      <div className="care-team-header">
        <div className="header-titles">
          <div className="header-badge">
            <Users size={16} />
            <span>Care Team</span>
          </div>
          <h1 className="care-team-title">Authorized Caregivers</h1>
          <p className="care-team-subtitle">
            Allow trusted family members or caregivers to view your medication routine and assist when needed.
          </p>
        </div>

        <div className="header-actions">
          <button
            type="button"
            className="refresh-btn"
            onClick={() => fetchTeamData(true)}
            disabled={refreshing}
            title="Refresh team data"
          >
            <RefreshCw size={16} className={refreshing ? 'spinning' : ''} />
          </button>
          <button
            type="button"
            className="invite-caregiver-btn"
            onClick={() => {
              setInviteResult(null);
              setInviteEmail('');
              setSelectedPermissions(['view_medicines', 'view_schedule']);
              setIsInviteModalOpen(true);
            }}
          >
            <UserPlus size={18} />
            <span>Invite Caregiver</span>
          </button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="team-kpi-grid">
        <div className="kpi-card">
          <div className="kpi-icon-wrap active-caregivers">
            <ShieldCheck size={22} />
          </div>
          <div className="kpi-data">
            <span className="kpi-value">{caregivers.length}</span>
            <span className="kpi-label">Active Caregivers</span>
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-icon-wrap pending-invites">
            <Clock size={22} />
          </div>
          <div className="kpi-data">
            <span className="kpi-value">{pendingInvites.length}</span>
            <span className="kpi-label">Pending Invitations</span>
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-icon-wrap security-status">
            <Shield size={22} />
          </div>
          <div className="kpi-data">
            <span className="kpi-value">Least-Privilege</span>
            <span className="kpi-label">Access Control Enforced</span>
          </div>
        </div>
      </div>

      {/* Main Content Layout */}
      <div className="care-team-sections">
        {/* Active Caregivers Section */}
        <section className="team-section">
          <div className="section-header">
            <h2 className="section-title">Active Care Team Members</h2>
            <span className="section-count">{caregivers.length} Authorized</span>
          </div>

          {loading ? (
            <div className="care-team-loading">Loading care team...</div>
          ) : caregivers.length === 0 ? (
            <div className="empty-team-card">
              <div className="empty-icon-wrap">
                <Users size={32} />
              </div>
              <h3 className="empty-title">No Caregivers Authorized Yet</h3>
              <p className="empty-desc">
                Invite a family member, nurse, or trusted friend to help oversee your schedule.
                You control exactly what each caregiver can see and do.
              </p>
              <button
                type="button"
                className="empty-cta-btn"
                onClick={() => setIsInviteModalOpen(true)}
              >
                <UserPlus size={16} />
                <span>Invite Your First Caregiver</span>
              </button>
            </div>
          ) : (
            <div className="caregiver-cards-grid">
              {caregivers.map((cg) => (
                <div key={cg.id || cg.relationship_id} className="caregiver-card">
                  <div className="caregiver-card-top">
                    <div className="caregiver-avatar">
                      {(cg.caregiver_name || 'C').charAt(0).toUpperCase()}
                    </div>
                    <div className="caregiver-meta">
                      <h3 className="caregiver-name">{cg.caregiver_name}</h3>
                      <span className="caregiver-email">{cg.caregiver_email}</span>
                      <span className="caregiver-date">
                        Joined {new Date(cg.accepted_at || cg.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>

                  <div className="caregiver-permissions-section">
                    <span className="permissions-label">Granted Access:</span>
                    <div className="permissions-badges">
                      {(cg.permissions || []).map((p) => {
                        const def = PERMISSION_DEFINITIONS.find((d) => d.id === p);
                        return (
                          <span key={p} className="perm-badge">
                            {def ? def.label : p}
                          </span>
                        );
                      })}
                      {(!cg.permissions || cg.permissions.length === 0) && (
                        <span className="perm-badge none">No permissions</span>
                      )}
                    </div>
                  </div>

                  <div className="caregiver-card-actions">
                    <button
                      type="button"
                      className="edit-perm-btn"
                      onClick={() => openEditPermissions(cg)}
                    >
                      <Settings2 size={15} />
                      <span>Edit Permissions</span>
                    </button>
                    <button
                      type="button"
                      className="revoke-btn"
                      onClick={() => setRevokingCaregiver(cg)}
                    >
                      <Trash2 size={15} />
                      <span>Revoke</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Pending & Historical Invitations */}
        <section className="team-section">
          <div className="section-header">
            <h2 className="section-title">Invitations</h2>
            <span className="section-count">{invitations.length} Total</span>
          </div>

          {invitations.length === 0 ? (
            <div className="empty-sub-card">
              <span>No invitations sent.</span>
            </div>
          ) : (
            <div className="invitations-table-wrap">
              <table className="invitations-table">
                <thead>
                  <tr>
                    <th>Invited Email</th>
                    <th>Permissions</th>
                    <th>Status</th>
                    <th>Expires</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {invitations.map((inv) => (
                    <tr key={inv.id}>
                      <td className="inv-email-cell">
                        <strong>{inv.invited_email}</strong>
                      </td>
                      <td>
                        <div className="table-perms-wrap">
                          {(inv.permissions || []).map((p) => (
                            <span key={p} className="table-perm-pill">
                              {p.replace('view_', '').replace('_', ' ')}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td>
                        <span className={`status-pill ${inv.status}`}>
                          {inv.status}
                        </span>
                      </td>
                      <td className="inv-date-cell">
                        {new Date(inv.expires_at).toLocaleDateString()}
                      </td>
                      <td>
                        <div className="table-action-btns">
                          {inv.status === 'pending' && inv.invite_token && (
                            <button
                              type="button"
                              className="table-action-btn copy"
                              onClick={() => handleCopyInviteLink(inv.invite_token)}
                              title="Copy invitation link"
                            >
                              <Copy size={14} />
                              <span>Copy Link</span>
                            </button>
                          )}
                          {inv.status === 'pending' && (
                            <button
                              type="button"
                              className="table-action-btn cancel"
                              onClick={() => handleCancelInvite(inv.id)}
                              title="Cancel invitation"
                            >
                              <XCircle size={14} />
                              <span>Cancel</span>
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Activity Audit Log */}
        {activityLogs.length > 0 && (
          <section className="team-section">
            <div className="section-header">
              <h2 className="section-title">Care Team Activity History</h2>
              <span className="section-count">Audit Trail</span>
            </div>

            <div className="activity-timeline">
              {activityLogs.map((log) => (
                <div key={log.id} className="timeline-item">
                  <div className="timeline-marker" />
                  <div className="timeline-content">
                    <div className="timeline-header">
                      <span className="actor-name">{log.actor_name}</span>
                      <span className="actor-role-badge">{log.actor_role}</span>
                      <span className="timeline-time">
                        {new Date(log.timestamp).toLocaleString([], {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                    <p className="timeline-details">{log.details || log.action}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* Modal: Invite Caregiver */}
      {/* ------------------------------------------------------------------- */}
      {isInviteModalOpen && (
        <div className="modal-backdrop" onClick={() => !submittingInvite && setIsInviteModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-wrap">
                <UserPlus size={20} className="modal-header-icon" />
                <h3 className="modal-title">Invite a Caregiver</h3>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setIsInviteModalOpen(false)}
              >
                &times;
              </button>
            </div>

            {inviteResult ? (
              <div className="invite-success-view">
                <div className="success-icon-wrap">
                  <CheckCircle2 size={36} />
                </div>
                <h4 className="success-title">Invitation Link Created!</h4>
                <p className="success-desc">
                  Share this secure single-use invitation link with <strong>{inviteResult.invitation.invited_email}</strong>.
                  They must log in or sign up to accept access.
                </p>

                <div className="invite-link-box">
                  <input
                    type="text"
                    readOnly
                    value={`${window.location.origin}/accept-invite?token=${inviteResult.invite_token}`}
                    className="invite-link-input"
                  />
                  <button
                    type="button"
                    className="copy-link-btn"
                    onClick={() => handleCopyInviteLink(inviteResult.invite_token)}
                  >
                    {copiedToken ? <Check size={16} /> : <Copy size={16} />}
                    <span>{copiedToken ? 'Copied!' : 'Copy'}</span>
                  </button>
                </div>

                <div className="modal-footer-single">
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={() => {
                      setIsInviteModalOpen(false);
                      setInviteResult(null);
                    }}
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSendInvite} className="invite-form">
                <div className="form-group">
                  <label htmlFor="invite-email" className="form-label">Caregiver's Email Address</label>
                  <input
                    id="invite-email"
                    type="email"
                    required
                    placeholder="caregiver@family.org"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    className="form-input"
                  />
                  <span className="form-hint">
                    The caregiver must accept from this email address.
                  </span>
                </div>

                <div className="permissions-selection-group">
                  <label className="form-label">Select Permissions (Least-Privilege Defaults)</label>
                  <div className="permissions-checklist">
                    {PERMISSION_DEFINITIONS.map((perm) => {
                      const isChecked = selectedPermissions.includes(perm.id);
                      return (
                        <label
                          key={perm.id}
                          className={`perm-checkbox-item ${isChecked ? 'selected' : ''}`}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => handlePermissionToggle(perm.id)}
                            className="perm-checkbox"
                          />
                          <div className="perm-text-content">
                            <span className="perm-item-label">{perm.label}</span>
                            <span className="perm-item-desc">{perm.description}</span>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                </div>

                <div className="modal-actions">
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => setIsInviteModalOpen(false)}
                    disabled={submittingInvite}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn-primary"
                    disabled={submittingInvite || !inviteEmail}
                  >
                    {submittingInvite ? 'Generating...' : 'Create Invitation'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* Modal: Edit Caregiver Permissions */}
      {/* ------------------------------------------------------------------- */}
      {editingCaregiver && (
        <div className="modal-backdrop" onClick={() => !savingPermissions && setEditingCaregiver(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-wrap">
                <Settings2 size={20} className="modal-header-icon" />
                <h3 className="modal-title">Edit Caregiver Permissions</h3>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setEditingCaregiver(null)}
              >
                &times;
              </button>
            </div>

            <p className="modal-intro-text">
              Adjust what <strong>{editingCaregiver.caregiver_name}</strong> is permitted to see and do.
            </p>

            <div className="permissions-checklist">
              {PERMISSION_DEFINITIONS.map((perm) => {
                const isChecked = editPermissionsList.includes(perm.id);
                return (
                  <label
                    key={perm.id}
                    className={`perm-checkbox-item ${isChecked ? 'selected' : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => handleEditPermissionToggle(perm.id)}
                      className="perm-checkbox"
                    />
                    <div className="perm-text-content">
                      <span className="perm-item-label">{perm.label}</span>
                      <span className="perm-item-desc">{perm.description}</span>
                    </div>
                  </label>
                );
              })}
            </div>

            <div className="modal-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setEditingCaregiver(null)}
                disabled={savingPermissions}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={handleSavePermissions}
                disabled={savingPermissions}
              >
                {savingPermissions ? 'Saving...' : 'Save Permissions'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* Modal: Revoke Caregiver Access */}
      {/* ------------------------------------------------------------------- */}
      {revokingCaregiver && (
        <div className="modal-backdrop" onClick={() => !submittingRevoke && setRevokingCaregiver(null)}>
          <div className="modal-content danger" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-wrap text-danger">
                <AlertTriangle size={22} />
                <h3 className="modal-title">Revoke Caregiver Access</h3>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setRevokingCaregiver(null)}
              >
                &times;
              </button>
            </div>

            <p className="danger-confirm-text">
              Are you sure you want to revoke access for <strong>{revokingCaregiver.caregiver_name}</strong> ({revokingCaregiver.caregiver_email})?
            </p>
            <p className="danger-sub-text">
              They will immediately lose access to your medication schedule, dose history, and daily summaries.
            </p>

            <div className="modal-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setRevokingCaregiver(null)}
                disabled={submittingRevoke}
              >
                Keep Access
              </button>
              <button
                type="button"
                className="btn-danger"
                onClick={handleConfirmRevoke}
                disabled={submittingRevoke}
              >
                {submittingRevoke ? 'Revoking...' : 'Revoke Access Immediately'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
