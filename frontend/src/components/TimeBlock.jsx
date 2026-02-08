import { AREAS, PRIORITY } from "../constants";
import { formatTime, getCurrentTimeMinutes, timeToMinutes } from "../utils";

export default function TimeBlock({ block, task, project, isCurrent, onStatusChange }) {
  const area = project ? AREAS[project.area] : null;
  const isBreak = block.type === "break";

  return (
    <div
      style={{
        display: "flex",
        gap: 12,
        padding: "10px 0",
        borderLeft: `3px solid ${isCurrent ? "#4f46e5" : isBreak ? "#1a1a3a" : area?.color || "#475569"}`,
        paddingLeft: 16,
        background: isCurrent ? "#4f46e508" : "transparent",
        transition: "background 0.2s",
      }}
    >
      {/* Time column */}
      <div style={{ width: 55, flexShrink: 0, textAlign: "right" }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: isCurrent ? "#4f46e5" : "#64748b", fontFamily: "'IBM Plex Mono', monospace" }}>
          {formatTime(block.start)}
        </div>
        <div style={{ fontSize: 10, color: "#3f3f5e", fontFamily: "'IBM Plex Mono', monospace" }}>
          {formatTime(block.end)}
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1 }}>
        {isBreak ? (
          <div style={{ fontSize: 12, color: "#475569", fontStyle: "italic" }}>
            {block.label || "Break"}
          </div>
        ) : task ? (
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span
                style={{ fontSize: 14, cursor: "pointer", userSelect: "none" }}
                onClick={() => {
                  if (!onStatusChange) return;
                  if (task.status === "todo") onStatusChange(task.id || task.sk, "doing");
                  else if (task.status === "doing") onStatusChange(task.id || task.sk, "done");
                }}
              >
                {task.status === "done" ? "\u2705" : task.status === "doing" ? "\uD83D\uDD35" : "\u2B1C"}
              </span>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 500,
                  color: task.status === "done" ? "#10b981" : "#e2e8f0",
                  textDecoration: task.status === "done" ? "line-through" : "none",
                }}
              >
                {task.name}
              </span>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 4, marginLeft: 22 }}>
              {project && (
                <span style={{ fontSize: 10, color: area?.color || "#475569", fontWeight: 600 }}>
                  {project.name}
                </span>
              )}
              {task.subtype && (
                <span style={{ fontSize: 10, color: "#475569" }}>{task.subtype}</span>
              )}
              <span style={{ fontSize: 10, color: "#3f3f5e" }}>{task.estimated_hours}h</span>
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 12, color: "#3f3f5e" }}>Unassigned block</div>
        )}
      </div>

      {/* Current indicator */}
      {isCurrent && (
        <div style={{ fontSize: 10, color: "#4f46e5", fontWeight: 700, alignSelf: "center" }}>NOW</div>
      )}
    </div>
  );
}
