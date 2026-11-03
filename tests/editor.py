#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

root, wrapper = map(lambda x: Path(x).resolve(), sys.argv[1:])
with socket.socket() as reserve:
    reserve.bind(("127.0.0.1", 0))
    port = reserve.getsockname()[1]
with (root / "ide.log").open("w") as log:
    process = subprocess.Popen(
        [
            wrapper,
            "--project",
            root,
            "shell",
            "--",
            "purs",
            "ide",
            "server",
            "--port",
            str(port),
            "--no-watch",
        ],
        stdout=log,
        stderr=log,
    )

    def request(command):
        with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
            connection.sendall(json.dumps(command).encode() + b"\n")
            line = connection.makefile("rb").readline()
            if command["command"] == "quit" and not line:
                return None
            response = json.loads(line)
            assert response["resultType"] == "success", response
            return response["result"]

    try:
        deadline = time.monotonic() + 60
        while True:
            try:
                request({"command": "cwd"})
                break
            except OSError:
                assert process.poll() is None, (root / "ide.log").read_text()
                if time.monotonic() > deadline:
                    raise TimeoutError("PureScript IDE did not start")
                time.sleep(0.2)
        request({"command": "load"})
        matches = request(
            {
                "command": "type",
                "params": {
                    "search": "log",
                    "filters": [
                        {"filter": "modules", "params": {"modules": ["Effect.Console"]}}
                    ],
                },
            }
        )
        assert matches, "IDE did not resolve native dependency log"
        definition = Path(matches[0]["definedAt"]["name"]).resolve()
        assert (
            str(definition).startswith("/nix/store/")
            and definition.name == "Console.purs"
        ), matches
        assert definition.is_file()
        request({"command": "quit"})
        assert process.wait(timeout=10) == 0
        print("IDE definition:", definition)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
