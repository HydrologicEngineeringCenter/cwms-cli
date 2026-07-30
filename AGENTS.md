# Repository instructions

- Never push to `origin` unless the user explicitly says they are ready for
  that push.
- Never name branches `codex` or use `codex` as a branch-name prefix.
- Use JDK 21 at `C:\Program Files\Java\jdk-21` unless a task specifically needs
  another Java version.
- Use the `.devcontainer` Linux/Python 3.12 environment for changes involving
  time zones, paths, native libraries, HEC-DSS, or other operating-system-
  dependent behavior.
- Run the full primary CI suite with
  `devcontainer exec --workspace-folder . poetry run pytest -q` when the dev
  container is available. Keep Python 3.9 compatibility considerations
  separate from the primary Python 3.12 environment.
