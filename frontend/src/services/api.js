/**
 * Curavit Medicine Tracker - API Client Service
 * Centralizes all HTTP communication with the Flask backend.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL !== undefined 
  ? import.meta.env.VITE_API_BASE_URL 
  : 'http://localhost:5000';

async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  const config = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  try {
    const response = await fetch(url, config);
    const data = await response.json().catch(() => null);

    if (!response.ok) {
      const errorMessage = data?.message || data?.error || `Request failed with status ${response.status}`;
      throw new Error(errorMessage);
    }

    return data;
  } catch (error) {
    console.error(`API Error on ${options.method || 'GET'} ${endpoint}:`, error.message);
    throw error;
  }
}

export const api = {
  // Medicines
  getMedicines: () => request('/api/medicines'),
  addMedicine: (medicine) => request('/api/medicines', {
    method: 'POST',
    body: JSON.stringify(medicine),
  }),
  updateMedicine: (id, medicine) => request(`/api/medicines/${id}`, {
    method: 'PUT',
    body: JSON.stringify(medicine),
  }),
  deleteMedicine: (id) => request(`/api/medicines/${id}`, {
    method: 'DELETE',
  }),

  // Schedules & Doses
  getTodaySchedule: () => request('/api/today-schedule'),
  getStatistics: () => request('/api/statistics'),
  getAnalytics: () => request('/api/analytics'),

  // Logs & History
  getLogs: (params = {}) => {
    const query = new URLSearchParams();
    if (params.days !== undefined) query.set('days', params.days);
    if (params.status) query.set('status', params.status);
    if (params.medicine_id) query.set('medicine_id', params.medicine_id);
    const queryString = query.toString();
    return request(`/api/logs${queryString ? `?${queryString}` : ''}`);
  },
  logDose: (data) => request('/api/logs', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  snoozeDose: (logId, snoozeMinutes = 10) => request('/api/logs', {
    method: 'POST',
    body: JSON.stringify({
      log_id: logId,
      action: 'snooze',
      snooze_minutes: snoozeMinutes,
    }),
  }),

  // Settings & System
  getSettings: () => request('/api/settings'),
  updateSettings: (settings) => request('/api/settings', {
    method: 'POST',
    body: JSON.stringify(settings),
  }),
  getExportData: () => request('/api/export'),
  checkHealth: () => request('/api/health'),
};

export default api;
