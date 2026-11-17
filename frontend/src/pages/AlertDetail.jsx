import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, getMeta } from "../api/client";
import AlertForm from "../components/AlertForm";
import { Card, ErrorBox, MitreList, Modal, SeverityBadge, Spinner, StatusBadge } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { fmtDate, userLabel } from "../utils/format";

function Row({ k, v }) {
  return <div className="kv"><dt>{k}</dt><dd>{v || <span className="muted">-</span>}</dd></div>;
}

export default function AlertDetail() {
  const { id } = useParams();
  const { user, isAdmin } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [alert, setAlert] = useState(null);
  const [meta, setMeta] = useState(null);
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);

  const load = useCallback(() => {
    setError("");
    api.get(`/alerts/${id}`).then(setAlert).catch((e) => setError(e.message));
  }, [id]);
  useEffect(load, [load]);
  useEffect(() => {
    getMeta().then(setMeta).catch(() => {});
    api.get("/users/assignable").then(setUsers).catch(() => {});
  }, []);

  if (error && !alert) return <ErrorBox error={error} onRetry={load} />;
  if (!alert || !meta) return <Spinner />;

  const ownerId = alert.assigned_to;
  const canEdit = isAdmin || !ownerId || ownerId === user.id;

  async function act(fn, okMessage) {
    try {
      const updated = await fn();
      if (updated) setAlert((a) => ({ ...a, ...updated }));
      if (okMessage) toast(okMessage);
      load();
    } catch (e) {
      toast(e.message, "error");
    }
  }

  const setStatus = (status) => act(() => api.patch(`/alerts/${id}`, { status }), `Status set to ${status}`);
  const assign = (assignee_id) => act(() => api.post(`/alerts/${id}/assign`, { assignee_id: assignee_id || null }), "Assignment updated");

  async function createCase() {
    try {
      const c = await api.post("/cases", { alert_ids: [id] });
      toast(`Created ${c.case_id}`);
      navigate(`/cases/${c.id}`);
    } catch (e) {
      toast(e.message, "error");
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <Link to="/alerts" className="back">&larr; Alerts</Link>
          <h2>{alert.alert_id}: {alert.title}</h2>
          <div className="badges"><SeverityBadge value={alert.severity} /><StatusBadge value={alert.status} /><span className="tag">{alert.category}</span></div>
        </div>
        <div className="head-actions">
          {canEdit && <button className="btn" onClick={() => setEditing(true)}>Edit</button>}
          {alert.case
            ? <Link className="btn btn-primary" to={`/cases/${alert.case.id}`}>Open {alert.case.case_id}</Link>
            : <button className="btn btn-primary" onClick={createCase}>Create investigation case</button>}
        </div>
      </div>
      {!canEdit && <div className="alert-box alert-info">This alert is assigned to {userLabel(alert.assigned_to_user)}. Only they or an admin can change it.</div>}

      <div className="grid-2">
        <Card title="Details">
          <p className="desc">{alert.description || <span className="muted">No description.</span>}</p>
          <dl className="kvs">
            <Row k="Source IP" v={alert.source_ip} />
            <Row k="Destination IP" v={alert.destination_ip} />
            <Row k="Hostname" v={alert.hostname} />
            <Row k="Affected user" v={alert.affected_user} />
            <Row k="Indicators" v={alert.indicators?.length ? alert.indicators.join(", ") : ""} />
            <Row k="Event time" v={fmtDate(alert.event_time)} />
            <Row k="Created" v={fmtDate(alert.created_at)} />
            <Row k="Created by" v={alert.created_by_user?.username} />
          </dl>
        </Card>

        <Card title="Workflow">
          <label className="field">
            <span className="field-label">Status</span>
            <select value={alert.status} disabled={!canEdit} onChange={(e) => setStatus(e.target.value)}>
              {meta.alert_statuses.map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Assigned analyst</span>
            {isAdmin ? (
              <select value={ownerId || ""} onChange={(e) => assign(e.target.value)}>
                <option value="">Unassigned</option>
                {users.map((u) => <option key={u.id} value={u.id}>{userLabel(u)} - {u.role}</option>)}
              </select>
            ) : (
              <div className="inline-actions">
                <strong>{userLabel(alert.assigned_to_user)}</strong>
                {canEdit && ownerId !== user.id && <button className="btn btn-sm" onClick={() => assign(user.id)}>Assign to me</button>}
                {ownerId === user.id && <button className="btn btn-sm" onClick={() => assign(null)}>Release</button>}
              </div>
            )}
          </label>
          {alert.case && <p>Linked case: <Link to={`/cases/${alert.case.id}`}>{alert.case.case_id}</Link> ({alert.case.status})</p>}
        </Card>
      </div>

      <Card title="MITRE ATT&CK suggestions"><MitreList items={alert.mitre_suggestions} /></Card>

      <Card title="Alert history">
        <ol className="timeline">
          {[...alert.history].reverse().map((h, i) => (
            <li key={i}>
              <div className="tl-dot" />
              <div><strong>{h.action}</strong> <small>by {h.by_username} - {fmtDate(h.at)}</small>{h.detail && <p>{h.detail}</p>}</div>
            </li>
          ))}
        </ol>
      </Card>

      {editing && (
        <Modal title={`Edit ${alert.alert_id}`} onClose={() => setEditing(false)} wide>
          <AlertForm meta={meta} initial={alert} submitLabel="Save changes" onCancel={() => setEditing(false)}
            onSubmit={async (body) => { const u = await api.patch(`/alerts/${id}`, body); setAlert((a) => ({ ...a, ...u })); toast("Alert updated"); setEditing(false); load(); }} />
        </Modal>
      )}
    </div>
  );
}
