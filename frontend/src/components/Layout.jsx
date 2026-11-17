import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Logo from "./Logo";

export default function Layout() {
  const { user, logout, isAdmin } = useAuth();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  const links = [
    ["/dashboard", "Dashboard"],
    ["/alerts", "Alerts"],
    ["/cases", "Cases"],
    ["/audit", "Audit Logs"],
    ...(isAdmin ? [["/admin/users", "User Management"]] : []),
    ["/profile", "Profile & Settings"],
  ];

  return (
    <div className="shell">
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <Link className="brand" to="/" title="Back to the home page">
          <Logo size={36} />
          <div>
            <strong>AlertDesk</strong>
            <small>AI SOC Analyst Assistant</small>
          </div>
        </Link>
        <nav>
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/dashboard"} onClick={() => setOpen(false)}
              className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">Simulated data only. Not a production SIEM.</div>
      </aside>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}

      <div className="main">
        <header className="topbar">
          <button className="icon-btn menu-btn" onClick={() => setOpen((o) => !o)} aria-label="Toggle menu">=</button>
          <div className="spacer" />
          <div className="who" onClick={() => navigate("/profile")} role="button" tabIndex={0}>
            <span className="avatar">{(user.full_name || user.username)[0].toUpperCase()}</span>
            <span className="who-text">
              <strong>{user.full_name || user.username}</strong>
              <small>{user.role}</small>
            </span>
          </div>
          <button className="btn" onClick={() => logout("You have been logged out.")}>Log out</button>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
