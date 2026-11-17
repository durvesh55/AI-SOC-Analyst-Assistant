import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, getMeta } from "../api/client";
import AlertForm from "../components/AlertForm";
import { Empty, ErrorBox, Modal, Pagination, SeverityBadge, Spinner, StatusBadge } from "../components/ui";
import { useToast } from "../context/ToastContext";
import { fmtDate } from "../utils/format";

const PAGE_SIZE = 15;

export default function Alerts() {
  const [params, setParams] = useSearchParams();
  const [meta, setMeta] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [selected, setSelected] = useState([]);
  const [q, setQ] = useState(params.get("q") || "");
  const navigate = useNavigate();
  const toast = useToast();

  const filters = {
    severity: params.get("severity") || "",
    status: params.get("status") || "",
    category: params.get("category") || "",
    assigned_to: params.get("assigned_to") || "",
    date_from: params.get("date_from") || "",
    date_to: params.get("date_to") || "",
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
    setSelected([]);
    api.get("/alerts", { ...filters, page, page_size: PAGE_SIZE }).then(setData).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);
  useEffect(load, [load]);

  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  async function createAlert(body) {
    const a = await api.post("/alerts", body);
    toast(`Created ${a.alert_id}`);
    setShowNew(false);
    navigate(`/alerts/${a.id}`);
  }

  async function createCase() {
    try {
      const c = await api.post("/cases", { alert_ids: selected });
      toast(`Created ${c.case_id}`);
      navigate(`/cases/${c.id}`);
    } catch (e) {
      toast(e.message, "error");
    }
  }

  if (!meta) return error ? <ErrorBox error={error} /> : <Spinner />;

  return (
    <div className="page">
      <div className="page-head">
        <h2>Alerts</h2>
        <div className="head-actions">
          {selected.length > 0 && <button className="btn" onClick={createCase}>Create case from {selected.length} selected</button>}
          <button className="btn btn-primary" onClick={() => setShowNew(true)}>New alert</button>
        </div>
      </div>

      <form className="filters" onSubmit={(e) => { e.preventDefault(); setFilter("q", q.trim()); }}>
        <input className="grow" placeholder="Search title, id, IP, host..." value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={filters.severity} onChange={(e) => setFilter("severity", e.target.value)} aria-label="Severity">
          <option value="">All severities</option>{meta.severities.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={filters.status} onChange={(e) => setFilter("status", e.target.value)} aria-label="Status">
          <option value="">All statuses</option>{meta.alert_statuses.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={filters.category} onChange={(e) => setFilter("category", e.target.value)} aria-label="Category">
          <option value="">All categories</option>{meta.categories.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={filters.assigned_to} onChange={(e) => setFilter("assigned_to", e.target.value)} aria-label="Assignee">
          <option value="">Anyone</option><option value="me">Assigned to me</option><option value="unassigned">Unassigned</option>
        </select>
        <label className="inline">From <input type="date" value={filters.date_from} onChange={(e) => setFilter("date_from", e.target.value)} /></label>
        <label className="inline">To <input type="date" value={filters.date_to} onChange={(e) => setFilter("date_to", e.target.value)} /></label>
        <button className="btn">Search</button>
        <button type="button" className="btn" onClick={() => { setQ(""); setParams({}); }}>Clear</button>
      </form>

      <ErrorBox error={error} onRetry={load} />
      {!data ? <Spinner /> : data.items.length === 0 ? <Empty>No alerts match these filters.</Empty> : (
        <div className="card flush">
          <div className="table-wrap">
            <table className="clickable">
              <thead><tr><th></th><th>ID</th><th>Title</th><th>Severity</th><th>Status</th><th>Category</th><th>Assignee</th><th>Created</th></tr></thead>
              <tbody>
                {data.items.map((a) => (
                  <tr key={a.id} onClick={() => navigate(`/alerts/${a.id}`)}>
                    <td onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" disabled={Boolean(a.case_id)} title={a.case_id ? "Already in a case" : "Select"}
                        checked={selected.includes(a.id)} onChange={() => toggle(a.id)} aria-label={`Select ${a.alert_id}`} />
                    </td>
                    <td><Link to={`/alerts/${a.id}`} onClick={(e) => e.stopPropagation()}>{a.alert_id}</Link></td>
                    <td>{a.title}</td>
                    <td><SeverityBadge value={a.severity} /></td>
                    <td><StatusBadge value={a.status} /></td>
                    <td>{a.category}</td>
                    <td>{a.assigned_to_user ? a.assigned_to_user.username : <span className="muted">Unassigned</span>}</td>
                    <td>{fmtDate(a.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={data.page} pageSize={data.page_size} total={data.total}
            onChange={(p) => { const n = new URLSearchParams(params); n.set("page", p); setParams(n); }} />
        </div>
      )}

      {showNew && (
        <Modal title="New alert" onClose={() => setShowNew(false)} wide>
          <AlertForm meta={meta} submitLabel="Create alert" onSubmit={createAlert} onCancel={() => setShowNew(false)} />
        </Modal>
      )}
    </div>
  );
}
