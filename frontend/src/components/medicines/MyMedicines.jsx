import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Pill,
  Search,
  Plus,
  Clock,
  Calendar,
  Edit2,
  Trash2,
  Sparkles,
  Filter,
  ArrowUpDown,
  RotateCw,
} from 'lucide-react';
import api from '../../services/api';
import { useToast } from '../common/ToastContext';
import AddMedicineModal from './AddMedicineModal';
import ConfirmDialog from '../common/ConfirmDialog';
import LoadingSkeleton from '../common/LoadingSkeleton';
import EmptyState from '../common/EmptyState';
import StatusBadge from '../common/StatusBadge';
import './MyMedicines.css';

export default function MyMedicines() {
  const toast = useToast();

  const [medicines, setMedicines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [frequencyFilter, setFrequencyFilter] = useState('all');
  const [sortBy, setSortBy] = useState('name_asc');

  // Modal & Dialog state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingMedicine, setEditingMedicine] = useState(null);
  const [confirmConfig, setConfirmConfig] = useState({ isOpen: false });

  const loadMedicines = useCallback(async () => {
    try {
      const data = await api.getMedicines();
      setMedicines(data || []);
    } catch (err) {
      toast.error(err.message || 'Failed to load medicines');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadMedicines();
  }, [loadMedicines]);

  // Deactivate handler
  const handleDeactivate = (med) => {
    setConfirmConfig({
      isOpen: true,
      title: 'Deactivate Medicine?',
      message: `Are you sure you want to deactivate "${med.name}"? It will no longer generate scheduled daily doses, but past history and logs will remain preserved.`,
      confirmLabel: 'Deactivate',
      isDestructive: true,
      onConfirm: async () => {
        try {
          await api.deleteMedicine(med.id);
          toast.success(`"${med.name}" has been deactivated`);
          setConfirmConfig({ isOpen: false });
          await loadMedicines();
        } catch (err) {
          toast.error(err.message || 'Failed to deactivate medicine');
        }
      },
      onCancel: () => setConfirmConfig({ isOpen: false }),
    });
  };

  const handleEdit = (med) => {
    setEditingMedicine(med);
    setIsAddModalOpen(true);
  };

  const handleModalClose = () => {
    setIsAddModalOpen(false);
    setEditingMedicine(null);
  };

  // Filter and sort logic
  const filteredMedicines = useMemo(() => {
    let list = [...medicines];

    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter(
        (m) =>
          m.name.toLowerCase().includes(q) ||
          m.dosage.toLowerCase().includes(q) ||
          (m.instructions && m.instructions.toLowerCase().includes(q))
      );
    }

    // Frequency filter
    if (frequencyFilter !== 'all') {
      list = list.filter((m) => (m.frequency || 'daily').toLowerCase() === frequencyFilter);
    }

    // Sort
    list.sort((a, b) => {
      if (sortBy === 'name_asc') {
        return a.name.localeCompare(b.name);
      } else if (sortBy === 'name_desc') {
        return b.name.localeCompare(a.name);
      } else if (sortBy === 'date_desc') {
        return (b.start_date || '').localeCompare(a.start_date || '');
      } else if (sortBy === 'date_asc') {
        return (a.start_date || '').localeCompare(b.start_date || '');
      }
      return 0;
    });

    return list;
  }, [medicines, searchQuery, frequencyFilter, sortBy]);

  return (
    <div className="medicines-page">
      {/* Top Header */}
      <div className="page-header-row">
        <div>
          <h1 className="page-main-title">My Medicines</h1>
          <p className="page-main-subtitle">
            Manage your prescriptions, dosages, time schedules, and regimen instructions
          </p>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          onClick={() => {
            setEditingMedicine(null);
            setIsAddModalOpen(true);
          }}
        >
          <Plus size={17} />
          <span>Add New Medicine</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="medicines-filter-bar">
        <div className="search-input-wrapper">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search by medicine name, dosage, or instruction..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button
              type="button"
              className="search-clear-btn"
              onClick={() => setSearchQuery('')}
            >
              Clear
            </button>
          )}
        </div>

        <div className="filter-controls-group">
          <div className="filter-select-wrap">
            <Filter size={15} className="select-icon" />
            <select
              value={frequencyFilter}
              onChange={(e) => setFrequencyFilter(e.target.value)}
              aria-label="Filter by frequency"
            >
              <option value="all">All Frequencies</option>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="as_needed">As Needed (PRN)</option>
            </select>
          </div>

          <div className="filter-select-wrap">
            <ArrowUpDown size={15} className="select-icon" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              aria-label="Sort medicines"
            >
              <option value="name_asc">Name (A to Z)</option>
              <option value="name_desc">Name (Z to A)</option>
              <option value="date_desc">Start Date (Newest)</option>
              <option value="date_asc">Start Date (Oldest)</option>
            </select>
          </div>

          <button
            type="button"
            className="btn btn-secondary btn-icon-only"
            onClick={loadMedicines}
            title="Refresh list"
          >
            <RotateCw size={15} />
          </button>
        </div>
      </div>

      {/* Main Content */}
      {loading ? (
        <LoadingSkeleton variant="grid" count={4} />
      ) : filteredMedicines.length === 0 ? (
        <EmptyState
          icon={Pill}
          title={searchQuery ? 'No matching medicines found' : 'No medicines added yet'}
          description={
            searchQuery
              ? `No results for "${searchQuery}". Try adjusting your filters or search keywords.`
              : 'Add your active medications to automatically schedule your reminders and start tracking.'
          }
          actionLabel={searchQuery ? 'Clear Search' : 'Add Medicine'}
          onAction={searchQuery ? () => setSearchQuery('') : () => setIsAddModalOpen(true)}
        />
      ) : (
        <div className="medicines-cards-grid">
          {filteredMedicines.map((med) => {
            const scheduleSlots = Array.isArray(med.schedule) ? med.schedule : [];

            return (
              <div key={med.id} className="medicine-card">
                <div className="medicine-card-header">
                  <div className="med-title-block">
                    <h3 className="med-name">{med.name}</h3>
                    <div className="med-badges-row">
                      <span className="med-dosage-tag">{med.dosage}</span>
                      <span className="med-freq-tag">
                        {med.frequency === 'as_needed'
                          ? 'PRN (As Needed)'
                          : med.frequency === 'weekly'
                          ? 'Weekly'
                          : `${med.times_per_day}x Daily`}
                      </span>
                    </div>
                  </div>

                  <div className="med-card-actions">
                    <button
                      type="button"
                      className="card-action-btn edit-btn"
                      onClick={() => handleEdit(med)}
                      title="Edit medicine"
                    >
                      <Edit2 size={15} />
                    </button>
                    <button
                      type="button"
                      className="card-action-btn delete-btn"
                      onClick={() => handleDeactivate(med)}
                      title="Deactivate medicine"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>

                {/* Schedule timeslots */}
                {med.frequency !== 'as_needed' && scheduleSlots.length > 0 && (
                  <div className="med-schedule-block">
                    <span className="block-label">
                      <Clock size={13} />
                      Daily Schedule
                    </span>
                    <div className="schedule-pills-wrap">
                      {scheduleSlots.map((slot, i) => (
                        <span key={i} className="schedule-time-tag">
                          {slot}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Instructions */}
                {med.instructions ? (
                  <div className="med-instructions-block">
                    <Sparkles size={13} className="instruction-icon" />
                    <span>{med.instructions}</span>
                  </div>
                ) : (
                  <div className="med-instructions-block no-instructions">
                    <span>No special instructions</span>
                  </div>
                )}

                {/* Dates footer */}
                <div className="med-card-footer">
                  <span className="med-date-span">
                    <Calendar size={13} />
                    Started: {med.start_date || 'N/A'}
                  </span>
                  {med.end_date && (
                    <span className="med-date-span end-date">
                      Ends: {med.end_date}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add / Edit Modal */}
      <AddMedicineModal
        isOpen={isAddModalOpen}
        onClose={handleModalClose}
        initialMedicine={editingMedicine}
        onSuccess={() => {
          loadMedicines();
          window.dispatchEvent(new CustomEvent('curavit:medicine-added'));
        }}
      />

      {/* Confirm Deactivate Dialog */}
      <ConfirmDialog {...confirmConfig} />
    </div>
  );
}
