// Diff viewer page: reads URL params, fetches /api/diff/..., renders before/after panels.

import { el } from "./lib/dom.js";

const CONTEXT = 15;

function parseParams() {
  const p = new URLSearchParams(window.location.search);
  return {
    owner: p.get("owner") || "",
    repo: p.get("repo") || "",
    sha: p.get("sha") || "",
    file: p.get("file") || "",
    editIndex: Number(p.get("edit_index") ?? "0"),
  };
}

function formatTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

// Build a sparse view of lines: only include changed lines ± CONTEXT.
// Returns an array of { lineNo (1-based), text, kind: "normal"|"removed"|"added"|"ellipsis" }.
function buildView(lines, changedSet) {
  if (changedSet.size === 0) {
    // No changes — show all lines
    return lines.map((text, i) => ({ lineNo: i + 1, text, kind: "normal" }));
  }

  const kept = new Set();
  for (const ln of changedSet) {
    for (let d = -CONTEXT; d <= CONTEXT; d++) {
      const n = ln + d;
      if (n >= 0 && n < lines.length) kept.add(n);
    }
  }

  const result = [];
  let prev = -1;
  for (const idx of [...kept].sort((a, b) => a - b)) {
    if (prev !== -1 && idx > prev + 1) {
      result.push({ lineNo: null, text: "…", kind: "ellipsis" });
    }
    result.push({
      lineNo: idx + 1,
      text: lines[idx],
      kind: changedSet.has(idx) ? "removed" : "normal",
    });
    prev = idx;
  }
  return result;
}

// Given before/after text and the list of ContentChange objects, compute which
// line indices (0-based) are "removed" in before and "added" in after.
function diffLines(before, after) {
  const bLines = before.split("\n");
  const aLines = after.split("\n");

  // Find the range of changed lines by comparing both arrays.
  let first = 0;
  const minLen = Math.min(bLines.length, aLines.length);
  while (first < minLen && bLines[first] === aLines[first]) first++;

  let lastB = bLines.length - 1;
  let lastA = aLines.length - 1;
  while (lastB > first && lastA > first && bLines[lastB] === aLines[lastA]) {
    lastB--;
    lastA--;
  }

  const removedSet = new Set();
  for (let i = first; i <= lastB; i++) removedSet.add(i);

  const addedSet = new Set();
  for (let i = first; i <= lastA; i++) addedSet.add(i);

  return { bLines, aLines, removedSet, addedSet };
}

function renderPanel(lines, changedSet, side) {
  const panel = el("div", { class: "dp-panel" });
  const headerClass = `dp-panel-header ${side === "before" ? "is-before" : "is-after"}`;
  panel.appendChild(el("div", { class: headerClass, text: side === "before" ? "Before" : "After" }));

  const pre = document.createElement("pre");
  pre.className = "dp-code";
  const table = document.createElement("table");
  table.className = "dp-table";

  const view = buildView(lines, changedSet);
  for (const row of view) {
    const tr = document.createElement("tr");
    if (row.kind === "ellipsis") {
      tr.className = "dp-ellipsis";
      const td = document.createElement("td");
      td.colSpan = 2;
      td.textContent = row.text;
      tr.appendChild(td);
    } else {
      tr.className = row.kind === "removed" ? "dp-removed" : row.kind === "added" ? "dp-added" : "";
      const tdNum = document.createElement("td");
      tdNum.className = "dp-td-num";
      tdNum.textContent = String(row.lineNo);
      const tdText = document.createElement("td");
      tdText.className = "dp-td-text";
      tdText.textContent = row.text;
      tr.appendChild(tdNum);
      tr.appendChild(tdText);
    }
    table.appendChild(tr);
  }

  pre.appendChild(table);
  panel.appendChild(pre);
  return panel;
}

async function mount(root) {
  const params = parseParams();
  const page = el("div", { class: "dp-page" });
  root.appendChild(page);

  const header = el("div", { class: "dp-header" });
  page.appendChild(header);
  header.appendChild(el("h1", {
    class: "dp-header-title",
    text: params.file || "Edit diff",
  }));
  const meta = el("div", { class: "dp-header-meta" });
  meta.textContent = `${params.owner}/${params.repo} · ${params.sha.slice(0, 7)} · edit #${params.editIndex}`;
  header.appendChild(meta);

  const body = el("div", { class: "dp-body" });
  page.appendChild(body);
  body.appendChild(el("p", { class: "dp-loading", text: "Loading diff…" }));

  const { owner, repo, sha, file, editIndex } = params;
  const url =
    `/api/diff/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/${encodeURIComponent(sha)}` +
    `?file=${encodeURIComponent(file)}&edit_index=${editIndex}`;

  let data;
  try {
    const resp = await fetch(url);
    if (!resp.ok) {
      const detail = await resp.text().catch(() => resp.statusText);
      throw new Error(`${resp.status}: ${detail}`);
    }
    data = await resp.json();
  } catch (err) {
    body.innerHTML = "";
    body.appendChild(el("p", { class: "dp-error", text: `Failed to load diff: ${err.message}` }));
    return;
  }

  // Update header with actual timestamp
  meta.textContent =
    `${owner}/${repo} · ${sha.slice(0, 7)} · edit #${editIndex} · ${formatTime(data.time)}`;

  const { bLines, aLines, removedSet, addedSet } = diffLines(data.before, data.after);

  body.innerHTML = "";
  body.className = "dp-panels";
  body.appendChild(renderPanel(bLines, removedSet, "before"));
  body.appendChild(renderPanel(aLines, addedSet, "after"));
}

mount(document.getElementById("app"));
