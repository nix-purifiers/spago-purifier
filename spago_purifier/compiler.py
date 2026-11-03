# SPDX-License-Identifier: MIT
"""Normalize Nix source globs to the cache keys used by the sandbox build."""

import os
import glob
import sys

args = sys.argv[1:]
if os.environ.get("SPAGO_PURIFIER_SOURCES"):
    for i, arg in enumerate(args):
        if "/nix/store/" in arg and not arg.startswith("-"):
            args[i] = os.path.abspath(arg)
epoch = os.environ.get("SPAGO_PURIFIER_BUILD_EPOCH")
if epoch and args[:1] == ["compile"]:
    for argument in args[1:]:
        for filename in glob.glob(argument, recursive=True):
            if os.path.isfile(filename) and not os.path.realpath(filename).startswith(
                "/nix/store/"
            ):
                os.utime(filename, (int(epoch), int(epoch)))
os.execv(os.environ["SPAGO_PURIFIER_COMPILER"], ["purs", *args])
