# AGENTS.md

Guidance for coding agents working in `HydrologicEngineeringCenter/cwms-cli`.

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
