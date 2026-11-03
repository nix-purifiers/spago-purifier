# SPDX-License-Identifier: MIT
{
  symlinkJoin,
  makeWrapper,
  python3,
  compiler,
  nativeSpago,
  nodejs,
  git,
  esbuild,
}:
symlinkJoin {
  name = "spago-purifier-toolchain";
  paths = [
    nativeSpago
    nodejs
    git
    esbuild
  ];
  nativeBuildInputs = [ makeWrapper ];
  postBuild = ''
    mkdir -p $out/lib/spago-purifier
    cp ${../spago_purifier/compiler.py} $out/lib/spago-purifier/compiler.py
    makeWrapper ${python3}/bin/python3 $out/bin/purs \
      --add-flags "$out/lib/spago-purifier/compiler.py" \
      --set SPAGO_PURIFIER_COMPILER ${compiler}/bin/purs
  '';
}
