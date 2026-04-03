import { useEffect, useState } from 'react';
import { api } from '../api/client';

// Placeholder data when API doesn't return these fields
const PLACEHOLDER_HOT_FILES = [
  'src/api/client.ts',
  'src/pages/Dashboard.tsx',
  'hooks/claude_code_hook.sh',
];
const PLACEHOLDER_SKILLS = ['code-review', 'refactor', 'debug', 'deploy'];

export function Agents() {
  const [agents, setAgents] = useState<any[]>([]);
  const [selected, setSelected] = useState<string>('');

  useEffect(() => {
    api.agents().then(setAgents).catch(console.error);
  }, []);

  const current = agents.find(a => a.agent_profile === selected) || agents[0];

  return (
    <div className="flex gap-6">
      {/* Left: Agent list */}
      <div className="w-56 shrink-0">
        <h2 className="text-lg font-semibold mb-3">Agents</h2>
        <div className="space-y-1">
          {agents.map((a) => {
            const name = a.agent_profile?.replace('_v1.0', '') || '--';
            const isActive = a.agent_profile === (selected || agents[0]?.agent_profile);
            const hasWork = (a.total_tasks || 0) > 0;
            return (
              <button
                key={a.agent_profile}
                onClick={() => setSelected(a.agent_profile)}
                className={`w-full text-left px-3 py-2 rounded-md text-sm flex items-center gap-2 transition-colors ${
                  isActive ? 'font-medium' : 'opacity-60 hover:opacity-100'
                }`}
                style={isActive ? { background: 'var(--sidebar-accent)', color: 'var(--sidebar-accent-foreground)' } : {}}
              >
                <span className={`w-2 h-2 rounded-full shrink-0`} style={{ background: hasWork ? 'var(--success)' : 'var(--muted-foreground)' }} />
                <span className="font-medium flex-1 truncate">{name}</span>
                <span className="text-xs opacity-70">{a.total_tasks}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Right: Agent detail */}
      <div className="flex-1">
        {current ? (
          <div>
            <h2 className="text-xl font-bold mb-1">{current.agent_profile?.replace('_v1.0', '')}</h2>
            <p className="text-sm mb-6" style={{ color: 'var(--muted-foreground)' }}>
              {current.total_tasks} tasks &middot; ${(current.total_cost || 0).toFixed(2)} cost
            </p>

            {/* Stats grid */}
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="rounded-[var(--radius)] border p-4" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
                <div className="text-xl font-bold">{current.total_tasks}</div>
                <div className="text-xs" style={{ color: 'var(--muted-foreground)' }}>Total Tasks</div>
              </div>
              <div className="rounded-[var(--radius)] border p-4" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
                <div className="text-xl font-bold">{current.avg_score?.toFixed(2) || '--'}</div>
                <div className="text-xs" style={{ color: 'var(--muted-foreground)' }}>Avg Score</div>
              </div>
              <div className="rounded-[var(--radius)] border p-4" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
                <div className="text-xl font-bold">${(current.total_cost || 0).toFixed(2)}</div>
                <div className="text-xs" style={{ color: 'var(--muted-foreground)' }}>Cost (7d)</div>
              </div>
            </div>

            {/* Skills */}
            <SectionBlock title="Skills">
              <div className="flex flex-wrap gap-1.5">
                {(current.skills && current.skills.length > 0 ? current.skills : PLACEHOLDER_SKILLS).map((s: string) => (
                  <span key={s} className="text-xs px-2 py-1 rounded-md font-medium" style={{ background: 'var(--secondary)', color: 'var(--brand)' }}>{s}</span>
                ))}
              </div>
            </SectionBlock>

            {/* Hot Files */}
            <SectionBlock title="Hot Files">
              <ul className="space-y-1">
                {(current.hot_files && current.hot_files.length > 0 ? current.hot_files : PLACEHOLDER_HOT_FILES).map((f: string) => (
                  <li key={f} className="text-sm font-mono truncate" style={{ color: 'var(--muted-foreground)' }}>{f}</li>
                ))}
              </ul>
            </SectionBlock>

            {/* Recent Traces */}
            <SectionBlock title="Recent Traces">
              {current.recent_traces && current.recent_traces.length > 0 ? (
                <ul className="space-y-1.5">
                  {current.recent_traces.map((t: any, i: number) => (
                    <li key={i} className="text-sm flex items-center gap-2">
                      <span className="text-xs font-mono" style={{ color: 'var(--muted-foreground)' }}>{t.timestamp?.slice(0, 10) || ''}</span>
                      <span className="truncate">{t.summary || t.goal || '--'}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>No recent traces available.</p>
              )}
            </SectionBlock>
          </div>
        ) : (
          <p style={{ color: 'var(--muted-foreground)' }}>Select an agent</p>
        )}
      </div>
    </div>
  );
}

function SectionBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <h3 className="text-sm font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--muted-foreground)' }}>{title}</h3>
      <div className="rounded-[var(--radius)] border p-4" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
        {children}
      </div>
    </div>
  );
}
