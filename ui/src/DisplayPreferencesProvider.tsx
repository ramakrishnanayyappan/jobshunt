/* eslint-disable react-refresh/only-export-components -- hook paired with provider */
import { createContext, useCallback, useContext, useLayoutEffect, useMemo, useState, type ReactNode } from 'react';
import {
  applyDisplayPreferencesToDocument,
  loadDisplayPreferences,
  saveDisplayPreferences,
  type DisplayPreferences,
  type FontFamilyId,
  type FontSizeId,
  type ThemeId,
} from './displayPreferences';

const Ctx = createContext<{
  prefs: DisplayPreferences;
  setTheme: (t: ThemeId) => void;
  setFontFamily: (f: FontFamilyId) => void;
  setFontSize: (s: FontSizeId) => void;
} | null>(null);

export function DisplayPreferencesProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<DisplayPreferences>(() => loadDisplayPreferences());

  useLayoutEffect(() => {
    applyDisplayPreferencesToDocument(prefs);
  }, [prefs]);

  const setTheme = useCallback((theme: ThemeId) => {
    setPrefs((p) => {
      const n = { ...p, theme };
      saveDisplayPreferences(n);
      return n;
    });
  }, []);
  const setFontFamily = useCallback((fontFamily: FontFamilyId) => {
    setPrefs((p) => {
      const n = { ...p, fontFamily };
      saveDisplayPreferences(n);
      return n;
    });
  }, []);
  const setFontSize = useCallback((fontSize: FontSizeId) => {
    setPrefs((p) => {
      const n = { ...p, fontSize };
      saveDisplayPreferences(n);
      return n;
    });
  }, []);

  const value = useMemo(
    () => ({ prefs, setTheme, setFontFamily, setFontSize }),
    [prefs, setTheme, setFontFamily, setFontSize]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useDisplayPreferences() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useDisplayPreferences needs DisplayPreferencesProvider');
  return v;
}
