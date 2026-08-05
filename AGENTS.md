# Repository instructions

- Never push to `origin` unless the user explicitly says they are ready for
  that push.
- Use JDK 21 or newer for new work that is not intended to run on T7 systems.
  On Windows, use JDK 21 at `C:\Program Files\Java\jdk-21`. On Linux or other
  Unix-like systems, select an installed JDK 21 or newer through `JAVA_HOME`.
  Use another Java version only when the target or task requires it.
- Use the `.devcontainer` Linux/Python 3.12 environment for changes involving
  time zones, paths, native libraries, HEC-DSS, or other operating-system-
  dependent behavior.
- Run the full dev-container test suite with
  `devcontainer exec --workspace-folder . poetry run pytest -q` when the dev
  container is available. The standard CI matrix separately covers Python 3.9
  and Python 3.12 package compatibility.
