import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Logo from "../components/Logo";
import { ErrorBox, Field, PasswordInput } from "../components/ui";

export default function Login() {
  const { login, notice } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(identifier, password);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <div className="brand brand-center">
          <Logo size={56} />
        </div>
        <h2>AlertDesk</h2>
        <p className="hint center">AI SOC Analyst Assistant</p>
        <p className="hint center">Sign in to manage alerts and investigations.</p>
        {notice && <div className="alert-box alert-info">{notice}</div>}
        <ErrorBox error={error} />
        <Field label="Username or email">
          <input value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoComplete="username" required autoFocus />
        </Field>
        <Field label="Password">
          <PasswordInput value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
        </Field>
        <button className="btn btn-primary btn-block" disabled={busy}>{busy ? "Signing in..." : "Sign in"}</button>
        <p className="center">No account? <Link to="/register">Register</Link> &nbsp;|&nbsp; <Link to="/">Back to home</Link></p>
        <p className="hint center">Educational project using simulated alerts.</p>
      </form>
    </div>
  );
}
