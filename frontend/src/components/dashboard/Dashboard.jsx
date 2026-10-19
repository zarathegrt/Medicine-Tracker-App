import React, { useState, useEffect, useCallback } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  CheckCircle2,
  Clock,
  Pill,
  TrendingUp,
  AlertCircle,
  Plus,
  SkipForward,
  RotateCw,
  Bell,
  Calendar,
  Sparkles,
} from 'lucide-react';
import api from '../../services/api';
import { useToast } from '../common/ToastContext';
import SpotlightCard from '../reactbits/SpotlightCard';
import CountUp from '../reactbits/CountUp';
import BlurText from '../reactbits/BlurText';
import Aurora from '../reactbits/Aurora';
import StatusBadge from '../common/StatusBadge';
import LoadingSkeleton from '../common/LoadingSkeleton';
import EmptyState from '../common/EmptyState';
import ConfirmDialog from '../common/ConfirmDialog';
import './Dashboard.css';

export default function Dashboard() {
  const { openAddModal } = useOutletContext();
  const toast = useToast();

  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [schedule, setSchedule] = useState([]);
  const [dialogConfig, setDialogConfig] = useState({ isOpen: false });

  // Compute greeting
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';

  const loadDashboardData = useCallback(async () => {
    try {
      const [statsRes, scheduleRes] = await Promise.all([
        api.getStatistics(),
        api.getTodaySchedule(),
      ]);
      setStats(statsRes);
      setSchedule(scheduleRes || []);
    } catch (err) {
      toast.error(err.message || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadDashboardData();

    // Listen for medicine addition events to refresh
    const handleMedAdded = () => loadDashboardData();
    window.addEventListener('curavit:medicine-added', handleMedAdded);
    return () => window.removeEventListener('curavit:medicine-added', handleMedAdded);
  }, [loadDashboardData]);

  // Dose actions
  const handleMarkTaken = async (logId, medName) => {
    try {
      await api.logDose({ log_id: logId, status: 'taken' });
      toast.success(`Dose for ${medName} marked as taken!`);
      await loadDashboardData();
    } catch (err) {
      toast.error(err.message || 'Failed to record dose');
    }
  };

  const handleSkipDose = (logId, medName) => {
    setDialogConfig({
      isOpen: true,
      title: 'Skip This Dose?',
      message: `Are you sure you want to skip your scheduled dose of ${medName}? This will be recorded in your history.`,
      confirmLabel: 'Yes, Skip',
      isDestructive: false,
      onConfirm: async () => {
        try {
          await api.logDose({ log_id: logId, status: 'skipped', notes: 'Dose skipped by user' });
          toast.info(`Dose for ${medName} marked as skipped`);
          setDialogConfig({ isOpen: false });
          await loadDashboardData();
        } catch (err) {
          toast.error(err.message || 'Failed to skip dose');
        }
      },
      onCancel: () => setDialogConfig({ isOpen: false }),
    });
  };

  const handleSnooze = async (logId, medName) => {
    try {
      const res = await api.snoozeDose(logId, 10);
      toast.info(`Snoozed ${medName} by 10 minutes`);
      await loadDashboardData();
    } catch (err) {
      toast.error(err.message || 'Failed to snooze dose');
    }
  };

  if (loading) {
    return (
      <div className="dashboard-page">
        <div className="skeleton-welcome" />
        <LoadingSkeleton variant="stat" count={4} />
        <div style={{ marginTop: '24px' }}>
          <LoadingSkeleton variant="list" count={3} />
        </div>
      </div>
    );
  }

  // Calculate completion percentage
  const totalToday = stats?.total_today || 0;
  const takenToday = stats?.taken_today || 0;
  const progressPercent = totalToday > 0 ? Math.round((takenToday / totalToday) * 100) : 0;

  // Split into upcoming / pending and completed
  const pendingDoses = schedule.filter((item) => item.status === 'pending');
  const completedDoses = schedule.filter((item) => item.status !== 'pending');

  return (
    <div className="dashboard-page">
      {/* Welcome Card with React Bits Aurora & BlurText */}
      <div className="welcome-banner">
        <Aurora opacity={0.35} />
        <div className="welcome-content">
          <div className="welcome-left">
            <span className="welcome-date-badge">
              <Calendar size={13} />
              {new Date().toLocaleDateString('en-US', {
                weekday: 'long',
                month: 'long',
                day: 'numeric',
              })}
            </span>
            <h1 className="welcome-title">
              <BlurText text={`${greeting}!`} />
            </h1>
            <p className="welcome-desc">
              {totalToday === 0
                ? "You have no scheduled doses for today. Stay healthy and hydrated!"
                : takenToday === totalToday
                ? "Awesome work! All your scheduled doses for today have been taken."
                : `You have completed ${takenToday} of ${totalToday} doses scheduled for today.`}
            </p>
          </div>

          <div className="welcome-right">
            <button
              type="button"
              className="welcome-add-btn"
              onClick={openAddModal}
            >
              <Plus size={16} />
              <span>Add Medicine</span>
            </button>
          </div>
        </div>

        {/* Progress bar inside banner */}
        {totalToday > 0 && (
          <div className="welcome-progress-bar-wrap">
            <div className="progress-label-row">
              <span>Today's Completion</span>
              <span className="progress-percent-val">{progressPercent}%</span>
            </div>
            <div className="progress-track">
              <div
                className="progress-fill"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Metrics Row using React Bits SpotlightCard & CountUp */}
      <div className="stats-cards-grid">
        <SpotlightCard className="metric-card">
          <div className="metric-icon-box box-primary">
            <Pill size={20} />
          </div>
          <div className="metric-data">
            <span className="metric-label">Active Medicines</span>
            <div className="metric-value">
              <CountUp to={stats?.total_medicines || 0} />
            </div>
            <span className="metric-subtext">Currently prescribed</span>
          </div>
        </SpotlightCard>

        <SpotlightCard className="metric-card">
          <div className="metric-icon-box box-success">
            <CheckCircle2 size={20} />
          </div>
          <div className="metric-data">
            <span className="metric-label">Doses Taken Today</span>
            <div className="metric-value">
              <CountUp to={stats?.taken_today || 0} />
              <span className="metric-total-denom">/ {stats?.total_today || 0}</span>
            </div>
            <span className="metric-subtext">
              {stats?.total_today ? `${progressPercent}% of daily regimen` : 'No doses today'}
            </span>
          </div>
        </SpotlightCard>

        <SpotlightCard className="metric-card">
          <div className="metric-icon-box box-upcoming">
            <Clock size={20} />
          </div>
          <div className="metric-data">
            <span className="metric-label">Pending / Upcoming</span>
            <div className="metric-value">
              <CountUp to={stats?.upcoming_today || 0} />
            </div>
            <span className="metric-subtext">
              {stats?.overdue_today ? `${stats.overdue_today} dose(s) overdue` : 'On schedule'}
            </span>
          </div>
        </SpotlightCard>

        <SpotlightCard className="metric-card">
          <div className="metric-icon-box box-lavender">
            <TrendingUp size={20} />
          </div>
          <div className="metric-data">
            <span className="metric-label">7-Day Adherence</span>
            <div className="metric-value">
              <CountUp to={stats?.adherence_rate || 100} decimals={1} suffix="%" />
            </div>
            <span className="metric-subtext">Based on past 7 days</span>
          </div>
        </SpotlightCard>
      </div>

      {/* Today's Schedule Section */}
      <section className="dashboard-schedule-section">
        <div className="section-header">
          <div>
            <h2>Today's Medication Schedule</h2>
            <p className="section-subtitle">
              Follow your planned doses or record when you take them
            </p>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={loadDashboardData}
            title="Refresh schedule"
          >
            <RotateCw size={14} />
            <span>Refresh</span>
          </button>
        </div>

        {schedule.length === 0 ? (
          <EmptyState
            icon={Pill}
            title="No doses scheduled for today"
            description="Add your daily medicines to automatically populate your daily medication timeline."
            actionLabel="Add Medicine"
            onAction={openAddModal}
          />
        ) : (
          <div className="schedule-timeline-list">
            {schedule.map((item) => {
              const isTaken = item.status === 'taken';
              const isSkipped = item.status === 'skipped';
              const isPending = item.status === 'pending';
              const isOverdue = item.is_overdue;

              const timeStr = item.scheduled_time
                ? item.scheduled_time.split(' ')[1] || item.scheduled_time
                : '--:--';

              return (
                <div
                  key={item.id}
                  className={`schedule-dose-card ${
                    isTaken ? 'dose-taken' : isOverdue ? 'dose-overdue' : ''
                  }`}
                >
                  <div className="dose-time-column">
                    <span className="dose-time-val">{timeStr}</span>
                    <span className="dose-time-label">
                      {isOverdue ? 'Overdue' : isTaken ? 'Completed' : 'Scheduled'}
                    </span>
                  </div>

                  <div className="dose-card-divider" />

                  <div className="dose-info-column">
                    <div className="dose-title-row">
                      <h3 className="dose-med-name">{item.medicine_name}</h3>
                      <span className="dose-pill-dosage">{item.dosage}</span>
                      <StatusBadge status={item.status} isOverdue={isOverdue} />
                    </div>

                    {item.instructions && (
                      <p className="dose-instructions">
                        <Sparkles size={13} className="instruction-icon" />
                        {item.instructions}
                      </p>
                    )}

                    {item.notes && (
                      <p className="dose-notes-text">
                        <strong>Note:</strong> {item.notes}
                      </p>
                    )}

                    {item.taken_time && (
                      <span className="dose-timestamp">
                        Taken at {item.taken_time.split(' ')[1] || item.taken_time}
                      </span>
                    )}
                  </div>

                  <div className="dose-actions-column">
                    {isPending ? (
                      <>
                        <button
                          type="button"
                          className="btn btn-primary dose-action-btn"
                          onClick={() => handleMarkTaken(item.id, item.medicine_name)}
                        >
                          <CheckCircle2 size={16} />
                          <span>Take Dose</span>
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary dose-action-btn"
                          onClick={() => handleSnooze(item.id, item.medicine_name)}
                          title="Snooze 10 minutes"
                        >
                          <Clock size={15} />
                          <span>Snooze</span>
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary dose-action-btn btn-skip"
                          onClick={() => handleSkipDose(item.id, item.medicine_name)}
                          title="Skip dose"
                        >
                          <SkipForward size={14} />
                          <span>Skip</span>
                        </button>
                      </>
                    ) : (
                      <div className="dose-status-completed">
                        <CheckCircle2 size={16} className="completed-check-icon" />
                        <span>{isTaken ? 'Dose Logged' : 'Skipped'}</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Confirmation Dialog */}
      <ConfirmDialog {...dialogConfig} />
    </div>
  );
}
