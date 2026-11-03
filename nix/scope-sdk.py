# SPDX-License-Identifier: MIT
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
old = '      if (v2 instanceof RegistryVersion) {\n        return appendPath13(appendPath7(root2)(localCachePackagesPath))(print5(name4) + ("-" + print6(v2.value0)));\n'
new = '      if (v2 instanceof RegistryVersion) {\n        if (process.env.SPAGO_PURIFIER_SOURCES) {\n          return appendPath13(appendPath7(root2)(process.env.SPAGO_PURIFIER_SOURCES))(print5(name4) + ("-" + print6(v2.value0)));\n        }\n        return appendPath13(appendPath7(root2)(localCachePackagesPath))(print5(name4) + ("-" + print6(v2.value0)));\n'
assert text.count(old) == 1, "Spago SDK source selector changed"
path.write_text(text.replace(old, new))
text = path.read_text()
for function in ["appendPath7", "appendPath16"]:
    old = function + '(v2.rootPath)("spago.lock")'
    new = (
        function
        + '(v2.rootPath)(process.env.SPAGO_PURIFIER_NATIVE_LOCK || "spago.lock")'
    )
    assert text.count(old) == 1, "Spago native lock selector changed"
    text = text.replace(old, new)
path.write_text(text)
text = path.read_text()
old = "return bind42(ask4)(function(v1) {\n          if (v1.offline instanceof Offline && repoExists) {"
new = """return bind42(ask4)(function(v1) {
          if (process.env.SPAGO_PURIFIER_PINNED_REGISTRIES && repoExists &&
              (v2.git === "https://github.com/purescript/registry.git" ||
               v2.git === "https://github.com/purescript/registry-index.git")) {
            return pure53(new Right(unit));
          }
          if (v1.offline instanceof Offline && repoExists) {"""
assert text.count(old) == 1, "Spago registry provider changed"
path.write_text(text.replace(old, new))
text = path.read_text()
old = """runSpago9(buildEnv)(run8({
                    depsOnly: false,
                    pursArgs: [],
                    jsonErrors: false
                  }))"""
new = """(process.env.SPAGO_PURIFIER_CAPTURE_ONLY ? pure92(true) : runSpago9(buildEnv)(run8({
                    depsOnly: false,
                    pursArgs: [],
                    jsonErrors: false
                  })))"""
assert text.count(old) == 1, "Spago upgrade build step changed"
text = text.replace(old, new)
old = 'logInfo16("Building with upgraded dependencies to verify compatibility...")'
new = 'logInfo16(process.env.SPAGO_PURIFIER_CAPTURE_ONLY ? "Capturing upgraded sources; compilation is deferred to Nix." : "Building with upgraded dependencies to verify compatibility...")'
assert text.count(old) == 1
path.write_text(text.replace(old, new))
