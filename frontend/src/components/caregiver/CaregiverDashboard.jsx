import React, { useState, useEffect, useCallback } from 'react';
import {
  HeartHandshake,
  Users,
  Calendar,
  CheckCircle2,
  Clock,
  AlertCircle,
  XCircle,
  Edit3,
  RefreshCw,
  Lock,
  ShieldCheck,
  TrendingUp,
  Activity,
  ChevronDown,
  Pill,
  Info
} from 'lucide-react';
import api from '../../services/api';
import { useAuth } from '../../services/authContext';
import { useToast } from '../common/ToastContext';
import './CaregiverDashboard.css';

export default function CaregiverDashboard() {
  const { user, caregiverPatients, activePatientId, setActivePatientId, fetchCaregiverPatients } = useAuth();
  const { showToast } = useToast();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [summary, setSummary] = useState(null);
  const [schedule, setSchedule] = useState([]);
  const [activityFeed, setActivityFeed] = useState([]);

  // Correction Modal State
  const [correctingDose, setCorrectingDose] = useState(null);
  const [newStatus, setNewStatus] = useState('pending');
  const [correctionReason, setCorrectionReason] = useState('');
  const [submittingCorrection, setSubmittingCorrection] = useState(false);

  // Active Patient Object
  const currentPatient = caregiverPatients.find(
    (p) => (p.id || p.patient_id) === activePatientId
  ) || caregiverPatients[0] || null;

  const permissions = currentPatient?.permissions || [];
  const canViewSchedule = permissions.includes('view_schedule');
  const canRecordDoses = permissions.includes('record_doses');
  const canCorrectDoses = permissions.includes('correct_doses');
  const canViewAdherence = permissions.includes('view_adherence');

  const loadPatientData = useCallback(async (isRefresh = false) => {
    if (!currentPatient) {
      setLoading(false);
      return;
    }

    const pId = currentPatient.id || currentPatient.patient_id;
    if (isRefresh) setRefreshing(true);

    try {
      // 1. Fetch Daily Summary
      const summaryData = await api.getPatientSummary(pId);
      setSummary(summaryData?.summary || null);

      // 2. Fetch Today's Schedule if permitted
      if (canViewSchedule) {
        const schedData = await api.getTodaySchedule(pId);
        setSchedule(schedData || []);
      } else {
        setSchedule([]);
      }

      // 3. Fetch Activity Feed
      const actData = await api.getPatientActivity(pId);
      setActivityFeed(actData?.activity || []);

    } catch (err) {
      showToast(err.message || 'Failed to load patient information', 'error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [currentPatient, canViewSchedule, showToast]);

  useEffect(() => {
    fetchCaregiverPatients().then(() => {
      loadPatientData();
    });
  }, [activePatientId]);

  // Handle Dose Recording (Taken or Skipped)
  const handleLogDose = async (logId, status) => {
    if (!canRecordDoses || !currentPatient) return;
    const pId = currentPatient.id || currentPatient.patient_id;

    try {
      await api.logDose({ log_id: logId, status }, pId);
      showToast(`Dose marked as ${status} successfully!`, 'success');
      loadPatientData(true);
    } catch (err) {
      showToast(err.message || `Failed to record dose as ${status}`, 'error');
    }
  };

  // Open Correction Modal
  const openCorrectionModal = (dose) => {
    setCorrectingDose(dose);
    setNewStatus(dose.status === 'taken' ? 'pending' : 'taken');
    setCorrectionReason('');
  };

  // Submit Dose Correction
  const handleSubmitCorrection = async (e) => {
    e.preventDefault();
    if (!correctingDose || !correctionReason.trim() || !currentPatient) return;
    const pId = currentPatient.id || currentPatient.patient_id;

    setSubmittingCorrection(true);
    try {
      await api.correctDose(
        correctingDose.id,
        {
          new_status: newStatus,
          reason: correctionReason.trim(),
        },
        pId
      );
      showToast('Dose record corrected and audited', 'success');
      setCorrectingDose(null);
      loadPatientData(true);
    } catch (err) {
      showToast(err.message || 'Failed to correct dose record', 'error');
    } finally {
      setSubmittingCorrection(false);
    }
  };

  if (loading && caregiverPatients.length === 0) {
    return (
      <div className="caregiver-loading-screen">
        <RefreshCw size={24} className="spinning" />
        <span>Loading Caregiver Dashboard...</span>
      </div>
    );
  }

  if (caregiverPatients.length === 0) {
    return (
      <div className="caregiver-empty-screen">
        <div className="empty-icon-box">
          <HeartHandshake size={36} />
        </div>
        <h2>No Authorized Patients Found</h2>
        <p>
          You are currently logged in as a Caregiver. When a patient invites you to join their
          care team, and you accept their invitation, their medications and schedule will appear here.
        </p>
      </div>
    );
  }

  const pName = currentPatient?.name || currentPatient?.patient_name || 'Patient';

  return (
    <div className="caregiver-dashboard-container">
      {/* Top Patient Selector & Header Bar */}
      <div className="caregiver-top-bar">
        <div className="patient-selector-wrap">
          <label htmlFor="patient-select" className="patient-select-label">
            <Users size={16} />
            <span>Active Patient:</span>
          </label>
          <div className="select-dropdown-container">
            <select
              id="patient-select"
              value={activePatientId || ''}
              onChange={(e) => setActivePatientId(Number(e.target.value))}
              className="patient-select-dropdown"
            >
              {caregiverPatients.map((p) => {
                const id = p.id || p.patient_id;
                const name = p.name || p.patient_name || `Patient #${id}`;
                return (
                  <option key={id} value={id}>
                    {name} ({p.patient_email || 'Patient'})
                  </option>
                );
              })}
            </select>
            <ChevronDown size={16} className="dropdown-arrow" />
          </div>
        </div>

        <div className="top-bar-actions">
          <button
            type="button"
            className="refresh-btn"
            onClick={() => loadPatientData(true)}
            disabled={refreshing}
            title="Refresh summary & schedule"
          >
            <RefreshCw size={16} className={refreshing ? 'spinning' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Permissions Transparency Pill Bar */}
      <div className="permissions-indicator-bar">
        <div className="perms-title">
          <ShieldCheck size={14} />
          <span>Caregiver Access Permissions for {pName}:</span>
        </div>
        <div className="perms-list">
          {permissions.map((p) => (
            <span key={p} className="perm-chip active">
              ✓ {p.replace('view_', '').replace('_', ' ')}
            </span>
          ))}
          {!canRecordDoses && (
            <span className="perm-chip lock" title="Patient has not granted dose recording permission">
              <Lock size={11} /> Read-Only Doses
            </span>
          )}
          {!canCorrectDoses && (
            <span className="perm-chip lock" title="Patient has not granted dose correction permission">
              <Lock size={11} /> No Corrections
            </span>
          )}
        </div>
      </div>

      {/* Daily Summary Banner (Section 9) */}
      <div className="daily-summary-card">
        <div className="summary-header">
          <div className="summary-title-wrap">
            <Calendar size={18} />
            <h2 className="summary-heading">Daily Care Summary — {pName}</h2>
          </div>
          {summary?.generated_at && (
            <span className="summary-timestamp">
              Updated {new Date(summary.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
        </div>

        <div className="summary-kpis-grid">
          <div className="summary-kpi">
            <span className="kpi-num">{summary?.total_scheduled ?? 0}</span>
            <span className="kpi-sub">Total Scheduled</span>
          </div>
          <div className="summary-kpi taken">
            <span className="kpi-num">{summary?.doses_taken ?? 0}</span>
            <span className="kpi-sub">Recorded Taken</span>
          </div>
          <div className="summary-kpi pending">
            <span className="kpi-num">{summary?.doses_pending ?? 0}</span>
            <span className="kpi-sub">Upcoming / Pending</span>
          </div>
          <div className="summary-kpi overdue">
            <span className="kpi-num">{summary?.doses_overdue ?? 0}</span>
            <span className="kpi-sub">Overdue</span>
          </div>
          {canViewAdherence && (
            <div className="summary-kpi adherence">
              <span className="kpi-num">
                {summary?.adherence_rate !== null && summary?.adherence_rate !== undefined 
                  ? `${summary.adherence_rate}%` 
                  : 'N/A'}
              </span>
              <span className="kpi-sub">Weekly Adherence</span>
            </div>
          )}
        </div>
      </div>

      {/* Main Grid: Today's Schedule & Activity Feed */}
      <div className="caregiver-main-grid">
        {/* Today's Schedule (Section 8) */}
        <div className="schedule-column">
          <div className="column-header">
            <div className="col-title-wrap">
              <Pill size={18} />
              <h3 className="column-title">Today's Medication Schedule</h3>
            </div>
            <span className="dose-count-badge">{schedule.length} Doses</span>
          </div>

          {!canViewSchedule ? (
            <div className="permission-locked-box">
              <Lock size={28} />
              <h4>Schedule View Not Authorized</h4>
              <p>The patient has not granted the "View Today's Schedule" permission to this caregiver account.</p>
            </div>
          ) : schedule.length === 0 ? (
            <div className="empty-schedule-box">
              <CheckCircle2 size={32} className="empty-sched-icon" />
              <h4>No Doses Scheduled Today</h4>
              <p>All active medications have either no doses today or have already been completed.</p>
            </div>
          ) : (
            <div className="schedule-cards-list">
              {schedule.map((dose) => {
                const isOverdue = dose.is_overdue || (dose.status === 'pending' && dose.scheduled_time && dose.scheduled_time.slice(11, 16) < new Date().toTimeString().slice(0, 5));
                const displayStatus = isOverdue ? 'overdue' : dose.status;

                return (
                  <div key={dose.id} className={`dose-item-card ${displayStatus}`}>
                    <div className="dose-time-box">
                      <Clock size={15} />
                      <span>{dose.scheduled_time ? dose.scheduled_time.slice(11, 16) : 'Daily'}</span>
                    </div>

                    <div className="dose-info-box">
                      <h4 className="dose-med-name">{dose.medicine_name}</h4>
                      <span className="dose-dosage">{dose.dosage}</span>
                      {dose.instructions && (
                        <p className="dose-instructions">
                          <Info size={12} />
                          <span>{dose.instructions}</span>
                        </p>
                      )}
                    </div>

                    <div className="dose-status-badge-wrap">
                      <span className={`dose-status-tag ${displayStatus}`}>
                        {displayStatus}
                      </span>
                    </div>

                    {/* Actions Column */}
                    <div className="dose-actions-box">
                      {canRecordDoses ? (
                        <>
                          {dose.status === 'pending' ? (
                            <div className="action-button-group">
                              <button
                                type="button"
                                className="action-btn take"
                                onClick={() => handleLogDose(dose.id, 'taken')}
                                title="Mark dose as taken"
                              >
                                <CheckCircle2 size={15} />
                                <span>Take</span>
                              </button>
                              <button
                                type="button"
                                className="action-btn skip"
                                onClick={() => handleLogDose(dose.id, 'skipped')}
                                title="Mark dose as skipped"
                              >
                                <XCircle size={15} />
                                <span>Skip</span>
                              </button>
                            </div>
                          ) : (
                            <div className="action-button-group">
                              {canCorrectDoses && (
                                <button
                                  type="button"
                                  className="action-btn correct"
                                  onClick={() => openCorrectionModal(dose)}
                                  title="Correct dose mistake"
                                >
                                  <Edit3 size={14} />
                                  <span>Correct</span>
                                </button>
                              )}
                            </div>
                          )}
                        </>
                      ) : (
                        <span className="view-only-tag" title="Record permission not granted">
                          <Lock size={12} /> View-Only
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Activity Feed Column (Section 8) */}
        <div className="activity-column">
          <div className="column-header">
            <div className="col-title-wrap">
              <Activity size={18} />
              <h3 className="column-title">Patient Care Activity</h3>
            </div>
          </div>

          {activityFeed.length === 0 ? (
            <div className="empty-activity-box">
              <span>No recorded caregiver events yet.</span>
            </div>
          ) : (
            <div className="activity-list">
              {activityFeed.map((item) => (
                <div key={item.id} className="activity-card">
                  <div className="activity-top">
                    <span className="actor-badge">{item.actor_name}</span>
                    <span className="activity-time">
                      {new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <p className="activity-desc">{item.details || item.action}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* Modal: Correct Dose with Mandatory Audit Reason (Section 10) */}
      {/* ------------------------------------------------------------------- */}
      {correctingDose && (
        <div className="modal-backdrop" onClick={() => !submittingCorrection && setCorrectingDose(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-wrap">
                <Edit3 size={20} className="modal-header-icon" />
                <h3 className="modal-title">Correct Dose Record</h3>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setCorrectingDose(null)}
              >
                &times;
              </button>
            </div>

            <p className="modal-intro-text">
              Correcting previously logged dose of <strong>{correctingDose.medicine_name}</strong> ({correctingDose.dosage}).
              Every correction is audited with your identity for patient safety.
            </p>

            <form onSubmit={handleSubmitCorrection} className="correction-form">
              <div className="form-group">
                <label className="form-label">Current Status</label>
                <div className="current-status-display">
                  <span className={`status-pill ${correctingDose.status}`}>{correctingDose.status}</span>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="new-status-select" className="form-label">New Corrected Status</label>
                <select
                  id="new-status-select"
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value)}
                  className="form-input"
                >
                  <option value="pending">Pending (Not yet taken)</option>
                  <option value="taken">Taken</option>
                  <option value="skipped">Skipped</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="correction-reason" className="form-label">
                  Mandatory Clinical / Audit Reason <span className="req">*</span>
                </label>
                <textarea
                  id="correction-reason"
                  required
                  rows={3}
                  placeholder="e.g., Patient vomited medication 5 minutes later; physician instructed to re-dose"
                  value={correctionReason}
                  onChange={(e) => setCorrectionReason(e.target.value)}
                  className="form-textarea"
                />
              </div>

              <div className="modal-actions">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setCorrectingDose(null)}
                  disabled={submittingCorrection}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={submittingCorrection || !correctionReason.trim()}
                >
                  {submittingCorrection ? 'Auditing...' : 'Save Correction'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
