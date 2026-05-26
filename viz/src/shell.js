// The single-page app shell: a sidebar of sessions and a main panel that composes
// the views of the selected session. Switches views in place (no page navigation),
// so the same logic moves cleanly into a VSCode webview later.

import { el, clear } from "./lib/dom.js";
import { loadManifest, loadSession } from "./data.js";
import * as registry from "./components/registry.js";

function formatDate(isoString) {
  if (!isoString) return "";
  const d = new Date(isoString);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export async function mountShell(root) {
  const manifest = await loadManifest();
  const sessions = manifest.sessions || [];

  const sidebar = el("nav", { class: "shell-sidebar" });
  const main = el("main", { class: "shell-main" });
  root.appendChild(el("div", { class: "shell" }, [sidebar, main]));

  sidebar.appendChild(el("h1", { class: "shell-title", text: "Lean edits" }));

  if (sessions.length === 0) {
    main.appendChild(
      el("p", { class: "shell-empty", text: "No sessions found in data/manifest.json." }),
    );
    return;
  }

  // Group sessions by owner → repo
  const ownerMap = new Map();
  for (const session of sessions) {
    if (!ownerMap.has(session.owner)) ownerMap.set(session.owner, new Map());
    const repoMap = ownerMap.get(session.owner);
    if (!repoMap.has(session.repo)) repoMap.set(session.repo, []);
    repoMap.get(session.repo).push(session);
  }

  // Sort owners descending by total edits
  const owners = [...ownerMap.entries()].map(([owner, repoMap]) => {
    const totalEdits = [...repoMap.values()]
      .flat()
      .reduce((sum, s) => sum + (s.num_edits || 0), 0);
    return { owner, repoMap, totalEdits };
  });
  owners.sort((a, b) => b.totalEdits - a.totalEdits);

  let activeItem = null;
  function select(session, item) {
    if (activeItem) activeItem.classList.remove("is-active");
    activeItem = item;
    item.classList.add("is-active");
    main.scrollTop = 0;
    showSession(main, session);
  }

  const ownerList = el("ul", { class: "shell-owners" });
  sidebar.appendChild(ownerList);

  let firstSession = null;
  let firstItem = null;
  let firstOwnerItem = null;
  let firstRepoItem = null;

  for (const { owner, repoMap, totalEdits } of owners) {
    const ownerItem = el("li", { class: "shell-owner" });
    ownerList.appendChild(ownerItem);

    const ownerHeader = el("div", { class: "shell-owner-header", onClick: () => ownerItem.classList.toggle("is-open") }, [
      el("span", { class: "shell-toggle-arrow", text: "▶" }),
      el("span", { class: "shell-owner-name", text: owner }),
      el("span", { class: "shell-owner-meta", text: `${totalEdits} edits` }),
    ]);
    ownerItem.appendChild(ownerHeader);

    // Sort repos descending by last_modified
    const repos = [...repoMap.entries()].map(([repo, commits]) => {
      const lastMod = commits.reduce(
        (latest, s) => (!latest || s.last_modified > latest ? s.last_modified : latest),
        null,
      );
      const repoEdits = commits.reduce((sum, s) => sum + (s.num_edits || 0), 0);
      return { repo, commits, lastMod, repoEdits };
    });
    repos.sort((a, b) => (b.lastMod || "").localeCompare(a.lastMod || ""));

    const repoList = el("ul", { class: "shell-repos" });
    ownerItem.appendChild(repoList);

    for (const { repo, commits, lastMod, repoEdits } of repos) {
      const repoItem = el("li", { class: "shell-repo" });
      repoList.appendChild(repoItem);

      const repoHeader = el("div", { class: "shell-repo-header", onClick: () => repoItem.classList.toggle("is-open") }, [
        el("span", { class: "shell-toggle-arrow", text: "▶" }),
        el("span", { class: "shell-repo-name", text: repo }),
        el("span", {
          class: "shell-repo-meta",
          text: `${repoEdits} edits · ${formatDate(lastMod)}`,
        }),
      ]);
      repoItem.appendChild(repoHeader);

      // Sort commits descending by last_modified
      const sortedCommits = [...commits].sort((a, b) =>
        (b.last_modified || "").localeCompare(a.last_modified || ""),
      );

      const commitList = el("ul", { class: "shell-commits" });
      repoItem.appendChild(commitList);

      for (const session of sortedCommits) {
        const item = el("li", { class: "shell-commit", onClick: () => select(session, item) }, [
          el("span", { class: "shell-commit-sha", text: session.sha.slice(0, 7) }),
          el("span", {
            class: "shell-commit-meta",
            text: `${session.num_edits || 0} edits · ${formatDate(session.last_modified)}`,
          }),
        ]);
        commitList.appendChild(item);

        if (firstSession === null) {
          firstSession = session;
          firstItem = item;
          firstOwnerItem = ownerItem;
          firstRepoItem = repoItem;
        }
      }
    }
  }

  if (firstSession !== null) {
    firstOwnerItem.classList.add("is-open");
    firstRepoItem.classList.add("is-open");
    queueMicrotask(() => select(firstSession, firstItem));
  }
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
