# SPDX-License-Identifier: MIT
"""Native Spago commands over locked Nix dependencies."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .capture import capture, manifests
from .common import digest, run
from .session import prepare

PREFIX = "SPAGO_PURIFIER_"


def clean_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith(PREFIX)}
    for key, value in json.loads(os.environ.get(PREFIX + "BASE_ENV", "{}")).items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return env


def root_from(start):
    candidates = [start, *start.parents]
    for path in candidates:
        if (path / "spago-purifier.lock.json").exists():
            return path
    for path in candidates:
        if (path / "spago.yaml").exists():
            return path
    return start


def paths(opts):
    root = Path(
        opts.project or os.environ.get(PREFIX + "PROJECT") or root_from(Path.cwd())
    ).resolve()
    companion = Path(
        opts.lock_file
        or os.environ.get(PREFIX + "LOCK_FILE")
        or root / "spago-purifier.lock.json"
    ).resolve()
    native_lock = Path(
        opts.native_lock
        or os.environ.get(PREFIX + "NATIVE_LOCK")
        or root / "spago.lock"
    ).resolve()
    return root, companion, native_lock


def validate(root, companion, native_lock):
    data = json.loads(companion.read_text())
    if data.get("schemaVersion") != 1 or data.get("purifier") != "spago":
        raise ValueError("unsupported lock format; run spago-purifier lock")
    if data["nativeLock"]["sha256"] != digest(native_lock.read_bytes()):
        raise ValueError("native lock changed; run spago-purifier lock")
    if set(manifests(root)) != set(data["manifests"]):
        raise ValueError("workspace manifests changed; run spago-purifier lock")
    for name, record in data["manifests"].items():
        path = Path(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or digest((root / path).read_bytes()) != record["sha256"]
        ):
            raise ValueError("Spago inputs changed; run spago-purifier lock")
    return data


def realize(root, companion, native_lock, target="environment"):
    result = run(
        [
            "nix",
            "build",
            "--impure",
            "--file",
            Path(__file__).resolve().parents[1] / "nix/realize.nix",
            "--no-link",
            "--print-out-paths",
            "--argstr",
            "project",
            root,
            "--argstr",
            "companion",
            companion,
            "--argstr",
            "nativeLock",
            native_lock,
            "--argstr",
            "target",
            target,
        ],
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    environment = Path(result)
    if not environment.is_dir() or len(result.splitlines()) != 1:
        raise ValueError("Nix did not return a single environment")
    roots = root / ".spago-purifier/gcroots"
    roots.mkdir(parents=True, exist_ok=True)
    run(
        [
            "nix-store",
            "--add-root",
            roots / environment.name,
            "--indirect",
            "--realise",
            environment,
        ],
        stdout=subprocess.DEVNULL,
    )
    sdk = os.environ.get(PREFIX + "SDK")
    if sdk:
        run(
            [
                "nix-store",
                "--add-root",
                roots / Path(sdk).name,
                "--indirect",
                "--realise",
                sdk,
            ],
            stdout=subprocess.DEVNULL,
        )
    return environment


def activated(root, companion, native_lock):
    validate(root, companion, native_lock)
    environment = realize(root, companion, native_lock)
    directory = root / ".spago-purifier/sessions" / environment.name
    env = prepare(root, environment, directory)
    env[PREFIX + "BASE_ENV"] = os.environ.get(
        PREFIX + "BASE_ENV",
        json.dumps(
            {k: os.environ.get(k) for k in ["XDG_CACHE_HOME", "XDG_CONFIG_HOME"]}
        ),
    )
    env.update(
        {
            PREFIX + "PROJECT": str(root),
            PREFIX + "LOCK_FILE": str(companion),
            PREFIX + "NATIVE_LOCK": str(native_lock),
        }
    )
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project")
    parser.add_argument("--lock-file")
    parser.add_argument("--native-lock")
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--compiler", action="store_true")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    opts = parser.parse_args()
    args = opts.args
    if args[:1] == ["--"]:
        args = args[1:]
    root, companion, native_lock = paths(opts)
    native = os.environ[PREFIX + "NATIVE"]
    if opts.compiler:
        compiler = os.environ[PREFIX + "PURS"]
        if not companion.exists():
            print(
                "spago-purifier: no lockfile; using ordinary impure PureScript resolution",
                file=sys.stderr,
            )
            os.execve(compiler, ["purs", *args], clean_env())
        if not args or args[0] in {"--help", "--version"}:
            os.execve(compiler, ["purs", *args], clean_env())
        env = activated(root, companion, native_lock)
        if args[:2] == ["ide", "server"]:
            if any(
                a == "--output-directory" or a.startswith("--output-directory=")
                for a in args
            ):
                raise ValueError("IDE output is managed by spago-purifier")
            args += [
                "--output-directory",
                env[PREFIX + "OUTPUT"],
                str(Path(env[PREFIX + "SOURCES"]) / "**/*.purs"),
                "src/**/*.purs",
                "test/**/*.purs",
            ]
        elif args[:1] == ["compile"]:
            if any(a in {"--output", "-o"} or a.startswith("--output=") for a in args):
                raise ValueError("compiler output is managed by spago-purifier")
            args += ["--output", env[PREFIX + "OUTPUT"]]
        os.execve(compiler, ["purs", *args], env)
    if opts.native:
        if not companion.exists():
            print(
                "spago-purifier: no lockfile; using ordinary impure Spago resolution",
                file=sys.stderr,
            )
            os.execve(native, ["spago", *args], clean_env())
        if not args or args[0] in {"--help", "--version", "-h", "-v"}:
            os.execve(native, ["spago", *args], clean_env())
        command = args[0]
        if command not in {
            "build",
            "test",
            "run",
            "bundle",
            "docs",
            "repl",
            "sources",
            "ls",
            "graph",
        }:
            raise ValueError("use spago-purifier lock for dependency changes")
        if any(
            a in {"--refresh", "--migrate", "--ensure-ranges", "--pure", "--output"}
            or a.startswith("--output=")
            for a in args
        ):
            raise ValueError(
                "locked resolution and output are managed by spago-purifier"
            )
        env = activated(root, companion, native_lock)
        if command in {"build", "test", "run", "bundle", "docs", "repl"}:
            args += ["--output", env[PREFIX + "OUTPUT"]]
        args += ["--offline"]
        os.execve(native, ["spago", *args], env)
    if not args:
        parser.error("choose lock, prefetch, shell, or release")
    command, rest = args[0], args[1:]
    if command == "lock":
        if rest not in ([], ["--update"]):
            raise ValueError("unexpected lock arguments")
        capture(
            root,
            companion,
            native_lock,
            native,
            {"spago": "1.0.5", "purescript": "0.15.16"},
            update=bool(rest),
        )
    elif command == "prefetch":
        validate(root, companion, native_lock)
        print(realize(root, companion, native_lock))
    elif command == "shell":
        env = activated(root, companion, native_lock)
        os.chdir(root)
        env["PATH"] = os.environ[PREFIX + "WRAPPER_BIN"] + os.pathsep + env["PATH"]
        if rest[:1] == ["--"]:
            rest = rest[1:]
        executable = rest[0] if rest else os.environ.get("SHELL", "/bin/sh")
        os.execvpe(executable, rest or [executable], env)
    elif command == "publish":
        publish = argparse.ArgumentParser()
        publish.add_argument("--repo", required=True)
        publish.add_argument("--tag", required=True)
        options = publish.parse_args(rest)
        validate(root, companion, native_lock)
        artifact = realize(root, companion, native_lock, "release") / "source.tar.gz"
        gh = os.environ.get(PREFIX + "GH", "gh")
        exists = (
            subprocess.run(
                [gh, "release", "view", options.tag, "--repo", options.repo],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0
        )
        run(
            [
                gh,
                "release",
                "upload",
                options.tag,
                artifact,
                "--repo",
                options.repo,
                "--clobber",
            ]
            if exists
            else [
                gh,
                "release",
                "create",
                options.tag,
                artifact,
                "--repo",
                options.repo,
                "--title",
                options.tag,
                "--notes",
                "Locked Spago project source release",
            ]
        )
    elif command == "release":
        validate(root, companion, native_lock)
        print(realize(root, companion, native_lock, "release"))
    else:
        raise ValueError("unknown command: " + command)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print("spago-purifier: " + str(error), file=sys.stderr)
        sys.exit(1)
