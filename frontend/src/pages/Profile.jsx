import { useState } from "react";
import { api } from "../api/client";
import { Card, ErrorBox, Field } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { fmtDate } from "../utils/format";

export default function Profile() {
  const { user, setUser, logout } = useAuth();
  const toast = useToast();
  const [profile, setProfile] = useState({ full_name: user.full_name || "", email: user.email });
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const [pErr, setPErr] = useState("");
  const [wErr, setWErr] = useState("");

  async function saveProfile(e) {
    e.preventDefault();
    setPErr("");
    try {
      setUser(await api.patch("/auth/me", profile));
      toast("Profile updated");
    } catch (err) {
      setPErr(err.message);
    }
  }

  async function changePassword(e) {
    e.preventDefault();
    setWErr("");
    if (pw.new_password !== pw.confirm) return setWErr("New passwords do not match");
    try {
      await api.post("/auth/change-password", { current_password: pw.current_password, new_password: pw.new_password });
      await logout("Password changed. Please log in with your new password.");
    } catch (err) {
      setWErr(err.message);
    }
  }

  return (
    <div className="page">
      <div className="page-head"><h2>Profile &amp; settings</h2></div>
      <div className="grid-2">
        <Card title="Account">
          <dl className="kvs">
            <div className="kv"><dt>Username</dt><dd>{user.username}</dd></div>
            <div className="kv"><dt>Role</dt><dd>{user.role}</dd></div>
            <div className="kv"><dt>Member since</dt><dd>{fmtDate(user.created_at)}</dd></div>
            <div className="kv"><dt>Last login</dt><dd>{fmtDate(user.last_login)}</dd></div>
          </dl>
          <form onSubmit={saveProfile} className="form-grid">
            <ErrorBox error={pErr} />
            <Field label="Full name"><input required maxLength={80} value={profile.full_name} onChange={(e) => setProfile({ ...profile, full_name: e.target.value })} /></Field>
            <Field label="Email"><input type="email" required value={profile.email} onChange={(e) => setProfile({ ...profile, email: e.target.value })} /></Field>
            <div className="form-actions"><button className="btn btn-primary">Save profile</button></div>
          </form>
        </Card>
        <Card title="Change password">
          <form onSubmit={changePassword} className="form-grid">
            <ErrorBox error={wErr} />
            <Field label="Current password"><input type="password" required autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
            <Field label="New password" hint="At least 8 characters with a letter and a digit">
              <input type="password" required minLength={8} maxLength={72} autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
            </Field>
            <Field label="Confirm new password"><input type="password" required autoComplete="new-password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} /></Field>
            <div className="form-actions"><button className="btn btn-primary">Change password</button></div>
            <small className="hint">You will be signed out after changing your password.</small>
          </form>
        </Card>
      </div>
    </div>
  );
}
