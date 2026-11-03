# SPDX-License-Identifier: MIT
"""Private mutable application state around immutable dependency modules."""

import os
import shutil


def prepare(root, environment, directory):
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "output"
    marker = directory / "prepared"
    if not marker.exists():
        output.mkdir(exist_ok=True)
        for path in (environment / "output").iterdir():
            destination = output / path.name
            if path.is_file():
                shutil.copyfile(path, destination)
            elif path.name == "Prim" or path.name.startswith("Prim."):
                shutil.copytree(path, destination)
                for child in [destination, *destination.rglob("*")]:
                    if not child.is_symlink():
                        child.chmod(0o755 if child.is_dir() else 0o644)
            else:
                destination.symlink_to(path)
        cache = directory / "cache/spago-nodejs"
        cache.mkdir(parents=True, exist_ok=True)
        for name in ["registry", "registry-index"]:
            (cache / name).symlink_to(environment / "registry" / name)
        marker.write_text("1\n")
    env = dict(os.environ)
    env.update(
        {
            "SPAGO_PURIFIER_SOURCES": str(environment / "sources"),
            "SPAGO_PURIFIER_OUTPUT": str(output),
            "XDG_CACHE_HOME": str(directory / "cache"),
            "XDG_CONFIG_HOME": str(directory / "config"),
        }
    )
    return env
