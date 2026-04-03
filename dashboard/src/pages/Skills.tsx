import { useEffect, useState } from 'react';
import { api } from '../api/client';

export function Skills() {
  const [skills, setSkills] = useState<any[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ name: '', description: '', content: '' });
  const [submitting, setSubmitting] = useState(false);

  const loadSkills = () => {
    api.skills().then(setSkills).catch(console.error);
  };

  useEffect(() => { loadSkills(); }, []);

  const handleCreate = async () => {
    if (!form.name.trim()) return;
    setSubmitting(true);
    try {
      await api.createSkill(form);
      setForm({ name: '', description: '', content: '' });
      setShowModal(false);
      loadSkills();
    } catch (e) {
      console.error(e);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete skill "${name}"?`)) return;
    try {
      await api.deleteSkill(id);
      loadSkills();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold">Skills Library</h2>
        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2 rounded-md text-sm font-medium transition-opacity hover:opacity-90"
          style={{ background: 'var(--brand)', color: 'var(--brand-foreground)' }}
        >
          + New Skill
        </button>
      </div>

      {skills.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-lg mb-2" style={{ color: 'var(--muted-foreground)' }}>No skills yet</p>
          <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>Skills are reusable capability definitions. Create your first skill to get started.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {skills.map((s) => {
            const agentList = s.agents ? (typeof s.agents === 'string' ? JSON.parse(s.agents) : s.agents) : [];
            const projectList = s.projects ? (typeof s.projects === 'string' ? JSON.parse(s.projects) : s.projects) : [];
            return (
              <div key={s.id} className="rounded-[var(--radius)] border p-5" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium">{s.name}</h3>
                    <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>{s.description}</p>
                  </div>
                  <div className="flex items-center gap-3 shrink-0 ml-4">
                    <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>Used {s.usage_count || 0} times</span>
                    <button
                      onClick={() => handleDelete(s.id, s.name)}
                      className="text-xs px-2 py-1 rounded-md transition-colors hover:opacity-80"
                      style={{ color: 'var(--destructive)' }}
                    >
                      Delete
                    </button>
                  </div>
                </div>
                {/* Agent tags */}
                {agentList.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {agentList.map((a: string) => (
                      <span key={a} className="text-xs px-2 py-0.5 rounded-md font-medium" style={{ background: 'var(--secondary)', color: 'var(--brand)' }}>{a}</span>
                    ))}
                  </div>
                )}
                {/* Project tags */}
                {projectList.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {projectList.map((p: string) => (
                      <span key={p} className="text-xs px-2 py-0.5 rounded-md font-medium" style={{ background: 'var(--secondary)', color: 'var(--success)' }}>{p}</span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Create Skill Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="rounded-[var(--radius)] border shadow-xl w-full max-w-lg mx-4 p-6" style={{ background: 'var(--background)', borderColor: 'var(--border)' }}>
            <h3 className="text-lg font-semibold mb-4">New Skill</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--muted-foreground)' }}>Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. code-review"
                  className="w-full px-3 py-2 rounded-md text-sm focus:outline-none focus:ring-2"
                  style={{ border: '1px solid var(--input)', background: 'var(--card)', color: 'var(--foreground)', '--tw-ring-color': 'var(--ring)' } as React.CSSProperties}
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--muted-foreground)' }}>Description</label>
                <input
                  type="text"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="What does this skill do?"
                  className="w-full px-3 py-2 rounded-md text-sm focus:outline-none focus:ring-2"
                  style={{ border: '1px solid var(--input)', background: 'var(--card)', color: 'var(--foreground)', '--tw-ring-color': 'var(--ring)' } as React.CSSProperties}
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--muted-foreground)' }}>Content</label>
                <textarea
                  value={form.content}
                  onChange={(e) => setForm({ ...form, content: e.target.value })}
                  placeholder="Skill definition / instructions..."
                  rows={6}
                  className="w-full px-3 py-2 rounded-md text-sm focus:outline-none focus:ring-2 resize-none"
                  style={{ border: '1px solid var(--input)', background: 'var(--card)', color: 'var(--foreground)', '--tw-ring-color': 'var(--ring)' } as React.CSSProperties}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button
                onClick={() => { setShowModal(false); setForm({ name: '', description: '', content: '' }); }}
                className="px-4 py-2 text-sm rounded-md transition-colors hover:opacity-80"
                style={{ background: 'var(--secondary)', color: 'var(--secondary-foreground)' }}
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={submitting || !form.name.trim()}
                className="px-4 py-2 rounded-md text-sm font-medium transition-opacity hover:opacity-90 disabled:opacity-50"
                style={{ background: 'var(--brand)', color: 'var(--brand-foreground)' }}
              >
                {submitting ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
