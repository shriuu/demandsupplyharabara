import type { LoginResponse } from "./types";

// The token lives in memory and in sessionStorage (cleared when the tab closes).
const KEY = "harabhara.session";
let current: LoginResponse | null = null;
let onExpired: () => void = () => undefined;

export function loadSession(): LoginResponse | null {
  if (current) return current;
  try {
    const raw = window.sessionStorage.getItem(KEY);
    if (raw) current = JSON.parse(raw) as LoginResponse;
  } catch {
    current = null;
  }
  return current;
}

export function saveSession(session: LoginResponse): void {
  current = session;
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(session));
  } catch {
    // Storage can be blocked; the in-memory copy still works for this page.
  }
}

export function clearSession(): void {
  current = null;
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    // nothing to clear
  }
}

/** The app registers what to do when the server says the sign-in is no longer valid (401). */
export function setOnExpired(handler: () => void): void {
  onExpired = handler;
}

export function signalExpired(): void {
  clearSession();
  onExpired();
}

let onSwitchedOff: () => void = () => undefined;

/** The app registers what to do when the server answers 423 (suggestions switched off). */
export function setOnSwitchedOff(handler: () => void): void {
  onSwitchedOff = handler;
}

export function signalSwitchedOff(): void {
  onSwitchedOff();
}
