import { useState } from "react";
import { AREAS, SUBTYPES as DEFAULT_SUBTYPES, PRIORITY, PRIO_ORDER, DAYS, css } from "../constants";
import { weekLabel, shiftWeek, getWeekId } from "../utils";
import * as api from "../api";
import Btn from "../components/Btn";
import Badge from "../components/Badge";
import Scoreboard from "../components/Scoreboard";
import TaskCard from "../components/TaskCard";
import DayLoadBar from "../components/DayLoadBar";

export default function WeekView({ week, setWeek, tasks, projects, locked, capacity, subtypes: dynamicSubtypes, onRefresh }) {
  const SUBTYPES = dynamicSubtypes && Object.keys(dynamicSubtypes).length > 0 ? dynamicSubtypes : DEFAULT_SUBTYPES;
  const [filter, setFilter] = useState("all");
  const [modal, setModal] = useState(null);
  const [pendingTask, setPending] = useState(null);
  const [form, setForm] = useState({
    name: "", projectId: "", subtype: "", priority: "normal",
    hours: 1, notes: "", due: "", recurring: false, courseWeek: "", day: "",
  });

  const active = tasks.filter((t) => t.status !== "dropped");
  const projOf = (t) => projects.find((p) => (p.id || p.sk) === t.project_id);
  const areaOf = (t) => { const p = projOf(t); return p ? p.area : "admin"; };
  const subtypesFor = (pid) => {
    const p = projects.find((x) => (x.id || x.sk) === pid);
    return p ? SUBTYPES[p.area] || [] : [];
  };

  const filtered = tasks.filter((t) => filter === "all" || areaOf(t) === filter);
  const byStatus = (s) =>
    filtered
      .filter((t) => t.status === s)
      .sort((a, b) => (PRIO_ORDER[a.priority] || 2) - (PRIO_ORDER[b.priority] || 2));

  // Neglect detection
  const neglected = Object.entries(AREAS)
    .filter(([k]) => !tasks.some((t) => areaOf(t) === k && t.status !== "dropped"))
    .map(([, a]) => a);

  const handleStatusChange = async (taskId, newStatus) => {
    try {
      await api.updateTask(taskId, { status: newStatus });
      onRefresh();
    } catch (e) {
      console.error("Failed to update:", e);
    }
  };

  const handleDrop = async (taskId) => {
    await api.updateTask(taskId, { status: "dropped" });
    onRefresh();
  };

  const handleRestore = async (taskId) => {
    await api.updateTask(taskId, { status: "todo" });
    onRefresh();
  };

  const handleDelete = async (taskId) => {
    await api.deleteTask(taskId);
    onRefresh();
  };

  const handleAddTask = async () => {
    const taskData = {
      week_id: week,
      name: form.name,
      project_id: form.projectId,
      subtype: form.subtype,
      priority: form.priority,
      estimated_hours: form.hours,
      notes: form.notes,
      due_date: form.due || null,
      recurring: form.recurring,
      course_week: form.courseWeek || null,
      day: form.day || null,
    };

    try {
      await api.createTask(taskData);
      setModal(null);
      setForm({ name: "", projectId: form.projectId, subtype: "", priority: "normal", hours: 1, notes: "", due: "", recurring: false, courseWeek: "", day: "" });
      onRefresh();
    } catch (e) {
      if (e.status === 409) {
        // Week locked, need trade
        setPending(taskData);
        setModal("trade");
      } else {
        console.error("Failed to add task:", e);
      }
    }
  };

  const handleTrade = async (dropId) => {
    try {
      await api.createTask({ ...pendingTask, drop_task_id: dropId });
      setModal(null);
      setPending(null);
      onRefresh();
    } catch (e) {
      console.error("Trade failed:", e);
    }
  };

  const handleCopyRecurring = async () => {
    await api.copyRecurring(week);
    onRefresh();
  };

  const handleLockToggle = async () => {
    if (locked) await api.unlockWeek(week);
    else await api.lockWeek(week);
    onRefresh();
  };

  return (
    <>
      {/* Week nav */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button onClick={() => setWeek(shiftWeek(week, -1))} style={{ background: "none", border: "none", color: "#475569", fontSize: 16, cursor: "pointer" }}>&lt;</button>
          <div>
            <span style={{ fontSize: 17, fontWeight: 700, fontFamily: "'IBM Plex Mono', monospace" }}>{weekLabel(week)}</span>
            {week === getWeekId() && <Badge bg="#059669" s={{ marginLeft: 8 }}>NOW</Badge>}
          </div>
          <button onClick={() => setWeek(shiftWeek(week, 1))} style={{ background: "none", border: "none", color: "#475569", fontSize: 16, cursor: "pointer" }}>&gt;</button>
          {week !== getWeekId() && (
            <button onClick={() => setWeek(getWeekId())} style={{ background: "none", border: "none", color: "#4f46e5", fontSize: 12, cursor: "pointer", fontFamily: "inherit" }}>
              Today
            </button>
          )}
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <Btn v="pri" onClick={() => {
            setForm({ name: "", projectId: "", subtype: "", priority: "normal", hours: 1, notes: "", due: "", recurring: false, courseWeek: "", day: "" });
            setModal("task");
          }}>+ Task</Btn>
          <Btn v="ghost" onClick={handleCopyRecurring}>Recurring</Btn>
          <Btn v={locked ? "warn" : "lock"} onClick={handleLockToggle}>
            {locked ? "Unlock" : "Lock Week"}
          </Btn>
        </div>
      </div>

      {/* Scoreboard */}
      <Scoreboard tasks={tasks} capacity={capacity} locked={locked} />

      {/* Day load bar */}
      <DayLoadBar tasks={active} dailyCapacity={capacity / 5} />

      {/* Neglect warning */}
      {neglected.length > 0 && (
        <div style={{ background: "#7f1d1d22", border: "1px solid #7f1d1d44", borderRadius: 8, padding: "8px 12px", marginBottom: 12, fontSize: 12, color: "#fca5a5" }}>
          Nothing planned for: {neglected.map((n) => `${n.icon} ${n.label}`).join(", ")}
        </div>
      )}

      {/* Area filter */}
      <div style={{ display: "flex", gap: 4, marginBottom: 14 }}>
        {[["all", "All", "#94a3b8"], ...Object.entries(AREAS).map(([k, a]) => [k, `${a.icon} ${a.label}`, a.color])].map(
          ([k, l, c]) => (
            <button
              key={k}
              onClick={() => setFilter(k)}
              style={{
                padding: "4px 10px", borderRadius: 5, fontSize: 11, fontWeight: 600, border: "none",
                background: filter === k ? (k === "all" ? "#1a1a3a" : c + "18") : "transparent",
                color: filter === k ? (k === "all" ? "#e2e8f0" : c) : "#475569",
                cursor: "pointer", fontFamily: "inherit",
              }}
            >
              {l}
            </button>
          )
        )}
      </div>

      {/* Kanban */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
        {[["todo", "To Do", "#94a3b8"], ["doing", "In Progress", "#3b82f6"], ["done", "Done", "#10b981"]].map(
          ([s, label, clr]) => (
            <div key={s}>
              <div style={{ fontSize: 11, fontWeight: 700, color: clr, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.8 }}>
                {label} ({byStatus(s).length})
              </div>
              {byStatus(s).map((t) => (
                <TaskCard
                  key={t.id || t.sk}
                  task={t}
                  project={projOf(t)}
                  onStatusChange={handleStatusChange}
                  onDrop={handleDrop}
                  onRestore={handleRestore}
                  onDelete={handleDelete}
                />
              ))}
              {s === "done" && byStatus("dropped").length > 0 && (
                <>
                  <div style={{ fontSize: 10, fontWeight: 700, color: "#3f3f5e", marginTop: 12, marginBottom: 6, textTransform: "uppercase" }}>
                    Dropped ({byStatus("dropped").length})
                  </div>
                  {byStatus("dropped").map((t) => (
                    <TaskCard
                      key={t.id || t.sk}
                      task={t}
                      project={projOf(t)}
                      onStatusChange={handleStatusChange}
                      onDrop={handleDrop}
                      onRestore={handleRestore}
                      onDelete={handleDelete}
                    />
                  ))}
                </>
              )}
            </div>
          )
        )}
      </div>

      {/* Add Task Modal */}
      {modal === "task" && (
        <div style={css.modal} onClick={() => setModal(null)}>
          <div style={css.modalBox} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>Add Task</h3>
              <button onClick={() => setModal(null)} style={{ background: "none", border: "none", color: "#475569", fontSize: 18, cursor: "pointer" }}>x</button>
            </div>
            <div style={css.field}>
              <label style={css.label}>Task name *</label>
              <input style={css.input} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g., Prepare Week 5 slides" autoFocus />
            </div>
            <div style={css.field}>
              <label style={css.label}>Project *</label>
              <select style={css.select} value={form.projectId} onChange={(e) => setForm({ ...form, projectId: e.target.value, subtype: "" })}>
                <option value="">Select...</option>
                {projects.filter((p) => p.active !== false).map((p) => (
                  <option key={p.id || p.sk} value={p.id || p.sk}>
                    {AREAS[p.area]?.icon} {p.name}
                  </option>
                ))}
              </select>
            </div>
            {form.projectId && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <div style={css.field}>
                  <label style={css.label}>Type</label>
                  <select style={css.select} value={form.subtype} onChange={(e) => setForm({ ...form, subtype: e.target.value })}>
                    <option value="">General</option>
                    {subtypesFor(form.projectId).map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
                {projects.find((p) => (p.id || p.sk) === form.projectId)?.area === "teaching" && (
                  <div style={css.field}>
                    <label style={css.label}>Course Week #</label>
                    <input style={css.input} type="number" value={form.courseWeek} onChange={(e) => setForm({ ...form, courseWeek: e.target.value })} placeholder="e.g., 5" />
                  </div>
                )}
              </div>
            )}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
              <div style={css.field}>
                <label style={css.label}>Priority</label>
                <select style={css.select} value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
                  {Object.entries(PRIORITY).map(([k, v]) => (
                    <option key={k} value={k}>{v} {k}</option>
                  ))}
                </select>
              </div>
              <div style={css.field}>
                <label style={css.label}>Hours</label>
                <input style={css.input} type="number" step="0.5" value={form.hours} onChange={(e) => setForm({ ...form, hours: +e.target.value || 0 })} />
              </div>
              <div style={css.field}>
                <label style={css.label}>Day</label>
                <select style={css.select} value={form.day} onChange={(e) => setForm({ ...form, day: e.target.value })}>
                  <option value="">Unscheduled</option>
                  {DAYS.map((d) => (
                    <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>
                  ))}
                </select>
              </div>
            </div>
            <div style={css.field}>
              <label style={css.label}>Due date</label>
              <input style={css.input} type="date" value={form.due} onChange={(e) => setForm({ ...form, due: e.target.value })} />
            </div>
            <div style={css.field}>
              <label style={css.label}>Notes</label>
              <input style={css.input} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Details..." />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 14 }}>
              <input type="checkbox" checked={form.recurring} onChange={(e) => setForm({ ...form, recurring: e.target.checked })} id="rec" />
              <label htmlFor="rec" style={{ fontSize: 12, color: "#94a3b8" }}>Recurring every week</label>
            </div>
            <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
              <Btn v="ghost" onClick={() => setModal(null)}>Cancel</Btn>
              <Btn v="pri" disabled={!form.name || !form.projectId} onClick={handleAddTask}>
                {locked ? "Add (trade required)" : "Add Task"}
              </Btn>
            </div>
          </div>
        </div>
      )}

      {/* Trade Modal */}
      {modal === "trade" && pendingTask && (
        <div style={css.modal} onClick={() => { setModal(null); setPending(null); }}>
          <div style={{ ...css.modalBox, width: 540 }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#f59e0b" }}>Trade Required</h3>
              <button onClick={() => { setModal(null); setPending(null); }} style={{ background: "none", border: "none", color: "#475569", fontSize: 18, cursor: "pointer" }}>x</button>
            </div>
            <div style={{ fontSize: 13, color: "#e2e8f0", marginBottom: 6 }}>
              Adding: <strong>{pendingTask.name}</strong>
            </div>
            <div style={{ fontSize: 12, color: "#fca5a5", marginBottom: 14 }}>
              Week is locked. Pick something to drop:
            </div>
            {active.filter((t) => t.status !== "done").map((t) => {
              const proj = projOf(t);
              const area = proj ? AREAS[proj.area] : null;
              return (
                <div key={t.id || t.sk} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: "#08081a", borderRadius: 6, padding: "8px 12px", marginBottom: 4, border: "1px solid #141432" }}>
                  <div>
                    <span style={{ fontSize: 12 }}>{PRIORITY[t.priority]} {t.name}</span>
                    {proj && <Badge bg={area.color + "1a"} color={area.color} s={{ marginLeft: 6 }}>{proj.name}</Badge>}
                  </div>
                  <Btn v="danger" s={{ fontSize: 10, padding: "3px 10px" }} onClick={() => handleTrade(t.id || t.sk)}>
                    Drop & Add new
                  </Btn>
                </div>
              );
            })}
            <div style={{ marginTop: 10, textAlign: "right" }}>
              <Btn v="ghost" onClick={() => { setModal(null); setPending(null); }}>Cancel</Btn>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
