# SPDX-License-Identifier: MIT
"""Select an owned native PureScript module and prove its browser bundle inputs."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside(path, root):
    return path.is_relative_to(root)


def build(source, output, environment, spec_path, destination, proof, esbuild, compiler):
    source, output, environment = (Path(p).resolve() for p in (source, output, environment))
    destination, proof = Path(destination), Path(proof)
    spec = json.loads(Path(spec_path).read_text())
    native = json.loads((source / "spago.lock").read_text())
    workspace = native["workspace"]["packages"]
    production = []
    for name, package in workspace.items():
        root = (source / package["path"]).resolve()
        if not inside(root, source):
            raise ValueError("workspace package escapes source: " + name)
        production.append((name, root / "src"))
    compiler_version = subprocess.check_output([compiler, "--version"], text=True).strip()
    bundler_version = subprocess.check_output([esbuild, "--version"], text=True).strip()
    owners = {}

    def owner(module):
        if module in owners:
            return owners[module]
        directory = output / module
        core_path = directory / "corefn.json"
        core = json.loads(core_path.read_text())
        if ".".join(core["moduleName"]) != module or core["builtWith"] != compiler_version:
            raise ValueError("native module/compiler identity mismatch: " + module)
        path = Path(core["modulePath"])
        path = (source / path).resolve() if not path.is_absolute() else path.resolve()
        identity = None
        for name, root in production:
            if inside(path, root) and inside(path, source):
                identity = {"kind": "project", "package": name,
                            "source": str(path.relative_to(source))}
                break
        if identity is None:
            for name, package in native["packages"].items():
                root = environment / "sources" / (name + "-" + package["version"])
                if inside(path, root):
                    identity = {"kind": "registry", "package": name,
                                "version": package["version"],
                                "source": str(path.relative_to(root))}
                    break
        if identity is None and module == "Spago.Generated.BuildInfo" and path == source / ".spago/BuildInfo.purs":
            identity = {"kind": "generated", "source": ".spago/BuildInfo.purs"}
        if identity is None or path.suffix != ".purs" or not path.is_file():
            raise ValueError("module has no production source owner: " + module)
        identity.update(module=module, sourceSha256=digest(path), corefnSha256=digest(core_path),
                        exports=core["exports"])
        target = proof / "modules" / module
        target.mkdir(parents=True)
        shutil.copyfile(core_path, target / "corefn.json")
        shutil.copyfile(path, target / "source.purs")
        owners[module] = identity
        return identity

    destination.mkdir(parents=True)
    proof.mkdir(parents=True)
    entry = spec["module"]
    if owner(entry)["kind"] != "project":
        raise ValueError("entry module must belong to a workspace production source")
    metafile = proof / "bundle.json"
    subprocess.run([esbuild, str(output / entry / "index.js"), "--bundle", "--platform=browser",
                    "--format=esm", "--outfile=" + str(destination / "main.mjs"),
                    "--metafile=" + str(metafile)], check=True)
    metadata = json.loads(metafile.read_text())
    inputs = []
    for filename in metadata["inputs"]:
        path = Path(filename).resolve()
        # Dependencies may resolve directly through immutable session symlinks.
        module = path.parent.name
        expected = (output / module / path.name).resolve()
        if path != expected or path.name not in ("index.js", "foreign.js"):
            raise ValueError("bundle input is not native compiler output: " + filename)
        identity = owner(module)
        if path.name == "foreign.js":
            core = json.loads((output / module / "corefn.json").read_text())
            foreign = Path(core["modulePath"]).with_suffix(".js")
            foreign = (source / foreign).resolve() if not foreign.is_absolute() else foreign.resolve()
            if not foreign.is_file() or digest(foreign) != digest(path):
                raise ValueError("native foreign module differs from owned source: " + module)
        inputs.append({"module": module, "file": path.name, "sha256": digest(path),
                       "owner": identity["kind"]})
    if any(item.get("imports") for item in metadata["outputs"].values()):
        raise ValueError("browser bundle has unresolved runtime imports")
    for name, relative in spec.get("assets", {}).items():
        path = (source / relative).resolve()
        target = destination / name
        if not inside(path, source) or not path.is_file():
            raise ValueError("asset is not a project source file: " + relative)
        if target.exists():
            raise ValueError("asset overwrites generated output: " + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    public = {str(p.relative_to(destination)): digest(p) for p in sorted(destination.rglob("*")) if p.is_file()}
    (proof / "provenance.json").write_text(json.dumps({"entry": entry, "compiler": compiler_version,
        "bundler": bundler_version, "modules": owners, "inputs": inputs, "files": public},
        sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    build(*sys.argv[1:])
