import React, { useState, useEffect } from 'react';
import { X, Plus, Clock, Calendar, AlertCircle } from 'lucide-react';
import { useToast } from '../common/ToastContext';
import api from '../../services/api';
import './AddMedicineModal.css';

const DEFAULT_TIME_PRESETS = ['08:00', '13:00', '18:00', '21:00', '09:00', '22:00'];

export default function AddMedicineModal({ isOpen, onClose, onSuccess, initialMedicine = null }) {
  const toast = useToast();
  const isEditing = Boolean(initialMedicine);

  const [formData, setFormData] = useState({
    name: '',
    dosage: '',
    times_per_day: 1,
    schedule: ['08:00'],
    start_date: new Date().toISOString().split('T')[0],
    end_date: '',
    frequency: 'daily',
    instructions: '',
  });

  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (initialMedicine) {
      setFormData({
        name: initialMedicine.name || '',
        dosage: initialMedicine.dosage || '',
        times_per_day: initialMedicine.times_per_day || 1,
        schedule: Array.isArray(initialMedicine.schedule) && initialMedicine.schedule.length > 0
          ? initialMedicine.schedule
          : ['08:00'],
        start_date: initialMedicine.start_date || new Date().toISOString().split('T')[0],
        end_date: initialMedicine.end_date || '',
        frequency: initialMedicine.frequency || 'daily',
        instructions: initialMedicine.instructions || '',
      });
      setErrors({});
    } else {
      setFormData({
        name: '',
        dosage: '',
        times_per_day: 1,
        schedule: ['08:00'],
        start_date: new Date().toISOString().split('T')[0],
        end_date: '',
        frequency: 'daily',
        instructions: '',
      });
      setErrors({});
    }
  }, [initialMedicine, isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleTimesPerDayChange = (newCount) => {
    const count = Math.max(1, Math.min(6, parseInt(newCount, 10) || 1));
    let newSchedule = [...formData.schedule];

    if (newSchedule.length < count) {
      while (newSchedule.length < count) {
        const nextPreset = DEFAULT_TIME_PRESETS[newSchedule.length] || '12:00';
        newSchedule.push(nextPreset);
      }
    } else if (newSchedule.length > count) {
      newSchedule = newSchedule.slice(0, count);
    }

    setFormData((prev) => ({
      ...prev,
      times_per_day: count,
      schedule: newSchedule,
    }));
  };

  const handleTimeSlotChange = (index, value) => {
    const updated = [...formData.schedule];
    updated[index] = value;
    setFormData((prev) => ({ ...prev, schedule: updated }));
  };

  const validate = () => {
    const errs = {};
    if (!formData.name.trim()) errs.name = 'Medicine name is required';
    if (!formData.dosage.trim()) errs.dosage = 'Dosage is required (e.g., 500mg, 1 tablet)';
    if (!formData.start_date) errs.start_date = 'Start date is required';

    if (formData.end_date && formData.start_date) {
      if (formData.end_date < formData.start_date) {
        errs.end_date = 'End date cannot be earlier than start date';
      }
    }

    if (formData.frequency !== 'as_needed') {
      if (formData.schedule.length !== formData.times_per_day) {
        errs.schedule = `Must have exactly ${formData.times_per_day} scheduled time(s)`;
      }
      for (let i = 0; i < formData.schedule.length; i++) {
        if (!formData.schedule[i]) {
          errs.schedule = 'All time slots must be filled';
          break;
        }
      }
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const payload = {
        name: formData.name.trim(),
        dosage: formData.dosage.trim(),
        times_per_day: formData.frequency === 'as_needed' ? 1 : formData.times_per_day,
        schedule: formData.frequency === 'as_needed' ? ['12:00'] : formData.schedule,
        start_date: formData.start_date,
        end_date: formData.end_date || '',
        frequency: formData.frequency,
        instructions: formData.instructions.trim(),
      };

      if (isEditing) {
        await api.updateMedicine(initialMedicine.id, payload);
        toast.success(`"${payload.name}" updated successfully`);
      } else {
        await api.addMedicine(payload);
        toast.success(`"${payload.name}" added to your medicines`);
      }

      onSuccess();
      onClose();
    } catch (err) {
      toast.error(err.message || 'Failed to save medicine');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="med-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="med-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="med-modal-header">
          <div>
            <h2>{isEditing ? 'Edit Medicine' : 'Add New Medicine'}</h2>
            <p className="med-modal-subtitle">
              {isEditing ? 'Update your medication regimen and timings' : 'Set up dosage, schedule, and personalized instructions'}
            </p>
          </div>
          <button type="button" className="med-modal-close" onClick={onClose} aria-label="Close">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="med-modal-form">
          <div className="form-row">
            <div className="form-group flex-2">
              <label htmlFor="med-name">Medicine Name *</label>
              <input
                id="med-name"
                type="text"
                placeholder="e.g. Amoxicillin, Lisinopril"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className={errors.name ? 'has-error' : ''}
              />
              {errors.name && <span className="field-error"><AlertCircle size={12} /> {errors.name}</span>}
            </div>

            <div className="form-group flex-1">
              <label htmlFor="med-dosage">Dosage *</label>
              <input
                id="med-dosage"
                type="text"
                placeholder="e.g. 500mg, 1 tab"
                value={formData.dosage}
                onChange={(e) => setFormData({ ...formData, dosage: e.target.value })}
                className={errors.dosage ? 'has-error' : ''}
              />
              {errors.dosage && <span className="field-error"><AlertCircle size={12} /> {errors.dosage}</span>}
            </div>
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label htmlFor="med-freq">Frequency</label>
              <select
                id="med-freq"
                value={formData.frequency}
                onChange={(e) => setFormData({ ...formData, frequency: e.target.value })}
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="as_needed">As Needed (PRN)</option>
              </select>
            </div>

            {formData.frequency !== 'as_needed' && (
              <div className="form-group flex-1">
                <label htmlFor="med-times">Times per day</label>
                <select
                  id="med-times"
                  value={formData.times_per_day}
                  onChange={(e) => handleTimesPerDayChange(e.target.value)}
                >
                  <option value={1}>1 time daily</option>
                  <option value={2}>2 times daily</option>
                  <option value={3}>3 times daily</option>
                  <option value={4}>4 times daily</option>
                  <option value={5}>5 times daily</option>
                  <option value={6}>6 times daily</option>
                </select>
              </div>
            )}
          </div>

          {formData.frequency !== 'as_needed' && (
            <div className="form-group">
              <label className="label-with-hint">
                <span>Schedule Times *</span>
                <span className="hint-text">Configure exact dose timings</span>
              </label>

              <div className="time-slots-grid">
                {formData.schedule.map((slot, index) => (
                  <div key={index} className="time-slot-pill">
                    <Clock size={14} className="time-icon" />
                    <input
                      type="time"
                      value={slot}
                      onChange={(e) => handleTimeSlotChange(index, e.target.value)}
                      required
                    />
                    <span className="slot-index-tag">#{index + 1}</span>
                  </div>
                ))}
              </div>
              {errors.schedule && <span className="field-error"><AlertCircle size={12} /> {errors.schedule}</span>}
            </div>
          )}

          <div className="form-row">
            <div className="form-group flex-1">
              <label htmlFor="med-start">Start Date *</label>
              <input
                id="med-start"
                type="date"
                value={formData.start_date}
                onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                className={errors.start_date ? 'has-error' : ''}
              />
              {errors.start_date && <span className="field-error"><AlertCircle size={12} /> {errors.start_date}</span>}
            </div>

            <div className="form-group flex-1">
              <label htmlFor="med-end">
                <span>End Date</span> <span className="optional-tag">(Optional)</span>
              </label>
              <input
                id="med-end"
                type="date"
                value={formData.end_date}
                onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                className={errors.end_date ? 'has-error' : ''}
              />
              {errors.end_date && <span className="field-error"><AlertCircle size={12} /> {errors.end_date}</span>}
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="med-instructions">
              <span>Special Instructions</span> <span className="optional-tag">(Optional)</span>
            </label>
            <input
              id="med-instructions"
              type="text"
              placeholder="e.g. Take with breakfast; do not take on empty stomach"
              value={formData.instructions}
              onChange={(e) => setFormData({ ...formData, instructions: e.target.value })}
            />
          </div>

          <div className="med-modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Saving...' : isEditing ? 'Save Changes' : 'Add Medication'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
