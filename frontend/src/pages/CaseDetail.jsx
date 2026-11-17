import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { Card, Empty, ErrorBox, Field, MitreList, Modal, SeverityBadge, Spinner, StatusBadge } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { fmtDate, userLabel } from "../utils/format";

export default function CaseDetail() {
  const { id } = useParams();
  const { user, isAdmin } = useAuth();
  const toast = useToast();
  const [c, setCase] = useState(null);
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [findings, setFindings] = useState("");
  const [conclusion, setConclusion] = useState("");
  const [modal, setModal] = useState(null); // "close" | "reopen"
  const [form, setForm] = useState({ text: "", outcome: "Resolved" });
  const [busy, setBusy] = useState(false);

  const apply = (data) => {
    setCase(data);
    setFindings(data.findings || "");
    setConclusion(data.conclusion || "");
  };
  const load = useCallback(() => {
    setError("");
    api.get(`/cases/${id}`).then(apply).catch((e) => setError(e.message));
  }, [id]);
  useEffect(load, [load]);
  useEffect(() => { api.get("/users/assignable").then(setUsers).catch(() => {}); }, []);

  if (error && !c) return <ErrorBox error={error} onRetry={load} />;
  if (!c) return <Spinner />;

  const closed = c.status === "Closed";
  const mine = c.assigned_to === user.id;
  const canWork = (isAdmin || mine) && !closed;
  const canClaim = !closed && (isAdmin || !c.assigned_to);

  async function run(fn, okMessage) {
    setBusy(true);
    try {
      apply(await fn());
      if (okMessage) toast(okMessage);
      return true;
    } catch (e) {
      toast(e.message, "error");
      return false;
    } finally {
      setBusy(false);
    }
  }

  const addNote = async (e) => {
    e.preventDefault();
    if (await run(() => api.post(`/cases/${id}/notes`, { text: note }), "Note added")) setNote("");
  };
  const saveText = () => run(() => api.patch(`/cases/${id}`, { findings, conclusion }), "Findings saved");
  const setStatus = (status) => run(() => api.patch(`/cases/${id}`, { status }), `Status set to ${status}`);
  const assign = (assignee_id) => run(() => api.post(`/cases/${id}/assign`, { assignee_id: assignee_id || null }), "Assignment updated");

  async function submitModal(e) {
    e.preventDefault();
    const ok = modal === "close"
      ? await run(() => api.post(`/cases/${id}/close`, { conclusion: form.text, outcome: form.outcome }), "Case closed")
      : await run(() => api.post(`/cases/${id}/reopen`, { reason: form.text }), "Case reopened");
    if (ok) setModal(null);
  }

  async function downloadReport() {
    try {
      await api.download(`/cases/${id}/report`, `${c.case_id}-report.pdf`);
      toast("Report downloaded");
    } catch (e) {
      toast(e.message, "error");
    }
  }

  const openModal = (kind) => { setForm({ text: kind === "close" ? conclusion : "", outcome: "Resolved" }); setModal(kind); };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <Link to="/cases" className="back">&larr; Cases</Link>
          <h2>{c.case_id}: {c.title}</h2>
          <div className="badges"><SeverityBadge value={c.severity} /><StatusBadge value={c.status} />{c.outcome && <span className="tag">Outcome: {c.outcome}</span>}</div>
        </div>
        <div className="head-actions">
          <button className="btn" onClick={downloadReport}>Download PDF report</button>
          {canWork && <button className="btn btn-primary" onClick={() => openModal("close")}>Close case</button>}
          {closed && isAdmin && <button className="btn btn-primary" onClick={() => openModal("reopen")}>Reopen case</button>}
        </div>
      </div>
      {closed && <div className="alert-box alert-info">This case is closed{c.closed_at ? ` (${fmtDate(c.closed_at)})` : ""}. {isAdmin ? "You can reopen it." : "Only an administrator can reopen it."}</div>}
      {!closed && !canWork && <div className="alert-box alert-info">This case is assigned to {userLabel(c.assigned_to_user)}. You can read it, but only they or an admin can change it.</div>}

      <div className="grid-2">
        <Card title="Summary">
          <dl className="kvs">
            <div className="kv"><dt>Status</dt><dd>
              {canWork ? (
                <select value={c.status} disabled={busy} onChange={(e) => setStatus(e.target.value)}>
                  <option>Open</option><option>In Progress</option>
                </select>
              ) : c.status}
            </dd></div>
            <div className="kv"><dt>Assigned to</dt><dd>
              {isAdmin && !closed ? (
                <select value={c.assigned_to || ""} disabled={busy} onChange={(e) => assign(e.target.value)}>
                  <option value="">Unassigned</option>
                  {users.map((u) => <option key={u.id} value={u.id}>{userLabel(u)}</option>)}
                </select>
              ) : (
                <>
                  {userLabel(c.assigned_to_user)}{" "}
                  {canClaim && !mine && <button className="btn btn-sm" onClick={() => assign(user.id)}>Assign to me</button>}
                </>
              )}
            </dd></div>
            <div className="kv"><dt>Created</dt><dd>{fmtDate(c.created_at)} by {c.created_by_user?.username}</dd></div>
            <div className="kv"><dt>Last updated</dt><dd>{fmtDate(c.updated_at)}</dd></div>
            {closed && <div className="kv"><dt>Closed by</dt><dd>{c.closed_by_user?.username} - {fmtDate(c.closed_at)}</dd></div>}
          </dl>
        </Card>

        <Card title={`Linked alerts (${c.alerts.length})`}>
          <ul className="plain">
            {c.alerts.map((a) => (
              <li key={a.id}>
                <Link to={`/alerts/${a.id}`}>{a.alert_id}</Link> {a.title}
                <div className="badges"><SeverityBadge value={a.severity} /><StatusBadge value={a.status} /></div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title="MITRE ATT&CK suggestions"><MitreList items={c.mitre_suggestions} /></Card>

      <div className="grid-2">
        <Card title="Findings &amp; conclusion">
          <Field label="Findings"><textarea rows={5} value={findings} disabled={!canWork} onChange={(e) => setFindings(e.target.value)} maxLength={10000} placeholder="What did the investigation uncover?" /></Field>
          <Field label="Conclusion"><textarea rows={4} value={conclusion} disabled={!canWork} onChange={(e) => setConclusion(e.target.value)} maxLength={10000} placeholder="Summary / recommended actions" /></Field>
          {canWork && <button className="btn btn-primary" disabled={busy || (findings === (c.findings || "") && conclusion === (c.conclusion || ""))} onClick={saveText}>Save findings</button>}
        </Card>

        <Card title={`Investigation notes (${c.notes.length})`}>
          {canWork && (
            <form onSubmit={addNote} className="note-form">
              <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add an analyst note..." required maxLength={5000} />
              <button className="btn btn-primary" disabled={busy || !note.trim()}>Add note</button>
            </form>
          )}
          {c.notes.length === 0 ? <Empty>No notes yet.</Empty> : (
            <ul className="notes">
              {[...c.notes].reverse().map((n) => (
                <li key={n.id}><div className="note-meta"><strong>{n.author_username}</strong> <small>{fmtDate(n.created_at)}</small></div><p>{n.text}</p></li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title="Investigation timeline">
        <ol className="timeline">
          {[...c.timeline].reverse().map((t, i) => (
            <li key={i}><div className="tl-dot" /><div><strong>{t.action}</strong> <small>by {t.by_username} - {fmtDate(t.at)}</small>{t.detail && <p>{t.detail}</p>}</div></li>
          ))}
        </ol>
      </Card>

      {modal && (
        <Modal title={modal === "close" ? `Close ${c.case_id}` : `Reopen ${c.case_id}`} onClose={() => setModal(null)}>
          <form onSubmit={submitModal} className="form-grid">
            {modal === "close" && (
              <Field label="Outcome" hint="Updates the status of all linked alerts">
                <select value={form.outcome} onChange={(e) => setForm({ ...form, outcome: e.target.value })}>
                  <option>Resolved</option><option>False Positive</option>
                </select>
              </Field>
            )}
            <Field label={modal === "close" ? "Conclusion (required)" : "Reason for reopening (required)"}>
              <textarea rows={4} required minLength={modal === "close" ? 5 : 3} value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} />
            </Field>
            <div className="form-actions">
              <button type="button" className="btn" onClick={() => setModal(null)}>Cancel</button>
              <button className="btn btn-primary" disabled={busy}>{modal === "close" ? "Close case" : "Reopen case"}</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
