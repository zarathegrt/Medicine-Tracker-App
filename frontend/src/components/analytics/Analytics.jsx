import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import {
  TrendingUp,
  CheckCircle2,
  Calendar,
  AlertCircle,
  SkipForward,
  RotateCw,
  Info,
  Pill,
} from 'lucide-react';
import api from '../../services/api';
import { useToast } from '../common/ToastContext';
import SpotlightCard from '../reactbits/SpotlightCard';
import CountUp from '../reactbits/CountUp';
import LoadingSkeleton from '../common/LoadingSkeleton';
import EmptyState from '../common/EmptyState';
import './Analytics.css';

// Chart color constants aligned with design palette
const COLOR_TAKEN = '#829477';     // Sage Green
const COLOR_SKIPPED = '#D8CCE8';   // Soft Lavender
const COLOR_MISSED = '#C55353';    // Muted Red
const COLOR_SCHEDULED = '#A3B49A'; // Light Sage

export default function Analytics() {
  const toast = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getAnalytics();
      setData(res);
    } catch (err) {
      toast.error(err.message || 'Failed to fetch analytics data');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics]);

  if (loading) {
    return (
      <div className="analytics-page">
        <LoadingSkeleton variant="stat" count={4} />
        <div style={{ marginTop: '24px' }}>
          <LoadingSkeleton variant="card" count={2} />
        </div>
      </div>
    );
  }

  const summary = data?.summary || {};
  const dailyTrend = data?.daily_trend || [];
  const medicineBreakdown = data?.medicine_breakdown || [];

  const pieData = [
    { name: 'Taken', value: summary.total_taken || 0, color: COLOR_TAKEN },
    { name: 'Skipped', value: summary.total_skipped || 0, color: COLOR_SKIPPED },
    { name: 'Missed / Pending', value: summary.total_missed || 0, color: COLOR_MISSED },
  ].filter((item) => item.value > 0);

  const hasActivity = summary.total_scheduled > 0 || summary.total_taken > 0;

  return (
    <div className="analytics-page">
      {/* Header */}
      <div className="page-header-row">
        <div>
          <h1 className="page-main-title">Analytics & Adherence</h1>
          <p className="page-main-subtitle">
            Track your medication consistency, completion rates, and daily dosage patterns
          </p>
        </div>

        <button
          type="button"
          className="btn btn-secondary"
          onClick={loadAnalytics}
          title="Refresh analytics data"
        >
          <RotateCw size={15} />
          <span>Refresh Data</span>
        </button>
      </div>

      {/* Overview Stat Cards */}
      <div className="stats-cards-grid">
        <SpotlightCard className="metric-card">
          <div className="metric-icon-box box-primary">
            <TrendingUp size={20} />
          </div>
          <div className="metric-data">
            <span className="metric-label">Weekly Adherence</span>
            <div className="metric-value">
              <CountUp to={summary.weekly_adherence ?? 100} decimals={1} suffix="%" />
            </div>
            <span className="metric-subtext">Past 7 days compliance</span>
          </div>
        </SpotlightCard>

        <SpotlightCard className="metric-card">
          <div className="metric-icon-box box-success">
            <CheckCircle2 size={20} />
          </div>
          <div className="metric-data">
            <span className="metric-label">Doses Taken</span>
            <div className="metric-value">
              <CountUp to={summary.total_taken || 0} />
              <span className="metric-total-denom">/ {summary.total_scheduled || 0}</span>
            </div>
            <span className="metric-subtext">Completed on schedule</span>
          </div>
        </SpotlightCard>

        <SpotlightCard className="metric-card">
          <div className="metric-icon-box box-upcoming">
            <SkipForward size={20} />
          </div>
          <div className="metric-data">
            <span className="metric-label">Doses Skipped</span>
            <div className="metric-value">
              <CountUp to={summary.total_skipped || 0} />
            </div>
            <span className="metric-subtext">Intentionally skipped</span>
          </div>
        </SpotlightCard>

        <SpotlightCard className="metric-card">
          <div className="metric-icon-box box-lavender">
            <AlertCircle size={20} />
          </div>
          <div className="metric-data">
            <span className="metric-label">Missed / Overdue</span>
            <div className="metric-value">
              <CountUp to={summary.total_missed || 0} />
            </div>
            <span className="metric-subtext">Past due without intake</span>
          </div>
        </SpotlightCard>
      </div>

      {!hasActivity ? (
        <EmptyState
          icon={TrendingUp}
          title="Not enough data for analytics yet"
          description="As you add medicines and record doses over the coming days, your 7-day adherence charts and compliance breakdowns will appear here."
        />
      ) : (
        <>
          {/* Charts Row */}
          <div className="analytics-charts-row">
            {/* 7-Day Adherence Bar Chart */}
            <div className="chart-card flex-2">
              <div className="chart-header">
                <h3>7-Day Intake & Adherence Trend</h3>
                <span className="chart-subtitle">Doses taken versus scheduled each day</span>
              </div>

              <div className="chart-container-box">
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={dailyTrend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-subtle)" />
                    <XAxis
                      dataKey="short_day"
                      stroke="var(--text-light)"
                      fontSize={12}
                      tickLine={false}
                    />
                    <YAxis
                      stroke="var(--text-light)"
                      fontSize={12}
                      tickLine={false}
                      allowDecimals={false}
                    />
                    <Tooltip
                      content={({ active, payload, label }) => {
                        if (active && payload && payload.length) {
                          const d = payload[0].payload;
                          return (
                            <div className="custom-chart-tooltip">
                              <p className="tooltip-title">{d.display}</p>
                              <p className="tooltip-stat">
                                <span className="stat-indicator taken" /> Taken: <strong>{d.taken}</strong>
                              </p>
                              <p className="tooltip-stat">
                                <span className="stat-indicator scheduled" /> Scheduled: <strong>{d.scheduled}</strong>
                              </p>
                              <p className="tooltip-stat">
                                <span className="stat-indicator skipped" /> Skipped: <strong>{d.skipped}</strong>
                              </p>
                              <p className="tooltip-rate">Adherence: <strong>{d.adherence}%</strong></p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Bar dataKey="taken" name="Taken" fill={COLOR_TAKEN} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="scheduled" name="Scheduled" fill="var(--bg-surface-tertiary)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Status Breakdown Donut Chart */}
            <div className="chart-card flex-1">
              <div className="chart-header">
                <h3>Dose Distribution</h3>
                <span className="chart-subtitle">Proportion of dose outcomes</span>
              </div>

              <div className="chart-container-box donut-container">
                {pieData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={280}>
                    <PieChart>
                      <Pie
                        data={pieData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="45%"
                        innerRadius={55}
                        outerRadius={80}
                        paddingAngle={4}
                      >
                        {pieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(val, name) => [`${val} dose(s)`, name]}
                        contentStyle={{
                          background: 'var(--bg-surface)',
                          borderColor: 'var(--border-subtle)',
                          borderRadius: '8px',
                          color: 'var(--text-main)',
                        }}
                      />
                      <Legend verticalAlign="bottom" height={36} iconType="circle" />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="donut-empty">No dose entries to display</div>
                )}
              </div>
            </div>
          </div>

          {/* Medicine Adherence Breakdown Table */}
          {medicineBreakdown.length > 0 && (
            <div className="medicine-adherence-card">
              <div className="chart-header">
                <h3>Medication Adherence Breakdown</h3>
                <span className="chart-subtitle">Individual adherence rates over the past 7 days</span>
              </div>

              <div className="med-adherence-list">
                {medicineBreakdown.map((med) => {
                  return (
                    <div key={med.id} className="med-adherence-row">
                      <div className="med-row-info">
                        <div className="med-row-icon">
                          <Pill size={16} />
                        </div>
                        <div>
                          <span className="med-row-name">{med.name}</span>
                          <span className="med-row-dosage">{med.dosage}</span>
                        </div>
                      </div>

                      <div className="med-row-bar-wrap">
                        <div className="med-bar-track">
                          <div
                            className="med-bar-fill"
                            style={{ width: `${Math.min(100, med.adherence)}%` }}
                          />
                        </div>
                        <span className="med-row-fraction">
                          {med.taken} of {med.total} taken
                        </span>
                      </div>

                      <div className="med-row-rate">
                        <strong>{med.adherence}%</strong>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Educational Note */}
          <div className="analytics-info-note">
            <Info size={16} className="info-icon" />
            <p>
              Adherence calculations reflect doses scheduled through your current medication plans.
              Future pending doses are excluded from the denominator to maintain accurate compliance metrics.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
