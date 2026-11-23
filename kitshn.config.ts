import { defineApp } from "kitshn";

export default defineApp({
  static: {
    // Stdlib-only Python. The web edition builds from the EPUB that the first step writes.
    build: "python3 tools/build_epub.py && python3 tools/build_web.py",
    output: "dist/web",
  },
  deploy: [
    { on: "push", branch: "main", name: "prod", startsIn: "Everyone" },
    { on: "pull_request", name: "pr-{pr}", ephemeral: true },
  ],
});
