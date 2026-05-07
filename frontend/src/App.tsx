import React from 'react';
import { Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import Login from './components/Login';
import Chat from './components/Chat';
import Dashboard from './components/Dashboard';
import OperatorDashboard from './components/OperatorDashboard';
import ProductSearch from './components/ProductSearch';

function Layout() {
  const { user, logout } = useAuth();
  const role = user?.role || 'user';

  const navItems = [
    { to: '/chat', label: 'Chat', icon: '💬', roles: ['user', 'operator', 'quality'] },
    { to: '/orders', label: 'Orders', icon: '📦', roles: ['user', 'operator', 'quality'] },
    { to: '/operator', label: 'Operator', icon: '⚙️', roles: ['operator', 'quality'] },
    { to: '/products', label: 'Products', icon: '🔍', roles: ['user', 'operator', 'quality'] },
  ];

  const roleLabel = role === 'user' ? 'Customer' : role === 'operator' ? 'Operator' : 'Quality';
  const roleColor = role === 'user' ? 'text-blue-400' : role === 'operator' ? 'text-amber-400' : 'text-emerald-400';

  return (
    <div className="min-h-screen flex flex-col relative">
      <div className="bg-mesh" />

      {/* Top Nav */}
      <header className="relative z-10 border-b border-white/5 bg-black/20 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10" />
                </svg>
              </div>
              <span className="text-white font-bold text-sm">Factory Mind AI</span>
            </div>

            <nav className="flex gap-1">
              {navItems.filter(n => n.roles.includes(role)).map((item) => (
                <NavLink key={item.to} to={item.to}
                  className={({ isActive }) =>
                    `px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
                      isActive
                        ? 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/20'
                        : 'text-white/40 hover:text-white/70 hover:bg-white/5'
                    }`
                  }>
                  <span>{item.icon}</span>
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-white/80 text-xs font-medium">{user?.name}</p>
              <p className={`text-[10px] font-semibold uppercase tracking-wider ${roleColor}`}>{roleLabel}</p>
            </div>
            <button id="logout-button" onClick={logout}
              className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-white/40 hover:text-white/80 text-xs transition-all">
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 flex-1 overflow-hidden">
        <div className="h-[calc(100vh-3.5rem)]">
          <Routes>
            <Route path="/chat" element={<Chat />} />
            <Route path="/orders" element={<Dashboard />} />
            <Route path="/operator" element={
              role === 'operator' || role === 'quality' ? <OperatorDashboard /> : <Navigate to="/chat" />
            } />
            <Route path="/products" element={<ProductSearch />} />
            <Route path="*" element={<Navigate to="/chat" />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

export default function App() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <Layout /> : <Login />;
}
