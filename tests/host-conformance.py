#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

REPO = Path(__file__).resolve().parents[1]


def run(args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, text=True, **kwargs)


case = sys.argv[1]
with tempfile.TemporaryDirectory(prefix="spago-conformance-") as temporary:
    temp = Path(temporary)
    cli = temp / "cli"
    run(["nix", "build", str(REPO) + "#cli", "--out-link", cli])
    helper, spago = cli / "bin/spago-purifier", cli / "bin/spago"
    root = temp / "project"
    shutil.copytree(
        REPO / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns(".spago", ".spago-purifier", "output", "*.log"),
    )
    native_lock, companion = root / "spago.lock", root / "spago-purifier.lock.json"
    args = [helper, "--project", root]
    if case == "external":
        native_lock.rename(temp / "external.lock")
        companion.rename(temp / "external.json")
        native_lock, companion = temp / "external.lock", temp / "external.json"
        args += ["--lock-file", companion, "--native-lock", native_lock]
    if case == "relock":
        before = companion.read_bytes(), native_lock.read_bytes()
        run([*args, "lock"])
        assert before == (companion.read_bytes(), native_lock.read_bytes())
    if case == "package-set":
        manifest = root / "spago.yaml"
        manifest.write_text(
            manifest.read_text() + "  packageSet:\n    registry: 81.11.0\n"
        )
        run([*args, "lock"])
    if case == "update":
        manifest = root / "spago.yaml"
        manifest.write_text(manifest.read_text().replace(">=6.1.1 <7.0.0", "6.0.0"))
        run([*args, "lock"])
        first = json.loads(native_lock.read_text())
        assert first["packages"]["console"]["version"] == "6.0.0"
        manifest.write_text(
            manifest.read_text()
            .replace("console: 6.0.0", 'console: ">=6.0.0 <7.0.0"')
            .replace('console: "6.0.0"', 'console: ">=6.0.0 <7.0.0"')
        )
        run([*args, "lock", "--update"])
        updated = json.loads(native_lock.read_text())
        assert updated["packages"]["console"]["version"] != "6.0.0"
    environment = Path(run([*args, "prefetch"], stdout=subprocess.PIPE).stdout.strip())
    assert (environment / "sources").is_dir()
    poisoned = root / ".spago/p/prelude-6.0.3/src/Prelude.purs"
    poisoned.parent.mkdir(parents=True, exist_ok=True)
    poisoned.write_text("poisoned ordinary cache\n")
    output = run(
        [*args, "shell", "--", "spago", "run"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert "locked Spago: 42" in output.stdout, output
    run([*args, "shell", "--", "spago", "test"])
    if case == "native":
        source = root / "src/Main.purs"
        source.write_text(source.read_text().replace("20 + 22", "21 + 22"))
        result = run(
            [*args, "shell", "--", "spago", "run"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert "locked Spago: 43" in result.stdout
        assert (
            "Compiling Prelude" not in result.stderr
            and "Compiling Effect" not in result.stderr
        )
        failed = subprocess.run(
            [*map(str, args), "shell", "--", "spago", "test"],
            capture_output=True,
            text=True,
        )
        assert (
            failed.returncode != 0 and "unexpected application answer" in failed.stderr
        )
        source.write_text(source.read_text().replace("21 + 22", "20 + 22"))
        run(["python3", REPO / "tests/editor.py", root, helper])
        native_binary = temp / "native"
        run(["nix", "build", str(REPO) + "#native", "--out-link", native_binary])
        empty = temp / "unlocked"
        empty.mkdir()
        compiler = temp / "compiler"
        run(["nix", "build", str(REPO) + "#compiler", "--out-link", compiler])
        baseline_env = os.environ | {
            "PATH": str(compiler / "bin") + os.pathsep + os.environ["PATH"]
        }
        baseline = subprocess.run(
            [native_binary / "bin/spago", "build"],
            cwd=empty,
            capture_output=True,
            text=True,
            env=baseline_env,
        )
        fallback = subprocess.run(
            [spago, "build"], cwd=empty, capture_output=True, text=True
        )
        assert fallback.returncode == baseline.returncode
        assert fallback.stdout == baseline.stdout
        warning, rest = fallback.stderr.split("\n", 1)
        assert "no lockfile" in warning and "impure" in warning
        assert rest == baseline.stderr, {"wrapper": rest, "baseline": baseline.stderr}
    if case == "release":
        release = (
            Path(run([*args, "release"], stdout=subprocess.PIPE).stdout.strip())
            / "source.tar.gz"
        )
        with tarfile.open(release) as archive:
            names = archive.getnames()
            assert "./spago.lock" in names and "./spago-purifier.lock.json" in names
            assert not any(
                "/.spago/" in name or "/.spago-purifier/" in name or "/output/" in name
                for name in names
            )
            assert (
                archive.extractfile("./spago.lock").read() == native_lock.read_bytes()
            )
    if case == "release":
        fake = temp / "gh"
        fake.write_text(
            "#!"
            + sys.executable
            + "\n"
            + """
import hashlib, json, os, pathlib, sys
args=sys.argv[1:]
state=pathlib.Path(os.environ['FAKE_GH_STATE'])
if args[:2]==['release','view']:
    sys.exit(0 if state.exists() else 1)
assert args[:2] in (['release','create'],['release','upload']), args
artifact=pathlib.Path(args[3])
assert artifact.is_file()
with open(os.environ['FAKE_GH_LOG'],'a') as stream:
    stream.write(json.dumps({'args':args,'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()})+'\\n')
state.write_text('created')
"""
        )
        fake.chmod(0o755)
        env = os.environ | {
            "SPAGO_PURIFIER_GH": str(fake),
            "FAKE_GH_STATE": str(temp / "release-created"),
            "FAKE_GH_LOG": str(temp / "publish.jsonl"),
        }
        for _ in range(2):
            run([*args, "publish", "--repo", "example/project", "--tag", "v1"], env=env)
        records = [
            json.loads(line)
            for line in (temp / "publish.jsonl").read_text().splitlines()
        ]
        assert records[0]["args"][:2] == ["release", "create"]
        assert records[1]["args"][:2] == ["release", "upload"]
        import hashlib

        assert all(
            record["sha256"] == hashlib.sha256(release.read_bytes()).hexdigest()
            for record in records
        )
    native_lock.write_text(native_lock.read_text() + "\n")
    refused = subprocess.run(
        [*map(str, args), "prefetch"], capture_output=True, text=True
    )
    assert refused.returncode != 0 and "native lock changed" in refused.stderr
    print("Spago conformance passed:", case)
