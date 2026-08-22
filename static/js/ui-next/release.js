export const MODULE_RELEASE = "wp03.1";

export class MixedReleaseError extends Error {
  constructor(moduleName, expected, received) {
    super(`Mixed interface release: ${moduleName}`);
    this.name = "MixedReleaseError";
    this.kind = "mixed-release";
    this.moduleName = String(moduleName || "unknown");
    this.expected = String(expected || "");
    this.received = String(received || "missing");
  }
}

export function assertReleaseModules(modules, expected = MODULE_RELEASE) {
  for (const [name, module] of Object.entries(modules || {})) {
    if (module?.MODULE_RELEASE !== expected) {
      throw new MixedReleaseError(name, expected, module?.MODULE_RELEASE);
    }
  }
  return modules;
}

export function releaseUrl(path, release = MODULE_RELEASE) {
  const url = new URL(path, import.meta.url);
  url.searchParams.set("release", release);
  return url.href;
}
