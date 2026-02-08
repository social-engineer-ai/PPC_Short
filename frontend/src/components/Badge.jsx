export default function Badge({ children, bg, color = "#fff", s = {} }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "1px 7px",
        borderRadius: 4,
        fontSize: 10,
        fontWeight: 700,
        background: bg,
        color,
        ...s,
      }}
    >
      {children}
    </span>
  );
}
