import { useState } from "react";
import { AREAS, css } from "../constants";
import * as api from "../api";
import Btn from "../components/Btn";

export default function ProjectsView({ projects, tasks, onRefresh }) {
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({ name: "", area: "teaching", desc: "" });

  const handleAdd = async () => {
    try {
      await api.createProject({
        name: form.name,
        area: form.area,
        description: form.desc,
        match_keywords: [],
      });
      setModal(false);
      setForm({ name: "", area: "teaching", desc: "" });
      onRefresh();
    } catch (e) {
      console.error("Failed to create project:", e);
    }
  };

  const handleToggleActive = async (project) => {
    try {
      await api.updateProject(project.id || project.sk, { active: !project.active });
      onRefresh();
    } catch (e) {
      console.error("Failed to toggle project:", e);
    }
  };

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ fontSize: 17, fontWeight: 700, fontFamily: "'IBM Plex Mono', monospace", margin: 0 }}>
          Projects & Areas
        </h2>
        <Btn v="ghost" onClick={() => { setForm({ name: "", area: "teaching", desc: "" }); setModal(true); }}>
          + Project
        </Btn>
      </div>

      {Object.entries(AREAS).map(([ak, area]) => {
        const projs = projects.filter((p) => p.area === ak);
        return (
          <div key={ak} style={{ marginBottom: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
              <span style={{ fontSize: 14 }}>{area.icon}</span>
              <span style={{ fontSize: 14, fontWeight: 700, color: area.color }}>{area.label}</span>
              <span style={{ fontSize: 11, color: "#475569" }}>({projs.length})</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 8 }}>
              {projs.map((p) => {
                const pts = tasks.filter((t) => t.project_id === (p.id || p.sk));
                const act = pts.filter((t) => t.status !== "dropped" && t.status !== "done").length;
                const dn = pts.filter((t) => t.status === "done").length;
                return (
                  <div
                    key={p.id || p.sk}
                    style={{
                      background: "#0e0e28",
                      border: "1px solid #1a1a3a",
                      borderRadius: 8,
                      padding: 12,
                      borderLeft: `3px solid ${area.color}`,
                      opacity: p.active !== false ? 1 : 0.4,
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: 13, color: "#e2e8f0" }}>{p.name}</div>
                    <div style={{ fontSize: 11, color: "#475569", marginBottom: 6 }}>{p.description}</div>
                    <div style={{ display: "flex", gap: 10, fontSize: 10, color: "#64748b" }}>
                      <span>{act} active</span>
                      <span>{dn} done</span>
                    </div>
                    {p.match_keywords?.length > 0 && (
                      <div style={{ fontSize: 9, color: "#3f3f5e", marginTop: 4 }}>
                        Keywords: {p.match_keywords.join(", ")}
                      </div>
                    )}
                    <button
                      onClick={() => handleToggleActive(p)}
                      style={{
                        background: "none", border: "none", color: "#475569",
                        fontSize: 10, cursor: "pointer", marginTop: 6, fontFamily: "inherit", padding: 0,
                      }}
                    >
                      {p.active !== false ? "Archive" : "Reactivate"}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {/* Add Project Modal */}
      {modal && (
        <div style={css.modal} onClick={() => setModal(false)}>
          <div style={{ ...css.modalBox, width: 380 }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>Add Project</h3>
              <button onClick={() => setModal(false)} style={{ background: "none", border: "none", color: "#475569", fontSize: 18, cursor: "pointer" }}>x</button>
            </div>
            <div style={css.field}>
              <label style={css.label}>Name *</label>
              <input style={css.input} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g., BADM 211" autoFocus />
            </div>
            <div style={css.field}>
              <label style={css.label}>Area *</label>
              <select style={css.select} value={form.area} onChange={(e) => setForm({ ...form, area: e.target.value })}>
                {Object.entries(AREAS).map(([k, a]) => (
                  <option key={k} value={k}>{a.icon} {a.label}</option>
                ))}
              </select>
            </div>
            <div style={css.field}>
              <label style={css.label}>Description</label>
              <input style={css.input} value={form.desc} onChange={(e) => setForm({ ...form, desc: e.target.value })} placeholder="Brief..." />
            </div>
            <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
              <Btn v="ghost" onClick={() => setModal(false)}>Cancel</Btn>
              <Btn v="pri" disabled={!form.name} onClick={handleAdd}>Add</Btn>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
