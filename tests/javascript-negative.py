#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Actual compiler/bundler controls for ownership and browser runtime boundaries."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="spago-javascript-reject-") as scratch:
    scratch = Path(scratch)
    cases = [
        ("dependency-entry", "Prelude", "entry module must belong", None),
        ("test-entry", "Test.Main", "module has no production source owner", None),
        ("missing-module", "Missing.Module", "corefn.json", None),
        ("node-runtime", "Projection.Node", "node:fs", None),
        ("asset-escape", "Projection.Answer", "asset is not a project source file", "escape.txt"),
    ]
    for label, module, expected, asset in cases:
        source = scratch / label
        shutil.copytree(repo / "tests/fixtures/browser42", source)
        if label == "node-runtime":
            (source / "src/Projection/Node.purs").write_text(
                "module Projection.Node (answer) where\nforeign import answer :: Int\n")
            (source / "src/Projection/Node.js").write_text(
                "import { readFileSync } from 'node:fs';\nexport const answer = readFileSync('/etc/hostname').length;\n")
        if asset:
            external = scratch / "external.txt"
            external.write_text("private external data")
            (source / asset).symlink_to(external)
        target = {"module": module, "assets": {"escape.txt": asset} if asset else {}}
        expression = f'''let f = builtins.getFlake {json.dumps(str(repo))};
          p = import f.inputs.nixpkgs {{ system = builtins.currentSystem; overlays = [ f.overlays.default ]; }};
          target = builtins.fromJSON {json.dumps(json.dumps(target))};
          in (p.spago-purifier.buildSpagoProject {{ src = builtins.path {{ path = builtins.toPath {json.dumps(str(source))}; name = "spago-negative-source"; }};
               javascriptTargets.site = target; }}).javascript.site'''
        result = subprocess.run(["nix", "build", "--impure", "--no-link", "-L", "--expr", expression],
                                capture_output=True, text=True, timeout=180)
        assert result.returncode != 0 and expected in result.stderr, (label, result.stdout, result.stderr)
        print(json.dumps({"case": label, "exitCode": result.returncode, "expectedDiagnostic": expected}), flush=True)
print("Native PureScript projection ownership and browser rejection controls passed")
