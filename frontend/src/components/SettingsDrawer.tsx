"use client";

import { useCallback, useState } from "react";

const STORAGE_KEY = "vbportal-ui-settings";

type UiSettings = {
  ultraCompact: boolean;
  wideLayout: boolean;
};

const defaults: UiSettings = {
  ultraCompact: true,
  wideLayout: true,
};

const isValidSettings = (value: unknown): value is UiSettings => {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as UiSettings).ultraCompact === "boolean" &&
    typeof (value as UiSettings).wideLayout === "boolean"
  );
};

const loadSettings = (): UiSettings => {
  if (typeof window === "undefined") {
    return defaults;
  }
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      return defaults;
    }
    const parsed = JSON.parse(stored);
    if (isValidSettings(parsed)) {
      return parsed;
    }
  } catch (error) {
    console.warn("Unable to parse UI settings:", error);
  }
  return defaults;
};

const saveSettings = (settings: UiSettings) => {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch (error) {
    console.warn("Unable to persist UI settings:", error);
  }
};

const applySettings = (settings: UiSettings) => {
  const root = document.documentElement;
  if (settings.ultraCompact) {
    root.setAttribute("data-theme", "ultra-compact");
  } else {
    root.removeAttribute("data-theme");
  }
  if (settings.wideLayout) {
    root.setAttribute("data-layout", "wide");
  } else {
    root.removeAttribute("data-layout");
  }
};

const ThemeControls = ({
  settings,
  onChange,
}: {
  settings: UiSettings;
  onChange: (next: UiSettings) => void;
}) => (
  <div className="theme-controls">
    <button
      type="button"
      className={`btn theme-toggle ${settings.ultraCompact ? "active" : ""}`}
      onClick={() => onChange({ ...settings, ultraCompact: !settings.ultraCompact })}
    >
      Ultra compact
    </button>
    <button
      type="button"
      className={`btn theme-toggle ${settings.wideLayout ? "active" : ""}`}
      onClick={() => onChange({ ...settings, wideLayout: !settings.wideLayout })}
    >
      Wide layout
    </button>
  </div>
);

export default function SettingsDrawer() {
  const [open, setOpen] = useState(false);
  const [settings, setSettings] = useState<UiSettings>(() => {
    const initial = loadSettings();
    if (typeof window !== "undefined") {
      applySettings(initial);
    }
    return initial;
  });

  const handleSettingsChange = useCallback(
    (next: UiSettings) => {
      setSettings(next);
      applySettings(next);
      saveSettings(next);
    },
    [],
  );

  return (
    <>
      <button
        type="button"
        className="btn settings-toggle"
        onClick={() => setOpen(true)}
      >
        Settings
      </button>
      {open && (
        <div className="settings-drawer">
          <div
            className="settings-drawer-backdrop"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div className="settings-drawer-panel">
            <header className="settings-drawer-header">
              <h3>Display settings</h3>
              <button
                type="button"
                className="btn theme-toggle"
                onClick={() => setOpen(false)}
              >
                Close
              </button>
            </header>
            <ThemeControls settings={settings} onChange={handleSettingsChange} />
          </div>
        </div>
      )}
    </>
  );
}
