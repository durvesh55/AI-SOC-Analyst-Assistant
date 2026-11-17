// Browser end-to-end test (Puppeteer drives a real Chromium browser through the React UI).
// Prerequisites: MongoDB + backend + frontend dev server running, and a FRESH seed:
//     cd backend && python -m app.seed --reset
// Run:  cd e2e && npm install && npm test        (set BROWSER_PATH to Chrome/Edge if not at the default path)
// NOTE: the run creates data (an alert, a case, two users) and is NOT repeatable without re-seeding.
import puppeteer from "puppeteer-core";
import path from "node:path";

import fs from "node:fs";
const OUT = path.resolve("shots"); // screenshots are written here (git-ignored)
fs.mkdirSync(OUT, { recursive: true });

const BASE = process.env.APP_URL || "http://localhost:5173";
const results = [];
const problems = [];
const ok = (name, cond, extra = "") => { results.push([cond ? "PASS" : "FAIL", name, extra]); if (!cond) problems.push(name); };

const browser = await puppeteer.launch({
  executablePath: process.env.BROWSER_PATH || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  headless: "new",
  args: ["--no-sandbox"],
  defaultViewport: { width: 1400, height: 900 },
});

async function session(label, fn) {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  page.on("pageerror", (e) => problems.push(`[${label}] pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") problems.push(`[${label}] console.error: ${m.text()}`); });
  page.on("response", (r) => {
    if (r.url().includes("/api/") && r.status() >= 400) results.push(["INFO", `[${label}] API ${r.status()}`, r.url().replace(BASE, "")]);
  });
  try { await fn(page); } finally { await ctx.close(); }
}

const text = (page) => page.evaluate(() => document.body.innerText);
const clickText = async (page, selector, label) => {
  const handle = await page.evaluateHandle((sel, lab) => [...document.querySelectorAll(sel)].find((e) => e.innerText.trim().startsWith(lab)), selector, label);
  const el = handle.asElement();
  if (!el) throw new Error(`no ${selector} starting with "${label}"`);
  await el.click();
};
const settle = (page, ms = 700) => new Promise((r) => setTimeout(r, ms));

async function login(page, id, pw) {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle0" });
  await page.type('input[autocomplete="username"]', id);
  await page.type('input[type="password"]', pw);
  await page.click("button.btn-primary");
  await page.waitForSelector(".sidebar", { timeout: 8000 });
}

// ============ ADMIN SESSION ============
await session("admin", async (page) => {
  // unauthenticated redirect
  await page.goto(`${BASE}/alerts`, { waitUntil: "networkidle0" });
  ok("unauthenticated /alerts redirects to login", page.url().endsWith("/login"));

  // wrong password shows an error
  await page.type('input[autocomplete="username"]', "admin");
  await page.type('input[type="password"]', "WrongPass1");
  await page.click("button.btn-primary");
  await page.waitForSelector(".alert-error", { timeout: 5000 });
  ok("bad login shows error", (await text(page)).includes("Invalid credentials"));

  await login(page, "admin", "Admin@12345");
  await page.waitForFunction(() => document.body.innerText.includes("Total alerts"), { timeout: 8000 });
  ok("login lands on dashboard", (await text(page)).includes("Dashboard") && (await text(page)).includes("Total alerts"));
  await settle(page);
  const dash = await text(page);
  ok("dashboard shows seeded totals (20 alerts)", /20\s*\n?\s*Total alerts/.test(dash.replace(/\n+/g, "\n")) || dash.includes("20"));
  ok("dashboard has workload + recent activity", dash.includes("Analyst workload") && dash.includes("Recent activity"));
  await page.screenshot({ path: `${OUT}/dashboard.png`, fullPage: true });

  // alerts list + filter
  await clickText(page, "a.nav-link", "Alerts");
  await page.waitForSelector("table tbody tr");
  const rows1 = await page.$$eval("table tbody tr", (r) => r.length);
  ok("alerts list shows rows", rows1 > 0, `${rows1} rows`);
  await page.select('select[aria-label="Severity"]', "Critical");
  await settle(page, 900);
  const rows2 = await page.$$eval("table tbody tr", (r) => r.length);
  ok("severity filter reduces rows to Critical only", rows2 === 5, `${rows2} rows`);
  await page.screenshot({ path: `${OUT}/alerts.png`, fullPage: true });

  // create a new alert through the UI
  await page.select('select[aria-label="Severity"]', "");
  await clickText(page, "button", "New alert");
  await page.waitForSelector(".modal");
  await page.type('.modal input[maxlength="200"]', "E2E: failed logins and mimikatz");
  await page.type(".modal textarea", "password spray observed, then mimikatz accessed lsass");
  await page.type('.modal input[placeholder="203.0.113.5"]', "203.0.113.77");
  await clickText(page, ".modal button", "Create alert");
  await page.waitForSelector("h2", { timeout: 8000 });
  await settle(page);
  const det = await text(page);
  ok("new alert created and detail opens", /ALT-\d{6}: E2E/.test(det));
  ok("MITRE suggestions displayed with disclaimer", det.includes("T1003") && det.includes("T1110") && det.includes("not confirmed attacker behaviour"));
  await page.screenshot({ path: `${OUT}/alert-detail.png`, fullPage: true });

  // change status via dropdown
  await page.select(".card select", "Under Investigation");
  await settle(page, 900);
  ok("status change recorded in history", (await text(page)).includes("Status changed"));

  // create case
  await clickText(page, "button", "Create investigation case");
  await page.waitForFunction(() => /CASE-\d{6}:/.test(document.body.innerText), { timeout: 8000 });
  ok("case created from alert", true);
  await settle(page);

  // add note + findings
  await page.type(".note-form textarea", "Verified source IP in threat intel; escalating.");
  await clickText(page, ".note-form button", "Add note");
  await settle(page, 900);
  ok("note appears", (await text(page)).includes("Verified source IP"));
  const areas = await page.$$(".card textarea");
  await areas[0].type("Brute force followed by credential dumping.");
  await clickText(page, "button", "Save findings");
  await settle(page, 900);
  ok("timeline shows note + update", (await text(page)).includes("Note added") && (await text(page)).includes("Case updated"));

  // PDF
  await clickText(page, "button", "Download PDF report");
  await page.waitForFunction(() => document.body.innerText.includes("Report downloaded"), { timeout: 8000 });
  const pdfInfo = await page.evaluate(async () => {
    const id = location.pathname.split("/").pop();
    const r = await fetch(`/api/cases/${id}/report`, { headers: { Authorization: `Bearer ${localStorage.getItem("soc_token")}` } });
    const b = new Uint8Array(await r.arrayBuffer());
    return { status: r.status, type: r.headers.get("content-type"), head: String.fromCharCode(...b.slice(0, 4)), size: b.length };
  });
  ok("PDF report downloads (UI toast + application/pdf, %PDF header)", pdfInfo.status === 200 && pdfInfo.head === "%PDF" && pdfInfo.type === "application/pdf", `${pdfInfo.size} bytes`);
  await page.screenshot({ path: `${OUT}/case-detail.png`, fullPage: true });

  // close case
  await clickText(page, "button", "Close case");
  await page.waitForSelector(".modal textarea");
  await page.type(".modal textarea", "Confirmed compromise attempt; host isolated and credentials reset.");
  await clickText(page, ".modal button", "Close case");
  await settle(page, 1000);
  ok("case shows Closed", (await text(page)).includes("This case is closed"));

  // reopen (admin)
  await clickText(page, "button", "Reopen case");
  await page.waitForSelector(".modal textarea");
  await page.type(".modal textarea", "New evidence from EDR");
  await clickText(page, ".modal button", "Reopen case");
  await settle(page, 1000);
  ok("admin reopened case", !(await text(page)).includes("This case is closed") && (await text(page)).includes("Case reopened"));

  // cases list
  await clickText(page, "a.nav-link", "Cases");
  await page.waitForSelector("table tbody tr");
  ok("cases list renders", (await page.$$eval("table tbody tr", (r) => r.length)) >= 3);

  // audit logs
  await clickText(page, "a.nav-link", "Audit Logs");
  await page.waitForSelector("table tbody tr");
  const audit = await text(page);
  ok("audit log shows events incl. report + reopen", audit.includes("Generated report") && audit.includes("Reopened case") && audit.includes("Created alert"));
  await page.screenshot({ path: `${OUT}/audit.png`, fullPage: true });

  // admin users
  await clickText(page, "a.nav-link", "User Management");
  await page.waitForSelector("table tbody tr");
  ok("admin user list shows 3 seeded users", (await page.$$eval("table tbody tr", (r) => r.length)) === 3);
  await clickText(page, "button", "Create user");
  await page.waitForSelector(".modal");
  const inputs = await page.$$(".modal input");
  await inputs[0].type("E2E User");
  await inputs[1].type("e2e_user");
  await inputs[2].type("e2e@example.com");
  await inputs[3].type("E2eUser#1234");
  await clickText(page, ".modal button", "Create");
  await settle(page, 1000);
  ok("admin created a user", (await text(page)).includes("e2e_user"));
  await page.screenshot({ path: `${OUT}/users.png`, fullPage: true });

  // profile
  await clickText(page, "a.nav-link", "Profile");
  await settle(page);
  ok("profile page renders", (await text(page)).includes("Change password"));

  // logout
  await clickText(page, "button", "Log out");
  await page.waitForSelector("form.auth-card");
  ok("logout returns to login", page.url().endsWith("/login"));
  await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle0" });
  ok("after logout dashboard is protected", page.url().endsWith("/login"));
});

// ============ ANALYST SESSION ============
await session("analyst", async (page) => {
  await login(page, "analyst1", "Analyst@12345");
  ok("analyst sees no User Management link", !(await text(page)).includes("User Management"));
  await page.goto(`${BASE}/admin/users`, { waitUntil: "networkidle0" });
  ok("analyst blocked from /admin/users", (await text(page)).includes("Access denied"));
  await page.goto(`${BASE}/audit`, { waitUntil: "networkidle0" });
  await page.waitForSelector("table tbody tr");
  const actors = await page.$$eval("table tbody tr td:nth-child(2)", (c) => [...new Set(c.map((x) => x.innerText))]);
  ok("analyst audit view limited to own entries", actors.length === 1 && actors[0] === "analyst1", actors.join(","));

  // someone else's case is read-only
  await page.goto(`${BASE}/cases`, { waitUntil: "networkidle0" });
  await page.waitForSelector("table tbody tr");
  const rows = await page.$$("table tbody tr");
  let sawReadOnly = false;
  for (let i = 0; i < rows.length && !sawReadOnly; i++) {
    await page.goto(`${BASE}/cases`, { waitUntil: "networkidle0" });
    await page.waitForSelector("table tbody tr");
    const r = await page.$$("table tbody tr");
    await r[i].click();
    await settle(page, 800);
    if ((await text(page)).includes("assigned to") && (await text(page)).includes("only they or an admin")) {
      sawReadOnly = true;
      ok("other analyst's case is read-only (no close/note controls)", !(await text(page)).includes("Add note") && !(await text(page)).includes("Close case"));
    }
  }
  ok("found a read-only case for analyst", sawReadOnly);
  await page.setViewport({ width: 390, height: 800 });
  await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle0" });
  await settle(page);
  ok("mobile: menu button visible, sidebar hidden", await page.$eval(".menu-btn", (e) => getComputedStyle(e).display !== "none"));
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
  ok("mobile: no horizontal page overflow", !overflow);
  await page.screenshot({ path: `${OUT}/mobile-dashboard.png` });
});

// ============ PUBLIC LANDING PAGE ============
await session("landing", async (page) => {
  await page.goto(`${BASE}/`, { waitUntil: "networkidle0" });
  ok("landing: hero headline renders", (await text(page)).includes("Investigate security alerts"));
  ok("landing: not behind login", page.url() === `${BASE}/`);
  const feedTop = () => page.$eval(".l-feed .l-alert b", (e) => e.innerText);
  await page.waitForSelector(".l-feed .l-alert");
  const first = await feedTop();
  await new Promise((r) => setTimeout(r, 3200));
  ok("landing: live feed updates on its own", (await feedTop()) !== first && (await page.$$(".l-feed .l-alert")).length >= 4);
  await page.evaluate(() => document.querySelector(".l-stats").scrollIntoView());
  await new Promise((r) => setTimeout(r, 2200));
  const stats = await page.$$eval(".l-stats b", (b) => b.map((x) => x.innerText));
  ok("landing: counters animate to real values", stats[0] === "21" && stats[1] === "86+" && stats[2] === "10", stats.join(","));
  await page.evaluate(() => document.querySelector("#try").scrollIntoView());
  await page.waitForSelector(".l-tech", { timeout: 8000 });
  ok("landing: live ATT&CK suggester calls the API (T1110)", (await text(page)).includes("T1110"));
  await clickText(page, ".l-chip", "Phishing macro");
  await page.waitForFunction(() => document.body.innerText.includes("T1566"), { timeout: 8000 });
  ok("landing: sample chip re-runs suggester (T1566 + T1059.001)", (await text(page)).includes("T1059.001"));
  await page.screenshot({ path: `${OUT}/landing.png` });
  await page.click('.l-nav-cta a[href="/login"]');
  await page.waitForSelector("form.auth-card");
  ok("landing: Sign in link opens login", page.url().endsWith("/login"));
  await page.goto(`${BASE}/`, { waitUntil: "networkidle0" });
  await page.click('.l-nav-cta a[href="/register"]');
  await page.waitForSelector("form.auth-card");
  ok("landing: Get started opens registration", page.url().endsWith("/register"));
  await page.setViewport({ width: 390, height: 844 });
  await page.goto(`${BASE}/`, { waitUntil: "networkidle0" });
  ok("landing (mobile): no horizontal overflow", !(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2)));
  await page.click(".l-burger");
  ok("landing (mobile): menu opens", await page.$eval(".l-nav nav", (n) => getComputedStyle(n).display !== "none"));
});

// ============ REGISTER FLOW ============
await session("register", async (page) => {
  await page.goto(`${BASE}/register`, { waitUntil: "networkidle0" });
  const ins = await page.$$("form input");
  await ins[0].type("Reg Tester");
  await ins[1].type("reg_tester");
  await ins[2].type("reg@example.com");
  await ins[3].type("RegTester#99");
  await ins[4].type("RegTester#99");
  await page.click("button.btn-primary");
  await page.waitForSelector(".sidebar", { timeout: 8000 });
  ok("registration auto-logs in as Analyst", (await text(page)).includes("Analyst") && !(await text(page)).includes("User Management"));
});

await browser.close();
for (const r of results) console.log(r.join(" | "));
console.log("\nPROBLEMS:", problems.length ? "\n - " + problems.join("\n - ") : "none");
process.exit(problems.length ? 1 : 0);
