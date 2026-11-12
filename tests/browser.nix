{ pkgs }:
let
  build = src: pkgs.spago-purifier.buildSpagoProject {
    inherit src;
    javascriptTargets.site = {
      module = "Projection.Answer";
      assets = { "index.html" = "web/index.html"; "style.css" = "web/style.css"; };
      webjar = { groupId = "org.webjars.purescript"; artifactId = "answer"; version = "1.0.0"; };
      npm = { name = "@fixture/purescript-answer"; version = "1.0.0"; };
    };
  };
  record = built: value: {
    inherit value;
    artifact = toString built.javascript.site;
    proof = toString built.javascript.site.proof;
    web = toString built.projections.site.web;
    maven = toString built.projections.site.maven;
    npm = toString built.projections.site.npm;
    npmCatalog = built.projections.site.npm.catalog;
  };
  reject = target: !(builtins.tryEval (pkgs.spago-purifier.buildSpagoProject {
    src = ./fixtures/browser42;
    javascriptTargets.site = target;
  }).packages.project.drvPath).success;
in
assert (pkgs.spago-purifier.buildSpagoProject { src = ./fixtures/browser42; }).projections == { };
assert reject { module = "../Main"; };
assert reject { module = "Main"; assets."main.mjs" = "web/style.css"; };
assert reject { module = "Main"; assets."../private.txt" = "private.txt"; };
assert reject { module = "Main"; webjar.artifactId = "../answer"; };
pkgs.runCommand "spago-browser-consumers" {
  nativeBuildInputs = [ pkgs.python3 pkgs.jdk pkgs.gradle pkgs.chromium pkgs.nodejs ];
  spec = builtins.toJSON {
    versions = [ (record (build ./fixtures/browser42) 42) (record (build ./fixtures/browser43) 43) ];
    chromium = "${pkgs.chromium}/bin/chromium";
    node = "${pkgs.nodejs}/bin/node";
    npm = "${pkgs.nodejs}/bin/npm";
  };
  passAsFile = [ "spec" ];
} ''
  export HOME="$TMPDIR/home" GRADLE_USER_HOME="$TMPDIR/gradle-home"
  mkdir -p "$HOME"
  python3 ${./browser}/proof.py "$specPath" "$out"
''
