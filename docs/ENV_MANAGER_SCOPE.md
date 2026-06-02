# Env Manager — Revised Scope

Working notes for the `cwms-cli env` feature (PR #209). Captures the
direction agreed in review: shift from keyring storage to plaintext config
files, drop the subshell-only activation model, add an `export` emitter,
and wire `load` into named environments. The user-facing value (named,
switchable envs) is unchanged; the storage and activation mechanisms
change.

## Goals

- Let users define named CDA environments once and reference them by name.
- Keep API keys out of project directories, shell history, and command lines.
- Work identically on Linux, macOS, Windows (cmd + PowerShell), and Solaris.
- Support `cwms-cli load --source-env X --target-env Y` as the headline payoff.
- No required rc-file edits, no required external services, no heavy deps.

## Non-goals

- Encrypted-at-rest secret storage. The threat model is "user account is the
  security boundary," matching `aws`, `gcloud`, `kubectl`, `gh`. Users who
  need a vault should use one (1Password CLI, Vault, AWS Secrets Manager)
  and feed values in via env vars.
- Mutating the parent shell's environment. Documented as an OS constraint;
  users get `export` for in-shell use and `activate` for subshell use.
- Per-project env files. Storage is per-user, in `~/.config/cwms-cli/envs/`.

## Storage

**Plaintext JSON, mode `0600`, one file per environment.**

```
~/.config/cwms-cli/envs/
  cwbi-prod.json
  cwbi-dev.json
  localhost.json
```

Windows: `%APPDATA%\cwms-cli\envs\`, ACL restricted to current user.

File schema:

```json
{
  "name": "cwbi-prod",
  "api_root": "https://cwms-data.usace.army.mil/cwms-data",
  "api_key": "abc123",
  "office": "SWT"
}
```

Rationale captured separately; short version: works everywhere including
Solaris and headless Linux, no `keyring`/`cryptography` dep tree, enumerable
by `os.listdir`, debuggable with `cat`/`chmod`, same model as every major
dev CLI. Encryption-at-rest on Linux keyring is mostly theater (any
same-user process can read an unlocked keyring); `0600` is the actual
boundary in practice.

## Commands

### `cwms-cli env setup <name>`

Create or update an env. Prompts for missing required fields when stdin
is a TTY; errors out otherwise (CI-friendly).

```
cwms-cli env setup cwbi-prod --api-key YOUR_KEY --office SWT
cwms-cli env setup cwbi-dev --api-root https://cwms-data-dev.example.mil/cwms-data --office SWT
cwms-cli env setup localhost --api-root http://localhost:8082/cwms-data --office DEV
```

- Writes `<envs_dir>/<name>.json` with `0600`.
- Default `api_root` for known names (`cwbi-prod` at minimum; add others
  if URLs are stable).
- Re-running with partial flags updates only the provided fields.

### `cwms-cli env show [<name>]`

List all envs, or show one. **Always redacts `api_key`** (prints
`has API key` / `no API key`). Safe to paste into tickets, screen-shares,
LLMs.

```
$ cwms-cli env show
Available environments:
  cwbi-prod
      API Root: https://cwms-data.usace.army.mil/cwms-data
      Office:   SWT
      Status:   has API key
  cwbi-dev
      API Root: https://cwms-data-dev.example.mil/cwms-data
      Office:   SWT
      Status:   no API key
```

### `cwms-cli env delete <name> [--yes]`

Remove the env file. Confirms unless `--yes`.

### `cwms-cli env export <name> [--format ...] [--output FILE] [--no-key] [--show-key]`

The high-leverage addition. Reads the env file and emits its values in
the requested syntax. **Default refuses to print `api_key` to a TTY**
(see Security below).

Formats:

| Flag                  | Output                                          | Use                                |
|-----------------------|-------------------------------------------------|------------------------------------|
| `--format dotenv` (default) | `KEY=value` lines                         | IDE dotenv plugins, docker-compose |
| `--format bash`       | `export KEY='value'`                            | `eval "$(... --format bash)"`      |
| `--format powershell` | `$env:KEY = 'value'`                            | `... \| Out-String \| Invoke-Expression` |
| `--format cmd`        | `set "KEY=value"`                               | cmd.exe                            |

Options:

- `--output FILE` writes directly to disk with `0600` perms (preferred over
  shell redirection — guarantees correct mode, no scrollback exposure, no
  quoting bugs).
- `--no-key` omits `api_key` (for templates / `.env.example`).
- `--show-key` overrides the TTY refusal.

Quoting must be correct per format (single-quote escaping in bash, doubled
single quotes in PowerShell, `^` escaping in cmd, `\` and `"` escaping in
dotenv). Get this right once.

### `cwms-cli env activate <name>` *(keep, with caveats documented)*

Spawns a subshell with env vars injected. Same as the current PR.

Documented limitations:
- Parent shell and any already-open IDE do **not** see the vars.
- On Windows, may launch `cmd.exe` even when invoked from PowerShell.
- For "I want my IDE to see this," point users at
  `cwms-cli env export <name> --output .env` instead.

This stays as the zero-friction path for users who just want a one-liner
that "works" without thinking about shell syntax.

## `load` integration

The actual payoff. Add to `cwms-cli load` (and any other multi-CDA
commands):

```
cwms-cli load timeseries --source-env cwbi-prod --target-env localhost
```

- `--source-env NAME` reads `<envs_dir>/<name>.json` and feeds its values
  into `--source-cda` and `--source-office`. CLI flags still win if both
  are passed.
- `--target-env NAME` mirrors for `--target-cda` and `--target-api-key`.
- Mutually exclusive with the explicit `--source-cda` / `--target-cda`
  flags (or override-with-warning — pick one and document).

This replaces today's juggling of `CDA_SOURCE_URL`, `CDA_TARGET_URL`,
`CDA_SOURCE_OFFICE`, `CDA_API_KEY` with two named references.

## Security posture

**Spell this out in user-facing docs.** What this feature does and doesn't
defend against:

| Threat                                | Defended? | How                                       |
|---------------------------------------|-----------|-------------------------------------------|
| Accidental `git add` of a key         | Yes       | Files live in `~/.config/`, not the repo  |
| Key pasted into LLM via `cat .env`    | Yes       | Users share `env show` output (redacted)  |
| Key visible in `ps` / shell history   | Yes       | Users reference env name, not flag value  |
| Key in tmux/terminal scrollback       | Mostly    | `export` refuses TTY by default; `--output FILE` skips shell entirely |
| Other user on shared box reading file | Yes (non-root) | `0600` perms, ACL on Windows         |
| Root / same-user process              | No        | Out of scope; matches `aws`/`gcloud`/`gh` |
| Disk theft on unencrypted drive       | No        | Use full-disk encryption                  |

`export --output FILE` is the recommended IDE setup path because it
guarantees `0600`, never touches scrollback, and emits a one-line
stderr reminder to `.gitignore` the output.

## Code changes

### Remove

- `cwmscli/utils/credentials.py` — entire file. Keyring helpers,
  `is_keyring_available`, the index management, the os-environ fallback
  reader.
- `keyring` dependency from `pyproject.toml`. Regenerate `poetry.lock`
  (drops ~544 lines: `keyring`, `cryptography`, `cffi`, `jeepney`,
  `SecretStorage`, `jaraco.*`, `backports.tarfile`, `pycparser`).
- `get_envs_dir()` migration block in `env.py` (`.env` files were never
  shipped — dead code).
- `tests/commands/test_env.py` keyring-mock fixtures.

### Add / rewrite

- `cwmscli/utils/env_store.py` — small module:
  - `envs_dir() -> Path` (XDG on Linux/macOS, `%APPDATA%` on Windows).
  - `load_env(name) -> dict | None`.
  - `save_env(name, dict) -> None` (writes `0600`; on Windows uses
    `os.open(..., 0o600)` + ACL helper or `pywin32` fallback).
  - `delete_env(name) -> bool`.
  - `list_envs() -> list[str]` (just `os.listdir` on the dir).
- `cwmscli/commands/env.py` — rewrite against `env_store`:
  - `setup`, `show`, `delete`, `activate` (subshell, unchanged behavior).
  - `export` (new) — formats, TTY-refusal, `--output`, `--no-key`.
- `cwmscli/load/root.py` — add `--source-env` / `--target-env` options
  that resolve via `load_env()` and populate the existing
  `--source-cda` / `--target-cda` / `--source-office` / `--target-api-key`.

### Tests

- `env_store`: round-trip save/load/delete/list, file mode is `0600`,
  Windows path branch, malformed JSON returns None.
- `env setup`: creates file with right perms; `--api-root` required for
  unknown names; partial update preserves other fields.
- `env show`: redacts key; lists multiple envs; handles empty dir.
- `env delete`: confirmation prompt; `--yes` skips it.
- `env export`:
  - Each format produces parseable output (shell out to `bash -c`,
    parse `KEY=value` for dotenv, etc.).
  - Quoting handles `'`, `"`, `$`, spaces, backslashes.
  - TTY refusal behavior (mock `isatty`).
  - `--output FILE` writes `0600`.
  - `--no-key` omits the key field.
- `load --source-env` / `--target-env`: populates the underlying flags;
  explicit flags override; missing env errors cleanly.

### Docs

- `docs/cli/env.rst` — rewrite to match the file-based model. Drop the
  keyring sections. Add the security table above. Document `export`
  prominently with the IDE setup recipe.
- `docs/cli/load.rst` (or wherever) — document `--source-env` /
  `--target-env`.
- `docs/ENV_MANAGER.md` — update or replace with this scope doc.

## Migration

No users yet (PR is draft, never merged). No migration needed. If keyring
data does exist on developer machines from testing, document a one-liner
to extract and rewrite as JSON, but don't ship migration code.

## Open questions

1. **Default env directory on Windows** — `%APPDATA%\cwms-cli\envs\` (per
   user roaming) or `%LOCALAPPDATA%` (per machine, no roaming)? Roaming
   matches `gh`; local matches `aws`.
2. **`--source-env` + explicit `--source-cda`**: hard error, or warn and
   let CLI flag win? The latter is more flexible for ad-hoc overrides.
3. **`activate` on Windows / PowerShell**: keep current `COMSPEC` fallback,
   or detect `PSModulePath` and prefer `pwsh`/`powershell`? Probably the
   detection — current behavior would drop a PowerShell user into cmd.exe.
4. **JSON vs dotenv on disk**: JSON is unambiguous and easy to extend;
   dotenv is one less format to parse since `export` already speaks it.
   Recommend JSON — env vars aren't the only thing we may want to store
   per-env (default time zones, output formats, etc.).

## Phasing

1. **Phase 1 (this PR, after revision):** storage + `setup`/`show`/`delete`/
   `activate`/`export`. No `load` integration yet.
2. **Phase 2 (follow-up PR):** `load --source-env` / `--target-env`. This
   is when the feature becomes obviously valuable to end users.
3. **Phase 3 (optional, only on demand):** opt-in keyring backend, or
   conda-style `init-shell` for in-place activation. Don't build either
   until a real user asks.
