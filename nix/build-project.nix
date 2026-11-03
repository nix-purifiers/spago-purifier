# SPDX-License-Identifier: MIT
{
  lib,
  runCommand,
  fetchgit,
  python3,
  writeText,
  purifier,
  compiler,
  nativeSpago,
  toolchain,
  gnutar,
  gzip,
  runtimeShell,
}:
{
  src,
  lockFile ? src + "/spago-purifier.lock.json",
  nativeLock ? src + "/spago.lock",
  fetchers ? { },
  nativeBuildInputs ? [ ],
  doCheck ? true,
  buildCommand ? "spago build",
  checkCommand ? "spago test",
  srcFilter ?
    path: type:
    !(builtins.elem (baseNameOf path) [
      ".git"
      ".spago"
      ".spago-purifier"
      "output"
      "__pycache__"
      "result"
    ])
    && !(lib.hasSuffix ".log" (baseNameOf path)),
}:
let
  lock = purifier.checkLock (
    import ./read-lock.nix { inherit lib; } { inherit src lockFile nativeLock; }
  );
  environment = import ./environment.nix {
    inherit
      runCommand
      fetchgit
      python3
      writeText
      purifier
      compiler
      ;
  } { inherit lock fetchers; };
  source = lib.cleanSourceWith {
    inherit src;
    filter = srcFilter;
  };
  build =
    runCommand "purified-spago-project"
      {
        nativeBuildInputs = [
          toolchain
          python3
        ]
        ++ nativeBuildInputs;
      }
      ''
          export HOME="$TMPDIR/home"
        export SOURCE_DATE_EPOCH=1 SPAGO_PURIFIER_BUILD_EPOCH=1
          mkdir -p "$HOME" work
          cp -pr ${source}/. work/
          chmod -R u+w work
          cp ${nativeLock} work/spago.lock
          cd work
          export PYTHONPATH=${../.}
          export SPAGO_PURIFIER_ENVIRONMENT=${environment}
          export SPAGO_PURIFIER_NATIVE=${nativeSpago}/bin/spago
          export SPAGO_PURIFIER_SHELL=${runtimeShell}
          export SPAGO_PURIFIER_SESSION="$TMPDIR/session"
          python3 ${../spago_purifier/sandbox.py} ${lib.escapeShellArg buildCommand} ${
            lib.escapeShellArg (if doCheck then checkCommand else "")
          }
          mkdir -p "$out"
          cp -r "$TMPDIR/session/output" "$out/output"
      '';
  release =
    runCommand "spago-project-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        mkdir -p "$out" source
        cp -r ${source}/. source/
        chmod -R u+w source
        cp ${lockFile} source/spago-purifier.lock.json
        cp ${nativeLock} source/spago.lock
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -czf "$out/source.tar.gz" -C source .
      '';
in
assert lock.problems == [ ];
{
  packages = {
    default = build;
    project = build;
    inherit environment;
  };
  tests = build;
  inherit release;
  fetches = lock.entries;
}
