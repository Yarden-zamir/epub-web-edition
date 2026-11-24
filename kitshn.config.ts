import { defineApp } from "kitshn";

export default defineApp({
  static: {
    // The build image has no uv. Each tool declares Python 3.15 and pinned dependencies in its PEP 723 header.
    build:
      "curl -LsSf https://astral.sh/uv/0.13.6/install.sh | sh && ~/.local/bin/uv run tools/build_epub.py && ~/.local/bin/uv run tools/build_web.py",
    output: "dist/web",
  },
  deploy: [
    { on: "push", branch: "main", name: "prod", startsIn: "Everyone" },
    { on: "pull_request", name: "pr-{pr}", ephemeral: true },
  ],
});
