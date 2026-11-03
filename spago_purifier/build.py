# SPDX-License-Identifier: MIT
"""Build the native lock's dependency modules inside the Nix sandbox."""

import glob
import json
from pathlib import Path
import subprocess
import sys
import tarfile

lock_path, source_path, output_path = map(Path, sys.argv[1:])
lock = json.loads(lock_path.read_text())
for name, package in sorted(lock["packages"].items()):
    if package["type"] != "registry":
        raise ValueError("unsupported package provider: " + name)
    archive = source_path / "archives" / f"{name}-{package['version']}.tar.gz"
    with tarfile.open(archive, "r:gz") as stream:
        stream.extractall(output_path / "sources", filter="data")
    package_path = output_path / "sources" / f"{name}-{package['version']}"
    if not package_path.is_dir():
        raise ValueError("native archive layout changed: " + name)
    # Registry timestamps are not part of the selected package identity.
    import os

    for path in package_path.rglob("*"):
        if not path.is_symlink():
            os.utime(path, (1, 1))
sources = sorted(glob.glob(str(output_path / "sources/**/*.purs"), recursive=True))
if sources:
    subprocess.run(
        [
            "purs",
            "compile",
            "--codegen",
            "corefn,docs,js,sourcemaps",
            "--output",
            str(output_path / "output"),
            *sources,
        ],
        check=True,
    )
