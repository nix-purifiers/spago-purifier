# SPDX-License-Identifier: MIT
"""Pack the self-contained native ESM library using ordinary npm."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

artifact, spec_path, destination, npm = sys.argv[1:]
artifact, destination = Path(artifact), Path(destination)
spec = json.loads(Path(spec_path).read_text())
package = Path("npm-package")
package.mkdir()
metadata = {"name": spec["name"], "version": spec["version"], "type": "module",
            "exports": "./main.mjs", "files": ["main.mjs"]}
(package / "package.json").write_text(json.dumps(metadata, sort_keys=True) + "\n")
shutil.copyfile(artifact / "main.mjs", package / "main.mjs")
archives = destination / "archives"
archives.mkdir(parents=True)
packed = json.loads(subprocess.check_output([npm, "pack", "--offline", "--ignore-scripts", "--json",
                    "--pack-destination", str(archives)], cwd=package, text=True))
assert len(packed) == 1
archive = archives / packed[0]["filename"]
with tarfile.open(archive, "r:gz") as stream:
    assert {m.name for m in stream.getmembers() if m.isfile()} == {"package/package.json", "package/main.mjs"}
    native = json.loads(stream.extractfile("package/package.json").read())
    assert native == metadata
    assert stream.extractfile("package/main.mjs").read() == (artifact / "main.mjs").read_bytes()
graph = {"version": 1, "primaries": {spec["name"]: "library"}, "nodes": {
    "library": {"name": native["name"], "version": native["version"], "package": native,
                "archive": archive.name, "contentHash": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "dependencies": {}}}}
(destination / "graph.json").write_text(json.dumps(graph, sort_keys=True, indent=2) + "\n")
(destination / "pack.json").write_text(json.dumps(packed, sort_keys=True, indent=2) + "\n")
