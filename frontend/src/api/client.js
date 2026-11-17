// Thin wrapper around fetch(): adds the JWT, parses errors, and signals expired sessions.
const BASE = (import.meta.env.VITE_API_BASE || "/api").replace(/\/$/, "");
const TOKEN_KEY = "soc_token";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function errorMessage(data, status) {
  const d = data && data.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d.map((e) => `${(e.loc || []).filter((x) => x !== "body").join(".")}: ${e.msg}`).join("; ");
  }
  return `Request failed (${status})`;
}

function query(params) {
  const q = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") q.append(k, v);
  });
  const s = q.toString();
  return s ? `?${s}` : "";
}

async function request(method, path, { body, params, raw, auth = true } = {}) {
  const headers = {};
  const token = tokenStore.get();
  if (auth && token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let res;
  try {
    res = await fetch(`${BASE}${path}${query(params)}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Cannot reach the server. Is the backend running?", 0);
  }

  if (res.status === 401 && auth) {
    tokenStore.clear();
    window.dispatchEvent(new Event("auth:expired"));
  }
  if (!res.ok) {
    let data = null;
    try {
      data = await res.json();
    } catch {
      /* not JSON */
    }
    throw new ApiError(errorMessage(data, res.status), res.status);
  }
  if (raw) return res;
  return res.json();
}

export const api = {
  get: (path, params) => request("GET", path, { params }),
  post: (path, body, opts) => request("POST", path, { body: body ?? {}, ...opts }),
  patch: (path, body) => request("PATCH", path, { body }),
  // Downloads a file with the Authorization header (a plain <a href> cannot send it).
  async download(path, fallbackName) {
    const res = await request("GET", path, { raw: true });
    const blob = await res.blob();
    const match = /filename="?([^"]+)"?/.exec(res.headers.get("Content-Disposition") || "");
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = match ? match[1] : fallbackName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};

let metaCache = null;
export async function getMeta() {
  if (!metaCache) metaCache = await api.get("/meta");
  return metaCache;
}
