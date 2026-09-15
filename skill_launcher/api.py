from __future__ import annotations

import uuid
from pathlib import Path

from aiohttp import web

from . import config, manager, scanner

routes = web.RouteTableDef()


def _skill_to_json(s: scanner.Skill, managed: dict) -> dict:
    target_name = manager.find_enabled_target_for(s.dir, managed)
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "category": s.category,
        "icon": scanner.icon_for(s.category),
        "source_id": s.source_id,
        "source_label": s.source_label,
        "path": str(s.path),
        "enabled": target_name is not None,
        "target_name": target_name,
        "kind": managed.get(target_name, {}).get("kind") if target_name else None,
    }


def _find_skill(skill_id: str) -> scanner.Skill:
    sources = config.load_sources()
    for s in scanner.scan_all(sources):
        if s.id == skill_id:
            return s
    raise web.HTTPNotFound(text="skill not found (source may have changed - try rescanning)")


@routes.get("/api/health")
async def health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


@routes.get("/api/sources")
async def list_sources(request: web.Request) -> web.Response:
    sources = config.load_sources()
    out = []
    for s in sources:
        p = Path(s["path"]).expanduser()
        out.append({**s, "exists": p.is_dir(), "skill_count": len(scanner.scan_source(s))})
    return web.json_response(out)


@routes.post("/api/sources")
async def add_source(request: web.Request) -> web.Response:
    data = await request.json()
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
    return web.json_response(entry, status=201)


@routes.delete("/api/sources/{source_id}")
async def remove_source(request: web.Request) -> web.Response:
    source_id = request.match_info["source_id"]
    sources = config.load_sources()
    remaining = [s for s in sources if s["id"] != source_id]
    if len(remaining) == len(sources):
        raise web.HTTPNotFound(text="source not found")
    config.save_sources(remaining)
    return web.json_response({"removed": source_id})


@routes.get("/api/skills")
async def list_skills(request: web.Request) -> web.Response:
    sources = config.load_sources()
    managed = manager.enabled_map()
    skills = scanner.scan_all(sources)
    return web.json_response([_skill_to_json(s, managed) for s in skills])


@routes.get("/api/skills/{skill_id}")
async def get_skill(request: web.Request) -> web.Response:
    skill = _find_skill(request.match_info["skill_id"])
    return web.json_response(manager.read_skill_source(skill))


@routes.put("/api/skills/{skill_id}")
async def update_skill(request: web.Request) -> web.Response:
    skill = _find_skill(request.match_info["skill_id"])
    data = await request.json()
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    body = data.get("body", "")
    if not name:
        raise web.HTTPBadRequest(text="name is required")
    try:
        backup_path = manager.write_skill_source(skill, name, description, body)
    except manager.ManagerError as e:
        raise web.HTTPBadRequest(text=str(e))
    return web.json_response({"saved": True, "backup": str(backup_path)})


@routes.post("/api/skills/{skill_id}/enable")
async def enable_skill(request: web.Request) -> web.Response:
    skill = _find_skill(request.match_info["skill_id"])
    data = {}
    if request.can_read_body:
        try:
            data = await request.json()
        except Exception:
            data = {}
    target_name = data.get("target_name") or None
    try:
        result = manager.enable_skill(skill, target_name)
    except manager.ManagerError as e:
        return web.json_response({"error": str(e), "code": e.code}, status=409)
    return web.json_response(result)


@routes.post("/api/skills/{skill_id}/disable")
async def disable_skill(request: web.Request) -> web.Response:
    skill = _find_skill(request.match_info["skill_id"])
    data = {}
    if request.can_read_body:
        try:
            data = await request.json()
        except Exception:
            data = {}
    if not data.get("confirm"):
        raise web.HTTPBadRequest(text="confirm:true is required to disable a skill")

    managed = manager.enabled_map()
    target_name = manager.find_enabled_target_for(skill.dir, managed)
    if target_name is None:
        raise web.HTTPBadRequest(text="skill is not currently enabled")
    try:
        manager.disable_skill(target_name)
    except manager.ManagerError as e:
        return web.json_response({"error": str(e), "code": e.code}, status=409)
    return web.json_response({"disabled": target_name})


@routes.post("/api/export")
async def export_skills(request: web.Request) -> web.Response:
    data = await request.json()
    ids = data.get("ids") or []
    if not ids:
        raise web.HTTPBadRequest(text="ids is required")
    skills = [_find_skill(i) for i in ids]
    text = manager.export_markdown(skills)
    return web.Response(
        text=text,
        content_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="skills-export.md"'},
    )
