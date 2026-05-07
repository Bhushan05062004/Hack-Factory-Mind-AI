import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface User {
  user_id: number;
  name: string;
  role: string;
  token: string;
}

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  api: ReturnType<typeof axios.create>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem('factory_mind_ai_user');
    return stored ? JSON.parse(stored) : null;
  });

  const api = axios.create({
    baseURL: API_BASE,
    headers: user ? { Authorization: `Bearer ${user.token}` } : {},
  });

  // Update headers when user changes
  api.interceptors.request.use((config) => {
    const stored = localStorage.getItem('factory_mind_ai_user');
    if (stored) {
      const u = JSON.parse(stored);
      config.headers.Authorization = `Bearer ${u.token}`;
    }
    return config;
  });

  const login = useCallback(async (email: string, password: string) => {
    const res = await axios.post(`${API_BASE}/login`, { email, password });
    const userData: User = {
      user_id: res.data.user_id,
      name: res.data.name,
      role: res.data.role,
      token: res.data.access_token,
    };
    setUser(userData);
    localStorage.setItem('factory_mind_ai_user', JSON.stringify(userData));
  }, []);

  const register = useCallback(async (name: string, email: string, password: string) => {
    const res = await axios.post(`${API_BASE}/register`, { name, email, password, role: 'user' });
    const userData: User = {
      user_id: res.data.user_id,
      name: res.data.name,
      role: res.data.role,
      token: res.data.access_token,
    };
    setUser(userData);
    localStorage.setItem('factory_mind_ai_user', JSON.stringify(userData));
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    localStorage.removeItem('factory_mind_ai_user');
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, register, logout, isAuthenticated: !!user, api }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
