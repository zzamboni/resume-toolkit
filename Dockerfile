FROM node:24-bookworm-slim AS base

USER root
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python-is-python3 \
    python3-pip \
    python3-venv \
    fontconfig \
    libgraphite2-3 \
    fonts-roboto \
    ca-certificates \
    curl \
    xz-utils \
    jq \
  && rm -rf /var/lib/apt/lists/*

FROM base AS runtime
ENV XDG_CACHE_HOME=/opt/vita-cache
ENV MISE_DATA_DIR=/opt/vita-cache/mise
ENV NPM_CONFIG_UPDATE_NOTIFIER=false

RUN cd /tmp \
  && curl --proto '=https' --tlsv1.2 -fsSLo typst.tar.xz \
    https://github.com/typst/typst/releases/download/v0.14.0/typst-x86_64-unknown-linux-musl.tar.xz \
  && tar -xJf typst.tar.xz \
  && install -m 0755 typst-x86_64-unknown-linux-musl/typst /usr/local/bin/typst \
  && rm -rf /tmp/typst.tar.xz /tmp/typst-x86_64-unknown-linux-musl

RUN curl https://mise.run | MISE_INSTALL_PATH=/usr/local/bin/mise sh

WORKDIR /opt/vita-toolkit

RUN mkdir -p /opt/vita-cache \
  && chmod -R a+rwx /opt/vita-cache

RUN mkdir -p /usr/local/share/fonts
COPY fonts/ /usr/local/share/fonts/
RUN fc-cache -f

FROM runtime AS theme-builder

WORKDIR /tmp/jsonresume-theme-even

COPY themes/jsonresume-theme-even/ ./

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
      && (echo '#import "@preview/brilliant-cv:3.1.2"'; echo '#import "@preview/fontawesome:0.6.0"; echo "#import "@preview/pergamon:0.7.2": *') | typst compile - /tmp/typst-prime/prime-typst.pdf \
      && rm -rf /tmp/typst-prime; \
    fi \
  && chmod -R a+rwX /opt/vita-cache

COPY mise.toml requirements.txt package.json package-lock.json ./
COPY --from=theme-builder /tmp/jsonresume-theme-even/package.json ./themes/jsonresume-theme-even/package.json
COPY --from=theme-builder /tmp/jsonresume-theme-even/bin ./themes/jsonresume-theme-even/bin
COPY --from=theme-builder /tmp/jsonresume-theme-even/dist ./themes/jsonresume-theme-even/dist

RUN mise trust /opt/vita-toolkit/mise.toml \
  && mise install \
  && mise x -- uv pip sync requirements.txt \
  && HUSKY=0 npm ci --omit=dev --ignore-scripts \
  && npm cache clean --force \
  && rm -rf /opt/vita-cache/tectonic /opt/vita-cache/Tectonic /root/.npm /tmp/*

FROM prewarm AS final

COPY scripts/ ./scripts/
COPY templates/ ./templates/
COPY assets/ ./assets/
COPY docker/entrypoint.sh /usr/local/bin/vita-pipeline
RUN  chmod +x /usr/local/bin/vita-pipeline

RUN chmod +x /opt/vita-toolkit/scripts/run_pipeline.sh

WORKDIR /work

ENTRYPOINT ["/usr/local/bin/vita-pipeline"]
CMD ["tasks"]
