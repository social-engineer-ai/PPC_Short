import { useState, useEffect } from "react";
import { AREAS, PRIORITY, css } from "../constants";
import { weekLabel, shiftWeek, getWeekId } from "../utils";
import * as api from "../api";
import Btn from "../components/Btn";
import Badge from "../components/Badge";

export default function ReviewView({ week, tasks, projects, capacity, onRefresh }) {
  const [stats, setStats] = useState(null);
  const [settings, setSettings] = useState(null);

  useEffect(() => {
    loadStats();
  }, [week]);

  const loadStats = async () => {
    try {
      const [s, sett] = await Promise.all([
        api.getWeekStats(week),
        api.getSettings(),
      ]);
      setStats(s);
      setSettings(sett);
    } catch (e) {
      console.error("Failed to load stats:", e);
    }
  };

  const projOf = (t) => projects.find((p) => (p.id || p.sk) === t.project_id);
  const areaOf = (t) => { const p = projOf(t); return p ? p.area : "admin"; };
  const active = tasks.filter((t) => t.status !== "dropped");

  const handleCarryForward = async (taskId) => {
    try {
      await api.carryForward(taskId);
      onRefresh();
    } catch (e) {
      console.error("Carry forward failed:", e);
    }
  };

  const handleDrop = async (taskId) => {
    try {
      await api.updateTask(taskId, { status: "dropped" });
      onRefresh();
    } catch (e) {
      console.error("Drop failed:", e);
    }
  };

  const handleUpdateCapacity = async (val) => {
    try {
      await api.updateSettings({ weekly_capacity_hours: val });
      if (settings) setSettings({ ...settings, weekly_capacity_hours: val });
    } catch (e) {
      console.error("Failed to update settings:", e);
    }
  };

  return (
    <>
      <h2 style={{ fontSize: 17, fontWeight: 700, fontFamily: "'IBM Plex Mono', monospace", marginBottom: 16, marginTop: 4 }}>
        Weekly Review
      </h2>

      <div style={css.card}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "#94a3b8" }}>
          {weekLabel(week)} Breakdown
        </div>

        {/* Per-area stats */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 16 }}>
          {Object.entries(AREAS).map(([k, a]) => {
            const areaStats = stats?.areas?.[k] || { total: 0, done: 0, hours: 0 };
            const pct = areaStats.total > 0 ? Math.round((areaStats.done / areaStats.total) * 100) : 0;
            return (
              <div key={k} style={{ background: "#08081a", borderRadius: 8, padding: 12, textAlign: "center", border: `1px solid ${a.color}1a` }}>
                <div style={{ fontSize: 18 }}>{a.icon}</div>
                <div style={{ fontSize: 12, fontWeight: 600, color: a.color, marginTop: 2 }}>{a.label}</div>
                <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "'IBM Plex Mono', monospace", marginTop: 2 }}>
                  {areaStats.done}/{areaStats.total}
                </div>
                <div style={{ fontSize: 10, color: "#475569" }}>{areaStats.hours}h planned</div>
                <div style={{ background: "#141432", borderRadius: 3, height: 3, marginTop: 6, overflow: "hidden" }}>
                  <div style={{ background: a.color, height: "100%", width: `${pct}%`, borderRadius: 3 }} />
                </div>
              </div>
            );
          })}
        </div>

        {/* Per-day stats */}
        {stats?.days && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 8 }}>Daily Completion</div>
            <div style={{ display: "flex", gap: 8 }}>
              {["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].map((day) => {
                const d = stats.days[day] || { tasks: 0, done: 0 };
                return (
                  <div key={day} style={{ flex: 1, textAlign: "center", background: "#08081a", borderRadius: 6, padding: "6px 4px" }}>
                    <div style={{ fontSize: 10, color: "#475569", fontWeight: 600 }}>{day.slice(0, 3).toUpperCase()}</div>
                    <div style={{ fontSize: 14, fontWeight: 700, fontFamily: "'IBM Plex Mono', monospace", color: d.done === d.tasks && d.tasks > 0 ? "#10b981" : "#e2e8f0" }}>
                      {d.done}/{d.tasks}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Neglected areas */}
        {stats?.neglected?.length > 0 && (
          <div style={{ background: "#7f1d1d22", border: "1px solid #7f1d1d44", borderRadius: 6, padding: "8px 12px", marginBottom: 12, fontSize: 12, color: "#fca5a5" }}>
            Neglected areas: {stats.neglected.map((a) => AREAS[a]?.label || a).join(", ")}
          </div>
        )}

        {/* Stale tasks */}
        {stats?.stale?.length > 0 && (
          <div style={{ background: "#78350f22", border: "1px solid #78350f44", borderRadius: 6, padding: "8px 12px", marginBottom: 12, fontSize: 12, color: "#fbbf24" }}>
            {stats.stale.length} stale task(s) carried forward 3+ weeks:
            {stats.stale.map((s) => (
              <div key={s.id} style={{ marginTop: 4, fontSize: 11 }}>
                - {s.name} ({s.carried_weeks} weeks)
              </div>
            ))}
          </div>
        )}

        {/* Unfinished tasks */}
        {(() => {
          const carry = active.filter((t) => t.status === "todo" || t.status === "doing");
          if (!carry.length)
            return <div style={{ fontSize: 13, color: "#10b981" }}>All tasks resolved this week!</div>;
          return (
            <>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#f59e0b", marginBottom: 8 }}>
                {carry.length} unfinished -- carry forward or drop?
              </div>
              {carry.map((t) => {
                const proj = projOf(t);
                const area = proj ? AREAS[proj.area] : null;
                return (
                  <div
                    key={t.id || t.sk}
                    style={{
                      display: "flex", alignItems: "center", justifyContent: "space-between",
                      background: "#08081a", borderRadius: 6, padding: "7px 11px", marginBottom: 4,
                    }}
                  >
                    <span style={{ fontSize: 12 }}>
                      {PRIORITY[t.priority]} {t.name}{" "}
                      {proj && <span style={{ color: "#475569" }}>({proj.name})</span>}
                    </span>
                    <div style={{ display: "flex", gap: 4 }}>
                      <Btn v="pri" s={{ fontSize: 10, padding: "2px 8px" }} onClick={() => handleCarryForward(t.id || t.sk)}>
                        Next Week
                      </Btn>
                      <Btn v="danger" s={{ fontSize: 10, padding: "2px 8px" }} onClick={() => handleDrop(t.id || t.sk)}>
                        Drop
                      </Btn>
                    </div>
                  </div>
                );
              })}
            </>
          );
        })()}
      </div>

      {/* Settings */}
      <div style={{ ...css.card, marginTop: 12 }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 10, color: "#94a3b8" }}>Settings</div>
        <div style={css.field}>
          <label style={css.label}>Weekly capacity (hours)</label>
          <input
            type="number"
            value={settings?.weekly_capacity_hours || capacity}
            onChange={(e) => handleUpdateCapacity(+e.target.value || 40)}
            style={{ ...css.input, width: 100 }}
          />
        </div>
        {settings && (
          <div style={{ fontSize: 11, color: "#475569", marginTop: 8 }}>
            <div>Morning briefing: {settings.morning_briefing_time}</div>
            <div>Midday check-in: {settings.midday_checkin_time}</div>
            <div>Evening summary: {settings.evening_summary_time}</div>
            <div>Agent persona: {settings.agent_persona}</div>
            <div>Timezone: {settings.timezone}</div>
          </div>
        )}
      </div>
    </>
  );
}
