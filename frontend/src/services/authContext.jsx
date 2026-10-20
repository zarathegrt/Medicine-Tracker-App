import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api, { tokenStorage } from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => tokenStorage.get());
  const [loading, setLoading] = useState(true);
  const [setupStatus, setSetupStatus] = useState(null);
  const [caregiverPatients, setCaregiverPatients] = useState([]);
  const [activePatientId, setActivePatientId] = useState(null);

  // Check setup status
  const refreshSetupStatus = useCallback(async () => {
    try {
      const status = await api.getSetupStatus();
      setSetupStatus(status);
      return status;
    } catch (err) {
      console.warn('Failed to fetch setup status:', err.message);
      return null;
    }
  }, []);

  // Fetch current user session
  const refreshUser = useCallback(async () => {
    const storedToken = tokenStorage.get();
    if (!storedToken) {
      setUser(null);
      setLoading(false);
      refreshSetupStatus();
      return null;
    }

    try {
      const data = await api.getMe();
      if (data?.user) {
        setUser(data.user);
        // If user is caregiver or both, load their patients
        if (data.user.role === 'caregiver' || data.user.role === 'both') {
          try {
            const pData = await api.getMyPatients();
            const list = pData?.patients || [];
            setCaregiverPatients(list);
            if (list.length > 0 && !activePatientId) {
              setActivePatientId(list[0].id || list[0].patient_id);
            }
          } catch {
            // Non-critical
          }
        }
        return data.user;
      }
      setUser(null);
      tokenStorage.clear();
      setToken(null);
    } catch {
      setUser(null);
      tokenStorage.clear();
      setToken(null);
    } finally {
      setLoading(false);
      refreshSetupStatus();
    }
    return null;
  }, [activePatientId, refreshSetupStatus]);

  // Initial load
  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  // Listen for 401 unauthorized broadcasts
  useEffect(() => {
    const handleUnauthorized = () => {
      tokenStorage.clear();
      setToken(null);
      setUser(null);
      setCaregiverPatients([]);
      setActivePatientId(null);
    };

    window.addEventListener('curavit:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('curavit:unauthorized', handleUnauthorized);
  }, []);

  const login = async (email, password) => {
    const res = await api.login({ email, password });
    if (res?.token && res?.user) {
      tokenStorage.set(res.token);
      setToken(res.token);
      setUser(res.user);

      if (res.user.role === 'caregiver' || res.user.role === 'both') {
        try {
          const pData = await api.getMyPatients();
          const list = pData?.patients || [];
          setCaregiverPatients(list);
          if (list.length > 0) {
            setActivePatientId(list[0].id || list[0].patient_id);
          }
        } catch {
          // Ignored
        }
      }
      refreshSetupStatus();
      return res.user;
    }
    throw new Error(res?.message || 'Login failed');
  };

  const register = async (payload) => {
    const res = await api.register(payload);
    if (res?.token && res?.user) {
      tokenStorage.set(res.token);
      setToken(res.token);
      setUser(res.user);
      refreshSetupStatus();
      return res.user;
    }
    throw new Error(res?.message || 'Registration failed');
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      // Ignored
    } finally {
      tokenStorage.clear();
      setToken(null);
      setUser(null);
      setCaregiverPatients([]);
      setActivePatientId(null);
      refreshSetupStatus();
    }
  };

  const claimLegacy = async () => {
    const res = await api.claimLegacy();
    await refreshSetupStatus();
    return res;
  };

  const fetchCaregiverPatients = async () => {
    try {
      const res = await api.getMyPatients();
      const list = res?.patients || [];
      setCaregiverPatients(list);
      if (list.length > 0 && !activePatientId) {
        setActivePatientId(list[0].id || list[0].patient_id);
      }
      return list;
    } catch (err) {
      console.warn('Failed to fetch caregiver patients:', err.message);
      return [];
    }
  };

  const activePatient = caregiverPatients.find(
    (p) => (p.id || p.patient_id) === activePatientId
  ) || null;

  const hasPermission = (permissionName) => {
    if (!user) return false;
    // Patient owns their own data; has all permissions for self
    if (!activePatientId || activePatientId === user.id) return true;
    // Caregiver: check active relationship permissions
    const perms = activePatient?.permissions || [];
    return perms.includes(permissionName);
  };

  const value = {
    user,
    token,
    isAuthenticated: !!user && !!token,
    loading,
    setupStatus,
    caregiverPatients,
    activePatientId,
    activePatient,
    setActivePatientId,
    login,
    register,
    logout,
    refreshUser,
    refreshSetupStatus,
    claimLegacy,
    fetchCaregiverPatients,
    hasPermission,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;
