import React, { useEffect, useState } from 'react';
import { useAuth } from '../hooks/useAuth';

interface Order {
  id: number;
  part_name: string;
  material: string;
  quantity: number;
  deadline: string;
  status: string;
  created_at: string;
  last_quality_note?: string | null;
  last_quality_ts?: string | null;
}

function StatusBadge({ status }: { status: string }) {
  const cls = status === 'Received' ? 'status-received'
    : status === 'In Review' ? 'status-in-review'
    : status === 'Accepted' ? 'status-accepted'
    : 'status-cancelled';
  return <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${cls}`}>{status}</span>;
}

export default function OperatorDashboard() {
  const { api, user } = useAuth();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [qualityNote, setQualityNote] = useState<{ orderId: number; note: string } | null>(null);
  const [feedback, setFeedback] = useState('');

  const fetchOrders = async () => {
    try {
      const res = await api.get('/orders', { params: { limit: 50 } });
      setOrders(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchOrders(); }, []);

  const sendAction = async (message: string, orderId: number) => {
    setActionLoading(orderId);
    setFeedback('');
    try {
      const res = await api.post('/chat', { message });
      setFeedback(res.data.message || 'Done');
      fetchOrders();
    } catch (err: any) {
      setFeedback(`Error: ${err.response?.data?.detail || err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const submitQualityNote = async () => {
    if (!qualityNote || !qualityNote.note.trim()) return;
    await sendAction(`Quality update on order #${qualityNote.orderId} — ${qualityNote.note}`, qualityNote.orderId);
    setQualityNote(null);
  };

  return (
    <div className="p-6 animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-white">Operator Dashboard</h2>
          <p className="text-white/40 text-sm mt-1">Manage orders, update status, log quality</p>
        </div>
        <button onClick={fetchOrders} className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white/50 hover:text-white/80 text-sm transition-all">
          ↻ Refresh
        </button>
      </div>

      {feedback && (
        <div className="mb-4 glass-card p-3 text-sm text-indigo-300 animate-slide-up">{feedback}</div>
      )}

      {/* Quality Note Modal */}
      {qualityNote && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="glass-card p-6 w-full max-w-md mx-4 animate-slide-up">
            <h3 className="text-white font-semibold mb-3">Quality Note — Order #{qualityNote.orderId}</h3>
            <textarea
              value={qualityNote.note}
              onChange={(e) => setQualityNote({ ...qualityNote, note: e.target.value })}
              placeholder="Enter inspection notes..."
              className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 outline-none input-glow text-sm resize-none h-24"
            />
            <div className="flex gap-3 mt-4">
              <button onClick={submitQualityNote}
                className="flex-1 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-medium rounded-xl text-sm hover:shadow-lg transition-all">
                Submit Note
              </button>
              <button onClick={() => setQualityNote(null)}
                className="px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white/50 text-sm hover:text-white/80 transition-all">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-white/30">Loading...</div>
      ) : (
        <div className="space-y-3">
          {orders.map((o) => (
            <div key={o.id} className="glass-card p-4 glass-card-hover">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-indigo-400 font-mono font-bold">#{o.id}</span>
                    <span className="text-white font-semibold">{o.part_name}</span>
                    <StatusBadge status={o.status} />
                  </div>
                  <div className="flex gap-4 text-xs text-white/40">
                    <span>Material: {o.material}</span>
                    <span>Qty: {o.quantity}</span>
                    <span>Deadline: {o.deadline}</span>
                  </div>
                  {o.last_quality_note && (
                    <div className="mt-2 text-xs text-emerald-400/70">
                      📋 {o.last_quality_note} <span className="text-white/20">({o.last_quality_ts})</span>
                    </div>
                  )}
                </div>

                <div className="flex gap-2 ml-4 shrink-0">
                  {o.status === 'Received' && (
                    <button
                      onClick={() => sendAction(`Move order #${o.id} to In Review`, o.id)}
                      disabled={actionLoading === o.id}
                      className="px-3 py-1.5 bg-amber-500/15 border border-amber-500/25 text-amber-300 rounded-lg text-xs font-medium hover:bg-amber-500/25 transition-all disabled:opacity-50">
                      → In Review
                    </button>
                  )}
                  {(o.status === 'Received' || o.status === 'In Review') && (
                    <button
                      onClick={() => sendAction(`Accept order #${o.id}`, o.id)}
                      disabled={actionLoading === o.id}
                      className="px-3 py-1.5 bg-emerald-500/15 border border-emerald-500/25 text-emerald-300 rounded-lg text-xs font-medium hover:bg-emerald-500/25 transition-all disabled:opacity-50">
                      ✓ Accept
                    </button>
                  )}
                  {(user?.role === 'quality' || user?.role === 'operator') && (
                    <button
                      onClick={() => setQualityNote({ orderId: o.id, note: '' })}
                      className="px-3 py-1.5 bg-violet-500/15 border border-violet-500/25 text-violet-300 rounded-lg text-xs font-medium hover:bg-violet-500/25 transition-all">
                      📋 Quality
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
