import { useCallback, useEffect, useState } from "react";
import { api, getMeta } from "../api/client";
import { ErrorBox, Field, Modal, Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { fmtDate } from "../utils/format";

export default function AdminUsers() {
  const { user: me } = useAuth();
  const toast = useToast();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [roles, setRoles] = useState(["Admin", "Analyst"]);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ username: "", email: "", full_name: "", password: "", role: "Analyst" });
  const [formError, setFormError] = useState("");

  const load = useCallback(() => {
    setError("");
    api.get("/users", { page_size: 100 }).then(setData).catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);
  useEffect(() => { getMeta().then((m) => setRoles(m.roles)).catch(() => {}); }, []);

  async function patch(u, changes, message) {
    try {
      await api.patch(`/users/${u.id}`, changes);
      toast(message);
      load();
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function create(e) {
    e.preventDefault();
    setFormError("");
    try {
      await api.post("/users", form);
      toast(`User ${form.username} created`);
      setShow(false);
      setForm({ username: "", email: "", full_name: "", password: "", role: "Analyst" });
      load();
    } catch (err) {
      setFormError(err.message);
    }
  }

  if (error) return <ErrorBox error={error} onRetry={load} />;
  if (!data) return <Spinner />;

  return (
    <div className="page">
      <div className="page-head">
        <h2>User management</h2>
        <button className="btn btn-primary" onClick={() => setShow(true)}>Create user</button>
      </div>
      <div className="card flush">
        <div className="table-wrap">
          <table>
            <thead><tr><th>User</th><th>Email</th><th>Role</th><th>Status</th><th>Last login</th><th>Actions</th></tr></thead>
            <tbody>
              {data.items.map((u) => {
                const self = u.id === me.id;
                return (
                  <tr key={u.id}>
                    <td><strong>{u.full_name}</strong><br /><small>{u.username}{self ? " (you)" : ""}</small></td>
                    <td>{u.email}</td>
                    <td>
                      <select value={u.role} disabled={self} onChange={(e) => patch(u, { role: e.target.value }, `${u.username} is now ${e.target.value}`)}>
                        {roles.map((r) => <option key={r}>{r}</option>)}
                      </select>
                    </td>
                    <td><span className={`badge ${u.is_active ? "badge-status-resolved" : "badge-sev-critical"}`}>{u.is_active ? "Active" : "Disabled"}</span></td>
                    <td>{u.last_login ? fmtDate(u.last_login) : "Never"}</td>
                    <td>
                      <button className="btn btn-sm" disabled={self}
                        onClick={() => patch(u, { is_active: !u.is_active }, `${u.username} ${u.is_active ? "disabled" : "enabled"}`)}>
                        {u.is_active ? "Disable" : "Enable"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {show && (
        <Modal title="Create user" onClose={() => setShow(false)}>
          <form onSubmit={create} className="form-grid">
            <ErrorBox error={formError} />
            <Field label="Full name"><input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></Field>
            <Field label="Username"><input required minLength={3} value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></Field>
            <Field label="Email"><input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
            <Field label="Temporary password" hint="At least 8 characters with a letter and a digit">
              <input type="password" required minLength={8} maxLength={72} autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            </Field>
            <Field label="Role"><select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>{roles.map((r) => <option key={r}>{r}</option>)}</select></Field>
            <div className="form-actions">
              <button type="button" className="btn" onClick={() => setShow(false)}>Cancel</button>
              <button className="btn btn-primary">Create</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
