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

export default function Dashboard() {
  const { api, user } = useAuth();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('');

  const fetchOrders = async () => {
    try {
      const params: any = { limit: 50 };
      if (filter) params.status = filter;
      const res = await api.get('/orders', { params });
      setOrders(res.data);
    } catch (err) {
      console.error('Failed to fetch orders', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchOrders(); }, [filter]);

  const showQuality = user?.role !== 'user';

  return (
    <div className="p-6 animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-white">Orders Dashboard</h2>
          <p className="text-white/40 text-sm mt-1">{orders.length} order(s) found</p>
        </div>
        <div className="flex gap-2">
          {['', 'Received', 'In Review', 'Accepted', 'Cancelled'].map((s) => (
            <button key={s} onClick={() => setFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                filter === s ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30' : 'bg-white/5 text-white/40 border border-white/10 hover:text-white/70'
              }`}>
              {s || 'All'}
            </button>
          ))}
          <button onClick={fetchOrders} className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-white/40 hover:text-white/70 text-xs transition-all">
            ↻ Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-white/30">Loading orders...</div>
      ) : orders.length === 0 ? (
        <div className="text-center py-12 glass-card">
          <p className="text-white/40">No orders found</p>
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left px-4 py-3 text-white/50 font-medium text-xs uppercase tracking-wider">ID</th>
                  <th className="text-left px-4 py-3 text-white/50 font-medium text-xs uppercase tracking-wider">Part</th>
                  <th className="text-left px-4 py-3 text-white/50 font-medium text-xs uppercase tracking-wider">Material</th>
                  <th className="text-left px-4 py-3 text-white/50 font-medium text-xs uppercase tracking-wider">Qty</th>
                  <th className="text-left px-4 py-3 text-white/50 font-medium text-xs uppercase tracking-wider">Deadline</th>
                  <th className="text-left px-4 py-3 text-white/50 font-medium text-xs uppercase tracking-wider">Status</th>
                  {showQuality && <th className="text-left px-4 py-3 text-white/50 font-medium text-xs uppercase tracking-wider">Quality Note</th>}
                  <th className="text-left px-4 py-3 text-white/50 font-medium text-xs uppercase tracking-wider">Created</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id} className="border-b border-white/5 hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-3 text-indigo-400 font-mono font-semibold">#{o.id}</td>
                    <td className="px-4 py-3 text-white/90 font-medium">{o.part_name}</td>
                    <td className="px-4 py-3 text-white/60">{o.material}</td>
                    <td className="px-4 py-3 text-white/80 font-mono">{o.quantity}</td>
                    <td className="px-4 py-3 text-white/60">{o.deadline}</td>
                    <td className="px-4 py-3"><StatusBadge status={o.status} /></td>
                    {showQuality && <td className="px-4 py-3 text-white/50 text-xs max-w-[200px] truncate">{o.last_quality_note || '—'}</td>}
                    <td className="px-4 py-3 text-white/40 text-xs">{o.created_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
