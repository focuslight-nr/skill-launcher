"""HTTP API.

Every handler works against a single activation target (the `target` query
parameter or body field, defaulting to the global ~/.claude/skills), so the
UI can switch between "enable globally" and "enable for this project" without
the backend keeping any session state.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from aiohttp import web

from . import config, manager, metrics, scanner

routes = web.RouteTableDef()


def _skill_to_json(s: scanner.Skill, managed: dict) -> dict:
    target_name = manager.find_enabled_target_for(s.dir, managed)
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "category": s.category,
        "tags": s.tags,
        "icon": scanner.icon_for(s.category, s.frontmatter),
        "source_id": s.source_id,
        "source_label": s.source_label,
        "path": str(s.path),
        "enabled": target_name is not None,
        "target_name": target_name,
        "kind": managed.get(target_name, {}).get("kind") if target_name else None,
        "tokens": s.context_tokens,
        "issues": [i.to_json() for i in s.issues],
    }


def _all_skills(force: bool = False) -> list[scanner.Skill]:
    return scanner.scan_all(config.load_sources(), force=force)


def _find_skill(skill_id: str) -> scanner.Skill:
    for s in _all_skills():
        if s.id == skill_id:
            return s
    raise web.HTTPNotFound(text="skill not found (source may have changed - try rescanning)")


async def _body(request: web.Request) -> dict:
    if not request.can_read_body:
        return {}
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _target_dir(request: web.Request, data: dict | None = None) -> Path:
    target_id = (data or {}).get("target") or request.query.get("target")
    try:
        return manager.resolve_target(target_id)
    except manager.ManagerError as e:
        raise web.HTTPBadRequest(text=str(e)) from e


@routes.get("/api/health")
async def health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


# --- sources ----------------------------------------------------------------


@routes.get("/api/sources")
async def list_sources(request: web.Request) -> web.Response:
    force = request.query.get("force") == "1"
    sources = config.load_sources()
    skills = _all_skills(force=force)
    counts: dict[str, int] = {}
    for s in skills:
        counts[s.source_id] = counts.get(s.source_id, 0) + 1
    out = []
    for s in sources:
        p = Path(s["path"]).expanduser()
        out.append({**s, "exists": p.is_dir(), "skill_count": counts.get(s["id"], 0)})
    return web.json_response(out)


@routes.post("/api/sources")
async def add_source(request: web.Request) -> web.Response:
    data = await _body(request)
    raw_path = str(data.get("path", "")).strip()
    label = str(data.get("label", "")).strip()
    if not raw_path:
        raise web.HTTPBadRequest(text="path is required")
    path = Path(raw_path).expanduser()
    if not path.is_dir():
        raise web.HTTPBadRequest(text=f"not a directory: {path}")

    sources = config.load_sources()
    resolved = str(path.resolve())
    for s in sources:
        if str(Path(s["path"]).expanduser().resolve()) == resolved:
            raise web.HTTPConflict(text="this path is already registered as a source")

    entry = {"id": uuid.uuid4().hex[:12], "path": str(path), "label": label or path.name}
    sources.append(entry)
    config.save_sources(sources)
    scanner.invalidate_cache()
    return web.json_response(entry, status=201)


@routes.delete("/api/sources/{source_id}")
async def remove_source(request: web.Request) -> web.Response:
    source_id = request.match_info["source_id"]
    sources = config.load_sources()
    remaining = [s for s in sources if s["id"] != source_id]
    if len(remaining) == len(sources):
        raise web.HTTPNotFound(text="source not found")
    config.save_sources(remaining)
    scanner.invalidate_cache()
    return web.json_response({"removed": source_id})


# --- activation targets -----------------------------------------------------


@routes.get("/api/targets")
async def list_targets(request: web.Request) -> web.Response:
    return web.json_response(manager.list_targets())


@routes.post("/api/targets")
async def add_target(request: web.Request) -> web.Response:
    data = await _body(request)
    raw_path = str(data.get("path", "")).strip()
    label = str(data.get("label", "")).strip()
    if not raw_path:
        raise web.HTTPBadRequest(text="path is required")

    path = Path(raw_path).expanduser()
    # A project target is <project>/.claude/skills; accept the project root too.
    if path.is_dir() and path.name != "skills":
        candidate = path / ".claude" / "skills"
        if candidate.is_dir() or (path / ".claude").is_dir():
            path = candidate
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise web.HTTPBadRequest(text=f"not a directory: {path}")

    targets = config.load_targets()
    resolved = str(path.resolve())
    if resolved == str(config.CLAUDE_SKILLS_DIR.resolve()):
        raise web.HTTPConflict(text="これは既定のグローバルターゲットです")
    for t in targets:
        if str(Path(t["path"]).expanduser().resolve()) == resolved:
            raise web.HTTPConflict(text="already registered")

    entry = {
        "id": uuid.uuid4().hex[:12],
        "path": str(path),
        "label": label or f"{path.parent.parent.name} (project)",
    }
    targets.append(entry)
    config.save_targets(targets)
    return web.json_response(entry, status=201)


@routes.delete("/api/targets/{target_id}")
async def remove_target(request: web.Request) -> web.Response:
    target_id = request.match_info["target_id"]
    if target_id == manager.DEFAULT_TARGET_ID:
        raise web.HTTPBadRequest(text="既定のターゲットは削除できません")
    targets = config.load_targets()
    remaining = [t for t in targets if t["id"] != target_id]
    if len(remaining) == len(targets):
        raise web.HTTPNotFound(text="target not found")
    config.save_targets(remaining)
    return web.json_response({"removed": target_id})


# --- skills -----------------------------------------------------------------


@routes.get("/api/skills")
async def list_skills(request: web.Request) -> web.Response:
    force = request.query.get("force") == "1"
    target_dir = _target_dir(request)
    managed = manager.enabled_map(target_dir)
    skills = _all_skills(force=force)
    return web.json_response([_skill_to_json(s, managed) for s in skills])


@routes.get("/api/stats")
async def stats(request: web.Request) -> web.Response:
    """Always-on context cost of the currently enabled set."""
    target_dir = _target_dir(request)
    managed = manager.enabled_map(target_dir)
    skills = _all_skills()
    enabled = [s for s in skills if manager.find_enabled_target_for(s.dir, managed) is not None]
    chars = sum(len(s.name) + len(s.description) for s in enabled)
    return web.json_response({
        "target": str(target_dir),
        "total_skills": len(skills),
        "enabled_skills": len(enabled),
        "enabled_managed_entries": len(managed),
        "description_chars": chars,
        "estimated_tokens": sum(s.context_tokens for s in enabled),
        "issue_counts": {
            level: sum(1 for s in skills for i in s.issues if i.level == level)
            for level in ("error", "warn", "info")
        },
    })


@routes.get("/api/search")
async def search(request: web.Request) -> web.Response:
    """Full-text search across SKILL.md bodies (the card list only has metadata)."""
    q = request.query.get("q", "").strip().lower()
    if not q:
        return web.json_response({"ids": []})
    ids = []
    for s in _all_skills():
        haystack = f"{s.name}\n{s.description}\n{' '.join(s.tags)}\n{s.body}".lower()
        if q in haystack:
            ids.append(s.id)
    return web.json_response({"ids": ids})


@routes.post("/api/skills")
async def create_skill(request: web.Request) -> web.Response:
    data = await _body(request)
    source_id = str(data.get("source_id", "")).strip()
    name = str(data.get("name", "")).strip()
    category = str(data.get("category", "")).strip()
    description = str(data.get("description", "")).strip()
    if not source_id or not name:
        raise web.HTTPBadRequest(text="source_id and name are required")

    source = next((s for s in config.load_sources() if s["id"] == source_id), None)
    if source is None:
        raise web.HTTPNotFound(text="source not found")
    try:
        path = manager.create_skill(Path(source["path"]), category, name, description)
    except manager.ManagerError as e:
        return web.json_response({"error": str(e), "code": e.code}, status=409)
    scanner.invalidate_cache()
    return web.json_response({"path": str(path), "id": scanner.make_id(path)}, status=201)


@routes.post("/api/skills/{skill_id}/duplicate")
async def duplicate_skill(request: web.Request) -> web.Response:
    skill = _find_skill(request.match_info["skill_id"])
    data = await _body(request)
    new_name = str(data.get("name", "")).strip() or f"{skill.name}-copy"
    try:
        path = manager.duplicate_skill(skill, new_name)
    except manager.ManagerError as e:
        return web.json_response({"error": str(e), "code": e.code}, status=409)
    scanner.invalidate_cache()
    return web.json_response({"path": str(path), "id": scanner.make_id(path)}, status=201)


@routes.get("/api/skills/{skill_id}")
async def get_skill(request: web.Request) -> web.Response:
    skill = _find_skill(request.match_info["skill_id"])
    data = manager.read_skill_source(skill)
    data["files"] = manager.list_skill_files(skill)
    return web.json_response(data)


@routes.get("/api/skills/{skill_id}/file")
async def get_skill_file(request: web.Request) -> web.Response:
    skill = _find_skill(request.match_info["skill_id"])
    rel = request.query.get("rel", "")
    if not rel:
        raise web.HTTPBadRequest(text="rel is required")
    try:
        return web.json_response(manager.read_skill_file(skill, rel))
    except manager.ManagerError as e:
        raise web.HTTPBadRequest(text=str(e)) from e


@routes.put("/api/skills/{skill_id}")
async def update_skill(request: web.Request) -> web.Response:
    skill = _find_skill(request.match_info["skill_id"])
    data = await _body(request)
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    body = data.get("body", "")
    mtime = data.get("mtime")
    if not name:
        raise web.HTTPBadRequest(text="name is required")
    try:
        backup_path = manager.write_skill_source(
            skill, name, description, body,
            expected_mtime=float(mtime) if mtime is not None else None,
        )
    except manager.ManagerError as e:
        status = 409 if e.code == "stale" else 400
        return web.json_response({"error": str(e), "code": e.code}, status=status)
    scanner.invalidate_cache()
    return web.json_response({"saved": True, "backup": str(backup_path)})


@routes.post("/api/skills/{skill_id}/enable")
async def enable_skill(request: web.Request) -> web.Response:
    skill = _find_skill(request.match_info["skill_id"])
    data = await _body(request)
    target_dir = _target_dir(request, data)
    try:
        result = manager.enable_skill(skill, target_dir, data.get("target_name") or None)
    except manager.ManagerError as e:
        return web.json_response({"error": str(e), "code": e.code}, status=409)
    return web.json_response(result)


@routes.post("/api/skills/{skill_id}/disable")
async def disable_skill(request: web.Request) -> web.Response:
    skill = _find_skill(request.match_info["skill_id"])
    data = await _body(request)
    if not data.get("confirm"):
        raise web.HTTPBadRequest(text="confirm:true is required to disable a skill")
    target_dir = _target_dir(request, data)

    managed = manager.enabled_map(target_dir)
    target_name = manager.find_enabled_target_for(skill.dir, managed)
    if target_name is None:
        raise web.HTTPBadRequest(text="skill is not currently enabled")
    try:
        manager.disable_skill(target_name, target_dir)
    except manager.ManagerError as e:
        return web.json_response({"error": str(e), "code": e.code}, status=409)
    return web.json_response({"disabled": target_name})


# --- profiles ---------------------------------------------------------------


@routes.get("/api/profiles")
async def list_profiles(request: web.Request) -> web.Response:
    profiles = manager.list_profiles()
    skills_by_real = {str(s.dir.resolve()): s for s in _all_skills()}
    out = []
    for name, p in sorted(profiles.items()):
        members = [skills_by_real.get(d) for d in p.get("skills", [])]
        found = [s for s in members if s is not None]
        out.append({
            "name": name,
            "target_id": p.get("target_id", manager.DEFAULT_TARGET_ID),
            "saved_at": p.get("saved_at"),
            "count": len(p.get("skills", [])),
            "missing": len(p.get("skills", [])) - len(found),
            "estimated_tokens": sum(s.context_tokens for s in found),
        })
    return web.json_response(out)


@routes.post("/api/profiles")
async def create_profile(request: web.Request) -> web.Response:
    data = await _body(request)
    name = str(data.get("name", "")).strip()
    ids = data.get("ids")
    target_id = str(data.get("target") or manager.DEFAULT_TARGET_ID)
    target_dir = _target_dir(request, data)

    skills = _all_skills()
    if ids:
        chosen = [s for s in skills if s.id in set(ids)]
    else:
        # No explicit selection: snapshot whatever is enabled on this target.
        managed = manager.enabled_map(target_dir)
        chosen = [s for s in skills if manager.find_enabled_target_for(s.dir, managed) is not None]

    try:
        entry = manager.save_profile(name, chosen, target_id)
    except manager.ManagerError as e:
        raise web.HTTPBadRequest(text=str(e)) from e
    return web.json_response({"name": name, **entry}, status=201)


@routes.post("/api/profiles/{name}/apply")
async def apply_profile(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    data = await _body(request)
    profile = manager.list_profiles().get(name)
    if profile is None:
        raise web.HTTPNotFound(text="profile not found")
    target_id = data.get("target") or profile.get("target_id")
    try:
        target_dir = manager.resolve_target(target_id)
        result = manager.apply_profile(name, _all_skills(), target_dir)
    except manager.ManagerError as e:
        return web.json_response({"error": str(e), "code": e.code}, status=409)
    return web.json_response(result)


@routes.delete("/api/profiles/{name}")
async def delete_profile(request: web.Request) -> web.Response:
    try:
        manager.delete_profile(request.match_info["name"])
    except manager.ManagerError as e:
        raise web.HTTPNotFound(text=str(e)) from e
    return web.json_response({"deleted": request.match_info["name"]})


# --- diagnostics ------------------------------------------------------------


@routes.get("/api/doctor")
async def doctor(request: web.Request) -> web.Response:
    return web.json_response(manager.diagnose(_all_skills()))


@routes.post("/api/doctor/repair")
async def doctor_repair(request: web.Request) -> web.Response:
    data = await _body(request)
    target_dir = data.get("target_dir")
    target_name = data.get("target_name")
    action = data.get("action")
    if not target_dir or not target_name or not action:
        raise web.HTTPBadRequest(text="target_dir, target_name and action are required")
    try:
        result = manager.repair(Path(target_dir), str(target_name), str(action))
    except manager.ManagerError as e:
        return web.json_response({"error": str(e), "code": e.code}, status=409)
    return web.json_response(result)


# --- icons ------------------------------------------------------------------


@routes.get("/api/icons")
async def get_icons(request: web.Request) -> web.Response:
    return web.json_response({"overrides": config.load_icons(), "builtin": scanner.CATEGORY_ICONS})


@routes.put("/api/icons")
async def put_icons(request: web.Request) -> web.Response:
    data = await _body(request)
    overrides = data.get("overrides")
    if not isinstance(overrides, dict):
        raise web.HTTPBadRequest(text="overrides must be an object")
    cleaned = {str(k).strip().lower(): str(v).strip() for k, v in overrides.items() if str(v).strip()}
    config.save_icons(cleaned)
    return web.json_response({"overrides": cleaned})


# --- export -----------------------------------------------------------------


@routes.post("/api/export")
async def export_skills(request: web.Request) -> web.Response:
    data = await _body(request)
    ids = data.get("ids") or []
    if not ids:
        raise web.HTTPBadRequest(text="ids is required")
    skills = [_find_skill(i) for i in ids]
    text = manager.export_markdown(skills)
    return web.Response(
        text=text,
        content_type="text/markdown",
        headers={
            "Content-Disposition": 'attachment; filename="skills-export.md"',
            "X-Estimated-Tokens": str(metrics.estimate_tokens(text)),
        },
    )
