// Tiny DOM/SVG element builders. No framework, no dependencies.

const SVG_NS = "http://www.w3.org/2000/svg";

// Build an HTML element. attrs supports: class, text, style, on<Event> handlers,
// and any plain attribute. children is a node, string, or array of those.
export function el(tag, attrs = {}, children = []) {
  return build(document.createElement(tag), attrs, children);
}

// Build an SVG element (same attr/children rules as el).
export function svg(tag, attrs = {}, children = []) {
  return build(document.createElementNS(SVG_NS, tag), attrs, children);
}

function build(node, attrs, children) {
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") {
      node.addEventListener(k.slice(2).toLowerCase(), v);
    } else {
      node.setAttribute(k, String(v));
    }
  }
  const kids = Array.isArray(children) ? children : [children];
  for (const c of kids) {
    if (c == null) continue;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

// Remove all children from a node; returns the node.
export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}
