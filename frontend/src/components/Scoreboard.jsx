export default function Scoreboard({ tasks, capacity, locked }) {
  const active = tasks.filter((t) => t.status !== "dropped");
  const totalH = active.reduce((s, t) => s + (t.estimated_hours || 0), 0);
  const doneH = active.filter((t) => t.status === "done").reduce((s, t) => s + (t.estimated_hours || 0), 0);
  const pct = totalH > 0 ? Math.round((doneH / totalH) * 100) : 0;

  return (
    <div style={{ background: "#0e0e28", border: "1px solid #1a1a3a", borderRadius: 10, padding: 16, marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <div>
          <span
            style={{
              fontSize: 28,
              fontWeight: 700,
              fontFamily: "'IBM Plex Mono', monospace",
              color: pct >= 80 ? "#10b981" : pct >= 40 ? "#f59e0b" : "#e2e8f0",
            }}
          >
            {pct}%
          </span>
          <span style={{ fontSize: 12, color: "#475569", marginLeft: 8 }}>done</span>
        </div>
        <div style={{ display: "flex", gap: 14, fontSize: 12 }}>
          <span style={{ color: "#94a3b8" }}>{active.length} tasks</span>
          <span style={{ color: "#2563eb" }}>{active.filter((t) => t.status === "doing").length} doing</span>
          <span style={{ color: "#059669" }}>{active.filter((t) => t.status === "done").length} done</span>
          <span style={{ color: totalH > capacity ? "#ef4444" : "#94a3b8" }}>
            {totalH}/{capacity}h{totalH > capacity ? " !!!" : ""}
          </span>
        </div>
      </div>
      <div style={{ background: "#08081a", borderRadius: 5, height: 6, overflow: "hidden" }}>
        <div
          style={{
            background: "linear-gradient(90deg, #4f46e5, #06b6d4)",
            height: "100%",
            width: `${Math.min(pct, 100)}%`,
            borderRadius: 5,
            transition: "width 0.3s",
          }}
        />
      </div>
      {locked && (
        <div
          style={{
            marginTop: 10,
            background: "#6d28d922",
            border: "1px solid #6d28d944",
            borderRadius: 6,
            padding: "6px 12px",
            fontSize: 12,
            color: "#a78bfa",
          }}
        >
          Locked -- adding a task requires dropping one first
        </div>
      )}
    </div>
  );
}
