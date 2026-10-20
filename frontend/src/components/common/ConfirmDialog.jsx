import React, { useEffect } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import './ConfirmDialog.css';

export default function ConfirmDialog({
  isOpen,
  title = 'Confirm Action',
  message = 'Are you sure you want to proceed?',
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  isDestructive = false,
  onConfirm,
  onCancel,
}) {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onCancel?.();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  return (
    <div className="confirm-overlay" onClick={onCancel} role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title">
      <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
        <button className="confirm-close-btn" onClick={onCancel} aria-label="Close dialog">
          <X size={18} />
        </button>

        <div className="confirm-header">
          <div className={`confirm-icon-box ${isDestructive ? 'destructive' : ''}`}>
            <AlertTriangle size={22} />
          </div>
          <div className="confirm-titles">
            <h3 id="confirm-dialog-title">{title}</h3>
            <p>{message}</p>
          </div>
        </div>

        <div className="confirm-actions">
          <button type="button" className="btn btn-secondary" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`btn ${isDestructive ? 'btn-danger' : 'btn-primary'}`}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
