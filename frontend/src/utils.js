export const getWeekId = () => {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + 3 - ((d.getDay() + 6) % 7));
  const w1 = new Date(d.getFullYear(), 0, 4);
  const wn = 1 + Math.round(((d - w1) / 864e5 - 3 + ((w1.getDay() + 6) % 7)) / 7);
  return `${d.getFullYear()}-W${String(wn).padStart(2, "0")}`;
};

export const weekLabel = (id) => {
  const [y, w] = id.split("-W");
  return `Week ${+w}, ${y}`;
};

export const shiftWeek = (id, dir) => {
  const [y, w] = id.split("-W").map(Number);
  let nw = w + dir, ny = y;
  if (nw < 1) { ny--; nw = 52; }
  if (nw > 52) { ny++; nw = 1; }
  return `${ny}-W${String(nw).padStart(2, "0")}`;
};

export const getTodayDate = () => {
  const d = new Date();
  return d.toISOString().split("T")[0];
};

export const getDayName = (dateStr) => {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("en-US", { weekday: "long" }).toLowerCase();
};

export const formatDate = (dateStr) => {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });
};

export const formatTime = (timeStr) => {
  if (!timeStr) return "";
  const [h, m] = timeStr.split(":").map(Number);
  const period = h >= 12 ? "PM" : "AM";
  const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${h12}:${String(m).padStart(2, "0")} ${period}`;
};

export const getCurrentTimeMinutes = () => {
  const now = new Date();
  return now.getHours() * 60 + now.getMinutes();
};

export const timeToMinutes = (timeStr) => {
  if (!timeStr) return 0;
  const [h, m] = timeStr.split(":").map(Number);
  return h * 60 + m;
};

export const weekIdToDates = (weekId) => {
  const [year, weekNum] = weekId.split("-W").map(Number);
  // ISO week: Monday of week 1 contains Jan 4
  const jan4 = new Date(year, 0, 4);
  const startOfWeek1 = new Date(jan4);
  startOfWeek1.setDate(jan4.getDate() - jan4.getDay() + 1); // Monday
  if (jan4.getDay() === 0) startOfWeek1.setDate(startOfWeek1.getDate() - 7);

  const monday = new Date(startOfWeek1);
  monday.setDate(startOfWeek1.getDate() + (weekNum - 1) * 7);

  const days = {};
  const names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
  names.forEach((name, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    days[name] = d.toISOString().split("T")[0];
  });
  return days;
};
