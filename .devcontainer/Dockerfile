FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git graphviz \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh -o /tmp/uv-installer.sh \
    && UV_INSTALL_DIR=/usr/local/bin sh /tmp/uv-installer.sh \
    && rm /tmp/uv-installer.sh