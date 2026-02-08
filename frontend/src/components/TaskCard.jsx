import { AREAS, PRIORITY, DAY_LABELS } from "../constants";
import Badge from "./Badge";

export default function TaskCard({ task, project, onStatusChange, onDrop, onRestore, onDelete }) {
  const area = project ? AREAS[project.area] : null;

  const handleToggle = () => {
    if (task.status === "todo") onStatusChange(task.id || task.sk, "doing");
    else if (task.status === "doing") onStatusChange(task.id || task.sk, "done");
  };

  return (
    <div
      style={{
        background: task.status === "done" ? "#081a14" : "#0b0b22",
        border: `1px solid ${task.status === "doing" ? "#3b82f644" : "#141432"}`,
        borderLeft: `3px solid ${area?.color || "#475569"}`,
        borderRadius: 7,
        padding: "10px 12px",
        marginBottom: 5,
        opacity: task.status === "done" ? 0.75 : 1,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
        <span
          style={{ fontSize: 13, cursor: "pointer", marginTop: 1, userSelect: "none" }}
          onClick={handleToggle}
        >
          {task.status === "done" ? "\u2705" : task.status === "doing" ? "\uD83D\uDD35" : "\u2B1C"}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <span
              style={{
                fontSize: 12.5,
                fontWeight: 500,
                color: task.status === "done" ? "#10b981" : "#e2e8f0",
              }}
            >
              {PRIORITY[task.priority]} {task.name}
            </span>
            {task.recurring && <span style={{ fontSize: 10, color: "#8b5cf6" }}>{"\uD83D\uDD01"}</span>}
          </div>
          <div style={{ display: "flex", gap: 6, marginTop: 3, flexWrap: "wrap", alignItems: "center" }}>
            {project && <Badge bg={area.color + "1a"} color={area.color}>{project.name}</Badge>}
            {task.subtype && <Badge bg="#141432" color="#64748b">{task.subtype}</Badge>}
            {task.course_week && <Badge bg="#141432" color="#64748b">CW{task.course_week}</Badge>}
            {task.day && <Badge bg="#141432" color="#475569">{DAY_LABELS[task.day] || task.day}</Badge>}
            {task.estimated_hours > 0 && (
              <span style={{ fontSize: 10, color: "#475569" }}>{task.estimated_hours}h</span>
            )}
            {task.block_start && (
              <span style={{ fontSize: 10, color: "#475569" }}>{task.block_start}</span>
            )}
          </div>
          {task.notes && <div style={{ fontSize: 11, color: "#475569", marginTop: 4 }}>{task.notes}</div>}
          <div style={{ display: "flex", gap: 4, marginTop: 6 }}>
            {task.status !== "done" && task.status !== "dropped" && (
              <button
                onClick={() => onDrop(task.id || task.sk)}
                style={{
                  background: "none", border: "none", color: "#64748b",
                  fontSize: 10, cursor: "pointer", fontFamily: "inherit", padding: 0,
                }}
              >
                x drop
              </button>
            )}
            {task.status === "dropped" && (
              <button
                onClick={() => onRestore(task.id || task.sk)}
                style={{
                  background: "none", border: "none", color: "#64748b",
                  fontSize: 10, cursor: "pointer", fontFamily: "inherit", padding: 0,
                }}
              >
                restore
              </button>
            )}
            <button
              onClick={() => onDelete(task.id || task.sk)}
              style={{
                background: "none", border: "none", color: "#3f3f5e",
                fontSize: 10, cursor: "pointer", fontFamily: "inherit", padding: 0,
              }}
            >
              del
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
