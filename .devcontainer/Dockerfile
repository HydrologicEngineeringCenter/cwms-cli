FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

ARG POETRY_VERSION=2.0.1

ENV TZ=Etc/UTC \
    POETRY_HOME=/opt/poetry \
    VIRTUAL_ENV=/home/vscode/.venv \
    POETRY_VIRTUALENVS_CREATE=false
ENV PATH="${VIRTUAL_ENV}/bin:${POETRY_HOME}/bin:${PATH}"

RUN python -m venv "${POETRY_HOME}" \
    && "${POETRY_HOME}/bin/python" -m pip install --no-cache-dir \
        "poetry==${POETRY_VERSION}" \
    && python -m venv "${VIRTUAL_ENV}" \
    && chown -R vscode:vscode "${VIRTUAL_ENV}"
