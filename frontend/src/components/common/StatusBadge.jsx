import React from 'react';
import { CheckCircle2, Clock, AlertCircle, SkipForward, HelpCircle } from 'lucide-react';
import './StatusBadge.css';

/**
 * Standardized StatusBadge with icons and high contrast labels
 */
export default function StatusBadge({ status = 'pending', isOverdue = false, size = 'md' }) {
  const normStatus = (status || 'pending').toLowerCase();

  let config = {
    label: 'Pending',
    className: 'badge-pending',
    Icon: Clock,
  };

  if (normStatus === 'taken') {
    config = {
      label: 'Taken',
      className: 'badge-taken',
      Icon: CheckCircle2,
    };
  } else if (normStatus === 'skipped') {
    config = {
      label: 'Skipped',
      className: 'badge-skipped',
      Icon: SkipForward,
    };
  } else if (normStatus === 'missed' || (normStatus === 'pending' && isOverdue)) {
    config = {
      label: 'Overdue',
      className: 'badge-missed',
      Icon: AlertCircle,
    };
  } else if (normStatus === 'upcoming') {
    config = {
      label: 'Upcoming',
      className: 'badge-upcoming',
      Icon: Clock,
    };
  } else if (normStatus === 'active') {
    config = {
      label: 'Active',
      className: 'badge-active-med',
      Icon: CheckCircle2,
    };
  } else if (normStatus === 'inactive') {
    config = {
      label: 'Inactive',
      className: 'badge-inactive-med',
      Icon: HelpCircle,
    };
  }

  const { label, className, Icon } = config;

  return (
    <span className={`status-badge ${className} badge-size-${size}`}>
      <Icon className="status-badge-icon" size={size === 'sm' ? 12 : 14} />
      <span>{label}</span>
    </span>
  );
}
