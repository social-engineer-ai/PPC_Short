const API_URL = import.meta.env.VITE_API_URL || "";
const API_KEY = import.meta.env.VITE_API_KEY || "dev-key";

const headers = () => ({
  "Content-Type": "application/json",
  Authorization: `Bearer ${API_KEY}`,
});

async function request(method, path, body = null) {
  const opts = { method, headers: headers() };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(`${API_URL}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const error = new Error(err.detail ? (typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail)) : `API error ${res.status}`);
    error.status = res.status;
    error.data = err.detail;
    throw error;
  }
  if (res.status === 204) return null;
  return res.json();
}

// Projects
export const listProjects = (active) =>
  request("GET", `/api/projects/${active != null ? `?active=${active}` : ""}`);
export const createProject = (data) => request("POST", "/api/projects/", data);
export const updateProject = (id, data) => request("PATCH", `/api/projects/${id}`);
export const deleteProject = (id) => request("DELETE", `/api/projects/${id}`);

// Tasks
export const listTasks = (weekId, day) => {
  let url = `/api/tasks/?week_id=${weekId}`;
  if (day) url += `&day=${day}`;
  return request("GET", url);
};
export const createTask = (data) => request("POST", "/api/tasks/", data);
export const updateTask = (id, data) => request("PATCH", `/api/tasks/${id}`, data);
export const deleteTask = (id) => request("DELETE", `/api/tasks/${id}`);
export const copyRecurring = (weekId) => request("POST", `/api/tasks/copy-recurring?week_id=${weekId}`);
export const carryForward = (taskId, targetWeek) =>
  request("POST", `/api/tasks/${taskId}/carry-forward${targetWeek ? `?target_week=${targetWeek}` : ""}`);

// Day Plans
export const getDayPlan = (date) => request("GET", `/api/dayplan/${date}`);
export const generateDayPlan = (date) => request("POST", `/api/dayplan/${date}/generate`);
export const updateDayPlan = (date, data) => request("PATCH", `/api/dayplan/${date}`, data);

// Weeks
export const getWeek = (weekId) => request("GET", `/api/weeks/${weekId}`);
export const lockWeek = (weekId) => request("POST", `/api/weeks/${weekId}/lock`);
export const unlockWeek = (weekId) => request("POST", `/api/weeks/${weekId}/unlock`);
export const getWeekStats = (weekId) => request("GET", `/api/weeks/${weekId}/stats`);

// Settings
export const getSettings = () => request("GET", "/api/settings/");
export const updateSettings = (data) => request("PATCH", "/api/settings/", data);
export const getSubtypes = () => request("GET", "/api/settings/subtypes");
