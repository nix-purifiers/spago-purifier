# SPDX-License-Identifier: MIT
{
  purescript,
  fetchurl,
  stdenv,
}:
let
  sources = {
    x86_64-linux = {
      name = "linux64";
      hash = "sha256-RNqe+4pOFFGej9U1Csw3ekuYHkI1GnjFPp+EBFvzjiI=";
    };
    aarch64-linux = {
      name = "linux-arm64";
      hash = "sha256-uNFTxcbg2MlhipCCTrNCtYGOFKkrC2zf91PZs1OpJ/M=";
    };
  };
  source = sources.${stdenv.hostPlatform.system};
in
purescript.overrideAttrs (old: {
  version = "0.15.16";
  installPhase = ''
    runHook preInstall
    install -Dm555 purs $out/bin/purs
    $out/bin/purs --version
    $out/bin/purs --bash-completion-script $out/bin/purs > purs.bash
    mkdir -p $out/share/bash-completion/completions
    install -m444 purs.bash $out/share/bash-completion/completions/purs
    runHook postInstall
  '';

  src = fetchurl {
    url = "https://github.com/purescript/purescript/releases/download/v0.15.16/${source.name}.tar.gz";
    inherit (source) hash;
  };
})
