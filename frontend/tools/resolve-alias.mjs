import { pathToFileURL } from "node:url";
import path from "node:path";
import { existsSync } from "node:fs";

const SRC_DIR = path.resolve(new URL("../src", import.meta.url).pathname);

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith("@/")) {
    const rel = specifier.slice(2);
    let resolvedPath = path.join(SRC_DIR, rel);
    if (!path.extname(resolvedPath)) {
      if (existsSync(resolvedPath + ".ts")) {
        resolvedPath += ".ts";
      } else if (existsSync(resolvedPath + ".tsx")) {
        resolvedPath += ".tsx";
      } else if (existsSync(path.join(resolvedPath, "index.ts"))) {
        resolvedPath = path.join(resolvedPath, "index.ts");
      }
    }
    return nextResolve(pathToFileURL(resolvedPath).href, context);
  }
  return nextResolve(specifier, context);
}
