import { defineApp } from "kitshn";

export default defineApp({
  // The build job of .github/workflows/kitshn.yml runs scripts/build_release.py and passes this folder as an artifact.
  static: { output: "dist/release/web" },
  deploy: [{ on: "push", branch: "main", name: "prod", startsIn: "Everyone" }],
});
