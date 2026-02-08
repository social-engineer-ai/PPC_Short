export const AREAS = {
  teaching: { label: "Teaching", icon: "\uD83D\uDCDA", color: "#06b6d4" },
  research: { label: "Research", icon: "\uD83D\uDD2C", color: "#8b5cf6" },
  admin: { label: "Admin", icon: "\uD83D\uDCCB", color: "#f59e0b" },
  personal: { label: "Personal", icon: "\uD83C\uDFE0", color: "#10b981" },
};

export const SUBTYPES = {
  teaching: ["Lecture Content", "Slides", "Examples", "Labs", "Homework", "Grading", "Office Hours", "Student Issues"],
  research: ["Planning", "Writing", "Analysis", "Experiments", "IRB", "Submissions", "Lit Review", "Collaboration"],
  admin: ["Email", "Meetings", "Reports", "Committee", "Letters", "Scheduling"],
  personal: ["Family", "House", "Finances", "Taxes", "Doctors", "Insurance", "Kids School", "Errands"],
};

export const PRIORITY = { urgent: "\uD83D\uDD34", high: "\uD83D\uDFE0", normal: "\uD83D\uDFE1", low: "\u26AA" };
export const PRIO_ORDER = { urgent: 0, high: 1, normal: 2, low: 3 };

export const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

export const DAY_LABELS = {
  monday: "Mon",
  tuesday: "Tue",
  wednesday: "Wed",
  thursday: "Thu",
  friday: "Fri",
  saturday: "Sat",
  sunday: "Sun",
  weekend: "Wknd",
};

export const css = {
  page: { minHeight: "100vh", background: "#08081a", color: "#e2e8f0", fontFamily: "'IBM Plex Sans', system-ui, sans-serif" },
  header: { background: "#0d0d24", borderBottom: "1px solid #1a1a3a", padding: "12px 20px", position: "sticky", top: 0, zIndex: 100 },
  headerInner: { display: "flex", justifyContent: "space-between", alignItems: "center", maxWidth: 1120, margin: "0 auto" },
  body: { maxWidth: 1120, margin: "0 auto", padding: "16px 20px" },
  card: { background: "#0e0e28", border: "1px solid #1a1a3a", borderRadius: 10, padding: 16, marginBottom: 12 },
  modal: { position: "fixed", inset: 0, zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(0,0,0,0.65)", backdropFilter: "blur(3px)" },
  modalBox: { background: "#0e0e28", border: "1px solid #1a1a3a", borderRadius: 12, padding: 24, width: 480, maxHeight: "85vh", overflowY: "auto" },
  input: { background: "#08081a", border: "1px solid #1a1a3a", borderRadius: 6, padding: "8px 11px", color: "#e2e8f0", fontSize: 13, width: "100%", boxSizing: "border-box", fontFamily: "inherit" },
  select: { background: "#08081a", border: "1px solid #1a1a3a", borderRadius: 6, padding: "8px 11px", color: "#e2e8f0", fontSize: 13, width: "100%", fontFamily: "inherit" },
  label: { display: "block", fontSize: 11, color: "#64748b", marginBottom: 3, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 },
  field: { marginBottom: 12 },
};
