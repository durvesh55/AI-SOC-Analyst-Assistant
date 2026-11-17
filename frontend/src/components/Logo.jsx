import { useEffect, useRef, useState } from "react";

// Interactive logo: a shield with an "all-seeing" eye. The pupil follows the cursor,
// the eye blinks when clicked, and the radar ring pulses on hover.
export default function Logo({ size = 40, className = "" }) {
  const ref = useRef(null);
  const [look, setLook] = useState({ x: 0, y: 0 });
  const [blink, setBlink] = useState(false);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;
    const move = (e) => {
      const el = ref.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const dx = e.clientX - (r.left + r.width / 2);
      const dy = e.clientY - (r.top + r.height / 2);
      const d = Math.hypot(dx, dy) || 1;
      const k = Math.min(1, d / 160) * 4.2; // max pupil travel in SVG units
      setLook({ x: (dx / d) * k, y: (dy / d) * k * 0.7 });
    };
    window.addEventListener("mousemove", move, { passive: true });
    return () => window.removeEventListener("mousemove", move);
  }, []);

  function onClick() {
    setBlink(true);
    setTimeout(() => setBlink(false), 220);
  }

  return (
    <svg ref={ref} className={`logo-mark ${className}`} viewBox="0 0 48 48" width={size} height={size} role="img" aria-label="AlertDesk logo" onClick={onClick}>
      <defs>
        <linearGradient id="lg-shield" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#3b82f6" />
          <stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
      <circle className="logo-ring" cx="24" cy="24" r="22" fill="none" stroke="#22d3ee" strokeWidth="1" />
      <path d="M24 3 41 9v14c0 11-7.5 18.5-17 22C14.5 41.500 7 34 7 23V9L24 3Z" fill="url(#lg-shield)" />
      <path d="M24 3 41 9v14c0 11-7.5 18.5-17 22" fill="none" stroke="rgba(255,255,255,.35)" strokeWidth="1" />
      <g style={{ transformOrigin: "24px 22px", transform: blink ? "scaleY(.08)" : "none", transition: "transform .12s" }}>
        <path d="M11 22s5-8 13-8 13 8 13 8-5 8-13 8-13-8-13-8Z" fill="#050b1a" />
        <circle cx={24 + look.x} cy={22 + look.y} r="5" fill="#22d3ee" />
        <circle cx={24 + look.x} cy={22 + look.y} r="2.200" fill="#050b1a" />
        <circle cx={22.800 + look.x} cy={20.600 + look.y} r="1" fill="#fff" />
      </g>
    </svg>
  );
}
