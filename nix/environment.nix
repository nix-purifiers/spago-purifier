# SPDX-License-Identifier: MIT
{
  runCommand,
  fetchgit,
  python3,
  writeText,
  purifier,
  compiler,
}:
{
  lock,
  fetchers ? { },
}:
let
  checked = purifier.checkLock lock;
  sources = purifier.tree (
    {
      name = "locked-spago-sources";
      entries = checked.entries;
      inherit
        runCommand
        fetchgit
        python3
        writeText
        ;
    }
    // fetchers
  );
  metadata = writeText "spago-native-lock.json" (builtins.toJSON checked.native);
  registries = checked.data.registries;
in
runCommand "purified-spago-environment"
  {
    nativeBuildInputs = [
      compiler
      python3
    ];
  }
  ''
    mkdir -p $out/sources $out/output $out/registry
    python3 ${../spago_purifier/build.py} ${metadata} ${sources} "$out"
    ln -s ${sources}/${registries.registry} $out/registry/registry
    ln -s ${sources}/${registries.registry-index} $out/registry/registry-index
    ln -s ${sources} $out/capture
  ''
