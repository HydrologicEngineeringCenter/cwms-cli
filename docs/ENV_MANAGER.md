# Environment Manager

Simple environment management for CDA environments.

## Suggested Environments

**Pre-configured (have default URLs):**
- `cwbi-prod` - Production CWBI (https://cwms-data.usace.army.mil/cwms-data)
- `localhost` - Local development server (http://localhost:8082/cwms-data)

**Need --api-root:**
- `cwbi-dev` - Development CWBI
- `cwbi-test` - Test CWBI
- `onsite` - Local non-cloud server

## Quick Start

**1. Install shell helper (recommended):**
```bash
cwms-cli env install
```

**2. Setup environments:**
```bash
# Pre-configured environments (just add key/office)
cwms-cli env setup cwbi-prod --office SWT --api-key YOUR_KEY
cwms-cli env setup localhost --office SWT --api-key YOUR_KEY

# Custom environments (need --api-root)
cwms-cli env setup cwbi-dev --api-root https://dev.example.mil/cwms-data --office SWT --api-key YOUR_KEY
```

**3. Switch environments:**
```bash
cwms-env cwbi-prod
cwms-env localhost
```

**4. View all environments:**
```bash
cwms-cli env show
```

## Shell Integration Details

**Run once to install the `cwms-env` helper:**

```bash
cwms-cli env install
```

**Restart your terminal** (or run `source ~/.bashrc` / `source ~/.zshrc`) for the `cwms-env` command to work.

**What it does:**
- **Linux/Mac**: Adds function to `~/.bashrc` or `~/.zshrc`
- **Windows**: Creates `cwms-env.bat` in your PATH

**Manual setup (if needed):**
- **Linux/Mac**: Add to shell config: `cwms-env() { eval $(cwms-cli --quiet env activate "$@"); }`
- **Windows**: Create `cwms-env.bat`: `@echo off` / `for /f "delims=" %%i in ('cwms-cli --quiet env activate %*') do %%i`

## How It Works

**Config files:** `~/.config/cwms-cli/envs/<env>.env` (Linux/Mac) or `%APPDATA%\cwms-cli\envs\<env>.env` (Windows)

**Environment variables set:**
- `ENVIRONMENT` - Environment name
- `CDA_API_ROOT` - API root URL
- `CDA_API_KEY` - API key (if provided)
- `OFFICE` - Default office (if provided)

**Usage with other commands:**
```bash
cwms-env cwbi-prod          # Activate environment
cwms-cli blob list          # Uses environment variables
cwms-cli users list         # Uses environment variables

# Command flags override environment variables
cwms-cli blob list --api-root https://other.mil/cwms-data
```
