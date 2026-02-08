import { useState, useEffect, useCallback } from "react";
import { getWeekId } from "./utils";
import * as api from "./api";
import Btn from "./components/Btn";
import Badge from "./components/Badge";
import TodayView from "./views/TodayView";
import WeekView from "./views/WeekView";
import ProjectsView from "./views/ProjectsView";
import ReviewView from "./views/ReviewView";

export default function App() {
  const [view, setView] = useState("today");
  const [week, setWeek] = useState(getWeekId());
  const [projects, setProjects] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [locked, setLocked] = useState(false);
  const [capacity, setCapacity] = useState(40);
  const [subtypes, setSubtypes] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const [projs, weekData, settings, subs] = await Promise.all([
        api.listProjects(),
        api.getWeek(week),
        api.getSettings(),
        api.getSubtypes(),
      ]);
      setProjects(projs);
      setTasks(weekData.tasks || []);
      setLocked(weekData.locked || false);
      setCapacity(settings.weekly_capacity_hours || 40);
      setSubtypes(subs || {});
    } catch (e) {
      console.error("Load failed:", e);
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [week]);

  useEffect(() => {
    setLoading(true);
    loadData();
  }, [loadData]);

  const handleRefresh = () => loadData();

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: "#08081a", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <span style={{ color: "#4f46e5", fontSize: 14 }}>Loading PCP Workboard...</span>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "#08081a", color: "#e2e8f0", fontFamily: "'IBM Plex Sans', system-ui, sans-serif" }}>
      {/* Header */}
      <div style={{ background: "#0d0d24", borderBottom: "1px solid #1a1a3a", padding: "12px 20px", position: "sticky", top: 0, zIndex: 100 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", maxWidth: 1120, margin: "0 auto" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <span style={{ fontSize: 18, fontWeight: 700, fontFamily: "'IBM Plex Mono', monospace", color: "#6366f1", letterSpacing: -0.5 }}>
              PCP
            </span>
            <div style={{ display: "flex", gap: 1, background: "#08081a", borderRadius: 7, padding: 2 }}>
              {[
                { key: "today", label: "Today" },
                { key: "week", label: "Week" },
                { key: "projects", label: "Projects" },
                { key: "review", label: "Review" },
              ].map((v) => (
                <button
                  key={v.key}
                  onClick={() => setView(v.key)}
                  style={{
                    padding: "5px 14px",
                    borderRadius: 5,
                    fontSize: 12,
                    fontWeight: 600,
                    border: "none",
                    background: view === v.key ? "#1a1a3a" : "transparent",
                    color: view === v.key ? "#e2e8f0" : "#475569",
                    cursor: "pointer",
                    fontFamily: "inherit",
                  }}
                >
                  {v.label}
                </button>
              ))}
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {error && (
              <span style={{ fontSize: 11, color: "#ef4444" }}>{error}</span>
            )}
            <Btn v="ghost" s={{ fontSize: 10, padding: "4px 8px" }} onClick={handleRefresh}>
              Refresh
            </Btn>
          </div>
        </div>
      </div>

      {/* Body */}
      <div style={{ maxWidth: 1120, margin: "0 auto", padding: "16px 20px" }}>
        {view === "today" && (
          <TodayView
            projects={projects}
            refreshTasks={handleRefresh}
          />
        )}

        {view === "week" && (
          <WeekView
            week={week}
            setWeek={setWeek}
            tasks={tasks}
            projects={projects}
            locked={locked}
            capacity={capacity}
            subtypes={subtypes}
            onRefresh={handleRefresh}
          />
        )}

        {view === "projects" && (
          <ProjectsView
            projects={projects}
            tasks={tasks}
            onRefresh={handleRefresh}
          />
        )}

        {view === "review" && (
          <ReviewView
            week={week}
            tasks={tasks}
            projects={projects}
            capacity={capacity}
            onRefresh={handleRefresh}
          />
        )}
      </div>
    </div>
  );
}
