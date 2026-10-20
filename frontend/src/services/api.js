/**
 * Curavit Medicine Tracker - API Client Service
 * Comprehensive HTTP client supporting secure bearer token authentication,
 * patient/caregiver context resolution, granular permissions, scheduling,
 * dose tracking, audit corrections, and care team management.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL !== undefined 
  ? import.meta.env.VITE_API_BASE_URL 
  : 'http://localhost:5000';

const TOKEN_KEY = 'curavit_auth_token';

export const tokenStorage = {
  get: () => {
    try {
      return sessionStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (token) => {
    try {
      if (token) {
        sessionStorage.setItem(TOKEN_KEY, token);
      } else {
        sessionStorage.removeItem(TOKEN_KEY);
      }
    } catch {
      // Ignored
    }
  },
  clear: () => {
    try {
      sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      // Ignored
    }
  }
};

async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  const token = tokenStorage.get();
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const config = {
    ...options,
    headers,
  };

  try {
    const response = await fetch(url, config);
    const data = await response.json().catch(() => null);

    if (!response.ok) {
      if (response.status === 401 && !endpoint.includes('/api/auth/login')) {
        // Broadcast auth error so app can handle session invalidation
        window.dispatchEvent(new CustomEvent('curavit:unauthorized'));
      }
      const errorMessage = data?.message || data?.error || `Request failed with status ${response.status}`;
      const error = new Error(errorMessage);
      error.status = response.status;
      error.code = data?.code;
      throw error;
    }

    return data;
  } catch (error) {
    if (!error.status) {
      console.error(`API Network Error on ${options.method || 'GET'} ${endpoint}:`, error.message);
    }
    throw error;
  }
}

export const api = {
  // ---------------------------------------------------------------------------
  // Authentication & Identity
  // ---------------------------------------------------------------------------
  getSetupStatus: () => request('/api/auth/setup-status'),
  register: (payload) => request('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  login: (payload) => request('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  logout: () => request('/api/auth/logout', {
    method: 'POST',
  }),
  getMe: () => request('/api/auth/me'),
  claimLegacy: () => request('/api/auth/claim-legacy', {
    method: 'POST',
  }),

  // ---------------------------------------------------------------------------
  // Patient Care Team Management (Patient Perspective)
  // ---------------------------------------------------------------------------
  getCaregiverTeam: () => request('/api/caregiver-team'),
  inviteCaregiver: (payload) => request('/api/caregiver-team/invite', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  cancelInvitation: (invitationId) => request(`/api/caregiver-team/invitations/${invitationId}`, {
    method: 'DELETE',
  }),
  revokeCaregiver: (relationshipId) => request(`/api/caregiver-team/caregivers/${relationshipId}`, {
    method: 'DELETE',
  }),
  updateCaregiverPermissions: (relationshipId, permissions) => request(`/api/caregiver-team/caregivers/${relationshipId}/permissions`, {
    method: 'PUT',
    body: JSON.stringify({ permissions }),
  }),

  // ---------------------------------------------------------------------------
  // Caregiver Portal & Acceptance (Caregiver Perspective)
  // ---------------------------------------------------------------------------
  verifyInvitation: (token) => request(`/api/caregiver-team/invitations/verify?token=${encodeURIComponent(token)}`),
  acceptInvitation: (inviteToken) => request('/api/caregiver-team/accept-invite', {
    method: 'POST',
    body: JSON.stringify({ invite_token: inviteToken }),
  }),
  getMyPatients: () => request('/api/caregiver/my-patients'),
  getPatientSummary: (patientId) => request(`/api/caregiver/patient/${patientId}/summary`),
  getPatientActivity: (patientId) => request(`/api/caregiver/patient/${patientId}/activity`),

  // ---------------------------------------------------------------------------
  // Medicines & Prescriptions (Scoped with optional patientId)
  // ---------------------------------------------------------------------------
  getMedicines: (patientId = null) => {
    const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : '';
    return request(`/api/medicines${query}`);
  },
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

  // ---------------------------------------------------------------------------
  // Schedules, Doses & Analytics (Scoped with optional patientId)
  // ---------------------------------------------------------------------------
  getTodaySchedule: (patientId = null) => {
    const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : '';
    return request(`/api/today-schedule${query}`);
  },
  getStatistics: (patientId = null) => {
    const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : '';
    return request(`/api/statistics${query}`);
  },
  getAnalytics: (patientId = null) => {
    const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : '';
    return request(`/api/analytics${query}`);
  },

  // ---------------------------------------------------------------------------
  // Logs & Dose History
  // ---------------------------------------------------------------------------
  getLogs: (params = {}, patientId = null) => {
    const query = new URLSearchParams();
    if (params.days !== undefined) query.set('days', params.days);
    if (params.status) query.set('status', params.status);
    if (params.medicine_id) query.set('medicine_id', params.medicine_id);
    if (patientId) query.set('patient_id', patientId);
    const queryString = query.toString();
    return request(`/api/logs${queryString ? `?${queryString}` : ''}`);
  },
  logDose: (data, patientId = null) => {
    const payload = patientId ? { ...data, patient_id: patientId } : data;
    const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : '';
    return request(`/api/logs${query}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  snoozeDose: (logId, snoozeMinutes = 10, patientId = null) => {
    const payload = {
      log_id: logId,
      action: 'snooze',
      snooze_minutes: snoozeMinutes,
      ...(patientId ? { patient_id: patientId } : {})
    };
    const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : '';
    return request(`/api/logs${query}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  correctDose: (logId, payload, patientId = null) => {
    const body = patientId ? { ...payload, patient_id: patientId } : payload;
    const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : '';
    return request(`/api/logs/${logId}/correct${query}`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // ---------------------------------------------------------------------------
  // Settings & System Backup
  // ---------------------------------------------------------------------------
  getSettings: () => request('/api/settings'),
  updateSettings: (settings) => request('/api/settings', {
    method: 'POST',
    body: JSON.stringify(settings),
  }),
  getExportData: () => request('/api/export'),
  restoreData: (backupJson) => request('/api/restore', {
    method: 'POST',
    body: JSON.stringify(backupJson),
  }),
  checkHealth: () => request('/api/health'),
};

export default api;
