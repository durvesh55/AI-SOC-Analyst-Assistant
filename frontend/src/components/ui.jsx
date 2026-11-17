// Small reusable UI building blocks shared by every page.
import { useEffect, useState } from "react";
import { pages } from "../utils/format";

export const slug = (s) => String(s || "").toLowerCase().replace(/\s+/g, "-");

export function Badge({ value, kind }) {
  return <span className={`badge badge-${kind}-${slug(value)}`}>{value}</span>;
}
export const SeverityBadge = ({ value }) => <Badge value={value} kind="sev" />;
export const StatusBadge = ({ value }) => <Badge value={value} kind="status" />;

export function Spinner({ label = "Loading..." }) {
  return <div className="spinner-wrap"><div className="spinner" /> <span>{label}</span></div>;
}

export function ErrorBox({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="alert-box alert-error" role="alert">
      <span>{error}</span>
      {onRetry && <button className="btn btn-sm" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function Empty({ children }) {
  return <div className="empty">{children}</div>;
}

export function Card({ title, actions, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          <h3>{title}</h3>
          <div className="card-actions">{actions}</div>
        </header>
      )}
      {children}
    </section>
  );
}

export function Field({ label, children, hint }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <small className="hint">{hint}</small>}
    </label>
  );
}

export function PasswordInput(props) {
  const [show, setShow] = useState(false);
  return (
    <span className="pw-wrap">
      <input {...props} type={show ? "text" : "password"} />
      <button type="button" className="pw-eye" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"} title={show ? "Hide password" : "Show password"}>
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
          <circle cx="12" cy="12" r="3" />
          {show && <path d="M3 3l18 18" />}
        </svg>
      </button>
    </span>
  );
}

export function Modal({ title, onClose, children, wide }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "modal-wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <header className="modal-head">
          <h3>{title}</h3>
          <button className="icon-btn" onClick={onClose} aria-label="Close">x</button>
        </header>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

export function Pagination({ page, pageSize, total, onChange }) {
  const last = pages(total, pageSize);
  if (total <= pageSize) return <div className="pagination"><small>{total} result{total === 1 ? "" : "s"}</small></div>;
  return (
    <div className="pagination">
      <small>{total} results</small>
      <button className="btn btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>Prev</button>
      <span>Page {page} of {last}</span>
      <button className="btn btn-sm" disabled={page >= last} onClick={() => onChange(page + 1)}>Next</button>
    </div>
  );
}

export function MitreList({ items }) {
  if (!items || items.length === 0) return <Empty>No ATT&amp;CK techniques were suggested by the rules.</Empty>;
  return (
    <div className="mitre-list">
      <p className="hint">
        Rule-based <strong>suggestions</strong> only - not confirmed attacker behaviour. An analyst must validate them.
      </p>
      {items.map((m) => (
        <div className="mitre-item" key={m.technique_id}>
          <div className="mitre-top">
            <a href={`https://attack.mitre.org/techniques/${m.technique_id.replace(".", "/")}/`} target="_blank" rel="noreferrer noopener" className="mitre-id">
              {m.technique_id}
            </a>
            <strong>{m.technique_name}</strong>
            <span className="tag">{m.tactic}</span>
            <span className="tag tag-muted">Suggested - {m.confidence} confidence</span>
          </div>
          <p>{m.reason}</p>
        </div>
      ))}
    </div>
  );
}
