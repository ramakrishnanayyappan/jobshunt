import { NavLink, Outlet } from 'react-router-dom';
import { useDisplayPreferences } from './DisplayPreferencesProvider';

function IconBriefcase({ className }: { className?: string }) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M4 15l1.5 5h13L20 15M4 15h16v-3a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v3Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconSparkle({ className }: { className?: string }) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 2.5l1.1 3.3h3.5L14.7 7.5l1.1 3.3L12 8.6 8.2 10.8l1.1-3.3-3-1.7h3.5L12 2.5zM4 16.5l.7 2h2.2L5.2 20l.7 2 .7-2-2-1.5h2.2l.7-2v0zM18.5 14l.4 1.1h1.1l-.9.6.3 1.1-.9-.6-.9.6.3-1.1-.9-.6h1.1L18.5 14z"
        fill="currentColor"
        opacity="0.95"
      />
    </svg>
  );
}

function AppearanceSettings() {
  const { prefs, setTheme, setFontFamily, setFontSize } = useDisplayPreferences();
  return (
    <div className="portico-appearance p-3 border-top border-secondary border-opacity-25">
      <div className="portico-kicker mb-2">Display</div>
      <label className="form-label small text-white-50 mb-0">Theme</label>
      <select
        className="form-select form-select-sm mb-2 bg-dark text-white border-secondary"
        value={prefs.theme}
        onChange={(e) => setTheme(e.target.value as 'light' | 'dark')}
      >
        <option value="light">Light</option>
        <option value="dark">Dark</option>
      </select>
      <label className="form-label small text-white-50 mb-0">Font</label>
      <select
        className="form-select form-select-sm mb-2 bg-dark text-white border-secondary"
        value={prefs.fontFamily}
        onChange={(e) =>
          setFontFamily(e.target.value as 'outfit' | 'inter' | 'dm_sans' | 'system')
        }
      >
        <option value="outfit">Outfit</option>
        <option value="inter">Inter</option>
        <option value="dm_sans">DM Sans</option>
        <option value="system">System</option>
      </select>
      <label className="form-label small text-white-50 mb-0">Text size</label>
      <select
        className="form-select form-select-sm bg-dark text-white border-secondary"
        value={prefs.fontSize}
        onChange={(e) => setFontSize(e.target.value as 's' | 'm' | 'l' | 'xl')}
      >
        <option value="s">S</option>
        <option value="m">M</option>
        <option value="l">L</option>
        <option value="xl">XL</option>
      </select>
    </div>
  );
}

export default function Layout() {
  return (
    <div className="d-flex flex-column flex-md-row min-vh-100 portico-app">
      <aside className="portico-sidebar d-flex flex-column">
        <div className="portico-sidebar-brand d-flex align-items-start gap-3">
          <div className="portico-logo-mark" aria-hidden>
            JH
          </div>
          <div>
            <div className="portico-kicker">JobsHunt</div>
            <div className="portico-sidebar-title">Local assistant</div>
            <p className="portico-sidebar-tagline mb-0">Résumé vault · pipeline · LLM</p>
          </div>
        </div>
        <nav className="portico-nav flex-grow-1" aria-label="Main">
          <NavLink
            to="/agents/jobshunt"
            className={({ isActive }) => (isActive ? 'portico-nav-link active' : 'portico-nav-link')}
            title="Résumé tailoring"
          >
            <span className="portico-nav-ico">
              <IconBriefcase />
            </span>
            JobsHunt
          </NavLink>
          <NavLink
            to="/settings/ai"
            className={({ isActive }) => (isActive ? 'portico-nav-link active' : 'portico-nav-link')}
            title="LLM and models"
          >
            <span className="portico-nav-ico">
              <IconSparkle />
            </span>
            AI settings
          </NavLink>
        </nav>
        <AppearanceSettings />
        <div className="portico-sidebar-footer d-none d-md-block">
          Runs on your machine — config and data stay local.
        </div>
      </aside>
      <main className="portico-content flex-grow-1 overflow-auto">
        <div className="portico-content-inner py-4 px-3 px-sm-4">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
