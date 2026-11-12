# SPDX-License-Identifier: MIT
{
  project,
  companion,
  nativeLock,
  target ? "environment",
}:
let
  pkgs = import (/. + "@nixpkgs@") { };
  purifier = import (/. + "@purifier@/nix/lib") { inherit (pkgs) lib; };
  compiler = pkgs.callPackage ./compiler.nix { };
  nativeSpago = pkgs.callPackage ./spago.nix { };
  toolchain = pkgs.callPackage ./toolchain.nix { inherit compiler nativeSpago; };
  args = {
    src = /. + project;
    lockFile = /. + companion;
    nativeLock = /. + nativeLock;
  };
  lock = import ../lib-overlays/default/read-lock.nix { inherit (pkgs) lib; } args;
in
if target == "environment" then
  pkgs.callPackage ../pkgs/build-spago-project/environment.nix { inherit purifier compiler; } { inherit lock; }
else if target == "release" then
  (pkgs.callPackage ../pkgs/build-spago-project/default.nix {
    inherit
      purifier
      compiler
      nativeSpago
      toolchain
      ;
  } args).release
else
  throw "spago-purifier: unknown output"
