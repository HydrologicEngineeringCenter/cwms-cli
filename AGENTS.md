# Repository instructions

Guidance for coding agents working in `HydrologicEngineeringCenter/cwms-cli`.

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

## Terminal colors

- Use the shared helpers in `cwmscli.utils.colors` for user-facing terminal
  color. Prefer `colors.ok`, `colors.warn`, `colors.err`, and `colors.dim` for
  their semantic cases, or `colors.c(text, color, bright=...)` when a specific
  color is needed.
- Do not embed ANSI escape sequences or initialize Colorama in individual
  commands. Global logging setup owns Colorama initialization and calls
  `colors.set_enabled(...)` so `--no-color`, `--log-file`, and non-TTY output
  remain consistent.
- Keep the text meaningful without color. Color should clarify status or
  structure, not carry information that disappears when color is disabled.
- Reuse the existing conventions: green for success, yellow for warnings,
  red for errors, cyan or blue for identifiers and commands, and dim text for
  secondary detail.
- When testing colored output, cover the plain-text behavior first. Enable the
  shared color helper explicitly only in tests that need to assert escape codes,
  and restore its state afterward.
