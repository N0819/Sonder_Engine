export const MODULE_RELEASE = "wp02.1";

export function installV1Adapter(adapter) {
  window.Sonder = adapter;
  return () => {
    if (window.Sonder === adapter) delete window.Sonder;
  };
}
