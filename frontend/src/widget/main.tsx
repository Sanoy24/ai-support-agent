/**
 * Embeddable chat widget.
 *
 *   <script src="https://support.example.com/widget.js" defer
 *           data-title="Trailhead Support"
 *           data-color="#1f6b52"></script>
 *
 * The widget renders inside a Shadow DOM so the host page's CSS can't
 * change it and its CSS can't leak into the host page.
 */
import { createRoot } from "react-dom/client";

import { ChatWidget, type WidgetConfig } from "./ChatWidget";
import styles from "./widget.css?inline";

const DEFAULT_SUGGESTIONS = [
  "Where's my order?",
  "What's your return policy?",
  "How long does shipping take?",
  "Talk to a person",
];

function readConfig(script: HTMLScriptElement | null): WidgetConfig & { color?: string } {
  const data = script?.dataset ?? {};
  return {
    apiBase: data.api ?? (script?.src ? new URL(script.src).origin : window.location.origin),
    title: data.title ?? "Customer support",
    greeting:
      data.greeting ??
      "Hi! I can check on an order or answer questions about shipping, returns and our products.",
    suggestions: data.suggestions
      ? data.suggestions.split("|").map((s) => s.trim())
      : DEFAULT_SUGGESTIONS,
    color: data.color,
  };
}

/**
 * Browsers ignore `@property` rules inside a shadow root, and Tailwind uses
 * them for shadows, rings and transforms. Register them on the document
 * instead. They only declare custom property types, so they can't change
 * how the host page looks.
 */
function registerCssProperties(): void {
  const rules = styles.match(/@property\s+[\w-]+\s*\{[^}]*\}/g);
  if (!rules) return;
  const style = document.createElement("style");
  style.setAttribute("data-ai-support-agent-properties", "");
  style.textContent = rules.join("\n");
  document.head.appendChild(style);
}

function mount(config: WidgetConfig, color?: string): void {
  if (document.querySelector("[data-ai-support-agent]")) return;
  registerCssProperties();

  const host = document.createElement("div");
  host.setAttribute("data-ai-support-agent", "");
  if (color) host.style.setProperty("--asa-brand", color);
  document.body.appendChild(host);

  const shadow = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = styles;
  shadow.appendChild(style);
  const container = document.createElement("div");
  shadow.appendChild(container);

  createRoot(container).render(<ChatWidget config={config} />);
}

// document.currentScript is only available while this script first runs,
// so read the configuration now and mount once the page is ready.
const { color, ...config } = readConfig(document.currentScript as HTMLScriptElement | null);
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => mount(config, color));
} else {
  mount(config, color);
}
