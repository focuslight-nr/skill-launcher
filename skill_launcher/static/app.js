(() => {
  const state = {
    skills: [],
    sources: [],
    targets: [],
    profiles: [],
    selected: new Set(),
    editingId: null,
    editingMtime: null,
    fullTextIds: null,   // ids matched by the last server-side body search
    doctorFindings: [],
  };

  const el = (id) => document.getElementById(id);
  const LS_TARGET = "skill-launcher.target";

  function currentTarget() {
    return el("targetSelect").value || "default";
  }

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

  function escapeHtml(str) {
    return String(str ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  const fmtNum = (n) => Number(n).toLocaleString("ja-JP");

  // --- targets --------------------------------------------------------------

  async function loadTargets() {
    state.targets = await api("/api/targets");
    const sel = el("targetSelect");
    const saved = localStorage.getItem(LS_TARGET);
    const keep = sel.value || saved || "default";
    sel.innerHTML = state.targets
      .map(t => `<option value="${t.id}">${escapeHtml(t.label)}${t.exists ? "" : " (未作成)"}</option>`)
      .join("");
    sel.value = state.targets.some(t => t.id === keep) ? keep : "default";
    renderTargetList();
  }

  function renderTargetList() {
    const box = el("targetList");
    box.innerHTML = state.targets.map(t => `
      <div class="source-row border rounded p-2 mb-2">
        <div class="flex-grow-1">
          <div><strong>${escapeHtml(t.label)}</strong> ${t.builtin ? '<span class="badge bg-secondary">既定</span>' : ""}</div>
          <div class="text-muted small">${escapeHtml(t.path)}</div>
        </div>
        ${t.builtin ? "" : `<button class="btn btn-sm btn-outline-danger" data-remove-target="${t.id}">削除</button>`}
      </div>
    `).join("");
    box.querySelectorAll("[data-remove-target]").forEach(btn => {
      btn.addEventListener("click", async () => {
        if (!confirm("この有効化先の登録を解除しますか？\n（登録が外れるだけで、既に作成済みのリンクは残ります）")) return;
        await api(`/api/targets/${btn.dataset.removeTarget}`, { method: "DELETE" });
        await loadTargets();
        await refreshAll();
      });
    });
  }

  // --- sources --------------------------------------------------------------

  async function loadSources(force = false) {
    state.sources = await api(`/api/sources${force ? "?force=1" : ""}`);
    renderSources();
    const sel = el("sourceFilter");
    const current = sel.value;
    sel.innerHTML = '<option value="">すべてのソース</option>' +
      state.sources.map(s => `<option value="${s.id}">${escapeHtml(s.label)} (${s.skill_count})</option>`).join("");
    sel.value = current;
    el("newSkillSource").innerHTML =
      state.sources.map(s => `<option value="${s.id}">${escapeHtml(s.label)}</option>`).join("");
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

  // --- skills ---------------------------------------------------------------

  async function loadSkills(force = false) {
    const params = new URLSearchParams({ target: currentTarget() });
    if (force) params.set("force", "1");
    state.skills = await api(`/api/skills?${params}`);
    const catSel = el("categoryFilter");
    const currentCat = catSel.value;
    const cats = [...new Set(state.skills.map(s => s.category))].sort();
    catSel.innerHTML = '<option value="">すべてのカテゴリ</option>' +
      cats.map(c => `<option value="${c}">${escapeHtml(c)}</option>`).join("");
    catSel.value = currentCat;
    renderSkills();
  }

  async function loadStats() {
    const stats = await api(`/api/stats?target=${encodeURIComponent(currentTarget())}`);
    const t = state.targets.find(x => x.id === currentTarget());
    el("statsLine").textContent =
      `${t ? t.path : ""} — スキル ${fmtNum(stats.total_skills)}件 / 有効化 ${fmtNum(stats.enabled_skills)}件`;
    el("tokenPill").textContent =
      `常時コンテキスト 約${fmtNum(stats.estimated_tokens)}トークン（説明 ${fmtNum(stats.description_chars)}文字）`;
    const errors = stats.issue_counts.error + stats.issue_counts.warn;
    el("doctorBtn").classList.toggle("d-none", errors === 0 && state.doctorFindings.length === 0);
    el("doctorBtn").textContent = `要確認 ${errors}件`;
  }

  function worstIssue(s) {
    if (!s.issues || s.issues.length === 0) return null;
    for (const level of ["error", "warn", "info"]) {
      const hit = s.issues.find(i => i.level === level);
      if (hit) return hit;
    }
    return null;
  }

  function matchesFilters(s) {
    const q = el("searchBox").value.trim().toLowerCase();
    const cat = el("categoryFilter").value;
    const src = el("sourceFilter").value;
    if (cat && s.category !== cat) return false;
    if (src && s.source_id !== src) return false;
    if (el("enabledOnlyFilter").checked && !s.enabled) return false;
    if (el("issuesOnlyFilter").checked && !(s.issues || []).some(i => i.level !== "info")) return false;
    if (!q) return true;
    if (state.fullTextIds) return state.fullTextIds.has(s.id);
    const hay = `${s.name} ${s.description} ${(s.tags || []).join(" ")}`.toLowerCase();
    return hay.includes(q);
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
    for (const s of filtered) (byCategory[s.category] ??= []).push(s);

    container.innerHTML = Object.keys(byCategory).sort().map(cat => {
      const group = byCategory[cat];
      const icon = group[0].icon;
      const tokens = group.filter(s => s.enabled).reduce((n, s) => n + s.tokens, 0);
      return `
        <div class="category-heading"><h5>${icon} ${escapeHtml(cat)}
          <span class="text-muted small">(${group.length}${tokens ? ` / 有効分 約${fmtNum(tokens)}tok` : ""})</span></h5></div>
        <div class="row row-cols-1 row-cols-md-2 row-cols-xl-3 g-3 mb-4">${group.map(renderCard).join("")}</div>
      `;
    }).join("");

    container.querySelectorAll("[data-toggle-id]").forEach(i => i.addEventListener("change", onToggleEnable));
    container.querySelectorAll("[data-edit-id]").forEach(b => b.addEventListener("click", () => openEditModal(b.dataset.editId)));
    container.querySelectorAll("[data-select-id]").forEach(chk => {
      chk.addEventListener("change", () => {
        if (chk.checked) state.selected.add(chk.dataset.selectId);
        else state.selected.delete(chk.dataset.selectId);
        updateExportBar();
      });
    });
    updateExportBar();
  }

  function renderCard(s) {
    const checked = state.selected.has(s.id) ? "checked" : "";
    const enabledBadge = s.enabled
      ? `<span class="badge bg-success">有効 (${escapeHtml(s.target_name)}${s.kind === "copy" ? " / コピー" : ""})</span>`
      : '<span class="badge bg-secondary">無効</span>';
    const issue = worstIssue(s);
    const issueDot = issue
      ? `<span class="issue-dot badge ${issue.level === "error" ? "bg-danger" : issue.level === "warn" ? "bg-warning text-dark" : "bg-light text-muted border"}"
              title="${escapeHtml(s.issues.map(i => i.message).join("\n"))}">${issue.level === "info" ? "i" : "!"} ${s.issues.length}</span>`
      : "";
    const tags = (s.tags || []).slice(0, 4)
      .map(t => `<span class="badge bg-light text-dark border badge-source">#${escapeHtml(t)}</span>`).join(" ");
    return `
      <div class="col">
        <div class="card skill-card h-100">
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-start">
              <div class="d-flex align-items-center gap-2">
                <span class="skill-icon">${s.icon}</span>
                <div>
                  <div class="fw-semibold">${escapeHtml(s.name)} ${issueDot}</div>
                  <span class="badge bg-light text-dark border badge-source">${escapeHtml(s.source_label)}</span>
                  <span class="badge bg-light text-dark border badge-source" title="有効化した場合の常時コスト（概算）">約${fmtNum(s.tokens)}tok</span>
                  ${tags}
                </div>
              </div>
              <input class="form-check-input mt-1" type="checkbox" data-select-id="${s.id}" ${checked} title="エクスポート/プロファイル対象に選択">
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
    const target = currentTarget();
    if (input.checked) {
      try {
        await api(`/api/skills/${id}/enable`, { method: "POST", body: JSON.stringify({ target }) });
      } catch (e) {
        if (e.status === 409) {
          const alt = prompt(`名前が衝突しました:\n${e.message}\n\n別の名前で有効化しますか？（空でキャンセル）`, skill.name + "-2");
          if (alt) {
            try {
              await api(`/api/skills/${id}/enable`, { method: "POST", body: JSON.stringify({ target, target_name: alt }) });
            } catch (e2) {
              alert("有効化に失敗しました: " + e2.message);
            }
          }
        } else {
          alert("有効化に失敗しました: " + e.message);
        }
      }
    } else {
      const t = state.targets.find(x => x.id === target);
      if (!confirm(`「${skill.name}」を無効化しますか？\n${t ? t.path : ""} から削除されます（元のソースファイルは削除されません）。`)) {
        input.checked = true;
        return;
      }
      try {
        await api(`/api/skills/${id}/disable`, { method: "POST", body: JSON.stringify({ target, confirm: true }) });
      } catch (e) {
        alert("無効化に失敗しました: " + e.message);
      }
    }
    await loadSkills();
    await loadStats();
  }

  function updateExportBar() {
    const bar = el("exportBar");
    el("selectedCount").textContent = state.selected.size;
    const tokens = state.skills.filter(s => state.selected.has(s.id)).reduce((n, s) => n + s.tokens, 0);
    el("selectedTokens").textContent = tokens ? `（有効化すると常時 約${fmtNum(tokens)}トークン）` : "";
    bar.classList.toggle("d-none", state.selected.size === 0);
  }

  // --- profiles -------------------------------------------------------------

  async function loadProfiles() {
    state.profiles = await api("/api/profiles");
    const sel = el("profileSelect");
    const current = sel.value;
    sel.innerHTML = '<option value="">（選択）</option>' + state.profiles.map(p =>
      `<option value="${escapeHtml(p.name)}">${escapeHtml(p.name)} — ${p.count}件 / 約${fmtNum(p.estimated_tokens)}tok${p.missing ? ` / 不明${p.missing}` : ""}</option>`
    ).join("");
    sel.value = current;
  }

  async function applyProfile() {
    const name = el("profileSelect").value;
    if (!name) { alert("プロファイルを選択してください。"); return; }
    const t = state.targets.find(x => x.id === currentTarget());
    if (!confirm(`プロファイル「${name}」を ${t ? t.path : ""} に適用します。\nこのプロファイルに含まれないスキルは無効化されます（手動配置のスキルは対象外）。`)) return;
    const res = await api(`/api/profiles/${encodeURIComponent(name)}/apply`, {
      method: "POST", body: JSON.stringify({ target: currentTarget() }),
    });
    await refreshAll();
    const msg = [`有効化: ${res.enabled.length}件`, `無効化: ${res.disabled.length}件`];
    if (res.errors.length) msg.push("エラー:\n" + res.errors.join("\n"));
    alert(msg.join(" / "));
  }

  async function saveProfile(ids) {
    const name = prompt("プロファイル名", el("profileSelect").value || "");
    if (!name) return;
    await api("/api/profiles", {
      method: "POST",
      body: JSON.stringify({ name, target: currentTarget(), ids: ids || null }),
    });
    await loadProfiles();
    el("profileSelect").value = name;
  }

  async function deleteProfile() {
    const name = el("profileSelect").value;
    if (!name) return;
    if (!confirm(`プロファイル「${name}」を削除しますか？（有効化状態は変わりません）`)) return;
    await api(`/api/profiles/${encodeURIComponent(name)}`, { method: "DELETE" });
    await loadProfiles();
  }

  // --- doctor ---------------------------------------------------------------

  async function loadDoctor() {
    state.doctorFindings = await api("/api/doctor");
    const actionable = state.doctorFindings.filter(f => f.level !== "info").length;
    const btn = el("doctorBtn");
    if (actionable > 0) {
      btn.classList.remove("d-none");
      btn.textContent = `診断: 要対応 ${actionable}件`;
    }
  }

  function renderDoctor() {
    const box = el("doctorList");
    if (state.doctorFindings.length === 0) {
      box.innerHTML = '<div class="text-success">問題は見つかりませんでした。</div>';
      return;
    }
    box.innerHTML = state.doctorFindings.map((f, idx) => {
      const cls = f.level === "error" ? "danger" : f.level === "warn" ? "warning" : "secondary";
      const actions = f.code === "link_missing" || f.code === "copy_stale"
        ? `<button class="btn btn-sm btn-outline-primary" data-repair="${idx}" data-action="relink">再リンク</button>`
        : "";
      const forget = f.code === "source_missing" || f.code === "link_missing"
        ? `<button class="btn btn-sm btn-outline-secondary" data-repair="${idx}" data-action="forget">管理から外す</button>`
        : "";
      return `
        <div class="border rounded p-2 mb-2">
          <div class="d-flex justify-content-between align-items-start gap-2">
            <div>
              <span class="badge bg-${cls}">${f.code}</span>
              <strong class="ms-1">${escapeHtml(f.target_name)}</strong>
              <div class="small">${escapeHtml(f.message)}</div>
              <div class="text-muted small">${escapeHtml(f.target_dir)}${f.source ? " ← " + escapeHtml(f.source) : ""}</div>
            </div>
            <div class="d-flex gap-1">${actions}${forget}</div>
          </div>
        </div>`;
    }).join("");

    box.querySelectorAll("[data-repair]").forEach(btn => {
      btn.addEventListener("click", async () => {
        const f = state.doctorFindings[Number(btn.dataset.repair)];
        try {
          await api("/api/doctor/repair", {
            method: "POST",
            body: JSON.stringify({ target_dir: f.target_dir, target_name: f.target_name, action: btn.dataset.action }),
          });
        } catch (e) {
          alert("修復に失敗しました: " + e.message);
        }
        await loadDoctor();
        renderDoctor();
        await refreshAll();
      });
    });
  }

  // --- edit / create --------------------------------------------------------

  function renderIssues(issues) {
    const box = el("editIssues");
    if (!issues || issues.length === 0) { box.innerHTML = ""; return; }
    box.innerHTML = issues.map(i => {
      const cls = i.level === "error" ? "danger" : i.level === "warn" ? "warning" : "secondary";
      return `<div class="alert alert-${cls} py-1 px-2 small mb-1">${escapeHtml(i.message)}</div>`;
    }).join("");
  }

  function updateDescCounter() {
    const len = el("editDescription").value.length;
    const counter = el("descCounter");
    counter.textContent = `${len} / 1024 文字`;
    counter.className = len > 1024 ? "text-danger small" : "text-muted small";
  }

  async function openEditModal(id) {
    const data = await api(`/api/skills/${id}`);
    state.editingId = id;
    state.editingMtime = data.mtime;
    el("editPath").textContent = data.path;
    el("editName").value = data.name;
    el("editDescription").value = data.description;
    el("editBody").value = data.body;
    el("editSavedMsg").style.display = "none";
    renderIssues(data.issues);
    updateDescCounter();
    renderFileList(id, data.files || []);
    new bootstrap.Modal(el("editModal")).show();
  }

  function renderFileList(id, files) {
    el("fileCount").textContent = files.length;
    el("filePreview").textContent = "左のファイルを選択すると内容を表示します。";
    el("fileList").innerHTML = files.map(f => `
      <button type="button" class="list-group-item list-group-item-action small" data-file="${escapeHtml(f.rel)}">
        ${escapeHtml(f.rel)} <span class="text-muted">(${fmtNum(f.size)}B)</span>
      </button>`).join("");
    el("fileList").querySelectorAll("[data-file]").forEach(btn => {
      btn.addEventListener("click", async () => {
        const res = await api(`/api/skills/${id}/file?rel=${encodeURIComponent(btn.dataset.file)}`);
        el("filePreview").textContent = res.text !== null && res.text !== undefined
          ? res.text
          : `（${res.reason === "binary" ? "バイナリ" : "サイズ超過"}のため表示できません）`;
      });
    });
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
        body: JSON.stringify({ name, description, body, mtime: state.editingMtime }),
      });
      const msg = el("editSavedMsg");
      msg.textContent = `保存しました。バックアップ: ${res.backup}`;
      msg.style.display = "block";
      const fresh = await api(`/api/skills/${id}`);
      state.editingMtime = fresh.mtime;
      renderIssues(fresh.issues);
      await refreshAll();
    } catch (e) {
      if (e.status === 409) {
        alert(e.message);
      } else {
        alert("保存に失敗しました: " + e.message);
      }
    }
  }

  async function duplicateSkill() {
    const id = state.editingId;
    const current = el("editName").value.trim();
    const name = prompt("複製後の名前（フォルダ名になります）", `${current}-copy`);
    if (!name) return;
    try {
      await api(`/api/skills/${id}/duplicate`, { method: "POST", body: JSON.stringify({ name }) });
      await refreshAll();
      alert(`複製しました: ${name}`);
    } catch (e) {
      alert("複製に失敗しました: " + e.message);
    }
  }

  async function createSkill() {
    const payload = {
      source_id: el("newSkillSource").value,
      category: el("newSkillCategory").value.trim(),
      name: el("newSkillName").value.trim(),
      description: el("newSkillDescription").value.trim(),
    };
    if (!payload.source_id || !payload.name) { alert("ソースと name は必須です"); return; }
    try {
      const res = await api("/api/skills", { method: "POST", body: JSON.stringify(payload) });
      bootstrap.Modal.getInstance(el("newSkillModal")).hide();
      el("newSkillName").value = "";
      el("newSkillDescription").value = "";
      await refreshAll();
      openEditModal(res.id);
    } catch (e) {
      alert("作成に失敗しました: " + e.message);
    }
  }

  // --- icons ----------------------------------------------------------------

  async function openIcons() {
    const { overrides, builtin } = await api("/api/icons");
    const cats = [...new Set([...state.skills.map(s => s.category), ...Object.keys(overrides)])].sort();
    el("iconRows").innerHTML = cats.map(c => `
      <div class="input-group input-group-sm mb-2">
        <span class="input-group-text" style="min-width:12rem">${escapeHtml(c)}</span>
        <input class="form-control" data-icon-cat="${escapeHtml(c)}" value="${escapeHtml(overrides[c] || "")}"
               placeholder="${escapeHtml(builtin[c] || "📄")}">
      </div>`).join("");
    new bootstrap.Modal(el("iconsModal")).show();
  }

  async function saveIcons() {
    const overrides = {};
    el("iconRows").querySelectorAll("[data-icon-cat]").forEach(inp => {
      if (inp.value.trim()) overrides[inp.dataset.iconCat] = inp.value.trim();
    });
    await api("/api/icons", { method: "PUT", body: JSON.stringify({ overrides }) });
    bootstrap.Modal.getInstance(el("iconsModal")).hide();
    await loadSkills(true);
  }

  // --- search ---------------------------------------------------------------

  let searchTimer = null;
  async function onSearchInput() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(async () => {
      const q = el("searchBox").value.trim();
      if (el("fullTextFilter").checked && q) {
        try {
          const res = await api(`/api/search?q=${encodeURIComponent(q)}`);
          state.fullTextIds = new Set(res.ids);
        } catch (_) {
          state.fullTextIds = null;
        }
      } else {
        state.fullTextIds = null;
      }
      renderSkills();
    }, 180);
  }

  // --- wiring ---------------------------------------------------------------

  async function refreshAll(force = false) {
    await loadSources(force);
    await loadSkills(force);
    await loadProfiles();
    await loadStats();
    await loadDoctor();
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
        await refreshAll(true);
      } catch (e) {
        alert("ソースの追加に失敗しました: " + e.message);
      }
    });

    el("addTargetForm").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const path = el("targetPath").value.trim();
      const label = el("targetLabel").value.trim();
      if (!path) return;
      try {
        await api("/api/targets", { method: "POST", body: JSON.stringify({ path, label }) });
        el("targetPath").value = "";
        el("targetLabel").value = "";
        await loadTargets();
      } catch (e) {
        alert("有効化先の追加に失敗しました: " + e.message);
      }
    });

    el("targetSelect").addEventListener("change", async () => {
      localStorage.setItem(LS_TARGET, currentTarget());
      await loadSkills();
      await loadStats();
    });
    el("manageTargetsBtn").addEventListener("click", () => new bootstrap.Modal(el("targetsModal")).show());

    el("applyProfileBtn").addEventListener("click", applyProfile);
    el("saveProfileBtn").addEventListener("click", () => saveProfile(null));
    el("deleteProfileBtn").addEventListener("click", deleteProfile);
    el("profileFromSelectionBtn").addEventListener("click", () => saveProfile([...state.selected]));

    el("rescanBtn").addEventListener("click", () => refreshAll(true));
    el("searchBox").addEventListener("input", onSearchInput);
    el("fullTextFilter").addEventListener("change", onSearchInput);
    el("categoryFilter").addEventListener("change", renderSkills);
    el("sourceFilter").addEventListener("change", renderSkills);
    el("enabledOnlyFilter").addEventListener("change", renderSkills);
    el("issuesOnlyFilter").addEventListener("change", renderSkills);

    el("saveEditBtn").addEventListener("click", saveEdit);
    el("duplicateBtn").addEventListener("click", duplicateSkill);
    el("editDescription").addEventListener("input", updateDescCounter);

    el("newSkillBtn").addEventListener("click", () => new bootstrap.Modal(el("newSkillModal")).show());
    el("createSkillBtn").addEventListener("click", createSkill);

    el("iconsBtn").addEventListener("click", openIcons);
    el("saveIconsBtn").addEventListener("click", saveIcons);

    const openDoctor = async () => { await loadDoctor(); renderDoctor(); new bootstrap.Modal(el("doctorModal")).show(); };
    el("doctorBtn").addEventListener("click", openDoctor);
    el("doctorOpenBtn").addEventListener("click", openDoctor);

    el("exportBtn").addEventListener("click", doExport);
    el("clearSelectionBtn").addEventListener("click", () => {
      state.selected.clear();
      renderSkills();
    });
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

  (async () => {
    wireStaticEvents();
    await loadTargets();
    await refreshAll();
  })();
})();
