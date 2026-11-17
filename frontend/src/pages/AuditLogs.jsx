import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { Empty, ErrorBox, Pagination, Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { actionLabel, fmtDate } from "../utils/format";

const PAGE_SIZE = 25;

function details(d) {
  if (!d || Object.keys(d).length === 0) return "";
  return Object.entries(d).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : typeof v === "object" ? JSON.stringify(v) : v}`).join(" | ");
}

export default function AuditLogs() {
  const { isAdmin } = useAuth();
  const [params, setParams] = useSearchParams();
  const [actions, setActions] = useState([]);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState(params.get("q") || "");
  const [actor, setActor] = useState(params.get("actor") || "");

  const filters = {
    action: params.get("action") || "", actor: params.get("actor") || "", q: params.get("q") || "",
    date_from: params.get("date_from") || "", date_to: params.get("date_to") || "",
  };
  const page = Number(params.get("page") || 1);
  const setFilter = (k, v) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v); else next.delete(k);
    next.delete("page");
    setParams(next);
  };

  useEffect(() => { api.get("/audit-logs/actions").then(setActions).catch(() => {}); }, []);
  const load = useCallback(() => {
    setError("");
    api.get("/audit-logs", { ...filters, page, page_size: PAGE_SIZE }).then(setData).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);
  useEffect(load, [load]);

  return (
    <div className="page">
      <div className="page-head"><h2>Audit logs</h2></div>
      <p className="hint">
        {isAdmin ? "All security-relevant actions across the platform. Entries are append-only and cannot be edited or deleted."
          : "You can see your own activity. Administrators can see everyone's. Entries cannot be edited or deleted."}
      </p>
      <form className="filters" onSubmit={(e) => { e.preventDefault(); const n = new URLSearchParams(params); q.trim() ? n.set("q", q.trim()) : n.delete("q"); actor.trim() ? n.set("actor", actor.trim()) : n.delete("actor"); n.delete("page"); setParams(n); }}>
        <select value={filters.action} onChange={(e) => setFilter("action", e.target.value)} aria-label="Action">
          <option value="">All actions</option>{actions.map((a) => <option key={a} value={a}>{actionLabel(a)}</option>)}
        </select>
        {isAdmin && <input placeholder="Actor username" value={actor} onChange={(e) => setActor(e.target.value)} />}
        <input placeholder="Resource id (e.g. CASE-000001)" value={q} onChange={(e) => setQ(e.target.value)} />
        <label className="inline">From <input type="date" value={filters.date_from} onChange={(e) => setFilter("date_from", e.target.value)} /></label>
        <label className="inline">To <input type="date" value={filters.date_to} onChange={(e) => setFilter("date_to", e.target.value)} /></label>
        <button className="btn">Search</button>
        <button type="button" className="btn" onClick={() => { setQ(""); setActor(""); setParams({}); }}>Clear</button>
      </form>
      <ErrorBox error={error} onRetry={load} />
      {!data ? <Spinner /> : data.items.length === 0 ? <Empty>No audit entries match.</Empty> : (
        <div className="card flush">
          <div className="table-wrap">
            <table>
              <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Resource</th><th>Details</th><th>IP</th></tr></thead>
              <tbody>
                {data.items.map((e) => (
                  <tr key={e.id}>
                    <td className="nowrap">{fmtDate(e.timestamp)}</td>
                    <td>{e.actor_username}</td>
                    <td><span className="tag">{actionLabel(e.action)}</span></td>
                    <td>{e.resource_id ? <code>{e.resource_id}</code> : "-"}</td>
                    <td className="wrap small">{details(e.details)}</td>
                    <td>{e.ip || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={data.page} pageSize={data.page_size} total={data.total}
            onChange={(p) => { const n = new URLSearchParams(params); n.set("page", p); setParams(n); }} />
        </div>
      )}
    </div>
  );
}
