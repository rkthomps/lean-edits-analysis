// Maps a view "kind" string to its render function. This is the composition point:
// the shell looks up registry[kind] and calls render(panel, view.data).
// A new visualization registers itself here by importing this module and calling
// register(kind, renderFn) at module load.

const registry = new Map();

export function register(kind, renderFn) {
  registry.set(kind, renderFn);
}

export function get(kind) {
  return registry.get(kind);
}
