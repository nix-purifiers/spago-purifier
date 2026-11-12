#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='spago-eval-') as temporary:
    root = Path(temporary) / 'project'
    shutil.copytree(REPO / 'examples/minimal', root, ignore=shutil.ignore_patterns('.spago', '.spago-purifier', 'output', '*.log'))
    path = root / 'spago-purifier.lock.json'
    original = json.loads(path.read_text())
    def evaluate():
        expression = f'let f=builtins.getFlake {json.dumps(str(REPO))}; in (import {REPO}/lib-overlays/default/read-lock.nix {{lib=f.inputs.nixpkgs.lib;}} {{src={root};}}).problems'
        return json.loads(subprocess.check_output(['nix','eval','--impure','--json','--expr',expression],text=True))
    assert evaluate() == []
    for mutation in [
        lambda d:d.update(schemaVersion=99),
        lambda d:d.update(entries={}),
        lambda d:d.update(manifests={}),
        lambda d:d.update(registries={}),
        lambda d:d['nativeLock'].update(sha256='bad'),
        lambda d:d['entries'][0].update(path='../escape'),
        lambda d:d['entries'][0].update(hash='bad'),
        lambda d:d['toolVersions'].update(purescript='old'),
        lambda d:d['entries'][-1]['git'].update(rev='main'),
    ]:
        data=copy.deepcopy(original)
        mutation(data)
        path.write_text(json.dumps(data))
        assert evaluate()
    path.write_text(json.dumps(original))
    manifest=root/'spago.yaml'
    manifest.write_text(manifest.read_text()+'\n')
    assert evaluate()
print('Malformed and stale Spago locks rejected before fetching')
