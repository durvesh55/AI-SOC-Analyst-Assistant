import { useEffect, useState } from "react";

const THEMES = [
  { id: "aurora", name: "Aurora (original)", colors: ["#050b1a", "#3b82f6", "#8b5cf6"] },
  { id: "slate", name: "1. Slate & Teal", colors: ["#0b1220", "#0d9488", "#5eead4"] },
  { id: "corporate", name: "2. Corporate Blue", colors: ["#f8fafc", "#1d4ed8", "#0b1f44"] },
  { id: "graphite", name: "3. Graphite & Amber", colors: ["#0f1115", "#d97706", "#fbbf24"] },
  { id: "emerald", name: "4. Midnight Emerald", colors: ["#06130f", "#059669", "#6ee7b7"] },
];
const KEY = "alertdesk-theme";

function readSaved() {
  try {
    const v = localStorage.getItem(KEY);
    return THEMES.some((t) => t.id === v) ? v : "aurora";
  } catch {
    return "aurora";
  }
}

// Floating palette picker so colour schemes can be compared live. Remove <ThemeSwitcher /> from App.jsx to hide it.
export default function ThemeSwitcher() {
  const [theme, setTheme] = useState(readSaved);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem(KEY, theme); } catch { /* storage unavailable */ }
  }, [theme]);

  return (
    <div className="theme-sw">
      {open && (
        <ul role="listbox" aria-label="Colour theme">
          {THEMES.map((t) => (
            <li key={t.id}>
              <button className={theme === t.id ? "on" : ""} onClick={() => { setTheme(t.id); setOpen(false); }} role="option" aria-selected={theme === t.id}>
                <i>{t.colors.map((c) => <b key={c} style={{ background: c }} />)}</i>
                <span>{t.name}</span>
                {theme === t.id && <em>✓</em>}
              </button>
            </li>
          ))}
        </ul>
      )}
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label="Change colour theme"><i /> Theme</button>
    </div>
  );
}
