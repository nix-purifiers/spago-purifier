# SPDX-License-Identifier: MIT
{
  buildNpmPackage,
  importNpmLock,
  fetchurl,
  lib,
  python3,
}:
let
  package = builtins.fromJSON (builtins.readFile ./package.json);
  packageLock = builtins.fromJSON (builtins.readFile ./package-lock.json);
in
buildNpmPackage {
  pname = "spago";
  version = "1.0.5";
  src = fetchurl {
    url = "https://registry.npmjs.org/spago/-/spago-1.0.5.tgz";
    hash = "sha512-TDkgSHEnVHdTuQKN0cq3SKlEZWjV4Y1/je6PljgUHhzBx6YYmGGnJFvDGV1vUqsOn5WVWMee2jM3G+pj6Mli3g==";
  };
  npmDeps = importNpmLock { inherit package packageLock; };
  npmConfigHook = importNpmLock.npmConfigHook;
  postPatch = ''
    cp ${./package.json} package.json
    cp ${./package-lock.json} package-lock.json
    python3 ${./scope-sdk.py} bin/bundle.js
  '';
  nativeBuildInputs = [ python3 ];
  npmFlags = [
    "--ignore-scripts"
    "--omit=dev"
  ];
  dontNpmBuild = true;
  doInstallCheck = true;
  installCheckPhase = "$out/bin/spago --version";
  meta = {
    description = "Spago with scoped immutable dependency source selection";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.bsd3;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
  };
}
