import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';

const DEMO_ACCOUNTS = [
  { email: 'alice@demo.com', role: 'user', label: 'Customer', icon: '👤', password: '123' },
  { email: 'bob@demo.com', role: 'operator', label: 'Operator', icon: '⚙️', password: '123' },
  { email: 'carol@demo.com', role: 'quality', label: 'Quality', icon: '✅', password: '123' },
];

type AuthMode = 'login' | 'register' | 'admin';

export default function Login() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<AuthMode>('login');
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const resetForm = () => {
    setEmail('');
    setPassword('');
    setName('');
    setError('');
  };

  const handleAction = async () => {
    if (!email || !password) {
      setError('Please fill in all fields.');
      return;
    }
    
    setLoading(true);
    setError('');
    try {
      if (mode === 'register') {
        if (!name) {
          setError('Please provide a name.');
          setLoading(false);
          return;
        }
        await register(name, email, password);
      } else {
        await login(email, password);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async (demoEmail: string, demoPass: string) => {
    setLoading(true);
    setError('');
    try {
      await login(demoEmail, demoPass);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative">
      <div className="bg-mesh" />
      <div className="relative z-10 w-full max-w-md px-6">
        {/* Logo */}
        <div className="text-center mb-8 animate-fade-in">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 mb-4 shadow-lg shadow-indigo-500/30">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-white mb-1">
            Factory Mind <span className="gradient-text">AI</span>
          </h1>
          <p className="text-white/40 text-sm">Order Management System</p>
        </div>

        {/* Auth Card */}
        <div className="glass-card p-6 mb-6 animate-slide-up">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-white/80 text-sm font-semibold uppercase tracking-wider">
              {mode === 'login' ? 'Sign In' : mode === 'register' ? 'Register' : 'Admin Login'}
            </h2>
            {mode !== 'login' && (
              <button onClick={() => { setMode('login'); resetForm(); }} className="text-xs text-indigo-400 hover:text-indigo-300">
                Back to Sign In
              </button>
            )}
          </div>

          <div className="space-y-3">
            {mode === 'register' && (
              <input
                type="text"
                placeholder="Full Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 outline-none input-glow transition-all text-sm"
              />
            )}
            <input
              type={mode === 'admin' ? "text" : "email"}
              placeholder={mode === 'admin' ? "Admin Username" : "Email Address"}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 outline-none input-glow transition-all text-sm"
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAction()}
              className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 outline-none input-glow transition-all text-sm"
            />
            <button
              onClick={handleAction}
              disabled={loading || !email || !password || (mode === 'register' && !name)}
              className="w-full py-3 bg-gradient-to-r from-indigo-500 to-violet-600 text-white font-semibold rounded-xl hover:shadow-lg hover:shadow-indigo-500/25 transition-all disabled:opacity-50 text-sm"
            >
              {loading ? 'Processing...' : mode === 'register' ? 'Create Account' : 'Sign In'}
            </button>
          </div>

          {error && (
            <p className="mt-3 text-red-400 text-xs text-center">{error}</p>
          )}

          {mode === 'login' && (
            <div className="mt-4 flex flex-col gap-2">
              <button onClick={() => { setMode('register'); resetForm(); }} className="text-xs text-white/50 hover:text-white transition-colors text-center">
                Don't have an account? <span className="text-indigo-400">Register here</span>
              </button>
              <button onClick={() => { setMode('admin'); resetForm(); }} className="text-xs text-white/30 hover:text-white/60 transition-colors text-center mt-2">
                Operator / Admin Login
              </button>
            </div>
          )}
        </div>

        {/* Quick Login */}
        {mode === 'login' && (
          <div className="animate-slide-up" style={{ animationDelay: '0.1s' }}>
            <p className="text-white/30 text-xs text-center mb-3 uppercase tracking-wider">Quick Demo Login</p>
            <div className="grid grid-cols-3 gap-3">
              {DEMO_ACCOUNTS.map((acc) => (
                <button
                  key={acc.email}
                  onClick={() => handleDemoLogin(acc.email, acc.password)}
                  disabled={loading}
                  className="glass-card glass-card-hover p-3 text-center group cursor-pointer"
                >
                  <span className="text-2xl block mb-1">{acc.icon}</span>
                  <span className="text-white/70 text-xs font-medium group-hover:text-white transition-colors">{acc.label}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
