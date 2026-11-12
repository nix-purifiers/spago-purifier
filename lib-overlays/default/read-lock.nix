# SPDX-License-Identifier: MIT
{ lib }:
{
  src,
  lockFile ? src + "/spago-purifier.lock.json",
  nativeLock ? src + "/spago.lock",
}:
let
  exists = builtins.pathExists lockFile && builtins.pathExists nativeLock;
  raw = if exists then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  native = if exists then builtins.fromJSON (builtins.readFile nativeLock) else { };
  relative =
    s:
    builtins.isString s
    && s != ""
    && !(lib.hasPrefix "/" s)
    && !(builtins.elem ".." (lib.splitString "/" s));
  sri = s: builtins.isString s && builtins.match "sha256-[A-Za-z0-9+/]{43}=" s != null;
  url = s: builtins.isString s && builtins.match "https://[^/@?#]+/[^@?#]+" s != null;
  manifests = data.manifests or { };
  discover =
    folder: prefix:
    let
      contents = builtins.readDir folder;
    in
    lib.concatMap (
      name:
      if
        lib.hasPrefix "." name
        || builtins.elem name [
          "node_modules"
          "output"
          "result"
        ]
      then
        [ ]
      else if contents.${name} == "directory" then
        discover (folder + "/${name}") (prefix + name + "/")
      else
        lib.optional (name == "spago.yaml") (prefix + name)
    ) (builtins.attrNames contents);

  manifestsOK =
    builtins.isAttrs manifests
    && manifests ? "spago.yaml"
    && builtins.sort builtins.lessThan (discover src "") == builtins.attrNames manifests
    && builtins.all (
      name:
      relative name
      && builtins.isAttrs manifests.${name}
      && builtins.isString (manifests.${name}.content or null)
      && builtins.pathExists (src + "/${name}")
      && builtins.hashFile "sha256" (src + "/${name}") == (manifests.${name}.sha256 or null)
      && builtins.hashString "sha256" manifests.${name}.content == manifests.${name}.sha256
    ) (builtins.attrNames manifests);
  entries = data.entries or [ ];
  entryOK =
    e:
    builtins.isAttrs e
    && relative (e.path or null)
    && sri (e.hash or null)
    && (
      if e ? git then
        builtins.isAttrs e.git
        && url (e.git.url or null)
        && builtins.match "[0-9a-f]{40}" (e.git.rev or "") != null
        && (e.git.submodules or null) == false
        && (e.git.leaveDotGit or null) == false
        && (e.git.commitObject or null) == null
      else
        url (e.url or null) && (e.mirrors or null) == [ ]
    );
  packages = native.packages or { };
  nativeOK =
    builtins.isAttrs native
    && builtins.isAttrs packages
    && builtins.all (
      name:
      builtins.match "[a-z][a-z0-9-]*" name != null
      && (
        let
          p = packages.${name};
        in
        builtins.isAttrs p
        && (p.type or null) == "registry"
        && builtins.isString (p.version or null)
        && builtins.match "[0-9]+\\.[0-9]+\\.[0-9]+" (p.version or "") != null
        && sri (p.integrity or null)
        && builtins.any (
          e:
          (e.path or null) == "archives/${name}-${p.version}.tar.gz"
          && (e.hash or null) == p.integrity
          && (e.url or null) == "https://packages.registry.purescript.org/${name}/${p.version}.tar.gz"
        ) entries
      )
    ) (builtins.attrNames packages);
  registries = data.registries or { };
  registriesOK =
    builtins.isAttrs registries
    &&
      builtins.all
        (
          name:
          builtins.isString (registries.${name} or null)
          && builtins.any (e: (e.path or null) == registries.${name} && e ? git) entries
        )
        [
          "registry"
          "registry-index"
        ];
  valid =
    exists
    && (data.schemaVersion or null) == 1
    && (data.purifier or null) == "spago"
    && manifestsOK
    && builtins.isList entries
    && builtins.all entryOK entries
    && nativeOK
    && registriesOK
    && builtins.isAttrs (data.nativeLock or null)
    && builtins.isAttrs (data.toolVersions or null)
    && builtins.length (lib.unique (map (e: e.path) entries)) == builtins.length entries
    && builtins.hashFile "sha256" nativeLock == (data.nativeLock.sha256 or null)
    && (data.toolVersions.spago or null) == "1.0.5"
    && (data.toolVersions.purescript or null) == "0.15.16";
in
{
  purifier = "spago";
  inherit entries data native;
  problems = lib.optional (
    !valid
  ) "Spago lock is missing, stale, or unsupported; run spago-purifier lock";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
