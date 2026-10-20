import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  History,
  Search,
  Filter,
  Calendar,
  RotateCw,
  Plus,
  CheckCircle2,
  Clock,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  FileText,
  RotateCcw,
} from 'lucide-react';
import api from '../../services/api';
import { useToast } from '../common/ToastContext';
import StatusBadge from '../common/StatusBadge';
import LoadingSkeleton from '../common/LoadingSkeleton';
import EmptyState from '../common/EmptyState';
import CorrectDoseModal from '../common/CorrectDoseModal';
import './DoseHistory.css';

const PAGE_SIZE = 15;

export default function DoseHistory() {
  const toast = useToast();

  const [logs, setLogs] = useState([]);
  const [medicines, setMedicines] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [daysFilter, setDaysFilter] = useState(30);
  const [statusFilter, setStatusFilter] = useState('all');
  const [medicineFilter, setMedicineFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  // Quick ad-hoc log modal state
  const [isAdHocModalOpen, setIsAdHocModalOpen] = useState(false);
  const [selectedMedId, setSelectedMedId] = useState('');
  const [adHocData, setAdHocData] = useState({
    medicine_id: null,
    medicine_name: '',
    dosage: '',
    notes: '',
  });

  // Dose correction modal state
  const [correctingDose, setCorrectingDose] = useState(null);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const [logsData, medsData] = await Promise.all([
        api.getLogs({ days: daysFilter }),
        api.getMedicines(),
      ]);
      setLogs(logsData || []);
      setMedicines(medsData || []);
    } catch (err) {
      toast.error(err.message || 'Failed to load dose history');
    } finally {
      setLoading(false);
    }
  }, [daysFilter, toast]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  // Keyboard Escape listener for modal
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isAdHocModalOpen) {
        setIsAdHocModalOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isAdHocModalOpen]);

  const handleSelectPrescription = (medId) => {
    setSelectedMedId(medId);
    if (!medId) {
      setAdHocData((prev) => ({ ...prev, medicine_id: null }));
      return;
    }
    const found = medicines.find((m) => String(m.id) === String(medId));
    if (found) {
      setAdHocData({
        medicine_id: found.id,
        medicine_name: found.name,
        dosage: found.dosage,
        notes: adHocData.notes,
      });
    }
  };

  // Handle ad-hoc dose logging
  const handleAdHocSubmit = async (e) => {
    e.preventDefault();
    if (!adHocData.medicine_name.trim() || !adHocData.dosage.trim()) {
      toast.error('Medicine name and dosage are required');
      return;
    }

    try {
      await api.logDose({
        medicine_id: adHocData.medicine_id || null,
        medicine_name: adHocData.medicine_name.trim(),
        dosage: adHocData.dosage.trim(),
        status: 'taken',
        notes: adHocData.notes.trim() || 'Ad-hoc / PRN dose',
      });
      toast.success(`Dose for "${adHocData.medicine_name}" recorded!`);
      setIsAdHocModalOpen(false);
      setSelectedMedId('');
      setAdHocData({ medicine_id: null, medicine_name: '', dosage: '', notes: '' });
      await loadLogs();
    } catch (err) {
      toast.error(err.message || 'Failed to record dose');
    }
  };

  // Filtered & Paginated records
  const filteredLogs = useMemo(() => {
    let result = [...logs];

    // Status filter
    if (statusFilter !== 'all') {
      result = result.filter((l) => (l.status || '').toLowerCase() === statusFilter);
    }

    // Medicine filter
    if (medicineFilter !== 'all') {
      const medId = parseInt(medicineFilter, 10);
      result = result.filter((l) => l.medicine_id === medId);
    }

    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter(
        (l) =>
          (l.medicine_name && l.medicine_name.toLowerCase().includes(q)) ||
          (l.dosage && l.dosage.toLowerCase().includes(q)) ||
          (l.notes && l.notes.toLowerCase().includes(q)) ||
          (l.instructions && l.instructions.toLowerCase().includes(q))
      );
    }

    return result;
  }, [logs, statusFilter, medicineFilter, searchQuery]);

  const totalPages = Math.max(1, Math.ceil(filteredLogs.length / PAGE_SIZE));
  const currentLogs = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filteredLogs.slice(start, start + PAGE_SIZE);
  }, [filteredLogs, currentPage]);

  const handlePageChange = (page) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="history-page">
      {/* Header */}
      <div className="page-header-row">
        <div>
          <h1 className="page-main-title">Dose History</h1>
          <p className="page-main-subtitle">
            Comprehensive chronological log of all your scheduled and ad-hoc medication intakes
          </p>
        </div>

        <div className="header-actions-group">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setIsAdHocModalOpen(true)}
          >
            <Plus size={16} />
            <span>Log Extra Dose</span>
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-icon-only"
            onClick={loadLogs}
            title="Refresh logs"
          >
            <RotateCw size={15} />
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="history-filters-bar">
        <div className="search-input-wrapper">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search logs by medication or notes..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
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

        <div className="history-filter-selects">
          <div className="filter-select-wrap">
            <Calendar size={14} className="select-icon" />
            <select
              value={daysFilter}
              onChange={(e) => {
                setDaysFilter(Number(e.target.value));
                setCurrentPage(1);
              }}
              aria-label="Filter by date range"
            >
              <option value={1}>Today Only</option>
              <option value={7}>Last 7 Days</option>
              <option value={30}>Last 30 Days</option>
              <option value={90}>Last 90 Days</option>
            </select>
          </div>

          <div className="filter-select-wrap">
            <Filter size={14} className="select-icon" />
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setCurrentPage(1);
              }}
              aria-label="Filter by dose status"
            >
              <option value="all">All Statuses</option>
              <option value="taken">Taken</option>
              <option value="pending">Pending / Overdue</option>
              <option value="skipped">Skipped</option>
            </select>
          </div>

          <div className="filter-select-wrap">
            <select
              value={medicineFilter}
              onChange={(e) => {
                setMedicineFilter(e.target.value);
                setCurrentPage(1);
              }}
              aria-label="Filter by medicine"
            >
              <option value="all">All Medicines</option>
              {medicines.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Logs Table / List */}
      {loading ? (
        <LoadingSkeleton variant="list" count={6} />
      ) : filteredLogs.length === 0 ? (
        <EmptyState
          icon={History}
          title={searchQuery || statusFilter !== 'all' ? 'No matching logs found' : 'No dose history available'}
          description={
            searchQuery || statusFilter !== 'all'
              ? 'Try widening your date range or removing active filters to see older entries.'
              : 'Dose intake events will appear here automatically as scheduled times pass and doses are logged.'
          }
          actionLabel="Refresh Records"
          onAction={loadLogs}
        />
      ) : (
        <div className="history-table-container">
          <table className="history-table">
            <thead>
              <tr>
                <th>Scheduled Date & Time</th>
                <th>Medicine & Dosage</th>
                <th>Status</th>
                <th>Taken Time</th>
                <th>Notes & Context</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {currentLogs.map((log) => {
                const schedDate = log.scheduled_time ? log.scheduled_time.split(' ')[0] : 'N/A';
                const schedTime = log.scheduled_time ? log.scheduled_time.split(' ')[1] : '';
                const takenTime = log.taken_time ? log.taken_time.split(' ')[1] : null;

                return (
                  <tr key={log.id} className="history-row">
                    <td>
                      <div className="table-datetime-cell">
                        <span className="table-date-str">{schedDate}</span>
                        <span className="table-time-str">
                          <Clock size={12} />
                          {schedTime}
                        </span>
                      </div>
                    </td>

                    <td>
                      <div className="table-med-cell">
                        <span className="table-med-name">{log.medicine_name}</span>
                        <span className="table-med-dosage">{log.dosage}</span>
                        {log.instructions && (
                          <span className="table-med-inst">
                            <Sparkles size={11} /> {log.instructions}
                          </span>
                        )}
                      </div>
                    </td>

                    <td>
                      <StatusBadge status={log.status} isOverdue={log.is_overdue} />
                    </td>

                    <td>
                      {takenTime ? (
                        <span className="taken-time-pill">
                          <CheckCircle2 size={12} /> {takenTime}
                        </span>
                      ) : (
                        <span className="not-taken-pill">—</span>
                      )}
                    </td>

                    <td>
                      {log.notes ? (
                        <span className="table-notes-text">
                          <FileText size={12} />
                          {log.notes}
                        </span>
                      ) : (
                        <span className="no-notes-text">—</span>
                      )}
                    </td>

                    <td>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm history-correct-btn"
                        onClick={() => setCorrectingDose(log)}
                        title="Correct this record"
                        aria-label={`Correct dose entry for ${log.medicine_name}`}
                      >
                        <RotateCcw size={12} />
                        <span>Correct</span>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="history-pagination-row">
              <span className="pagination-count-label">
                Showing {(currentPage - 1) * PAGE_SIZE + 1} to{' '}
                {Math.min(currentPage * PAGE_SIZE, filteredLogs.length)} of {filteredLogs.length} logs
              </span>

              <div className="pagination-btns-wrap">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={currentPage === 1}
                  onClick={() => handlePageChange(currentPage - 1)}
                  aria-label="Previous page"
                >
                  <ChevronLeft size={16} />
                  <span>Previous</span>
                </button>

                <span className="page-indicator">
                  Page {currentPage} of {totalPages}
                </span>

                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={currentPage === totalPages}
                  onClick={() => handlePageChange(currentPage + 1)}
                  aria-label="Next page"
                >
                  <span>Next</span>
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Ad-Hoc Dose Logging Modal */}
      {isAdHocModalOpen && (
        <div className="confirm-overlay" onClick={() => setIsAdHocModalOpen(false)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="confirm-header">
              <div className="confirm-icon-box">
                <Plus size={22} />
              </div>
              <div className="confirm-titles">
                <h3>Log Extra / PRN Dose</h3>
                <p>Record a non-scheduled medication intake right now.</p>
              </div>
            </div>

            <form onSubmit={handleAdHocSubmit} className="ad-hoc-form">
              <div className="form-group">
                <label htmlFor="adhoc-prescription">Select From My Prescriptions</label>
                <select
                  id="adhoc-prescription"
                  value={selectedMedId}
                  onChange={(e) => handleSelectPrescription(e.target.value)}
                >
                  <option value="">-- Choose from your medicines (or enter below) --</option>
                  {medicines.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({m.dosage})
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="adhoc-name">Medicine Name *</label>
                <input
                  id="adhoc-name"
                  type="text"
                  placeholder="e.g. Ibuprofen, Antacid"
                  value={adHocData.medicine_name}
                  onChange={(e) => setAdHocData({ ...adHocData, medicine_name: e.target.value })}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="adhoc-dosage">Dosage *</label>
                <input
                  id="adhoc-dosage"
                  type="text"
                  placeholder="e.g. 200mg, 1 tablet"
                  value={adHocData.dosage}
                  onChange={(e) => setAdHocData({ ...adHocData, dosage: e.target.value })}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="adhoc-notes">Notes / Reason</label>
                <input
                  id="adhoc-notes"
                  type="text"
                  placeholder="e.g. Mild headache after lunch"
                  value={adHocData.notes}
                  onChange={(e) => setAdHocData({ ...adHocData, notes: e.target.value })}
                />
              </div>

              <div className="confirm-actions" style={{ marginTop: '16px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsAdHocModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Intake
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Safe Dose Correction Modal */}
      <CorrectDoseModal
        isOpen={Boolean(correctingDose)}
        dose={correctingDose}
        onClose={() => setCorrectingDose(null)}
        onSuccess={loadLogs}
      />
    </div>
  );
}
