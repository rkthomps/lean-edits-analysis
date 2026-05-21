// Fetches the JSON the Python side emits into viz/data/.
// (Browsers block fetch() over file:// — run `python -m http.server` in viz/.)

export async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load ${url} (${res.status})`);
  return res.json();
}

export function loadManifest() {
  return fetchJSON("data/manifest.json");
}

export function loadSession(file) {
  return fetchJSON(`data/${file}`);
}
