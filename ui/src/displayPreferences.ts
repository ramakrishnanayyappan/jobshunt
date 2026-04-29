const STORAGE_KEY = 'jobshunt.ui.display';

export type ThemeId = 'light' | 'dark';
export type FontFamilyId = 'outfit' | 'inter' | 'dm_sans' | 'system';
export type FontSizeId = 's' | 'm' | 'l' | 'xl';

export type DisplayPreferences = {
  theme: ThemeId;
  fontFamily: FontFamilyId;
  fontSize: FontSizeId;
};

const defaults: DisplayPreferences = { theme: 'light', fontFamily: 'outfit', fontSize: 'm' };

function parse(raw: string | null): DisplayPreferences {
  if (!raw) return { ...defaults };
  try {
    const j = JSON.parse(raw) as Partial<DisplayPreferences>;
    return {
      theme: j.theme === 'dark' ? 'dark' : 'light',
      fontFamily: ['outfit', 'inter', 'dm_sans', 'system'].includes(j.fontFamily as string)
        ? (j.fontFamily as FontFamilyId)
        : defaults.fontFamily,
      fontSize: ['s', 'm', 'l', 'xl'].includes(j.fontSize as string) ? (j.fontSize as FontSizeId) : defaults.fontSize,
    };
  } catch {
    return { ...defaults };
  }
}

export function loadDisplayPreferences(): DisplayPreferences {
  if (typeof localStorage === 'undefined') return { ...defaults };
  return parse(localStorage.getItem(STORAGE_KEY));
}

export function saveDisplayPreferences(p: DisplayPreferences) {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
}

const FAMILY_CSS: Record<FontFamilyId, string> = {
  outfit: "'Outfit', system-ui, -apple-system, 'Segoe UI', sans-serif",
  inter: "'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif",
  dm_sans: "'DM Sans', system-ui, -apple-system, 'Segoe UI', sans-serif",
  system: "system-ui, -apple-system, 'Segoe UI', sans-serif",
};

const SIZE_ROOT: Record<FontSizeId, string> = {
  s: '93.75%',
  m: '100%',
  l: '112.5%',
  xl: '125%',
};

/** Apply to document root (and color-scheme for native UI). */
export function applyDisplayPreferencesToDocument(p: DisplayPreferences) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  root.setAttribute('data-bs-theme', p.theme);
  root.style.setProperty('color-scheme', p.theme);
  root.style.fontSize = SIZE_ROOT[p.fontSize] ?? SIZE_ROOT.m;
  const fam = FAMILY_CSS[p.fontFamily] ?? FAMILY_CSS.outfit;
  root.style.setProperty('--portico-font-sans', fam);
  root.style.setProperty('--bs-body-font-family', fam);
}
