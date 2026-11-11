const root = document.documentElement;
const stored = (() => { try { return localStorage.getItem("doc-theme"); } catch { return null; } })();
if (stored) root.dataset.theme = stored;

const isDark = () => root.dataset.theme
  ? root.dataset.theme === "dark"
  : matchMedia("(prefers-color-scheme: dark)").matches;

const nodes = [...document.querySelectorAll("pre.mermaid")];
nodes.forEach(n => { n.dataset.src = n.textContent; });

async function draw() {
  const css = getComputedStyle(root);
  const v = name => css.getPropertyValue(name).trim();
  mermaid.initialize({
    startOnLoad: false,
    theme: "base",
    securityLevel: "strict",
    flowchart: { htmlLabels: true, curve: "basis", padding: 12, subGraphTitleMargin: { top: 10, bottom: 6 } },
    themeCSS: ".node rect { rx: 8px; ry: 8px; stroke-width: 1.5px; } .node polygon { stroke-width: 1.5px; }"
      + " .cluster rect { rx: 12px; ry: 12px; }"
      + " .edgePath path, .flowchart-link { stroke-width: 1.6px; }",
    themeVariables: {
      darkMode: isDark(),
      fontFamily: "Inter, system-ui, sans-serif",
      fontSize: "14px",
      background: v("--surface"),
      primaryColor: v("--node"),
      primaryTextColor: v("--ink"),
      primaryBorderColor: v("--accent"),
      secondaryColor: v("--accent-soft"),
      tertiaryColor: v("--paper"),
      lineColor: v("--accent"),
      textColor: v("--ink"),
      clusterBkg: v("--canvas"),
      clusterBorder: v("--tan-strong"),
      edgeLabelBackground: v("--surface"),
    },
  });
  // Emphasis classes: a figure marks its key boxes with `class X key` (dark) or `class X hot`
  // (terracotta). Any classDef for them in the Markdown is replaced by the current theme's colours.
  const themed = src => {
    if (!/^\s*(flowchart|graph)\b/.test(src)) return src;
    const kept = src.split("\n").filter(l => !/^\s*classDef\s+(key|hot)\b/.test(l)).join("\n");
    return kept
      + `\n  classDef key fill:${v("--block")},stroke:${v("--block")},color:${v("--on-block")}`
      + `\n  classDef hot fill:${v("--accent")},stroke:${v("--accent")},color:${v("--on-accent")}`;
  };
  nodes.forEach(n => {
    n.removeAttribute("data-processed"); n.innerHTML = ""; n.textContent = themed(n.dataset.src);
  });
  try { await mermaid.run({ nodes }); } catch (e) { console.error(e); }
}
draw();

document.querySelector(".theme")?.addEventListener("click", () => {
  root.dataset.theme = isDark() ? "light" : "dark";
  try { localStorage.setItem("doc-theme", root.dataset.theme); } catch {}
  draw();
});

const links = new Map([...document.querySelectorAll(".toc a")].map(a => [a.getAttribute("href").slice(1), a]));
const seen = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting && links.has(e.target.id)) {
      links.forEach(a => a.classList.remove("active"));
      links.get(e.target.id).classList.add("active");
    }
  });
}, { rootMargin: "-80px 0px -70% 0px" });
document.querySelectorAll("main h2[id], main h3[id]").forEach(h => seen.observe(h));
