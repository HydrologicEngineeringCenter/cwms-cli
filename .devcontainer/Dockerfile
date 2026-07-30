FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

ARG POETRY_VERSION=2.0.1

ENV TZ=Etc/UTC \
    VIRTUAL_ENV=/opt/venv \
    POETRY_VIRTUALENVS_CREATE=false
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

RUN python -m venv "${VIRTUAL_ENV}" \
    && "${VIRTUAL_ENV}/bin/python" -m pip install --no-cache-dir \
        "poetry==${POETRY_VERSION}" \
    && chown -R vscode:vscode "${VIRTUAL_ENV}"
