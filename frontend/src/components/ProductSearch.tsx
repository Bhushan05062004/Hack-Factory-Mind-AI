import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';

interface Product {
  id: number;
  part_number: string;
  name: string;
  material: string;
  specification: string;
  snippet: string;
  similarity_score: number;
}

export default function ProductSearch() {
  const { api } = useAuth();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Product[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const res = await api.post('/chat', { message: `Do you have ${query}?` });
      if (res.data.payload?.products) {
        setResults(res.data.payload.products);
      } else {
        setResults([]);
      }
    } catch (err) {
      console.error(err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 animate-fade-in">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-white mb-1">Product Catalog Search</h2>
        <p className="text-white/40 text-sm">Search our catalog using natural language (powered by RAG)</p>
      </div>

      <div className="flex gap-3 mb-6 max-w-2xl">
        <input
          id="product-search-input"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && search()}
          placeholder="e.g., titanium flange for aerospace, steel brackets..."
          className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 outline-none input-glow transition-all text-sm"
        />
        <button
          id="product-search-button"
          onClick={search}
          disabled={loading}
          className="px-6 py-3 bg-gradient-to-r from-indigo-500 to-violet-600 text-white font-medium rounded-xl hover:shadow-lg hover:shadow-indigo-500/25 transition-all disabled:opacity-50 text-sm"
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>

      {loading && <div className="text-white/30 text-sm">Searching catalog...</div>}

      {!loading && searched && results.length === 0 && (
        <div className="glass-card p-8 text-center">
          <p className="text-white/40">No matching products found. Try different keywords.</p>
        </div>
      )}

      {results.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {results.map((p) => (
            <div key={p.id || p.part_number} className="glass-card glass-card-hover p-5">
              <div className="flex items-start justify-between mb-3">
                <h3 className="text-white font-semibold">{p.name}</h3>
                <span className="text-[10px] bg-indigo-500/15 text-indigo-300 px-2 py-0.5 rounded-full font-mono">
                  {(p.similarity_score * 100).toFixed(0)}% match
                </span>
              </div>
              <div className="space-y-1 text-xs text-white/50">
                <p><span className="text-white/30">Part #:</span> {p.part_number}</p>
                <p><span className="text-white/30">Material:</span> {p.material}</p>
                <p><span className="text-white/30">Spec:</span> {p.specification}</p>
              </div>
              <div className="mt-3 pt-3 border-t border-white/5">
                <p className="text-xs text-white/40 leading-relaxed">{p.snippet}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
