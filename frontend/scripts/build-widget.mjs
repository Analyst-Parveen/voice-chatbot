// Build the standalone embeddable widget: public/widget.js
//
//   1. Compile the widget's Tailwind CSS to a string file.
//   2. Bundle embed.tsx (React + widget + inlined CSS) into a single IIFE that
//      exposes window.VoiceAI = { mount, unmount } and auto-mounts.
//
//   npm run build:widget

import { execSync } from "node:child_process";
import { build } from "esbuild";

console.log("[widget] compiling Tailwind CSS…");
execSync(
  "npx tailwindcss -i ./src/embed/widget.css -o ./src/embed/widget.generated.css --minify",
  { stdio: "inherit" },
);

console.log("[widget] bundling widget.js…");
await build({
  entryPoints: ["src/embed/embed.tsx"],
  bundle: true,
  format: "iife",
  globalName: "VoiceAI",
  outfile: "public/widget.js",
  minify: true,
  sourcemap: false,
  loader: { ".generated.css": "text" },
  define: { "process.env.NODE_ENV": '"production"' },
  // Browsers have no `process`/`global`; some deps still reference them.
  // Shim them so the bundle runs standalone on any page.
  banner: {
    js: "window.global=window.global||window;window.process=window.process||{env:{NODE_ENV:'production'}};",
  },
  jsx: "automatic",
  target: ["es2019"],
  logLevel: "info",
});

console.log("[widget] done → public/widget.js");
