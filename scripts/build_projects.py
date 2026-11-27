#!/usr/bin/env python3
"""Genera data/projects.json combinando data/projects.yml con la API de GitHub.

Variables de entorno:
  GH_PAT    token de solo lectura (Metadata + Contents) con acceso a todos los repos.
            Sin token solo se leen los repos públicos (y con límite de peticiones).
  GH_USER   usuario de GitHub (por defecto: mangrovex).
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
USER = os.environ.get("GH_USER", "mangrovex")
TOKEN = os.environ.get("GH_PAT", "").strip()
TOPIC = "portafolio"
HIDE_TOPIC = "no-portafolio"
CATS = {"odoo", "integ", "fin", "devops", "mobile"}


def api(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"{USER}-portfolio-sync",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_repos():
    repos, page = [], 1
    base = (f"https://api.github.com/user/repos?affiliation=owner&visibility=all"
            if TOKEN else f"https://api.github.com/users/{USER}/repos?type=owner")
    while True:
        batch = api(f"{base}&per_page=100&page={page}")
        repos += [r for r in batch if r["owner"]["login"].lower() == USER.lower()]
        if len(batch) < 100:
            return {r["name"]: r for r in repos}
        page += 1


def main():
    cfg = yaml.safe_load((ROOT / "data/projects.yml").read_text(encoding="utf-8"))
    try:
        gh = fetch_repos()
        source = "api-privada" if TOKEN else "api-publica"
    except Exception as e:  # sin red o sin token: se usa solo el YAML
        print(f"Aviso: no se pudo leer la API de GitHub ({e}); se usa solo projects.yml", file=sys.stderr)
        gh, source = {}, "yml"

    # Repos ocultos: lista `exclude` del YAML o topic "no-portafolio" en GitHub.
    exclude = set(cfg.get("exclude", [])) | {n for n, r in gh.items() if HIDE_TOPIC in (r.get("topics") or [])}
    now = dt.datetime.now(dt.timezone.utc)
    auto_since = str(cfg.get("auto_since", "2100-01-01"))
    new_days = int(cfg.get("new_days", 60))

    def created(r):
        return (r.get("created_at") or "")[:10]

    def is_recent(r):
        c = r.get("created_at")
        return bool(c) and (now - dt.datetime.fromisoformat(c.replace("Z", "+00:00"))).days < new_days
    used = set()
    projects = []

    def build(card, auto=False):
        names = card["repos"]
        data = [gh[n] for n in names if n in gh]
        used.update(names)
        if data:
            private = all(d["private"] for d in data)
        else:
            private = card.get("visibility", "public") == "private"
        pushed = max((d["pushed_at"] for d in data if d.get("pushed_at")), default=None)
        langs = sorted({d["language"] for d in data if d.get("language")})
        desc = card.get("description") or next((d["description"] for d in data if d.get("description")), "") or ""
        links = []
        if not private:
            links.append({"label": "Repositorio", "url": f"https://github.com/{USER}/{names[0]}"})
            hp = next((d.get("homepage") for d in data if d.get("homepage")), None)
            if hp and not any(l["url"].rstrip("/") == hp.rstrip("/") for l in card.get("links", [])):
                links.append({"label": "Sitio", "url": hp})
            links += card.get("links", [])
        return {
            "name": card["name"],
            "code": card.get("code") or (f"{USER}/{names[0]}" if not private and len(names) == 1 else " · ".join(names)),
            "icon": card.get("icon", "📦"),
            "vis": "private" if private else "public",
            "st": card.get("status", "wip"),
            "cat": card.get("categories", []),
            "featured": bool(card.get("featured")),
            "desc": desc,
            "bullets": card.get("bullets", []),
            "tags": card.get("tags") or langs,
            "links": links,
            "pushed_at": pushed,
            "stars": sum(d.get("stargazers_count", 0) for d in data),
            "auto": auto,
            "new": bool(card.get("new")),
        }

    for card in cfg.get("cards", []):
        projects.append(build(card))

    # Tarjetas automáticas: repos con el topic "portafolio" que no estén en el YAML.
    for name, r in gh.items():
        if name in used or name in exclude or TOPIC not in (r.get("topics") or []):
            continue
        projects.append(build({
            "name": name, "repos": [name], "icon": "✨",
            "status": "arch" if r.get("archived") else "wip",
            "categories": [t for t in r.get("topics", []) if t in CATS],
        }, auto=True))

    # Repos nuevos: todo repo propio (no fork) creado desde `auto_since` aparece solo
    # como tarjeta "Nuevo" durante `new_days` días, público o privado.
    old_private = []
    for name, r in sorted(gh.items(), key=lambda kv: kv[1].get("created_at") or "", reverse=True):
        if name in used or name in exclude or r.get("fork") or created(r) < auto_since:
            continue
        if is_recent(r):
            projects.append(build({
                "name": name, "repos": [name], "icon": "🆕", "new": True,
                "status": "arch" if r.get("archived") else "wip",
                "categories": [t for t in r.get("topics", []) if t in CATS],
                "description": r.get("description") or "Nuevo repositorio, recién creado.",
            }, auto=True))
        elif r["private"]:
            old_private.append(name)  # pasado el plazo: a "Otros repositorios privados"

    # Archivo: repos públicos no usados en tarjetas.
    labels = cfg.get("archive_labels", {})
    archive = []
    if gh:
        for name, r in gh.items():
            if r["private"] or name in used or name in exclude:
                continue
            archive.append({
                "name": name,
                "label": labels.get(name) or ("fork" if r["fork"] else (r.get("language") or "proyecto")),
                "pushed_at": r.get("pushed_at"),
            })
        archive.sort(key=lambda a: a["pushed_at"] or "", reverse=True)
    else:
        archive = [{"name": n, "label": l, "pushed_at": None} for n, l in labels.items() if n not in exclude]

    private_other = [n for n in cfg.get("private_other", []) if n not in used and n not in exclude]
    private_other += [n for n in old_private if n not in private_other]
    if source == "api-privada":  # solo los que aún existen
        private_other = [n for n in private_other if n in gh]
    private_total = sum(1 for r in gh.values() if r["private"]) if source == "api-privada" \
        else sum(len(c["repos"]) for c in cfg["cards"] if c.get("visibility") == "private") + len(private_other)

    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "source": source,
        "projects": projects,
        "archive": archive,
        "private_other": private_other,
        "counts": {
            "active": sum(1 for p in projects if p["st"] != "arch"),
            "public": sum(1 for p in projects if p["vis"] == "public") + len(archive),
            "private": private_total,
        },
    }
    dest = ROOT / "data/projects.json"
    new = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if dest.exists():
        old = json.loads(dest.read_text(encoding="utf-8"))
        old.pop("generated_at", None)
        cmp = dict(out); cmp.pop("generated_at")
        if old == cmp:
            print("Sin cambios en los proyectos.")
            return
    dest.write_text(new, encoding="utf-8")
    print(f"projects.json actualizado ({len(projects)} tarjetas, {len(archive)} en archivo, fuente: {source}).")


if __name__ == "__main__":
    main()
