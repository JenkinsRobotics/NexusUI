/** localStorage that never throws: it is blocked in some private windows and previews. */
export const ls = {
  get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* blocked */ } },
  remove: (k: string) => { try { localStorage.removeItem(k); } catch { /* blocked */ } },
};
