import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, getMeta } from "../api/client";
import { ErrorBox, Field } from "../components/ui";
import { useAuth } from "../context/AuthContext";

export default function Register() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [form, setForm] = useState({ username: "", email: "", full_name: "", password: "", confirm: "", invite_code: "" });
  const [inviteRequired, setInviteRequired] = useState(false);
  useEffect(() => { getMeta().then((m) => setInviteRequired(Boolean(m.registration_invite_required))).catch(() => {}); }, []);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError("");
    if (form.password !== form.confirm) return setError("Passwords do not match");
    setBusy(true);
    try {
      const { confirm, invite_code, ...rest } = form;
      const body = inviteRequired ? { ...rest, invite_code } : rest;
      await api.post("/auth/register", body, { auth: false });
      await login(form.username, form.password); // auto sign-in after registering
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <h2>Create an Analyst account</h2>
        <ErrorBox error={error} />
        {inviteRequired && (
          <Field label="Invite code" hint="Registration is invite-only on this server"><input value={form.invite_code} onChange={set("invite_code")} required maxLength={100} autoComplete="off" /></Field>
        )}
        <Field label="Full name"><input value={form.full_name} onChange={set("full_name")} required maxLength={80} /></Field>
        <Field label="Username" hint="3-30 characters: letters, digits, _ . -">
          <input value={form.username} onChange={set("username")} required minLength={3} maxLength={30} autoComplete="username" />
        </Field>
        <Field label="Email"><input type="email" value={form.email} onChange={set("email")} required autoComplete="email" /></Field>
        <Field label="Password" hint="At least 8 characters with a letter and a digit">
          <input type="password" value={form.password} onChange={set("password")} required minLength={8} maxLength={72} autoComplete="new-password" />
        </Field>
        <Field label="Confirm password">
          <input type="password" value={form.confirm} onChange={set("confirm")} required autoComplete="new-password" />
        </Field>
        <button className="btn btn-primary btn-block" disabled={busy}>{busy ? "Creating..." : "Register"}</button>
        <p className="center">Already registered? <Link to="/login">Sign in</Link> &nbsp;|&nbsp; <Link to="/">Home</Link></p>
      </form>
    </div>
  );
}
