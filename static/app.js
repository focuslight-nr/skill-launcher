(() => {
  const state = {
    skills: [],
    sources: [],
    selected: new Set(),
    editingId: null,
  };

  const el = (id) => document.getElementById(id);

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    if (!res.ok) {
      let msg = res.statusText;
      try {
        const body = await res.json();
        msg = body.error || JSON.stringify(body);
      } catch (_) {
        try { msg = await res.text(); } catch (__) {}
      }
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) return res.json();
    return res;
  }

  async function loadSources() {
    state.sources = await api("/api/sources");
    renderSources();
    const sel = el("sourceFilter");
    const current = sel.value;
    sel.innerHTML = '<option value="">すべてのソース</option>' +
      state.sources.map(s => `<option value="${s.id}">${escapeHtml(s.label)} (${s.skill_count})</option>`).join("");
    sel.value = current;
  }

  function renderSources() {
    const box = el("sourceList");
    if (state.sources.length === 0) {
      box.innerHTML = '<div class="text-muted small">まだソースが登録されていません。</div>';
      return;
    }
    box.innerHTML = state.sources.map(s => `
      <div class="source-row border rounded p-2 mb-2">
        <span class="badge ${s.exists ? "bg-secondary" : "bg-danger"}">${s.skill_count}</span>
        <div class="flex-grow-1">
          <div><strong>${escapeHtml(s.label)}</strong> ${s.exists ? "" : '<span class="text-danger small">(パスが見つかりません)</span>'}</div>
          <div class="text-muted small">${escapeHtml(s.path)}</div>
        </div>
        <button class="btn btn-sm btn-outline-danger" data-remove-source="${s.id}">削除</button>
      </div>
    `).join("");
    box.querySelectorAll("[data-remove-source]").forEach(btn => {
      btn.addEventListener("click", async () => {
        if (!confirm(`ソース「${btn.closest(".source-row").querySelector("strong").textContent}」の登録を解除しますか？\n(スキャン対象から外れるだけで、既に有効化中のスキルはそのまま残ります)`)) return;
        await api(`/api/sources/${btn.dataset.removeSource}`, { method: "DELETE" });
        await refreshAll();
      });
    });
  }

  async function loadSkills() {
    state.skills = await api("/api/skills");
    const catSel = el("categoryFilter");
    const currentCat = catSel.value;
    const cats = [...new Set(state.skills.map(s => s.category))].sort();
    catSel.innerHTML = '<option value="">すべてのカテゴリ</option>' +
      cats.map(c => `<option value="${c}">${escapeHtml(c)}</option>`).join("");
    catSel.value = currentCat;
    renderSkills();
  }

  function escapeHtml(str) {
    return String(str ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function matchesFilters(s) {
    const q = el("searchBox").value.trim().toLowerCase();
    const cat = el("categoryFilter").value;
    const src = el("sourceFilter").value;
    const enabledOnly = el("enabledOnlyFilter").checked;
    if (cat && s.category !== cat) return false;
    if (src && s.source_id !== src) return false;
    if (enabledOnly && !s.enabled) return false;
    if (q && !(s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q))) return false;
    return true;
  }

  function renderSkills() {
    const filtered = state.skills.filter(matchesFilters);
    const container = el("skillContainer");
    el("emptyState").classList.toggle("d-none", state.skills.length !== 0);

    if (filtered.length === 0) {
      container.innerHTML = state.skills.length === 0 ? "" : '<div class="text-muted py-4">条件に一致するスキルがありません。</div>';
      updateExportBar();
      return;
    }

    const byCategory = {};
    for (const s of filtered) {
      (byCategory[s.category] ??= []).push(s);
    }

    container.innerHTML = Object.keys(byCategory).sort().map(cat => {
      const icon = byCategory[cat][0].icon;
      const cards = byCategory[cat].map(renderCard).join("");
      return `
        <div class="category-heading"><h5>${icon} ${escapeHtml(cat)} <span class="text-muted small">(${byCategory[cat].length})</span></h5></div>
        <div class="row row-cols-1 row-cols-md-2 row-cols-xl-3 g-3 mb-4">${cards}</div>
      `;
    }).join("");

    container.querySelectorAll("[data-toggle-id]").forEach(input => {
      input.addEventListener("change", onToggleEnable);
    });
    container.querySelectorAll("[data-edit-id]").forEach(btn => {
      btn.addEventListener("click", () => openEditModal(btn.dataset.editId));
    });
    container.querySelectorAll("[data-select-id]").forEach(chk => {
      chk.addEventListener("change", () => {
        if (chk.checked) state.selected.add(chk.dataset.selectId);
        else state.selected.delete(chk.dataset.selectId);
        updateExportBar();
      });
    });
  }

  function renderCard(s) {
    const checked = state.selected.has(s.id) ? "checked" : "";
    const enabledBadge = s.enabled
      ? `<span class="badge bg-success">有効 (${escapeHtml(s.target_name)}${s.kind === "copy" ? " / コピー" : ""})</span>`
      : '<span class="badge bg-secondary">無効</span>';
    return `
      <div class="col">
        <div class="card skill-card h-100">
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-start">
              <div class="d-flex align-items-center gap-2">
                <span class="skill-icon">${s.icon}</span>
                <div>
                  <div class="fw-semibold">${escapeHtml(s.name)}</div>
                  <span class="badge bg-light text-dark border badge-source">${escapeHtml(s.source_label)}</span>
                </div>
              </div>
              <input class="form-check-input mt-1" type="checkbox" data-select-id="${s.id}" ${checked} title="エクスポート対象に選択">
            </div>
            <p class="small text-muted mt-2 mb-2" style="max-height:4.5rem;overflow:auto">${escapeHtml(s.description)}</p>
            <div class="d-flex justify-content-between align-items-center">
              <div class="form-check form-switch mb-0">
                <input class="form-check-input" type="checkbox" role="switch" data-toggle-id="${s.id}" ${s.enabled ? "checked" : ""}>
                <label class="form-check-label small">${enabledBadge}</label>
              </div>
              <button class="btn btn-sm btn-outline-primary" data-edit-id="${s.id}">編集</button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  async function onToggleEnable(ev) {
    const input = ev.target;
    const id = input.dataset.toggleId;
    const skill = state.skills.find(s => s.id === id);
    if (input.checked) {
      try {
        await api(`/api/skills/${id}/enable`, { method: "POST", body: JSON.stringify({}) });
      } catch (e) {
        if (e.status === 409) {
          const alt = prompt(`名前が衝突しました:\n${e.message}\n\n別の名前で有効化しますか？（空でキャンセル）`, skill.name + "-2");
          if (alt) {
            try {
              await api(`/api/skills/${id}/enable`, { method: "POST", body: JSON.stringify({ target_name: alt }) });
            } catch (e2) {
              alert("有効化に失敗しました: " + e2.message);
            }
          }
        } else {
          alert("有効化に失敗しました: " + e.message);
        }
      }
    } else {
      if (!confirm(`「${skill.name}」を無効化しますか？\n~/.claude/skills から削除されます（元のソースファイルは削除されません）。`)) {
        input.checked = true;
        return;
      }
      try {
        await api(`/api/skills/${id}/disable`, { method: "POST", body: JSON.stringify({ confirm: true }) });
      } catch (e) {
        alert("無効化に失敗しました: " + e.message);
      }
    }
    await loadSkills();
  }

  function updateExportBar() {
    const bar = el("exportBar");
    el("selectedCount").textContent = state.selected.size;
    bar.classList.toggle("d-none", state.selected.size === 0);
  }

  async function openEditModal(id) {
    const data = await api(`/api/skills/${id}`);
    state.editingId = id;
    el("editPath").textContent = data.path;
    el("editName").value = data.name;
    el("editDescription").value = data.description;
    el("editBody").value = data.body;
    el("editSavedMsg").style.display = "none";
    new bootstrap.Modal(el("editModal")).show();
  }

  async function saveEdit() {
    const id = state.editingId;
    const name = el("editName").value.trim();
    const description = el("editDescription").value.trim();
    const body = el("editBody").value;
    if (!name) { alert("name は必須です"); return; }
    try {
      const res = await api(`/api/skills/${id}`, {
        method: "PUT",
        body: JSON.stringify({ name, description, body }),
      });
      const msg = el("editSavedMsg");
      msg.textContent = `保存しました。バックアップ: ${res.backup}`;
      msg.style.display = "block";
      await loadSkills();
    } catch (e) {
      alert("保存に失敗しました: " + e.message);
    }
  }

  async function doExport() {
    const ids = [...state.selected];
    const res = await fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    if (!res.ok) {
      alert("エクスポートに失敗しました");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "skills-export.md";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function refreshAll() {
    await loadSources();
    await loadSkills();
  }

  function wireStaticEvents() {
    el("addSourceForm").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const path = el("sourcePath").value.trim();
      const label = el("sourceLabel").value.trim();
      if (!path) return;
      try {
        await api("/api/sources", { method: "POST", body: JSON.stringify({ path, label }) });
        el("sourcePath").value = "";
        el("sourceLabel").value = "";
        await refreshAll();
      } catch (e) {
        alert("ソースの追加に失敗しました: " + e.message);
      }
    });

    el("rescanBtn").addEventListener("click", refreshAll);
    el("searchBox").addEventListener("input", renderSkills);
    el("categoryFilter").addEventListener("change", renderSkills);
    el("sourceFilter").addEventListener("change", renderSkills);
    el("enabledOnlyFilter").addEventListener("change", renderSkills);
    el("saveEditBtn").addEventListener("click", saveEdit);
    el("exportBtn").addEventListener("click", doExport);
    el("clearSelectionBtn").addEventListener("click", () => {
      state.selected.clear();
      renderSkills();
    });
  }

  wireStaticEvents();
  refreshAll();
})();
