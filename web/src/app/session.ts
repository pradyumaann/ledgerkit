import { useSyncExternalStore } from "react";

/**
 * Who the browser is acting as.
 *
 * `token` is the bearer token when the server requires one (kept for the tab only).
 * `actAs` lets a human preview what an agent experiences: with "agent", postings are
 * held for approval. The server only ever honours this as a reduction of rights.
 */
export type Session = {
  token: string | null;
  /** The last token tried was refused by the server. */
  tokenRejected: boolean;
  actAs: "user" | "agent";
  theme: "light" | "dark";
};

const TOKEN_KEY = "ledgerkit.token";
const ACT_AS_KEY = "ledgerkit.actAs";
const THEME_KEY = "ledgerkit.theme";

function read(storage: Storage, key: string): string | null {
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

function write(storage: Storage, key: string, value: string | null): void {
  try {
    if (value === null) storage.removeItem(key);
    else storage.setItem(key, value);
  } catch {
    // Storage can be unavailable (private mode); the session then lasts for the page only.
  }
}

let session: Session = {
  token: read(sessionStorage, TOKEN_KEY),
  tokenRejected: false,
  actAs: read(localStorage, ACT_AS_KEY) === "agent" ? "agent" : "user",
  theme: document.documentElement.dataset.theme === "dark" ? "dark" : "light",
};

const listeners = new Set<() => void>();

function update(changes: Partial<Session>): void {
  session = { ...session, ...changes };
  listeners.forEach((listener) => listener());
}

export function getSession(): Session {
  return session;
}

export function setToken(token: string): void {
  write(sessionStorage, TOKEN_KEY, token);
  update({ token, tokenRejected: false });
}

/** The server refused the request: forget the token and ask again. */
export function rejectToken(): void {
  write(sessionStorage, TOKEN_KEY, null);
  update({ token: null, tokenRejected: session.token !== null || session.tokenRejected });
}

export function setActAs(actAs: Session["actAs"]): void {
  write(localStorage, ACT_AS_KEY, actAs);
  update({ actAs });
}

export function setTheme(theme: Session["theme"]): void {
  write(localStorage, THEME_KEY, theme);
  document.documentElement.dataset.theme = theme;
  update({ theme });
}

export function useSession(): Session {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    getSession,
  );
}
