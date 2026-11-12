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
  esbuild,
  nodejs,
}:
{
  src,
  lockFile ? src + "/spago-purifier.lock.json",
  nativeLock ? src + "/spago.lock",
  fetchers ? { },
  nativeBuildInputs ? [ ],
  javascriptTargets ? { },
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
  relative = path:
    builtins.isString path && path != "" && !(lib.hasPrefix "/" path)
    && !(lib.hasInfix "\\" path)
    && builtins.all (part: part != "" && part != "." && part != "..") (lib.splitString "/" path);
  coordinate = value:
    builtins.isString value && builtins.match "[A-Za-z0-9_][A-Za-z0-9_.-]*" value != null;
  validTarget = target:
    builtins.isAttrs target
    && builtins.all (key: builtins.elem key [ "module" "assets" "webjar" "npm" ]) (builtins.attrNames target)
    && builtins.isString (target.module or null)
    && builtins.match "[A-Z][A-Za-z0-9_]*(\\.[A-Z][A-Za-z0-9_]*)*" target.module != null
    && builtins.isAttrs (target.assets or { })
    && builtins.all (path: relative path && path != "main.mjs" && relative target.assets.${path})
      (builtins.attrNames (target.assets or { }))
    && ((target.webjar or null) == null || (
      builtins.isAttrs target.webjar
      && builtins.all (key: builtins.elem key [ "groupId" "artifactId" "version" ]) (builtins.attrNames target.webjar)
      && coordinate (target.webjar.groupId or "org.webjars.npm")
      && coordinate (target.webjar.artifactId or null)
      && coordinate (target.webjar.version or null)
    ))
    && ((target.npm or null) == null || (
      builtins.isAttrs target.npm
      && builtins.attrNames target.npm == [ "name" "version" ]
      && builtins.isString (target.npm.name or null)
      && builtins.match "(@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*" target.npm.name != null
      && builtins.isString (target.npm.version or null)
      && builtins.match "[0-9]+\\.[0-9]+\\.[0-9]+(-[A-Za-z0-9.-]+)?" target.npm.version != null
    ));
  validTargets = builtins.isAttrs javascriptTargets
    && builtins.all (name: coordinate name && validTarget javascriptTargets.${name})
      (builtins.attrNames javascriptTargets);
  specs = lib.mapAttrs (name: target: writeText "spago-javascript-${name}.json"
    (builtins.toJSON { inherit (target) module; assets = target.assets or { }; })) javascriptTargets;
  javascriptBuild = lib.concatMapStringsSep "\n" (name: ''
    python3 ${./javascript-output.py} "$PWD" "$TMPDIR/session/output" ${environment} ${specs.${name}} \
      "$out/javascript/${name}" "$out/javascript-proof/${name}" ${esbuild}/bin/esbuild ${compiler}/bin/purs
  '') (builtins.attrNames javascriptTargets);
  rawProject =
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
          ${javascriptBuild}
      '';
  javascript = lib.mapAttrs (name: target:
    let
      artifact = runCommand "spago-javascript-${name}" { outputs = [ "out" "proof" ]; } ''
        mkdir -p "$out" "$proof"
        cp -r ${rawProject}/javascript/${name}/. "$out/"
        cp -r ${rawProject}/javascript-proof/${name}/. "$proof/"
      '';
      npmSpec = writeText "spago-npm-${name}.json" (builtins.toJSON target.npm);
      npmArchive = runCommand "spago-npm-${name}" { nativeBuildInputs = [ python3 nodejs ]; } ''
        export HOME="$TMPDIR/home" npm_config_cache="$TMPDIR/npm-cache"
        mkdir -p "$HOME"
        python3 ${./npm-output.py} ${artifact} ${npmSpec} "$out" ${nodejs}/bin/npm
      '';
    in artifact // lib.optionalAttrs ((target.npm or null) != null) { inherit npmArchive; } // {
      projections = (purifier.resourceProjections {
        producer = artifact;
        roots."." = ".";
        inherit runCommand python3;
      }) // lib.optionalAttrs ((target.webjar or null) != null) (purifier.webjarProjections (
        target.webjar // { producer = artifact; assets = artifact; inherit runCommand python3; }
      )) // lib.optionalAttrs ((target.npm or null) != null) (purifier.npmProjections {
        producer = artifact;
        graph = "${npmArchive}/graph.json";
        archives = "${npmArchive}/archives";
        inherit runCommand python3;
      });
    }
  ) javascriptTargets;
  projections = lib.mapAttrs (_: artifact: artifact.projections) javascript;
  build = rawProject // { inherit projections; };
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
assert lib.assertMsg validTargets
  "spago-purifier: javascriptTargets requires an owned PureScript production module, relative public assets and optional WebJar coordinates";
{
  packages = {
    default = build;
    project = build;
    inherit environment;
  } // lib.mapAttrs' (name: artifact: lib.nameValuePair "javascript-${name}" artifact) javascript;
  inherit javascript projections;
  tests = build;
  inherit release;
  fetches = lock.entries;
}
