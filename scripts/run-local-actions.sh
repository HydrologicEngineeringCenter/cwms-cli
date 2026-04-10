#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
EVENT_FILE="${REPO_ROOT}/.github/act/pull_request.json"
ACT_INSTALL_DIR="/usr/local/bin"
REPO_BIN_DIR="${REPO_ROOT}/bin"
BASH_PROFILE="${HOME}/.bash_profile"

usage() {
    cat <<'EOF'
Usage:
  scripts/run-local-actions.sh <target> [act args...]

Targets:
  cli-tests    Run .github/workflows/cli-tests.yml
  code-check   Run .github/workflows/code-check.yml
  docs         Run .github/workflows/docs.yml
  all          Run the three local-safe workflows above
  clean        Remove local act runner image and cache directories
  list         Show act workflows

Examples:
  scripts/run-local-actions.sh cli-tests
  scripts/run-local-actions.sh code-check --verbose
  scripts/run-local-actions.sh docs -j html
  scripts/run-local-actions.sh clean

EOF
}

run_act() {
    local workflow="$1"
    shift
    act pull_request -W "${workflow}" -e "${EVENT_FILE}" "$@"
}

cleanup_act_artifacts() {
    echo "Cleaning act Docker image and local caches..."

    cleanup_act_containers
    docker image rm -f catthehacker/ubuntu:act-latest >/dev/null 2>&1 || true
    rm -rf "${HOME}/.cache/act" "${HOME}/.cache/actcache"

    echo "Cleanup complete."
}

cleanup_act_containers() {
    local container_ids
    container_ids="$(docker ps -aq --filter "name=act-")"
    if [[ -n "${container_ids}" ]]; then
        echo "Removing leftover act containers..."
        # shellcheck disable=SC2086
        docker rm -f ${container_ids} >/dev/null 2>&1 || true
    fi
}

maybe_cleanup_after_run() {
    local exit_code=$?
    if [[ "${target:-}" != "clean" ]] && [[ "${target:-}" != "list" ]] && [[ -n "${target:-}" ]]; then
        cleanup_act_containers
    fi
    return "${exit_code}"
}

detect_os_name() {
    if [[ -r /etc/os-release ]]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        if [[ -n "${PRETTY_NAME:-}" ]]; then
            printf '%s\n' "${PRETTY_NAME}"
            return
        fi
        if [[ -n "${NAME:-}" ]]; then
            printf '%s\n' "${NAME}"
            return
        fi
    fi
    uname -s
}

ensure_path_in_profile() {
    local dir="$1"
    local path_line="export PATH=\"${dir}:\$PATH\""
    touch "${BASH_PROFILE}"
    if ! grep -Fqx "${path_line}" "${BASH_PROFILE}"; then
        {
            echo ""
            echo "# Added by cwms-cli local GitHub Actions helper"
            echo "${path_line}"
        } >> "${BASH_PROFILE}"
        echo "Added ${dir} to ${BASH_PROFILE}"
    fi
}

prompt_install_act() {
    local os_name="$1"
    local prompt
    prompt="act is not installed. Would you like to install act for ${os_name} into ${ACT_INSTALL_DIR}? [y/N] "
    read -r -p "${prompt}" reply
    case "${reply}" in
        y|Y|yes|YES)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

install_act() {
    local os_name="$1"

    if ! prompt_install_act "${os_name}"; then
        echo "act is required to run local GitHub Actions workflows." >&2
        exit 1
    fi

    echo "Installing act for ${os_name} into ${ACT_INSTALL_DIR}..."
    curl --proto '=https' --tlsv1.2 -sSf \
        https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash -s -- -b "${ACT_INSTALL_DIR}"

    hash -r

    if command -v act >/dev/null 2>&1; then
        echo "act installed successfully."
        return 0
    fi

    if [[ -x "${ACT_INSTALL_DIR}/act" ]]; then
        export PATH="${ACT_INSTALL_DIR}:$PATH"
        hash -r
        if command -v act >/dev/null 2>&1; then
            ensure_path_in_profile "${ACT_INSTALL_DIR}"
            echo "act installed successfully."
            return 0
        fi
    fi

    if [[ -x "${REPO_BIN_DIR}/act" ]]; then
        export PATH="${REPO_BIN_DIR}:$PATH"
        hash -r
        if command -v act >/dev/null 2>&1; then
            ensure_path_in_profile "${REPO_BIN_DIR}"
            echo "Found act in ${REPO_BIN_DIR} and added it to your PATH."
            echo "act installed successfully."
            return 0
        fi
    fi

    if [[ ! -x "${ACT_INSTALL_DIR}/act" ]] && [[ ! -x "${REPO_BIN_DIR}/act" ]] && ! command -v act >/dev/null 2>&1; then
        echo "act installation completed, but the binary was not found in ${ACT_INSTALL_DIR}, ${REPO_BIN_DIR}, or PATH." >&2
        echo "Check the install output above and verify where the binary was placed." >&2
        exit 1
    fi

    echo "act installed successfully."
}

target="${1:-}"

if [[ -z "${target}" ]]; then
    usage
    exit 1
fi

shift || true

cd "${REPO_ROOT}"

case "${target}" in
    -h|--help|help)
        usage
        exit 0
        ;;
    cli-tests|code-check|docs|all|list|clean)
        ;;
    *)
        echo "Unknown target: ${target}" >&2
        usage
        exit 1
        ;;
esac

if ! command -v act >/dev/null 2>&1; then
    install_act "$(detect_os_name)"
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Missing dependency: docker" >&2
    echo "act requires Docker to run these workflows locally." >&2
    exit 1
fi

trap maybe_cleanup_after_run EXIT

case "${target}" in
    cli-tests)
        run_act ".github/workflows/cli-tests.yml" "$@"
        ;;
    code-check)
        run_act ".github/workflows/code-check.yml" "$@"
        ;;
    docs)
        run_act ".github/workflows/docs.yml" "$@"
        ;;
    all)
        run_act ".github/workflows/cli-tests.yml" "$@"
        run_act ".github/workflows/code-check.yml" "$@"
        run_act ".github/workflows/docs.yml" "$@"
        ;;
    clean)
        cleanup_act_artifacts
        exit 0
        ;;
    list)
        act --list
        ;;
esac
