import React, { useState, useEffect, useRef } from 'react';
import { RotateCcw, CheckCircle2, SkipForward, Clock, AlertTriangle, X } from 'lucide-react';
import api from '../../services/api';
import { useToast } from './ToastContext';
import './CorrectDoseModal.css';

export default function CorrectDoseModal({ isOpen, onClose, dose, onSuccess }) {
  const toast = useToast();
  const modalRef = useRef(null);

  const [newStatus, setNewStatus] = useState('pending');
  const [reason, setReason] = useState('Marked by accident');
  const [customReason, setCustomReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (dose) {
      // Suggest opposite or pending
      if (dose.status === 'taken') {
        setNewStatus('pending');
      } else if (dose.status === 'skipped') {
        setNewStatus('pending');
      } else {
        setNewStatus('taken');
      }
      setReason('Marked by accident');
      setCustomReason('');
    }
  }, [dose, isOpen]);

  // Keyboard accessibility: Escape to close and focus trap
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);

    // Focus the first button on open
    const timer = setTimeout(() => {
      if (modalRef.current) {
        const focusable = modalRef.current.querySelector('button, select, input');
        if (focusable) focusable.focus();
      }
    }, 50);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      clearTimeout(timer);
    };
  }, [isOpen, onClose]);

  if (!isOpen || !dose) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;

    const finalReason = reason === 'Other' ? customReason.trim() : reason;
    setIsSubmitting(true);

    try {
      await api.correctDose(dose.id, {
        new_status: newStatus,
        reason: finalReason || 'Dose corrected by user',
      });
      toast.success(`Dose for ${dose.medicine_name} corrected to ${newStatus}`);
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(err.message || 'Failed to correct dose status');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="correct-modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="correct-dose-title">
      <div className="correct-modal-card" ref={modalRef} onClick={(e) => e.stopPropagation()}>
        <div className="correct-modal-header">
          <div className="header-icon-pill">
            <RotateCcw size={18} />
          </div>
          <div>
            <h3 id="correct-dose-title">Correct Dose Record</h3>
            <p className="correct-modal-sub">
              Adjust previously recorded intake for <strong>{dose.medicine_name}</strong> ({dose.dosage})
            </p>
          </div>
          <button
            type="button"
            className="correct-modal-close"
            onClick={onClose}
            aria-label="Close correction modal"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="correct-modal-form">
          <div className="current-status-banner">
            <span className="banner-label">Current Record:</span>
            <span className={`status-badge-inline status-${dose.status}`}>
              {dose.status.toUpperCase()}
            </span>
            <span className="banner-sched-time">
              Scheduled: {dose.scheduled_time || 'N/A'}
            </span>
          </div>

          <div className="form-group">
            <label htmlFor="target-status">Select New Status *</label>
            <select
              id="target-status"
              value={newStatus}
              onChange={(e) => setNewStatus(e.target.value)}
              required
            >
              <option value="pending">Pending (Undo / Revert to Un-taken)</option>
              <option value="taken">Taken (Completed Dose)</option>
              <option value="skipped">Skipped (Intentionally Skipped)</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="correction-reason">Reason for Correction</label>
            <select
              id="correction-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            >
              <option value="Marked by accident">Marked by accident</option>
              <option value="Taken at different time">Taken at different time</option>
              <option value="Dose was skipped, not taken">Dose was skipped, not taken</option>
              <option value="Dose was taken, not skipped">Dose was taken, not skipped</option>
              <option value="Other">Other reason...</option>
            </select>
          </div>

          {reason === 'Other' && (
            <div className="form-group">
              <label htmlFor="custom-reason">Explain Reason *</label>
              <input
                id="custom-reason"
                type="text"
                placeholder="e.g. Took half dose per doctor instruction"
                value={customReason}
                onChange={(e) => setCustomReason(e.target.value)}
                required
                maxLength={200}
              />
            </div>
          )}

          <div className="clinical-preservation-notice">
            <AlertTriangle size={15} className="notice-icon" />
            <span>
              This correction will be permanently logged in your dose audit history with a timestamp. Prescribed regimens are never automatically adjusted.
            </span>
          </div>

          <div className="correct-modal-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Saving Correction...' : 'Confirm Correction'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
