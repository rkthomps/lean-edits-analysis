// The single-page app shell: a sidebar of sessions and a main panel that composes
// the views of the selected session. Switches views in place (no page navigation),
// so the same logic moves cleanly into a VSCode webview later.

import { el, clear } from "./lib/dom.js";
import { loadManifest, loadSession } from "./data.js";
import * as registry from "./components/registry.js";

export async function mountShell(root) {
  const manifest = await loadManifest();
  const sessions = manifest.sessions || [];

  const sidebar = el("nav", { class: "shell-sidebar" });
  const main = el("main", { class: "shell-main" });
  root.appendChild(el("div", { class: "shell" }, [sidebar, main]));

  sidebar.appendChild(el("h1", { class: "shell-title", text: "Lean edits" }));
  const list = el("ul", { class: "shell-sessions" });
  sidebar.appendChild(list);

  if (sessions.length === 0) {
    main.appendChild(
      el("p", { class: "shell-empty", text: "No sessions found in data/manifest.json." }),
    );
    return;
  }

  let activeItem = null;
  function select(session, item) {
    if (activeItem) activeItem.classList.remove("is-active");
    activeItem = item;
    item.classList.add("is-active");
    showSession(main, session);
  }

  sessions.forEach((session, i) => {
    const item = el("li", {
      class: "shell-session",
      text: session.title || session.id,
      onClick: () => select(session, item),
    });
    list.appendChild(item);
    if (i === 0) queueMicrotask(() => select(session, item));
  });
}

async function showSession(main, session) {
  clear(main);
  main.appendChild(
    el("h2", { class: "shell-session-title", text: session.title || session.id }),
  );

  let data;
  try {
    data = await loadSession(session.file);
  } catch (err) {
    main.appendChild(el("p", { class: "shell-error", text: String(err.message || err) }));
    return;
  }

  const views = data.views || [];
  for (const view of views) {
    const panel = el("section", { class: "shell-view" });
    main.appendChild(panel);
    const renderFn = registry.get(view.kind);
    if (!renderFn) {
      panel.appendChild(
        el("p", { class: "shell-error", text: `No component registered for "${view.kind}".` }),
      );
      continue;
    }
    renderFn(panel, view.data, {});
  }
}
