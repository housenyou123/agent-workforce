import { useState, useEffect } from 'react';
import { LayoutDashboard, Bot, BookOpen, Brain, Sun, Moon } from 'lucide-react';
import { Dashboard } from './pages/Dashboard';
import { Agents } from './pages/Agents';
import { Skills } from './pages/Skills';
import { Memory } from './pages/Memory';

const PAGES = {
  dashboard: Dashboard,
  agents: Agents,
  skills: Skills,
  memory: Memory,
} as const;

const NAV_ITEMS = [
  { key: 'dashboard' as const, label: 'Dashboard', icon: LayoutDashboard },
  { key: 'agents' as const, label: 'Agents', icon: Bot },
  { key: 'skills' as const, label: 'Skills', icon: BookOpen },
  { key: 'memory' as const, label: 'Memory', icon: Brain },
];

export default function App() {
  const [page, setPage] = useState<keyof typeof PAGES>('dashboard');
  const [dark, setDark] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('theme') === 'dark' ||
        (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
    }
    return false;
  });

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem('theme', dark ? 'dark' : 'light');
  }, [dark]);

  const Page = PAGES[page];

  return (
    <div className="flex h-screen" style={{ background: 'var(--background)', color: 'var(--foreground)' }}>
      {/* Sidebar */}
      <aside className="w-56 shrink-0 flex flex-col border-r" style={{ background: 'var(--sidebar)', borderColor: 'var(--sidebar-border)' }}>
        {/* Logo */}
        <div className="px-4 py-4 flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center text-white text-sm font-bold" style={{ background: 'var(--brand)' }}>A</div>
          <span className="font-semibold text-sm">Agent Workforce</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-2 space-y-0.5">
          {NAV_ITEMS.map(item => {
            const isActive = page === item.key;
            return (
              <button
                key={item.key}
                onClick={() => setPage(item.key)}
                className={`w-full flex items-center gap-2.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'font-medium'
                    : 'opacity-60 hover:opacity-100'
                }`}
                style={isActive ? { background: 'var(--sidebar-accent)', color: 'var(--sidebar-accent-foreground)' } : {}}
              >
                <item.icon size={16} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Footer: Theme toggle */}
        <div className="px-2 py-3 border-t" style={{ borderColor: 'var(--sidebar-border)' }}>
          <button
            onClick={() => setDark(!dark)}
            className="w-full flex items-center gap-2.5 px-3 py-1.5 rounded-md text-sm opacity-60 hover:opacity-100 transition-colors"
          >
            {dark ? <Sun size={16} /> : <Moon size={16} />}
            <span>Theme</span>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-6" style={{ background: 'var(--background)' }}>
        <Page />
      </main>
    </div>
  );
}
