/** Lazy Mermaid loading and rendering for completed transcript turns. */
let mermaidPromise = null;

// The 2.7 MB renderer loads only when a reply actually contains a diagram.
function loadMermaid() {
  if (window.mermaid) return Promise.resolve(window.mermaid);
  if (!mermaidPromise) {
    mermaidPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "/vendor/mermaid.min.js";
      script.onload = () => {
        try {
          window.mermaid.initialize({
            startOnLoad: false,
            securityLevel: "strict",
            theme: window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "neutral",
          });
          resolve(window.mermaid);
        } catch (error) {
          reject(error);
        }
      };
      script.onerror = () => reject(new Error("mermaid failed to load"));
      document.head.appendChild(script);
    });
  }
  return mermaidPromise;
}

/** Render every pending mermaid node under root once the library loads. */
export function renderDiagrams(root) {
  const nodes = root.querySelectorAll(".mermaid[data-code]");
  if (!nodes.length) return;
  loadMermaid().then((lib) => {
    nodes.forEach((node) => {
      const code = node.dataset.code;
      if (!code) return;
      delete node.dataset.code;
      const id = "mmd" + Math.random().toString(36).slice(2);
      Promise.resolve(lib.render(id, code)).then((result) => {
        node.innerHTML = result.svg;
        const svg = node.querySelector("svg");
        if (svg && svg.viewBox && svg.viewBox.baseVal && svg.viewBox.baseVal.width) {
          const box = svg.viewBox.baseVal;
          const width = Math.round(Math.min(Math.max(box.width, 260), 1100));
          svg.style.maxWidth = "none";
          svg.style.width = width + "px";
          svg.style.height = "auto";
        }
        node.classList.add("rendered");
      }).catch(() => {
        node.textContent = code;
        node.classList.add("failed");
      });
    });
  }).catch(() => {
    nodes.forEach((node) => {
      if (!node.dataset.code) return;
      node.textContent = node.dataset.code;
      delete node.dataset.code;
      node.classList.add("failed");
    });
  });
}

