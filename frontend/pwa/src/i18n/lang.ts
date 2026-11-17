import { useSyncExternalStore } from "react";

/** The languages the screens come in. English is the fallback for anything not yet translated. */
export const LANGS = ["en", "kn", "hi", "ta", "te"] as const;
export type Lang = (typeof LANGS)[number];

/** A script sample (not a word) is what the switch shows, so it can be read without reading English. */
export const LANG_SAMPLE: Record<Lang, string> = { en: "A", kn: "ಕ", hi: "अ", ta: "அ", te: "అ" };
/** The language's own name, for screen readers and the tooltip. */
export const LANG_NAME: Record<Lang, string> = {
  en: "English",
  kn: "ಕನ್ನಡ",
  hi: "हिन्दी",
  ta: "தமிழ்",
  te: "తెలుగు",
};

const KEY = "harabhara.lang";
const listeners = new Set<() => void>();

function read(): Lang {
  try {
    const saved = window.localStorage.getItem(KEY);
    if (saved && (LANGS as readonly string[]).includes(saved)) return saved as Lang;
  } catch {
    /* private mode: stay on English */
  }
  return "en";
}

let current: Lang = read();

export function getLang(): Lang {
  return current;
}

export function setLang(next: Lang): void {
  if (next === current) return;
  current = next;
  try {
    window.localStorage.setItem(KEY, next);
  } catch {
    /* not saved, still switched for this visit */
  }
  document.documentElement.lang = next;
  listeners.forEach((l) => l());
}

export function useLang(): Lang {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    getLang,
    getLang,
  );
}
