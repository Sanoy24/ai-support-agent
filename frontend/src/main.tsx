import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./index.css";

function App() {
  return <p className="p-8 text-sm text-zinc-600">Frontend scaffold is working.</p>;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
