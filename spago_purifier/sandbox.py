# SPDX-License-Identifier: MIT
import os
from pathlib import Path
import subprocess
import sys
from spago_purifier.session import prepare

root = Path.cwd()
env = prepare(
    root,
    Path(os.environ["SPAGO_PURIFIER_ENVIRONMENT"]),
    Path(os.environ["SPAGO_PURIFIER_SESSION"]),
)
# Custom build commands retain a normal `spago` command in the sandbox.
wrapper = Path(os.environ["TMPDIR"]) / "sandbox-bin"
wrapper.mkdir()
script = wrapper / "spago"
script.write_text(
    "#!"
    + os.environ["SPAGO_PURIFIER_SHELL"]
    + "\nexec "
    + os.environ["SPAGO_PURIFIER_NATIVE"]
    + ' "$@" --offline --output "$SPAGO_PURIFIER_OUTPUT"\n'
)
script.chmod(0o755)
env["PATH"] = str(wrapper) + os.pathsep + env["PATH"]
for command in sys.argv[1:]:
    if command:
        subprocess.run(
            [os.environ["SPAGO_PURIFIER_SHELL"], "-eu", "-c", command],
            env=env,
            check=True,
        )
