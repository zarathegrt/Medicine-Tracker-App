import React from 'react';
import './LoadingSkeleton.css';

export default function LoadingSkeleton({ variant = 'card', count = 1, className = '' }) {
  const items = Array.from({ length: count }, (_, i) => i);

  if (variant === 'stat') {
    return (
      <div className={`skeleton-stat-grid ${className}`}>
        {items.map((i) => (
          <div key={i} className="skeleton-card skeleton-stat-card">
            <div className="skeleton-line skeleton-title" />
            <div className="skeleton-line skeleton-large-num" />
            <div className="skeleton-line skeleton-sub" />
          </div>
        ))}
      </div>
    );
  }

  if (variant === 'list') {
    return (
      <div className={`skeleton-list-container ${className}`}>
        {items.map((i) => (
          <div key={i} className="skeleton-card skeleton-list-item">
            <div className="skeleton-circle" />
            <div className="skeleton-list-details">
              <div className="skeleton-line skeleton-title" style={{ width: '40%' }} />
              <div className="skeleton-line skeleton-sub" style={{ width: '65%' }} />
            </div>
            <div className="skeleton-btn-placeholder" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className={`skeleton-grid ${className}`}>
      {items.map((i) => (
        <div key={i} className="skeleton-card">
          <div className="skeleton-line skeleton-title" />
          <div className="skeleton-line skeleton-body" />
          <div className="skeleton-line skeleton-body" style={{ width: '80%' }} />
        </div>
      ))}
    </div>
  );
}
