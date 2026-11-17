import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, getMeta } from "../api/client";
import { Empty, ErrorBox, Pagination, SeverityBadge, Spinner, StatusBadge } from "../components/ui";
import { fmtDate } from "../utils/format";

const PAGE_SIZE = 15;

export default function Cases() {
  const [params, setParams] = useSearchParams();
  const [meta, setMeta] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState(params.get("q") || "");
  const navigate = useNavigate();

  const filters = {
    status: params.get("status") || "",
    severity: params.get("severity") || "",
    assigned_to: params.get("assigned_to") || "",
    q: params.get("q") || "",
  };
  const page = Number(params.get("page") || 1);
  const setFilter = (k, v) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v); else next.delete(k);
    next.delete("page");
    setParams(next);
  };

  useEffect(() => { getMeta().then(setMeta).catch((e) => setError(e.message)); }, []);
  const load = useCallback(() => {
    setError("");
    api.get("/cases", { ...filters, page, page_size: PAGE_SIZE }).then(setData).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);
  useEffect(load, [load]);

  if (!meta) return error ? <ErrorBox error={error} /> : <Spinner />;

  return (
    <div className="page">
      <div className="page-head">
        <h2>Cases</h2>
        <Link className="btn btn-primary" to="/alerts">Open a case from an alert</Link>
      </div>

      <form className="filters" onSubmit={(e) => { e.preventDefault(); setFilter("q", q.trim()); }}>
        <input className="grow" placeholder="Search case id, title, alert id..." value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={filters.status} onChange={(e) => setFilter("status", e.target.value)} aria-label="Status">
          <option value="">All statuses</option>{meta.case_statuses.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={filters.severity} onChange={(e) => setFilter("severity", e.target.value)} aria-label="Severity">
          <option value="">All severities</option>{meta.severities.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={filters.assigned_to} onChange={(e) => setFilter("assigned_to", e.target.value)} aria-label="Assignee">
          <option value="">Anyone</option><option value="me">Assigned to me</option><option value="unassigned">Unassigned</option>
        </select>
        <button className="btn">Search</button>
        <button type="button" className="btn" onClick={() => { setQ(""); setParams({}); }}>Clear</button>
      </form>

      <ErrorBox error={error} onRetry={load} />
      {!data ? <Spinner /> : data.items.length === 0 ? <Empty>No cases yet. Open one from an alert's detail page.</Empty> : (
        <div className="card flush">
          <div className="table-wrap">
            <table className="clickable">
              <thead><tr><th>Case</th><th>Title</th><th>Severity</th><th>Status</th><th>Alerts</th><th>Assignee</th><th>Updated</th></tr></thead>
              <tbody>
                {data.items.map((c) => (
                  <tr key={c.id} onClick={() => navigate(`/cases/${c.id}`)}>
                    <td><Link to={`/cases/${c.id}`} onClick={(e) => e.stopPropagation()}>{c.case_id}</Link></td>
                    <td>{c.title}</td>
                    <td><SeverityBadge value={c.severity} /></td>
                    <td><StatusBadge value={c.status} /></td>
                    <td>{c.alert_ids.length}</td>
                    <td>{c.assigned_to_user ? c.assigned_to_user.username : <span className="muted">Unassigned</span>}</td>
                    <td>{fmtDate(c.updated_at)}</td>
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
