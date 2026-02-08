export default function Btn({ children, onClick, v = "default", disabled, s = {} }) {
  const map = {
    pri: { background: "#4f46e5", color: "#fff", border: "none" },
    danger: { background: "#b91c1c", color: "#fff", border: "none" },
    warn: { background: "#b45309", color: "#fff", border: "none" },
    lock: { background: "#6d28d9", color: "#fff", border: "none" },
    success: { background: "#047857", color: "#fff", border: "none" },
    ghost: { background: "transparent", color: "#94a3b8", border: "1px solid #1a1a3a" },
    default: { background: "#141432", color: "#cbd5e1", border: "1px solid #1a1a3a" },
  };
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: "6px 14px",
        borderRadius: 6,
        fontSize: 12,
        cursor: disabled ? "not-allowed" : "pointer",
        fontWeight: 600,
        fontFamily: "inherit",
        opacity: disabled ? 0.4 : 1,
        transition: "all 0.12s",
        ...map[v],
        ...s,
      }}
    >
      {children}
    </button>
  );
}
