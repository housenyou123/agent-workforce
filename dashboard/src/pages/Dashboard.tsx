import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useSSE } from '../hooks/useSSE';
import { FileText, Clock, Zap, AlertTriangle, CheckCircle, XCircle, X, ChevronDown, ChevronRight } from 'lucide-react';

export function Dashboard() {
  const [stats, setStats] = useState<any[]>([]);
  const [sessions, setSessions] = useState<any[]>([]);
  const [memoryCount, setMemoryCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [activityLoading, setActivityLoading] = useState(true);
  const [selectedTrace, setSelectedTrace] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [expandedSessions, setExpandedSessions] = useState<Set<string>>(new Set());

  useEffect(() => {
    api.stats(7).then(setStats).catch(console.error).finally(() => setLoading(false));
    api.activityGrouped({ limit: '60' }).then(setSessions).catch(console.error).finally(() => setActivityLoading(false));
    api.memoryStats().then((s) => setMemoryCount(s.total ?? null)).catch(console.error);
  }, []);

  useSSE((event) => {
    if (event.type === 'trace:new') {
      api.stats(7).then(setStats);
      api.activityGrouped({ limit: '60' }).then(setSessions);
    }
  });

  const toggleSession = (sessionId: string) => {
    setExpandedSessions(prev => {
      const next = new Set(prev);
      if (next.has(sessionId)) next.delete(sessionId);
      else next.add(sessionId);
      return next;
    });
  };

  const handleTraceClick = async (traceId: string) => {
    if (selectedTrace?.trace_id === traceId) {
      setSelectedTrace(null);
      return;
    }
    setDetailLoading(true);
    try {
      const detail = await api.traceDetail(traceId);
      setSelectedTrace(detail);
    } catch (e) {
      console.error(e);
    } finally {
      setDetailLoading(false);
    }
  };

  const totalTasks = stats.reduce((s, a) => s + (a.total_tasks || 0), 0);
  const totalCost = stats.reduce((s, a) => s + (a.total_cost || 0), 0);

  return (
    <div className="flex gap-6">
      {/* Left: main content */}
      <div className={`${selectedTrace ? 'flex-1 min-w-0' : 'w-full'} transition-all`}>
        {/* Stat Cards */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          {loading ? (
            <>{[1,2,3,4].map(k => <SkeletonCard key={k} />)}</>
          ) : (
            <>
              <StatCard label="Tasks (7d)" value={totalTasks} />
              <StatCard label="Agents" value={stats.length} />
              <StatCard label="Cost" value={`$${totalCost.toFixed(2)}`} />
              <StatCard label="Memories" value={memoryCount ?? '...'} />
            </>
          )}
        </div>

        {/* Agent Performance */}
        <h2 className="text-lg font-semibold mb-3">Agent Performance</h2>
        <div className="rounded-[var(--radius)] border overflow-hidden mb-8" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
          {loading ? (
            <div className="p-4 space-y-3">
              <div className="skeleton h-4 w-full" />
              <div className="skeleton h-4 w-3/4" />
              <div className="skeleton h-4 w-5/6" />
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                  {['Agent', 'Tasks', 'Avg Score', 'Golden Rate', 'Cost'].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-medium uppercase" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {stats.map((a, i) => {
                  const goldenRate = a.total_tasks > 0 ? ((a.golden_count || 0) / a.total_tasks * 100).toFixed(0) : '--';
                  return (
                    <tr key={i} className="border-b last:border-0" style={{ borderColor: 'var(--border)' }}>
                      <td className="px-4 py-3 text-sm font-medium">{a.agent_profile?.replace('_v1.0', '')}</td>
                      <td className="px-4 py-3 text-sm">{a.total_tasks}</td>
                      <td className="px-4 py-3 text-sm">{a.avg_score?.toFixed(2) || '--'}</td>
                      <td className="px-4 py-3 text-sm">{goldenRate === '--' ? '--' : `${goldenRate}%`}</td>
                      <td className="px-4 py-3 text-sm">${(a.total_cost || 0).toFixed(2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Activity Feed — Session Grouped */}
        <h2 className="text-lg font-semibold mb-3">Activity Feed</h2>
        {activityLoading ? (
          <div className="space-y-3">
            {[1,2,3].map(k => (
              <div key={k} className="flex gap-3">
                <div className="skeleton w-8 h-8 rounded-full shrink-0" />
                <div className="flex-1 space-y-2 pt-1"><div className="skeleton h-3 w-1/3" /><div className="skeleton h-4 w-full" /></div>
              </div>
            ))}
          </div>
        ) : sessions.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>No recent activity</p>
          </div>
        ) : (
          <div className="space-y-1">
            {sessions.map((session, si) => {
              const isExpanded = expandedSessions.has(session.session_id);
              const hasMultiple = session.trace_count > 1;
              const agent = session.agent?.replace('_v1.0', '') || '--';
              const initial = agent.charAt(0).toUpperCase();
              const time = session.timestamp?.slice(11, 16) || '';
              const fbKey = String(session.auto_feedback);
              const fbColor = FEEDBACK_COLORS[fbKey] || '';
              const fbLabel: Record<string, string> = { '4': 'Golden', '3': 'Good', '2': 'Fine', '1': 'Bad' };
              const dur = session.total_duration > 0 ? `${Math.round(session.total_duration / 60)}m` : '';
              const fileCount = session.all_files?.length || 0;

              return (
                <div key={session.session_id || si}>
                  {/* Session header */}
                  <div
                    className={`flex items-center gap-3 px-2 py-2.5 rounded-md cursor-pointer transition-colors ${si === 0 ? 'animate-fade-in' : ''}`}
                    style={selectedTrace?.trace_id === session.traces?.[0]?.trace_id ? { background: 'var(--secondary)' } : {}}
                    onClick={() => {
                      if (hasMultiple) {
                        toggleSession(session.session_id);
                      } else {
                        handleTraceClick(session.traces?.[0]?.trace_id);
                      }
                    }}
                  >
                    {/* Avatar */}
                    <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium shrink-0"
                      style={{ background: fbColor || 'var(--brand)', color: 'var(--brand-foreground)' }}>
                      {initial}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{agent}</span>
                        {fbLabel[fbKey] && (
                          <span className="text-xs px-1.5 py-0.5 rounded-md font-medium" style={{ background: 'var(--secondary)', color: fbColor }}>
                            {fbLabel[fbKey]}
                          </span>
                        )}
                        <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{session.project}</span>
                        {hasMultiple && (
                          <span className="text-xs px-1.5 py-0.5 rounded-full font-medium" style={{ background: 'var(--secondary)', color: 'var(--muted-foreground)' }}>
                            {session.trace_count} tasks
                          </span>
                        )}
                        {fileCount > 0 && (
                          <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                            {fileCount} files
                          </span>
                        )}
                      </div>
                      <p className="text-sm mt-0.5 truncate" style={{ color: 'var(--muted-foreground)' }}>
                        {session.summary || '--'}
                      </p>
                    </div>

                    {/* Right: time + expand */}
                    <div className="flex items-center gap-2 shrink-0">
                      {dur && <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{dur}</span>}
                      <span className="text-xs font-mono" style={{ color: 'var(--muted-foreground)' }}>{time}</span>
                      {hasMultiple && (
                        <span style={{ color: 'var(--muted-foreground)' }}>
                          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Expanded: child traces */}
                  {isExpanded && hasMultiple && (
                    <div className="ml-10 pl-3 border-l space-y-0.5 pb-2" style={{ borderColor: 'var(--border)' }}>
                      {session.traces.map((trace: any, ti: number) => {
                        const tTime = trace.timestamp?.slice(11, 16) || '';
                        const tFb = FEEDBACK_COLORS[String(trace.auto_feedback)] || '';
                        return (
                          <div
                            key={trace.trace_id || ti}
                            className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:opacity-80 text-sm"
                            style={selectedTrace?.trace_id === trace.trace_id ? { background: 'var(--secondary)' } : {}}
                            onClick={(e) => { e.stopPropagation(); handleTraceClick(trace.trace_id); }}
                          >
                            <div className="w-2 h-2 rounded-full shrink-0" style={{ background: tFb || 'var(--muted-foreground)' }} />
                            <span className="flex-1 truncate" style={{ color: 'var(--muted-foreground)' }}>{trace.summary || trace.goal || '--'}</span>
                            <code className="text-xs font-mono shrink-0" style={{ color: 'var(--muted-foreground)' }}>{tTime}</code>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Right: Trace Detail Panel */}
      {(selectedTrace || detailLoading) && (
        <div className="w-96 shrink-0 rounded-[var(--radius)] border overflow-hidden sticky top-0 h-fit max-h-[calc(100vh-3rem)]" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
          {detailLoading ? (
            <div className="p-5 space-y-3">
              <div className="skeleton h-5 w-2/3" />
              <div className="skeleton h-4 w-full" />
              <div className="skeleton h-4 w-3/4" />
              <div className="skeleton h-20 w-full" />
            </div>
          ) : selectedTrace && (
            <TraceDetail trace={selectedTrace} onClose={() => setSelectedTrace(null)} />
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Trace Detail Panel ─── */

function TraceDetail({ trace, onClose }: { trace: any; onClose: () => void }) {
  const agent = trace.agent?.replace('_v1.0', '') || '--';
  const fbLabels: Record<string, string> = { '4': 'Golden', '3': 'Good', '2': 'Fine', '1': 'Bad' };
  const fbLabel = fbLabels[String(trace.auto_feedback)] || '--';
  const statusColors: Record<string, string> = {
    completed: 'var(--success)', completed_with_concern: 'var(--warning)', failed: 'var(--destructive)',
  };
  const duration = trace.duration_sec ? `${Math.round(trace.duration_sec)}s` : '--';
  const time = trace.timestamp?.slice(0, 16).replace('T', ' ') || '';

  return (
    <div className="overflow-auto max-h-[calc(100vh-3rem)]">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <code className="text-xs font-mono" style={{ color: 'var(--muted-foreground)' }}>{trace.trace_id}</code>
        <button onClick={onClose} className="p-1 rounded-md hover:opacity-70"><X size={14} /></button>
      </div>

      {/* Goal */}
      <div className="px-5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="text-xs font-medium mb-1" style={{ color: 'var(--muted-foreground)' }}>Goal</div>
        <p className="text-sm">{trace.goal || '--'}</p>
      </div>

      {/* Summary */}
      {trace.summary && (
        <div className="px-5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="text-xs font-medium mb-1" style={{ color: 'var(--muted-foreground)' }}>Summary</div>
          <p className="text-sm">{trace.summary}</p>
        </div>
      )}

      {/* Properties grid */}
      <div className="px-5 py-3 grid grid-cols-2 gap-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <PropItem label="Agent" value={agent} />
        <PropItem label="Project" value={trace.project || '--'} />
        <PropItem label="Status" value={trace.completion_status || '--'} color={statusColors[trace.completion_status]} />
        <PropItem label="Rating" value={fbLabel} color={FEEDBACK_COLORS[String(trace.auto_feedback)]} />
        <PropItem label="Duration" value={duration} icon={<Clock size={12} />} />
        <PropItem label="Time" value={time} />
        <PropItem label="Tokens" value={trace.total_tokens?.toLocaleString() || '--'} icon={<Zap size={12} />} />
        <PropItem label="Cost" value={`$${(trace.estimated_cost_usd || 0).toFixed(4)}`} />
        <PropItem label="Quality" value={trace.quality_score?.toFixed(2) || '--'} />
        <PropItem label="Completion" value={trace.completion_score?.toFixed(2) || '--'} />
      </div>

      {/* Files Modified */}
      {trace.files_modified?.length > 0 && (
        <div className="px-5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="text-xs font-medium mb-2" style={{ color: 'var(--muted-foreground)' }}>
            <FileText size={12} className="inline mr-1" />
            Files Modified ({trace.total_edits} edits, {trace.retry_edits} retries)
          </div>
          <div className="space-y-1">
            {trace.files_modified.map((f: string, i: number) => {
              const fname = f.split('/').pop() || f;
              return (
                <div key={i} className="text-xs font-mono px-2 py-1 rounded" style={{ background: 'var(--secondary)' }}>
                  {fname}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tool Calls */}
      {trace.tool_calls?.length > 0 && (
        <div className="px-5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="text-xs font-medium mb-2" style={{ color: 'var(--muted-foreground)' }}>
            Tool Calls ({trace.tool_call_count})
          </div>
          <div className="space-y-1 max-h-48 overflow-auto">
            {trace.tool_calls.map((tc: any, i: number) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <span className="font-mono font-medium shrink-0 w-10" style={{ color: 'var(--brand)' }}>{tc.tool}</span>
                <span className="font-mono truncate" style={{ color: 'var(--muted-foreground)' }}>
                  {(tc.target || '').slice(0, 60)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Verification */}
      <div className="px-5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="text-xs font-medium mb-2" style={{ color: 'var(--muted-foreground)' }}>Verification</div>
        <div className="flex flex-wrap gap-2">
          <VerifyBadge label="Build" value={trace.build_success} />
          <VerifyBadge label="Verified" value={trace.verification_passed} />
          <VerifyBadge label="Scope" value={trace.scope_respected} />
        </div>
        {trace.boundary_violations?.length > 0 && (
          <div className="mt-2 flex items-center gap-1 text-xs" style={{ color: 'var(--destructive)' }}>
            <AlertTriangle size={12} />
            Boundary violations: {trace.boundary_violations.join(', ')}
          </div>
        )}
      </div>

      {/* CWD */}
      {trace.cwd && (
        <div className="px-5 py-3">
          <div className="text-xs font-medium mb-1" style={{ color: 'var(--muted-foreground)' }}>Working Directory</div>
          <code className="text-xs font-mono" style={{ color: 'var(--muted-foreground)' }}>{trace.cwd}</code>
        </div>
      )}
    </div>
  );
}

function PropItem({ label, value, color, icon }: { label: string; value: string; color?: string; icon?: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{label}</div>
      <div className="text-sm font-medium flex items-center gap-1" style={color ? { color } : {}}>
        {icon}{value}
      </div>
    </div>
  );
}

function VerifyBadge({ label, value }: { label: string; value: any }) {
  if (value === null || value === undefined) {
    return <span className="text-xs px-2 py-0.5 rounded" style={{ background: 'var(--secondary)', color: 'var(--muted-foreground)' }}>{label}: --</span>;
  }
  const passed = value === true || value === 1;
  return (
    <span className="text-xs px-2 py-0.5 rounded flex items-center gap-1" style={{ background: 'var(--secondary)', color: passed ? 'var(--success)' : 'var(--destructive)' }}>
      {passed ? <CheckCircle size={10} /> : <XCircle size={10} />}
      {label}
    </span>
  );
}

/* ─── Shared Components ─── */

function SkeletonCard() {
  return (
    <div className="rounded-[var(--radius)] border p-5" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
      <div className="skeleton h-7 w-16 mb-2" /><div className="skeleton h-3 w-20" />
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-[var(--radius)] border p-5" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>{label}</div>
    </div>
  );
}

const FEEDBACK_COLORS: Record<string, string> = {
  '4': 'var(--success)', '3': 'var(--info)', '2': 'var(--warning)', '1': 'var(--destructive)',
};

