import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Card, Empty, ErrorBox, Spinner, slug } from "../components/ui";
import { actionLabel, fmtDate } from "../utils/format";

function Stat({ label, value, tone, to }) {
  const body = (
    <div className={`stat stat-${tone || "default"}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
  return to ? <Link to={to} className="stat-link">{body}</Link> : body;
}

function Bars({ data, kind }) {
  const max = Math.max(1, ...Object.values(data));
  return (
    <div className="bars">
      {Object.entries(data).map(([k, v]) => (
        <div className="bar-row" key={k}>
          <span className="bar-label">{k}</span>
          <div className="bar-track"><div className={`bar-fill fill-${kind}-${slug(k)}`} style={{ width: `${(v / max) * 100}%` }} /></div>
          <span className="bar-value">{v}</span>
        </div>
      ))}
    </div>
  );
}

function Trend({ points }) {
  const max = Math.max(1, ...points.map((p) => p.count));
  const w = 100 / points.length;
  return (
    <div>
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="trend" role="img" aria-label="Alerts created per day">
        {points.map((p, i) => {
          const h = (p.count / max) * 34;
          return <rect key={p.date} x={i * w + w * 0.15} y={38 - h} width={w * 0.7} height={Math.max(h, 0.6)} rx="0.6" className="trend-bar">
            <title>{`${p.date}: ${p.count}`}</title>
          </rect>;
        })}
      </svg>
      <div className="trend-axis"><span>{points[0].date}</span><span>peak {max}/day</span><span>{points[points.length - 1].date}</span></div>
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError("");
    api.get("/dashboard").then(setData).catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  if (error) return <ErrorBox error={error} onRetry={load} />;
  if (!data) return <Spinner />;

  return (
    <div className="page">
      <div className="page-head">
        <h2>Dashboard</h2>
        <button className="btn" onClick={load}>Refresh</button>
      </div>

      <div className="stats">
        <Stat label="Total alerts" value={data.total_alerts} to="/alerts" />
        <Stat label="Open cases" value={data.open_cases} tone="warn" to="/cases?status=Open" />
        <Stat label="Resolved cases" value={data.resolved_cases} tone="ok" to="/cases?status=Closed" />
        <Stat label="False positives" value={data.false_positives} tone="muted" to="/alerts?status=False Positive" />
      </div>

      <div className="grid-2">
        <Card title="Alerts by severity"><Bars data={data.alerts_by_severity} kind="sev" /></Card>
        <Card title="Alerts by status"><Bars data={data.alerts_by_status} kind="status" /></Card>
      </div>

      <Card title={`Alert trend (last ${data.alert_trend.length} days)`}>
        <Trend points={data.alert_trend} />
      </Card>

      <div className="grid-2">
        <Card title="Analyst workload">
          <div className="table-wrap">
            <table>
              <thead><tr><th>Analyst</th><th>Open alerts</th><th>Open cases</th></tr></thead>
              <tbody>
                {data.analyst_workload.map((w) => (
                  <tr key={w.user_id}><td>{w.full_name || w.username} <small>({w.username})</small></td><td>{w.open_alerts}</td><td>{w.open_cases}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card title="Recent activity" actions={<Link to="/audit">View all</Link>}>
          {data.recent_activities.length === 0 ? <Empty>No activity yet.</Empty> : (
            <ul className="activity">
              {data.recent_activities.map((a) => (
                <li key={a.id}>
                  <strong>{a.actor_username}</strong> {actionLabel(a.action).toLowerCase()}
                  {a.resource_id && <> <code>{a.resource_id}</code></>}
                  <small>{fmtDate(a.timestamp)}</small>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
