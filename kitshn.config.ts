import { defineApps } from "kitshn";

export default defineApps({
  // The synthetic sample edition. The key "app" keeps the card and address of the former one-app recipe (K-804).
  app: {
    static: {
      // The build image has no uv. Each tool declares Python 3.15 and pinned dependencies in its PEP 723 header.
      build:
        "curl -LsSf https://astral.sh/uv/0.13.6/install.sh | sh && ~/.local/bin/uv run tools/build_epub.py && ~/.local/bin/uv run tools/build_web.py",
      output: "dist/web",
    },
    // Deploy after the book, so the live book never waits for the sample (the CLI otherwise sorts apps by key).
    needs: { apps: ["book"] },
    deploy: [
      { on: "push", branch: "main", name: "prod", startsIn: "Everyone" },
    ],
  },
  // The Eli Raz edition. The "book" job of .github/workflows/kitshn.yml runs books/eli-raz/scripts/check.py
  // and passes this folder as an artifact.
  book: {
    static: { output: "books/eli-raz/dist/release/web" },
    deploy: [
      { on: "push", branch: "main", name: "prod", address: ["eli-raz.yarden-zamir.com"], startsIn: "Everyone" },
    ],
  },
});
