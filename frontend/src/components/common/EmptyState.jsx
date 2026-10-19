import React from 'react';
import { Inbox } from 'lucide-react';
import './EmptyState.css';

export default function EmptyState({
  icon: Icon = Inbox,
  title = 'No items found',
  description = 'There is nothing to display here at the moment.',
  actionLabel,
  onAction,
  className = '',
}) {
  return (
    <div className={`empty-state-card ${className}`}>
      <div className="empty-state-icon-wrapper">
        <Icon size={28} />
      </div>
      <h3 className="empty-state-title">{title}</h3>
      <p className="empty-state-desc">{description}</p>
      {actionLabel && onAction && (
        <button type="button" className="btn btn-primary empty-state-btn" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  );
}
