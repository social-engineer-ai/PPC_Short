import { DAYS, DAY_LABELS } from "../constants";

export default function DayLoadBar({ tasks, dailyCapacity = 8 }) {
  const dayHours = {};
  DAYS.forEach((d) => { dayHours[d] = 0; });

  tasks.forEach((t) => {
    if (t.status !== "dropped" && t.day && dayHours[t.day] !== undefined) {
      dayHours[t.day] += t.estimated_hours || 0;
    }
  });

  return (
    <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
      {DAYS.map((day) => {
        const hrs = dayHours[day];
        const pct = Math.min((hrs / dailyCapacity) * 100, 100);
        const over = hrs > dailyCapacity;
        return (
          <div key={day} style={{ flex: 1, minWidth: 80 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
              <span style={{ fontSize: 10, fontWeight: 600, color: "#64748b" }}>
                {DAY_LABELS[day]}
              </span>
              <span style={{ fontSize: 10, color: over ? "#ef4444" : "#475569" }}>
                {hrs}h{over ? " !!!" : ""}
              </span>
            </div>
            <div style={{ background: "#08081a", borderRadius: 3, height: 4, overflow: "hidden" }}>
              <div
                style={{
                  background: over ? "#ef4444" : hrs > dailyCapacity * 0.8 ? "#f59e0b" : "#4f46e5",
                  height: "100%",
                  width: `${pct}%`,
                  borderRadius: 3,
                  transition: "width 0.2s",
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
