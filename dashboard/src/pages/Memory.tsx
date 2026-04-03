import { useEffect, useState } from 'react';
import { api } from '../api/client';

const TYPES = ['All', 'lesson', 'feedback', 'pattern', 'project'] as const;

export function Memory() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [typeFilter, setTypeFilter] = useState<string>('All');
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);

  // Load default memories on mount
  useEffect(() => {
    api.memoryStats().then(setStats).catch(console.error);
    loadDefault();
  }, []);

  const loadDefault = async () => {
    setLoading(true);
    try {
      const data = await api.recallMemory();
      // Sort by importance desc, take top 20
      const sorted = (data || [])
        .sort((a: any, b: any) => (b.importance || 0) - (a.importance || 0))
        .slice(0, 20);
      setResults(sorted);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!query.trim()) {
      loadDefault();
      setSearched(false);
      return;
    }
    setLoading(true);
    setSearched(true);
    try {
      const data = await api.searchMemory(query);
      setResults(data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const importanceColor = (imp: number) => {
    if (imp >= 0.8) return 'var(--warning)';
    if (imp >= 0.6) return 'var(--info)';
    return 'var(--muted-foreground)';
  };

  const filtered = typeFilter === 'All' ? results : results.filter((m) => m.type === typeFilter);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold">Memory Explorer</h2>
        {stats && <span className="text-sm" style={{ color: 'var(--muted-foreground)' }}>{stats.total} memories &middot; {stats.db_size_kb}KB</span>}
      </div>

      {/* Search */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="Search memories (e.g. VPN 503, shadowrocket)..."
          className="flex-1 px-4 py-2.5 rounded-md text-sm focus:outline-none focus:ring-2"
          style={{ border: '1px solid var(--input)', background: 'var(--card)', color: 'var(--foreground)', '--tw-ring-color': 'var(--ring)' } as React.CSSProperties}
        />
        <button
          onClick={handleSearch}
          className="px-6 py-2.5 rounded-md text-sm font-medium transition-opacity hover:opacity-90"
          style={{ background: 'var(--brand)', color: 'var(--brand-foreground)' }}
        >
          Search
        </button>
      </div>

      {/* Type filter */}
      <div className="flex gap-1.5 mb-6">
        {TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t)}
            className="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
            style={
              typeFilter === t
                ? { background: 'var(--brand)', color: 'var(--brand-foreground)' }
                : { background: 'var(--secondary)', color: 'var(--muted-foreground)' }
            }
          >
            {t === 'All' ? 'All' : t}
          </button>
        ))}
      </div>

      {/* Results */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((k) => (
            <div key={k} className="rounded-[var(--radius)] border p-4" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
              <div className="skeleton h-3 w-1/4 mb-2" />
              <div className="skeleton h-4 w-full mb-1" />
              <div className="skeleton h-4 w-3/4" />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((m, i) => (
            <div key={i} className="rounded-[var(--radius)] border p-4" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-bold" style={{ color: importanceColor(m.importance) }}>
                  *{m.importance?.toFixed(1)}
                </span>
                <span className="text-xs px-1.5 py-0.5 rounded-md" style={{ background: 'var(--secondary)', color: 'var(--muted-foreground)' }}>{m.type}</span>
                {m.project && <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{m.project}</span>}
                {m.access_count > 0 && <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>&middot; {m.access_count}x accessed</span>}
              </div>
              <p className="text-sm whitespace-pre-wrap">{m.content?.slice(0, 300)}{m.content?.length > 300 ? '...' : ''}</p>
              {m.created_at && (
                <div className="text-xs mt-2" style={{ color: 'var(--muted-foreground)' }}>
                  {new Date(m.created_at).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })}
                </div>
              )}
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="text-center py-12">
              <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
                {searched ? 'No results found. Try a different query or filter.' : 'No memories available yet.'}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
