import { useState, useEffect } from "react";
import { AREAS } from "../constants";
import { getTodayDate, formatDate, getCurrentTimeMinutes, timeToMinutes, getWeekId } from "../utils";
import * as api from "../api";
import TimeBlock from "../components/TimeBlock";
import Btn from "../components/Btn";

export default function TodayView({ projects, refreshTasks }) {
  const [dayPlan, setDayPlan] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [weekStats, setWeekStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [currentMinutes, setCurrentMinutes] = useState(getCurrentTimeMinutes());

  const today = getTodayDate();
  const weekId = getWeekId();

  useEffect(() => {
    loadData();
  }, []);

  // Update "NOW" indicator every minute
  useEffect(() => {
    const interval = setInterval(() => setCurrentMinutes(getCurrentTimeMinutes()), 60000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [plan, weekData] = await Promise.all([
        api.getDayPlan(today),
        api.getWeekStats(weekId),
      ]);

      // Load tasks that are referenced in the day plan
      const weekTasks = await api.listTasks(weekId);
      setDayPlan(plan);
      setTasks(weekTasks);
      setWeekStats(weekData);
    } catch (e) {
      console.error("Failed to load today data:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    try {
      const plan = await api.generateDayPlan(today);
      setDayPlan(plan);
      const weekTasks = await api.listTasks(weekId);
      setTasks(weekTasks);
    } catch (e) {
      console.error("Failed to generate day plan:", e);
    }
  };

  const handleStatusChange = async (taskId, newStatus) => {
    try {
      await api.updateTask(taskId, { status: newStatus });
      setTasks((prev) =>
        prev.map((t) => ((t.id || t.sk) === taskId ? { ...t, status: newStatus } : t))
      );
      if (refreshTasks) refreshTasks();
    } catch (e) {
      console.error("Failed to update task:", e);
    }
  };

  const getTaskForBlock = (block) => {
    if (!block.task_id) return null;
    return tasks.find((t) => (t.id || t.sk) === block.task_id);
  };

  const getProjectForTask = (task) => {
    if (!task) return null;
    return projects.find((p) => (p.id || p.sk) === task.project_id);
  };

  const isCurrentBlock = (block) => {
    const start = timeToMinutes(block.start);
    const end = timeToMinutes(block.end);
    return currentMinutes >= start && currentMinutes < end;
  };

  if (loading) {
    return <div style={{ padding: 20, color: "#475569" }}>Loading today's plan...</div>;
  }

  const blocks = dayPlan?.blocks || [];
  const todayTasks = tasks.filter((t) => {
    const dayName = new Date(today + "T12:00:00").toLocaleDateString("en-US", { weekday: "long" }).toLowerCase();
    return t.day === dayName && t.status !== "dropped";
  });
  const doneTasks = todayTasks.filter((t) => t.status === "done");
  const totalAreas = weekStats?.areas || {};
  const weekTotal = Object.values(totalAreas).reduce((s, a) => s + a.total, 0);
  const weekDone = Object.values(totalAreas).reduce((s, a) => s + a.done, 0);
  const weekPct = weekTotal > 0 ? Math.round((weekDone / weekTotal) * 100) : 0;

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <h2 style={{ fontSize: 17, fontWeight: 700, fontFamily: "'IBM Plex Mono', monospace", margin: 0 }}>
            TODAY -- {formatDate(today)}
          </h2>
          <span style={{ fontSize: 12, color: "#475569" }}>
            Week {weekId.split("-W")[1]}: {weekPct}% done ({weekDone}/{weekTotal} tasks)
          </span>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {blocks.length === 0 && (
            <Btn v="pri" onClick={handleGenerate}>Generate Day Plan</Btn>
          )}
          {blocks.length > 0 && (
            <Btn v="ghost" onClick={handleGenerate}>Regenerate</Btn>
          )}
        </div>
      </div>

      {/* Day summary bar */}
      <div
        style={{
          background: "#0e0e28",
          border: "1px solid #1a1a3a",
          borderRadius: 10,
          padding: "12px 16px",
          marginBottom: 14,
          display: "flex",
          gap: 20,
          fontSize: 12,
        }}
      >
        <span style={{ color: "#94a3b8" }}>
          {todayTasks.reduce((s, t) => s + (t.estimated_hours || 0), 0)}h planned
        </span>
        <span style={{ color: "#059669" }}>{doneTasks.length} done</span>
        <span style={{ color: "#3b82f6" }}>
          {todayTasks.filter((t) => t.status === "doing").length} in progress
        </span>
        {todayTasks.filter((t) => t.priority === "urgent").length > 0 && (
          <span style={{ color: "#ef4444" }}>
            {todayTasks.filter((t) => t.priority === "urgent").length} urgent
          </span>
        )}
      </div>

      {/* Timeline */}
      {blocks.length > 0 ? (
        <div
          style={{
            background: "#0e0e28",
            border: "1px solid #1a1a3a",
            borderRadius: 10,
            padding: 16,
          }}
        >
          {blocks.map((block, i) => {
            const task = getTaskForBlock(block);
            const project = getProjectForTask(task);
            return (
              <TimeBlock
                key={i}
                block={block}
                task={task}
                project={project}
                isCurrent={isCurrentBlock(block)}
                onStatusChange={handleStatusChange}
              />
            );
          })}
        </div>
      ) : (
        <div
          style={{
            background: "#0e0e28",
            border: "1px solid #1a1a3a",
            borderRadius: 10,
            padding: 40,
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: 14, color: "#475569", marginBottom: 12 }}>
            No day plan generated yet.
          </div>
          <div style={{ fontSize: 12, color: "#3f3f5e" }}>
            Assign tasks to today in Week View, then generate a day plan.
          </div>
        </div>
      )}

      {/* Unblocked tasks (assigned to today but not in blocks) */}
      {(() => {
        const blockedIds = new Set(blocks.filter((b) => b.task_id).map((b) => b.task_id));
        const unblockedTasks = todayTasks.filter((t) => !blockedIds.has(t.id || t.sk));
        if (unblockedTasks.length === 0) return null;
        return (
          <div style={{ marginTop: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "#64748b", marginBottom: 8, textTransform: "uppercase" }}>
              Unscheduled for Today ({unblockedTasks.length})
            </div>
            {unblockedTasks.map((t) => {
              const proj = getProjectForTask(t);
              const area = proj ? AREAS[proj.area] : null;
              return (
                <div
                  key={t.id || t.sk}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    background: "#0b0b22",
                    border: "1px solid #141432",
                    borderLeft: `3px solid ${area?.color || "#475569"}`,
                    borderRadius: 6,
                    padding: "8px 12px",
                    marginBottom: 4,
                  }}
                >
                  <span
                    style={{ cursor: "pointer", userSelect: "none" }}
                    onClick={() => handleStatusChange(t.id || t.sk, t.status === "todo" ? "doing" : "done")}
                  >
                    {t.status === "done" ? "\u2705" : t.status === "doing" ? "\uD83D\uDD35" : "\u2B1C"}
                  </span>
                  <span style={{ fontSize: 12, color: "#e2e8f0" }}>{t.name}</span>
                  <span style={{ fontSize: 10, color: "#475569", marginLeft: "auto" }}>{t.estimated_hours}h</span>
                </div>
              );
            })}
          </div>
        );
      })()}
    </div>
  );
}
