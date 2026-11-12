# SPDX-License-Identifier: MIT
{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  toolchain,
  nativeSpago,
  cacert,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "spago-purifier";
  version = "0.1.0";
  src = ../..;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/spago-purifier"
    cp -r spago_purifier nix lib-overlays pkgs "$out/lib/spago-purifier/"
    install -m755 bin/spago-purifier "$out/bin/spago-purifier"
    substituteInPlace "$out/lib/spago-purifier/nix/realize.nix" \
      --replace-fail '@nixpkgs@' '${nixpkgsSrc}' \
      --replace-fail '@purifier@' '${purifierSrc}'
    wrapProgram "$out/bin/spago-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
          toolchain
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set SPAGO_PURIFIER_NATIVE ${nativeSpago}/bin/spago \
      --set SPAGO_PURIFIER_PURS ${toolchain}/bin/purs \
      --set SPAGO_PURIFIER_SDK "$out" \
      --set SPAGO_PURIFIER_WRAPPER_BIN "$out/bin"
    makeWrapper "$out/bin/spago-purifier" "$out/bin/spago" --add-flags '--native --'
    makeWrapper "$out/bin/spago-purifier" "$out/bin/purs" --add-flags '--compiler --'
    for program in ${toolchain}/bin/*; do
      name=$(basename "$program")
      if [ ! -e "$out/bin/$name" ]; then ln -s "$program" "$out/bin/$name"; fi
    done
  '';
  meta = {
    description = "Native Spago workflow with locked Nix-resolved dependencies";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "spago-purifier";
  };
}
