#!/usr/bin/env python3
"""Mirror community plugins from their GitHub repos into plugins/ and rebuild
.claude-plugin/marketplace.json from sources.json.

A plugin's files are only rewritten when the upstream content actually changes,
so the repo only gets a new commit (and Claude Desktop only sees an update)
when an author has changed something.

Usage: python3 scripts/sync.py   (run from the repo root)
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "sources.json"
PLUGINS_DIR = ROOT / "plugins"
LOCK = ROOT / "upstream.lock.json"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def tree_hash(path: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p for p in path.rglob("*") if p.is_file() or p.is_symlink()):
        rel = f.relative_to(path).as_posix()
        h.update(rel.encode())
        h.update(b"\0")
        if f.is_symlink():
            h.update(b"L" + str(f.readlink()).encode())
        else:
            h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def fetch(src, workdir: Path) -> tuple[Path, str]:
    """Shallow, sparse clone of only the folders we need."""
    dest = workdir / src["name"]
    url = f"https://github.com/{src['repo']}.git"
    run("git", "clone", "--depth", "1", "--filter=blob:none", "--sparse",
        "--branch", src.get("ref", "main"), url, str(dest))
    wanted = [src["path"]] if src["mode"] == "plugin" else list(src["skills"])
    run("git", "sparse-checkout", "set", "--no-cone", *[f"/{p}/" for p in wanted],
        f"/{src['license_file']}", cwd=dest)
    sha = run("git", "rev-parse", "HEAD", cwd=dest)
    return dest, sha


def build(src, clone: Path, out: Path):
    """Lay out the plugin folder for one source in `out`."""
    if src["mode"] == "plugin":
        shutil.copytree(clone / src["path"], out, symlinks=True)
    elif src["mode"] == "skills":
        (out / ".claude-plugin").mkdir(parents=True)
        for skill in src["skills"]:
            shutil.copytree(clone / skill, out / "skills" / Path(skill).name, symlinks=True)
        manifest = {
            "name": src["name"],
            "description": src["description"],
            "author": {"name": src["author"]},
            "homepage": src["homepage"],
            "repository": f"https://github.com/{src['repo']}",
            "license": src["license"],
        }
        # No "version" on purpose: Claude then tracks this repo's commits,
        # which only happen when the upstream skill changes.
        (out / ".claude-plugin" / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n")
    else:
        raise ValueError(f"unknown mode {src['mode']!r} for {src['name']}")
    lic = clone / src["license_file"]
    if lic.exists() and not (out / "LICENSE").exists():
        shutil.copy2(lic, out / "LICENSE")


def main() -> int:
    cfg = json.loads(SOURCES.read_text())
    lock = json.loads(LOCK.read_text()) if LOCK.exists() else {}
    PLUGINS_DIR.mkdir(exist_ok=True)
    changed, failed = [], []

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for src in cfg["plugins"]:
            name = src["name"]
            try:
                clone, sha = fetch(src, tmp / "clones")
                staged = tmp / "staged" / name
                build(src, clone, staged)
            except Exception as e:  # keep the last good copy if one source breaks
                detail = getattr(e, "stderr", "") or str(e)
                print(f"!! {name}: {detail.strip()}", file=sys.stderr)
                failed.append(name)
                continue
            target = PLUGINS_DIR / name
            if target.exists() and tree_hash(target) == tree_hash(staged):
                print(f"   {name}: unchanged")
                continue
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(staged, target, symlinks=True)
            lock[name] = {"repo": src["repo"], "ref": src.get("ref", "main"), "commit": sha}
            changed.append(name)
            print(f"-> {name}: updated from {src['repo']}@{sha[:7]}")

    # Drop plugins that were removed from sources.json
    names = {p["name"] for p in cfg["plugins"]}
    for d in PLUGINS_DIR.iterdir():
        if d.is_dir() and d.name not in names:
            shutil.rmtree(d)
            lock.pop(d.name, None)
            changed.append(d.name)
            print(f"-> {d.name}: removed")

    m = cfg["marketplace"]
    market = {
        "name": m["name"],
        "description": m["description"],
        "owner": m["owner"],
        "plugins": [],
    }
    for src in cfg["plugins"]:
        if not (PLUGINS_DIR / src["name"]).exists():
            continue
        manifest = json.loads((PLUGINS_DIR / src["name"] / ".claude-plugin" / "plugin.json").read_text())
        market["plugins"].append({
            "name": src["name"],
            "description": manifest.get("description", ""),
            "source": f"./plugins/{src['name']}",
            "homepage": manifest.get("homepage", f"https://github.com/{src['repo']}"),
        })
    MARKETPLACE.parent.mkdir(exist_ok=True)
    MARKETPLACE.write_text(json.dumps(market, indent=2) + "\n")
    LOCK.write_text(json.dumps(dict(sorted(lock.items())), indent=2) + "\n")

    print(f"\nupdated: {changed or 'none'}; failed: {failed or 'none'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
