# SPDX-License-Identifier: MIT
{
  description = "Locked, Nix-resolved dependencies for Spago";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        spago-purifier = final.lib.makeScope final.newScope (scope: {
          compiler = scope.callPackage ./nix/compiler.nix { };
          nativeSpago = scope.callPackage ./nix/spago.nix { };
          toolchain = scope.callPackage ./nix/toolchain.nix { };
          cli = scope.callPackage ./nix/cli.nix {
            nixpkgsSrc = nixpkgs;
            purifierSrc = purifier;
          };
          buildSpagoProject = scope.callPackage ./nix/build-project.nix {
            purifier = import (purifier + "/nix/lib") { inherit (final) lib; };
          };
        });
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        default = (pkgsFor system).spago-purifier.cli;
        cli = self.packages.${system}.default;
        native = (pkgsFor system).spago-purifier.nativeSpago;
        compiler = (pkgsFor system).spago-purifier.compiler;
      });
      lib.spago-purifier.readLock = import ./nix/read-lock.nix { lib = nixpkgs.lib; };
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/spago-purifier";
          meta.description = "Lock and prefetch Spago dependencies";
        };
      });
      checks = forAll (
        system:
        let
          project = (pkgsFor system).spago-purifier.buildSpagoProject { src = ./examples/minimal; };
        in
        {
          environment = project.packages.environment;
          project = project.packages.default;
          release = project.release;
          cli = self.packages.${system}.default;
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
