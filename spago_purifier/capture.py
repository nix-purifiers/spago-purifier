# SPDX-License-Identifier: MIT
"""Capture native Spago solutions and the registry snapshots they use."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from .common import atomic, capture_git, digest, run


def manifests(root):
    result = {}
    for folder, dirs, files in os.walk(root):
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".") and d not in {"node_modules", "output", "result"}
        ]
        if "spago.yaml" in files:
            path = Path(folder) / "spago.yaml"
            result[path.relative_to(root).as_posix()] = path.read_bytes()
    if "spago.yaml" not in result:
        raise ValueError("no spago.yaml at the project root")
    return result


def capture(root, lock_file, native_lock, native, versions, update=False):
    inputs = manifests(root)
    with tempfile.TemporaryDirectory(prefix="spago-lock-") as temporary:
        scratch = Path(temporary)
        project = scratch / "project"
        project.mkdir()
        for name, content in inputs.items():
            path = project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        if native_lock.exists():
            shutil.copyfile(native_lock, project / "spago.lock")
        env = {
            k: v for k, v in os.environ.items() if not k.startswith("SPAGO_PURIFIER_")
        }
        env["XDG_CACHE_HOME"] = str(scratch / "cache")
        env["XDG_CONFIG_HOME"] = str(scratch / "config")
        env["SPAGO_PURIFIER_CAPTURE_ONLY"] = "1"
        if lock_file.exists() and not update:
            previous = json.loads(lock_file.read_text())
            for name in ["registry", "registry-index"]:
                entry = next(
                    e
                    for e in previous["entries"]
                    if e["path"] == previous["registries"][name]
                )
                checkout = scratch / "cache/spago-nodejs" / name
                checkout.parent.mkdir(parents=True, exist_ok=True)
                run(
                    [
                        "git",
                        "clone",
                        "--no-checkout",
                        "--filter=blob:none",
                        entry["git"]["url"],
                        checkout,
                    ]
                )
                run(
                    ["git", "-C", checkout, "checkout", "--detach", entry["git"]["rev"]]
                )
            env["SPAGO_PURIFIER_PINNED_REGISTRIES"] = "1"
        if update:
            run([native, "upgrade"], cwd=project, env=env)
        run([native, "fetch"], cwd=project, env=env)
        if (project / "output").exists():
            raise ValueError("native capture unexpectedly compiled dependencies")
        lock_bytes = (project / "spago.lock").read_bytes()
        lock = json.loads(lock_bytes)
        entries = []
        for name, package in sorted(lock["packages"].items()):
            if (
                not re.fullmatch("[a-z][a-z0-9-]*", name)
                or package.get("type") != "registry"
            ):
                raise ValueError(
                    "initial source adapter requires registry packages: " + name
                )
            version, integrity = package["version"], package["integrity"]
            if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
                raise ValueError("unsupported native registry version: " + version)
            archive = (
                scratch / "cache/spago-nodejs/packages" / name / (version + ".tar.gz")
            )
            import base64

            expected = (
                "sha256-"
                + base64.b64encode(bytes.fromhex(digest(archive.read_bytes()))).decode()
            )
            if integrity != expected:
                raise ValueError("native archive integrity mismatch: " + name)
            entries.append(
                {
                    "path": f"archives/{name}-{version}.tar.gz",
                    "url": f"https://packages.registry.purescript.org/{name}/{version}.tar.gz",
                    "hash": integrity,
                    "mirrors": [],
                }
            )
        registries = {}
        for name in ["registry", "registry-index"]:
            checkout = scratch / "cache/spago-nodejs" / name
            commit = run(
                ["git", "-C", checkout, "rev-parse", "HEAD"],
                stdout=subprocess.PIPE,
                text=True,
            ).stdout.strip()
            entry = capture_git(
                {
                    "url": f"https://github.com/purescript/{name}.git",
                    "commit": commit,
                    "directory": str(checkout),
                    "name": name,
                },
                scratch,
            )
            entries.append(entry)
            registries[name] = entry["path"]
        selected = {}
        for name in inputs:
            content = (project / name).read_bytes()
            selected[name] = {"content": content.decode(), "sha256": digest(content)}
        data = {
            "schemaVersion": 1,
            "purifier": "spago",
            "toolVersions": versions,
            "manifests": selected,
            "nativeLock": {"sha256": digest(lock_bytes)},
            "entries": entries,
            "registries": registries,
        }
        # Commit only after native capture and every archive/snapshot validate.
        for name in inputs:
            atomic(root / name, (project / name).read_bytes())
        atomic(native_lock, lock_bytes)
        atomic(lock_file, json.dumps(data, indent=2, sort_keys=True) + "\n")
