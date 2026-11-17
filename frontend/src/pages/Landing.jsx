import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import Logo from "../components/Logo";
import "./landing.css";

/* ------------------------------------------------------------------ data */
const FEED = [
  { sev: "Critical", title: "Encoded PowerShell spawned by winword.exe", host: "ws-fin-07", tech: "T1059.001", tactic: "Execution" },
  { sev: "High", title: "47 failed SSH logins for root in 5 minutes", host: "srv-ssh-01", tech: "T1110", tactic: "Credential Access" },
  { sev: "High", title: "Phishing attachment invoice.docm reported", host: "mail-gw", tech: "T1566", tactic: "Initial Access" },
  { sev: "Critical", title: "mimikatz touching lsass.exe on domain controller", host: "dc-02", tech: "T1003", tactic: "Credential Access" },
  { sev: "Medium", title: "Port scan across 40 internal hosts", host: "ws-dev-11", tech: "T1046", tactic: "Discovery" },
  { sev: "High", title: "SQL injection against customer portal", host: "web-portal-01", tech: "T1190", tactic: "Initial Access" },
  { sev: "Critical", title: "4.2 GB upload to unsanctioned cloud storage", host: "ws-eng-03", tech: "T1567", tactic: "Exfiltration" },
  { sev: "Medium", title: "Impossible travel: India and Brazil in 20 min", host: "vpn-gw", tech: "T1078", tactic: "Initial Access" },
  { sev: "Low", title: "Off-hours VPN login from a known device", host: "vpn-gw", tech: "T1078", tactic: "Initial Access" },
  { sev: "High", title: "Security event log cleared on app server", host: "app-srv-09", tech: "T1070", tactic: "Defense Evasion" },
];

const FEATURES = [
  { icon: "alert", title: "Alert triage", text: "Search, filter and prioritise by severity, status, category and date. Assign work, and keep a full history of every change." },
  { icon: "case", title: "Case investigation", text: "Turn alerts into cases with notes, findings, a live timeline and a clear close/reopen workflow with outcomes." },
  { icon: "map", title: "ATT&CK suggestions", text: "Transparent rules suggest techniques and tactics - with the reason shown. Clearly labelled as suggestions to validate." },
  { icon: "audit", title: "Tamper-resistant audit trail", text: "Logins, assignments, notes, status changes and reports are recorded in an append-only log nobody can edit." },
  { icon: "pdf", title: "One-click PDF reports", text: "Export a polished investigation report: alert data, notes, MITRE mapping, timeline, findings and conclusion." },
  { icon: "lock", title: "Role-based access", text: "Admins and analysts with enforced ownership rules. JWT sessions, revocation on logout and strict input validation." },
];

const STEPS = [
  { n: "01", title: "Alert arrives", text: "A simulated detection lands in the queue with severity, source, host and indicators." },
  { n: "02", title: "Triage & map", text: "Rules suggest ATT&CK techniques and explain why. You confirm, adjust or dismiss." },
  { n: "03", title: "Investigate", text: "Open a case, assign an analyst, add notes and follow the timeline as the story builds." },
  { n: "04", title: "Report & close", text: "Record findings and a conclusion, close with an outcome and download the PDF report." },
];

const SAMPLES = [
  { label: "Password spray", title: "Multiple failed SSH logins", description: "47 failed login attempts for root in 5 minutes - possible password spray.", category: "Brute Force" },
  { label: "Phishing macro", title: "Suspicious email with attachment", description: "User opened invoice.docm. Macro enabled document launched powershell -EncodedCommand.", category: "Phishing" },
  { label: "Credential dumping", title: "EDR alert on domain controller", description: "mimikatz accessed lsass memory, followed by lateral movement over smb.", category: "Privilege Escalation" },
  { label: "Data exfiltration", title: "Unusual outbound transfer", description: "4 GB uploaded to dropbox outside business hours from an engineering workstation.", category: "Data Exfiltration" },
];

const TACTICS = ["Initial Access", "Execution", "Persistence", "Privilege Escalation", "Defense Evasion", "Credential Access", "Discovery", "Lateral Movement", "Collection", "Exfiltration", "Command & Control", "Impact"];

const SUMMARY = "Encoded PowerShell was launched by winword.exe on ws-fin-07 right after a macro-enabled attachment was opened. This matches Phishing (T1566) leading to Execution (T1059.001). Suggested next steps: isolate the host, pull the mail gateway logs for the sender, and check ws-fin-07 for new scheduled tasks.";

const BARS = [["Critical", 3, "var(--crit)"], ["High", 7, "var(--high)"], ["Medium", 5, "var(--med)"], ["Low", 2, "var(--low)"]];

const FAQ = [
  ["Is this a real SIEM or threat-detection product?", "No. It is an educational SOC workflow platform built with simulated alerts. It does not ingest real logs or detect attacks by itself."],
  ["How much of it is AI?", "Today the ATT&CK suggestions come from transparent, readable rules - there is no hidden model, and every suggestion explains itself. An optional LLM-written case summary (always human-reviewed) is on the roadmap."],
  ["Can I trust the ATT&CK mapping?", "Treat it as a starting point. Every mapping is labelled a suggestion, never confirmed attacker behaviour, and an analyst must validate it."],
  ["Is my data safe?", "Passwords are bcrypt-hashed, sessions use signed JWTs that can be revoked, access is role-checked on the server and every important action is audited. Use simulated data only."],
];

/* ------------------------------------------------------------------ hooks */
function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll(".landing [data-reveal]");
    if (!("IntersectionObserver" in window)) {
      els.forEach((e) => e.classList.add("in"));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }),
      { threshold: 0.15 }
    );
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, []);
}

function CountUp({ to, suffix = "", duration = 1400 }) {
  const ref = useRef(null);
  const [val, setVal] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !("IntersectionObserver" in window)) { setVal(to); return; }
    let raf;
    const io = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      io.disconnect();
      const t0 = performance.now();
      const tick = (t) => {
        const p = Math.min(1, (t - t0) / duration);
        setVal(Math.round(to * (1 - Math.pow(1 - p, 3))));
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    }, { threshold: 0.4 });
    io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, [to, duration]);
  return <span ref={ref}>{val}{suffix}</span>;
}

/* ------------------------------------------------------------------ pieces */
const Icon = ({ name }) => {
  const paths = {
    alert: "M12 3 2 20h20L12 3Zm0 6v5m0 3v.01",
    case: "M4 7h16v12H4V7Zm5 0V5h6v2M4 12h16",
    map: "M4 4h6v6H4V4Zm10 0h6v6h-6V4ZM4 14h6v6H4v-6Zm10 3h6m-3-3v6",
    audit: "M6 3h9l4 4v14H6V3Zm8 0v5h5M9 13h7M9 17h7",
    pdf: "M7 3h8l4 4v14H7V3Zm7 0v5h5M10 14h6M10 18h4",
    lock: "M6 11h12v9H6v-9Zm3 0V8a3 3 0 0 1 6 0v3",
  };
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={paths[name]} />
    </svg>
  );
};

function LiveFeed() {
  const [items, setItems] = useState(() => FEED.slice(0, 4).map((f, i) => ({ ...f, id: i })));
  const next = useRef(4);
  useEffect(() => {
    const t = setInterval(() => {
      if (document.hidden) return;
      const i = next.current++;
      setItems((cur) => [{ ...FEED[i % FEED.length], id: i }, ...cur].slice(0, 5));
    }, 2400);
    return () => clearInterval(t);
  }, []);
  const top = items[0];
  return (
    <div className="l-feed" aria-label="Simulated live alert feed">
      <div className="l-feed-head">
        <span className="l-live"><i /> LIVE</span>
        <strong>Alert queue</strong>
        <small>simulated data</small>
      </div>
      <ul>
        {items.map((a) => (
          <li key={a.id} className={`l-alert sev-${a.sev.toLowerCase()}`}>
            <span className="l-sev">{a.sev}</span>
            <div><b>{a.title}</b><small>{a.host}</small></div>
          </li>
        ))}
      </ul>
      <div className="l-suggest" key={top.id}>
        <small>ATT&amp;CK suggestion for latest alert</small>
        <div><code>{top.tech}</code> <span>{top.tactic}</span> <em>suggested</em></div>
      </div>
    </div>
  );
}

function Suggester() {
  const [form, setForm] = useState(SAMPLES[0]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(payload = form) {
    setBusy(true);
    setError("");
    try {
      const data = await api.post("/public/mitre-suggest", { title: payload.title, description: payload.description, category: payload.category }, { auth: false });
      setResult(data.suggestions);
    } catch (e) {
      setResult(null);
      setError(e.status === 0 ? "The live demo needs the backend running. Start it and try again." : e.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => { run(SAMPLES[0]); /* eslint-disable-next-line */ }, []);

  return (
    <div className="l-try">
      <div className="l-try-in">
        <div className="l-chips">
          {SAMPLES.map((s) => (
            <button key={s.label} className={`l-chip ${form.label === s.label ? "on" : ""}`} onClick={() => { setForm(s); run(s); }}>{s.label}</button>
          ))}
        </div>
        <label>Alert title<input value={form.title} maxLength={200} onChange={(e) => setForm({ ...form, label: "", title: e.target.value })} /></label>
        <label>Description<textarea rows={4} value={form.description} maxLength={2000} onChange={(e) => setForm({ ...form, label: "", description: e.target.value })} /></label>
        <button className="l-btn l-btn-primary" disabled={busy || !(form.title.trim() || form.description.trim())} onClick={() => run()}>
          {busy ? "Analysing..." : "Suggest ATT&CK techniques"}
        </button>
      </div>
      <div className="l-try-out" aria-live="polite">
        <div className="l-out-head"><strong>Suggestions</strong><small>rule-based - live from the API</small></div>
        {error && <p className="l-err">{error}</p>}
        {result && result.length === 0 && <p className="l-muted">No techniques matched these words. Try adding details such as &quot;powershell&quot;, &quot;rdp&quot; or &quot;port scan&quot;.</p>}
        {result && result.map((m, i) => (
          <div className="l-tech" key={m.technique_id} style={{ animationDelay: `${i * 90}ms` }}>
            <div><code>{m.technique_id}</code><b>{m.technique_name}</b></div>
            <div className="l-tags"><span>{m.tactic}</span><span className="warn">Suggested - {m.confidence}</span></div>
            <p>{m.reason}</p>
          </div>
        ))}
        <p className="l-note">Suggestions only - must be validated by an analyst.</p>
      </div>
    </div>
  );
}

function Typewriter({ text, speed = 22 }) {
  const ref = useRef(null);
  const [n, setN] = useState(0);
  const [started, setStarted] = useState(false);
  useEffect(() => {
    const el = ref.current;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !el || !("IntersectionObserver" in window)) { setN(text.length); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setStarted(true); io.disconnect(); } }, { threshold: 0.3 });
    io.observe(el);
    return () => io.disconnect();
  }, [text]);
  useEffect(() => {
    if (!started) return;
    const t = setInterval(() => setN((v) => { if (v >= text.length) { clearInterval(t); return v; } return v + 1; }), speed);
    return () => clearInterval(t);
  }, [started, text, speed]);
  return <p ref={ref} className="l-type">{text.slice(0, n)}<i className={n < text.length ? "caret" : "caret off"} /></p>;
}

function Preview() {
  return (
    <div className="l-preview">
      <div className="l-win">
        <div className="l-win-bar"><i /><i /><i /><span>soc-assistant / dashboard</span></div>
        <div className="l-win-body">
          <div className="l-kpis">
            <div><small>Open alerts</small><b><CountUp to={17} /></b></div>
            <div><small>Active cases</small><b><CountUp to={6} /></b></div>
            <div><small>Avg. triage</small><b><CountUp to={9} suffix=" min" /></b></div>
          </div>
          <div className="l-chart">
            <small>Alerts by severity (sample data)</small>
            {BARS.map(([k, v, c], i) => (
              <div className="l-barrow" key={k}>
                <span>{k}</span>
                <div><i style={{ "--w": `${(v / 7) * 100}%`, background: c, transitionDelay: `${i * 120}ms` }} /></div>
                <em>{v}</em>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="l-ai">
        <div className="l-ai-head"><span className="l-spark">AI</span><strong>Investigation copilot</strong><small>preview - human review required</small></div>
        <Typewriter text={SUMMARY} />
        <div className="l-chain">
          <span>T1566 Phishing</span><b>&rarr;</b><span>T1059.001 PowerShell</span><b>&rarr;</b><span className="dim">T1003 Credential dumping?</span>
        </div>
      </div>
    </div>
  );
}

function Steps() {
  const [active, setActive] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setActive((a) => (a + 1) % STEPS.length), 3200);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="l-steps">
      {STEPS.map((s, i) => (
        <button key={s.n} className={`l-step ${i === active ? "on" : ""}`} onClick={() => setActive(i)}>
          <span className="l-step-n">{s.n}</span>
          <h3>{s.title}</h3>
          <p>{s.text}</p>
          <span className="l-bar"><i key={active === i ? `a${active}` : `i${i}`} /></span>
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ page */
export default function Landing() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [faq, setFaq] = useState(0);
  useReveal();

  useEffect(() => {
    document.title = "SOCrates - AI SOC Analyst Assistant";
    return () => { document.title = "SOCrates - AI SOC Analyst Assistant"; };
  }, []);

  const cta = user
    ? <Link className="l-btn l-btn-primary" to="/dashboard">Open dashboard</Link>
    : <Link className="l-btn l-btn-primary" to="/register">Get started free</Link>;

  return (
    <div className="landing">
      <header className="l-nav">
        <a className="l-logo" href="#top"><Logo size={38} /><b className="l-wordmark">SOC<em>rates</em></b></a>
        <nav className={open ? "open" : ""} onClick={() => setOpen(false)}>
          <a href="#preview">Preview</a>
          <a href="#features">Features</a>
          <a href="#how">How it works</a>
          <a href="#try">Try it</a>
          <a href="#security">Security</a>
          <a href="#faq">FAQ</a>
        </nav>
        <div className="l-nav-cta">
          {user ? <Link className="l-btn l-btn-primary" to="/dashboard">Open dashboard</Link> : (
            <>
              <Link className="l-btn l-btn-ghost" to="/login">Sign in</Link>
              <Link className="l-btn l-btn-primary" to="/register">Get started</Link>
            </>
          )}
        </div>
        <button className="l-burger" aria-label="Menu" onClick={() => setOpen((o) => !o)}>{open ? "x" : "="}</button>
      </header>

      <section className="l-hero" id="top" onMouseMove={(e) => { const r = e.currentTarget.getBoundingClientRect(); e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`); e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`); }}>
        <div className="l-spot" />
        <div className="l-orb o1" /><div className="l-orb o2" /><div className="l-grid" />
        <div className="l-hero-copy">
          <span className="l-pill"><i /> Educational project - simulated data</span>
          <h1>Investigate security alerts <em>faster</em> with an AI-assisted SOC workspace</h1>
          <p>Triage alerts, build investigation cases, map activity to MITRE ATT&amp;CK with explainable suggestions and ship a professional PDF report - all in one place.</p>
          <div className="l-hero-cta">
            {cta}
            {!user && <Link className="l-btn l-btn-ghost" to="/login">Sign in</Link>}
            <a className="l-btn l-btn-link" href="#try">Try the ATT&amp;CK suggester</a>
          </div>
          <ul className="l-trust">
            <li>FastAPI</li><li>React</li><li>MongoDB</li><li>MITRE ATT&amp;CK</li><li>JWT + RBAC</li>
          </ul>
        </div>
        <LiveFeed />
      </section>

      <section className="l-stats" data-reveal>
        <div><b><CountUp to={21} /></b><span>ATT&amp;CK techniques covered by rules</span></div>
        <div><b><CountUp to={86} suffix="+" /></b><span>automated backend tests</span></div>
        <div><b><CountUp to={10} /></b><span>connected workflow screens</span></div>
        <div><b>100%</b><span>of key actions audited</span></div>
      </section>

      <div className="l-marquee" aria-hidden="true">
        <div>{[...TACTICS, ...TACTICS].map((t, i) => <span key={i}>{t}</span>)}</div>
      </div>

      <section className="l-section" id="preview">
        <div className="l-head" data-reveal><small>Product preview</small><h2>One workspace, from first alert to final report</h2><p>See the queue, the story and the AI-assisted summary side by side.</p></div>
        <div data-reveal><Preview /></div>
      </section>

      <section className="l-section" id="features">
        <div className="l-head" data-reveal><small>Capabilities</small><h2>Everything an analyst needs, nothing hidden</h2><p>A focused toolkit that follows the real investigation lifecycle from alert to report.</p></div>
        <div className="l-cards">
          {FEATURES.map((f, i) => (
            <article key={f.title} className="l-card" data-reveal style={{ transitionDelay: `${(i % 3) * 80}ms` }}>
              <span className="l-ico"><Icon name={f.icon} /></span>
              <h3>{f.title}</h3><p>{f.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="l-section l-alt" id="how">
        <div className="l-head" data-reveal><small>Workflow</small><h2>From alert to answer in four steps</h2></div>
        <div data-reveal><Steps /></div>
      </section>

      <section className="l-section" id="try">
        <div className="l-head" data-reveal><small>Live demo</small><h2>Try the ATT&amp;CK suggester</h2><p>Paste an alert description and see the explainable suggestion engine respond - the same one used inside the app.</p></div>
        <div data-reveal><Suggester /></div>
      </section>

      <section className="l-section l-alt" id="security">
        <div className="l-head" data-reveal><small>Security by design</small><h2>Built the way a SOC tool should be</h2></div>
        <div className="l-sec" data-reveal>
          {["bcrypt password hashing", "Signed JWTs with expiry and revocation", "Server-side RBAC and ownership checks", "Append-only audit log", "Strict input validation", "Explicit CORS allow-list and security headers", "Generic errors - no stack traces to clients", "Secrets only in environment variables"].map((t) => (
            <div key={t}><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 5 5 9-10" /></svg>{t}</div>
          ))}
        </div>
      </section>

      <section className="l-section" id="faq">
        <div className="l-head" data-reveal><small>FAQ</small><h2>Honest answers</h2></div>
        <div className="l-faq" data-reveal>
          {FAQ.map(([q, a], i) => (
            <div key={q} className={faq === i ? "on" : ""}>
              <button onClick={() => setFaq(faq === i ? -1 : i)} aria-expanded={faq === i}>{q}<span>{faq === i ? "-" : "+"}</span></button>
              <div className="l-faq-a"><p>{a}</p></div>
            </div>
          ))}
        </div>
      </section>

      <section className="l-final" data-reveal>
        <h2>Ready to run your first investigation?</h2>
        <p>Create a free analyst account and work through a sample alert in minutes.</p>
        <div className="l-hero-cta center">{cta}{!user && <Link className="l-btn l-btn-ghost" to="/login">Sign in</Link>}</div>
      </section>

      <footer className="l-foot">
        <div><span className="l-logo"><Logo size={34} /><b className="l-wordmark">SOC<em>rates</em></b> <small>AI SOC Analyst Assistant</small></span><p>Educational project with simulated alerts. Not a production SIEM and not an autonomous threat-detection system.</p></div>
        <div><a href="#features">Features</a><a href="#how">How it works</a><a href="#try">Try it</a><Link to="/login">Sign in</Link></div>
      </footer>
    </div>
  );
}
