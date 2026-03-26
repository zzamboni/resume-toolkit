FROM node:24-alpine AS base

ARG VITA_TOOLKIT_VERSION=dev
LABEL org.opencontainers.image.title="resume-toolkit"
LABEL org.opencontainers.image.version="${VITA_TOOLKIT_VERSION}"
ENV VITA_TOOLKIT_VERSION="${VITA_TOOLKIT_VERSION}"

USER root

RUN apk add --no-cache \
    bash \
    python3 \
    py3-pip \
    py3-virtualenv \
    fontconfig \
    graphite2 \
    font-roboto \
    ca-certificates \
    jq \
    coreutils \
    findutils

FROM base AS downloader

RUN apk add --no-cache \
    curl \
    xz

RUN cd /tmp \
  && curl --proto '=https' --tlsv1.2 -fsSLo typst.tar.xz \
    https://github.com/typst/typst/releases/download/v0.14.0/typst-x86_64-unknown-linux-musl.tar.xz \
  && tar -xJf typst.tar.xz \
  && install -m 0755 typst-x86_64-unknown-linux-musl/typst /usr/local/bin/typst \
  && rm -rf /tmp/typst.tar.xz /tmp/typst-x86_64-unknown-linux-musl

RUN cd /tmp \
  && curl --proto '=https' --tlsv1.2 -fsSLo watchexec.tar.xz \
    https://github.com/watchexec/watchexec/releases/download/v2.5.0/watchexec-2.5.0-x86_64-unknown-linux-musl.tar.xz \
  && tar -xJf watchexec.tar.xz \
  && install -m 0755 watchexec-2.5.0-x86_64-unknown-linux-musl/watchexec /usr/local/bin/watchexec \
  && rm -rf /tmp/watchexec.tar.xz /tmp/watchexec-2.5.0-x86_64-unknown-linux-musl

FROM base AS runtime
ENV XDG_CACHE_HOME=/opt/vita-cache
ENV NPM_CONFIG_UPDATE_NOTIFIER=false

COPY --from=downloader /usr/local/bin/typst /usr/local/bin/typst
COPY --from=downloader /usr/local/bin/watchexec /usr/local/bin/watchexec

WORKDIR /opt/vita-toolkit

RUN mkdir -p /opt/vita-cache \
  && chmod -R a+rwx /opt/vita-cache

RUN mkdir -p /usr/share/fonts
COPY fonts/ /usr/share/fonts/
RUN fc-cache -f /usr/share/fonts

FROM runtime AS theme-builder

WORKDIR /tmp/jsonresume-theme-eventide

COPY themes/jsonresume-theme-eventide/ ./

RUN if [ -f package-lock.json ]; then \
      npm ci --ignore-scripts; \
    else \
      npm install --ignore-scripts; \
    fi \
  && NPM_CONFIG_IGNORE_SCRIPTS=false npm run build

FROM runtime AS prewarm

ARG PREWARM_CACHE=0
RUN if [ "$PREWARM_CACHE" = "1" ]; then \
      mkdir -p /tmp/typst-prime \
      && cd /tmp/typst-prime \
      && (echo '#import "@preview/brilliant-cv:3.3.0"'; echo '#import "@preview/fontawesome:0.6.0"; echo "#import "@preview/pergamon:0.7.2": *') | typst compile - /tmp/typst-prime/prime-typst.pdf \
      && rm -rf /tmp/typst-prime; \
    fi \
  && chmod -R a+rwX /opt/vita-cache

COPY VERSION requirements.txt package.json package-lock.json ./
COPY --from=theme-builder /tmp/jsonresume-theme-eventide/package.json ./themes/jsonresume-theme-eventide/package.json
COPY --from=theme-builder /tmp/jsonresume-theme-eventide/bin ./themes/jsonresume-theme-eventide/bin
COPY --from=theme-builder /tmp/jsonresume-theme-eventide/dist ./themes/jsonresume-theme-eventide/dist

RUN python3 -m venv /opt/vita-toolkit/.venv \
  && /opt/vita-toolkit/.venv/bin/pip install --no-cache-dir --upgrade pip \
  && /opt/vita-toolkit/.venv/bin/pip install --no-cache-dir -r requirements.txt \
  && HUSKY=0 npm ci --omit=dev --ignore-scripts \
  && npm cache clean --force \
  && rm -rf /opt/vita-cache/tectonic /opt/vita-cache/Tectonic /root/.npm /tmp/*

FROM prewarm AS final

COPY scripts/ ./scripts/
COPY templates/ ./templates/
# COPY assets/ ./assets/
COPY docker/entrypoint.sh /usr/local/bin/vita-pipeline
RUN  chmod +x /usr/local/bin/vita-pipeline

RUN chmod +x /opt/vita-toolkit/scripts/run_pipeline.sh

WORKDIR /work

ENTRYPOINT ["/usr/local/bin/vita-pipeline"]
CMD ["tasks"]
