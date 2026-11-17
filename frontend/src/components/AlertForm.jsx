import { useState } from "react";
import { ErrorBox, Field } from "./ui";

const blankToNull = (v) => (v && v.trim() ? v.trim() : null);

// Used for both "New alert" and "Edit alert". `meta` holds the severity/category lists from the API.
export default function AlertForm({ meta, initial, onSubmit, submitLabel, onCancel }) {
  const [f, setF] = useState({
    title: initial?.title || "",
    description: initial?.description || "",
    severity: initial?.severity || "Medium",
    category: initial?.category || "Other",
    source_ip: initial?.source_ip || "",
    destination_ip: initial?.destination_ip || "",
    hostname: initial?.hostname || "",
    affected_user: initial?.affected_user || "",
    indicators: (initial?.indicators || []).join(", "),
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await onSubmit({
        title: f.title.trim(),
        description: f.description,
        severity: f.severity,
        category: f.category,
        source_ip: blankToNull(f.source_ip),
        destination_ip: blankToNull(f.destination_ip),
        hostname: blankToNull(f.hostname),
        affected_user: blankToNull(f.affected_user),
        indicators: f.indicators.split(/[,\n]/).map((s) => s.trim()).filter(Boolean),
      });
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="form-grid">
      <ErrorBox error={error} />
      <Field label="Title"><input value={f.title} onChange={set("title")} required minLength={3} maxLength={200} /></Field>
      <div className="row">
        <Field label="Severity">
          <select value={f.severity} onChange={set("severity")}>{meta.severities.map((s) => <option key={s}>{s}</option>)}</select>
        </Field>
        <Field label="Category">
          <select value={f.category} onChange={set("category")}>{meta.categories.map((s) => <option key={s}>{s}</option>)}</select>
        </Field>
      </div>
      <Field label="Description"><textarea rows={4} value={f.description} onChange={set("description")} maxLength={5000} /></Field>
      <div className="row">
        <Field label="Source IP"><input value={f.source_ip} onChange={set("source_ip")} placeholder="203.0.113.5" /></Field>
        <Field label="Destination IP"><input value={f.destination_ip} onChange={set("destination_ip")} placeholder="10.0.0.12" /></Field>
      </div>
      <div className="row">
        <Field label="Hostname"><input value={f.hostname} onChange={set("hostname")} maxLength={255} /></Field>
        <Field label="Affected user"><input value={f.affected_user} onChange={set("affected_user")} maxLength={100} /></Field>
      </div>
      <Field label="Indicators" hint="Comma separated: hashes, domains, commands, ...">
        <input value={f.indicators} onChange={set("indicators")} />
      </Field>
      <div className="form-actions">
        <button type="button" className="btn" onClick={onCancel}>Cancel</button>
        <button className="btn btn-primary" disabled={busy}>{busy ? "Saving..." : submitLabel}</button>
      </div>
    </form>
  );
}
