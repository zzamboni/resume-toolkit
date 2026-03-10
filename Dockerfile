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

FROM runtime AS prewarm

ARG PREWARM_CACHE=0
RUN if [ "$PREWARM_CACHE" = "1" ]; then \
      mkdir -p /tmp/typst-prime \
      && printf '%s\n' \
        '@article{prime-entry,' \
        '  title={Prime},' \
        '  author={Prime, Example},' \
        '  journal={Prime Journal},' \
        '  year={2024},' \
        '  keywords={other}' \
        '}' > /tmp/typst-prime/publications.bib \
      && printf '%s\n' \
        '#import "@preview/pergamon:0.7.2": *' \
        '#let has-keyword(keywords, wanted) = {' \
        '  if keywords == none { false } else {' \
        '    keywords.split(",").map(s => s.trim()).contains(wanted)' \
        '  }' \
        '}' \
        '#let style = format-citation-numeric()' \
        '#add-bib-resource(read("publications.bib"))' \
        '#refsection(format-citation: style.format-citation)[' \
        '  #print-bibliography(' \
        '    format-reference: format-reference(reference-label: style.reference-label),' \
        '    title: "Other Publications",' \
        '    label-generator: style.label-generator,' \
        '    show-all: true,' \
        '    filter: reference => has-keyword(reference.fields.at("keywords", default: none), "other")' \
        '  )' \
        ']' > /tmp/typst-prime/publications.typ \
      && cd /tmp/typst-prime && typst compile publications.typ publications.pdf \
      && (echo '#import "@preview/brilliant-cv:3.1.2"'; echo '#import "@preview/fontawesome:0.6.0"') | typst compile - /tmp/typst-prime/prime-typst.pdf \
      && rm -rf /tmp/typst-prime; \
    fi \
  && chmod -R a+rwX /opt/vita-cache

COPY mise.toml requirements.txt package.json package-lock.json ./
COPY themes/jsonresume-theme-even/ ./themes/jsonresume-theme-even/

RUN mise trust /opt/vita-toolkit/mise.toml \
  && mise install \
  && HUSKY=0 NPM_CONFIG_IGNORE_SCRIPTS=true mise run bootstrap \
  && npm cache clean --force

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
