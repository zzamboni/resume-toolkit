# Development Guide

This document is for maintaining `resume-toolkit` itself.

It covers the workflows that are easy to forget after some time away from the
repo:

- building and testing the container image
- working with the vendored Eventide theme
- releasing new toolkit versions
- updating Node.js and Python runtime pins
- updating Typst-related package versions
- the most relevant `mise` tasks

## Repository model

At a high level:

- `build-resume.sh` is the user-facing wrapper around the container image
- `docker/entrypoint.sh` is the container entrypoint
- `scripts/run_pipeline.py` and related scripts implement the build pipeline
- `themes/jsonresume-theme-eventide/` is a git submodule pointing at the theme repo
- `typst-package-versions.json` is the source of truth for Typst package pins used by the toolkit
- `runtime-versions.json` is the source of truth for the Node and Python versions used by the toolkit

The normal development loop is:

1. change toolkit code and/or the vendored theme
2. build the image locally
3. run the container integration tests
4. test one or two real resumes manually

## Prerequisites

Required tools:

- `mise`
- `docker` or `podman`
- `git`

The local `mise` tasks handle most recurring maintenance commands.

## Most useful `mise` tasks

User-facing tasks:

- `mise run build <resume.json> [bibfiles...]`
- `mise run fetch-logos <resume.json> ...`
- `mise run update-logos <resume.json> ...`
- `mise run update-certs <username> <resume.json> ...`
- `mise run update-pub-numbers <resume.json> ...`
- `mise run update-inline-pubs <resume.json> [bibfiles...]`

Important maintainer tasks:

- `mise toolkit-image-build`
  - When needed: `mise toolkit-image-build --no-cache`
- `mise test-toolkit`
- `mise run release patch|minor|major` - default `release`
- `mise run update-all-versions` - calls all the following:
  - `mise run update-runtime-versions` - calls the following:
    - `mise run update-node-version`
    - `mise run update-python-version`
  - `mise run update-typst-version`
  - `mise run update-typst-package-versions`
- `mise refresh-root-lock`
- `mise bootstrap`

To inspect everything:

```sh
mise tasks ls
```

## Building the image

Normal local build:

```sh
mise toolkit-image-build
```

Useful variants:

```sh
mise toolkit-image-build --no-cache
mise toolkit-image-build --no-test
mise toolkit-image-build --no-cache-filter prewarm
```

Notes:

- `toolkit-image-build` refreshes the root `package-lock.json` before building
- by default it also runs `mise test-toolkit` after the image build
- the built image tag defaults to `ghcr.io/zzamboni/resume-toolkit:latest`

## Running tests

Primary integration suite:

```sh
mise test-toolkit
```

Equivalent direct command:

```sh
tests/container/test_container.sh
```

To test a specific image:

```sh
mise test-toolkit ghcr.io/zzamboni/resume-toolkit:latest
```

The integration suite exercises the public wrapper and validates:

- task exposure
- end-to-end pipeline output
- publications flows
- logo-fetch wiring
- Typst-generation regressions

After larger PDF or theme changes, also test manually with one or two real
resumes:

```sh
build-resume.sh zamboni-vita-general.json --serve
build-resume.sh samples/example-resume/example-resume.json --serve
```

## Working with the Eventide theme

The HTML theme lives in:

- `themes/jsonresume-theme-eventide/`

It is a git submodule:

```sh
git submodule update --init --recursive
```

If the theme submodule changes, the root npm lockfile usually also needs to be
refreshed because the root package depends on the theme via:

- `file:themes/jsonresume-theme-eventide`

Refresh it with:

```sh
mise refresh-root-lock
```

This is already run automatically by `mise toolkit-image-build`.

### Updating the theme to a newer commit or release

From the toolkit repo:

```sh
cd themes/jsonresume-theme-eventide
git fetch --tags origin
git checkout <tag-or-commit>
cd ../..
mise refresh-root-lock
mise toolkit-image-build
```

If you are actively developing the theme and then consuming the changes here:

1. update the theme repo first
2. move the submodule to the desired commit
3. refresh the root lockfile
4. rebuild and test the toolkit image

## Typst package versions

The toolkit-side Typst package pins live in:

- `typst-package-versions.json`

Currently this includes:

- `brilliant-cv`
- `fontawesome`
- `pergamon`

These values are used by:

- `scripts/render_typst_cv.py`
- `scripts/render_typst_publications.py`
- `docker/entrypoint.sh` (`version` output)
- the Docker prewarm step

So for toolkit-managed Typst package upgrades, this file is the first place to
change.

### Updating Typst itself

Update the pinned Typst binary version in `Dockerfile`:

```sh
mise run update-typst-version
```

Then rebuild and test:

```sh
mise toolkit-image-build --no-cache
```

## Runtime versions

The toolkit keeps explicit maintainer pins for:

- the Node.js major used by the container base image
- the Python version used by `mise`

Those values live in:

- `runtime-versions.json`

They are then applied to:

- `Dockerfile` (`FROM node:<major>-alpine`)
- `mise.toml` (`[tools].python`)

### Updating Node.js and Python

Refresh both runtime pins:

```sh
mise run update-runtime-versions
```

Refresh only one of them:

```sh
mise run update-node-version
mise run update-python-version
```

Policy:

- Node.js follows the latest official LTS major release
- Python follows the latest supported stable 3.x release branch from the Python release metadata

After updating either runtime pin, rebuild and test the image:

```sh
mise toolkit-image-build --no-cache
```

## Releasing

Toolkit releases are driven by the `VERSION` file and a git tag.

Preferred flow:

```sh
mise run release patch
mise run release minor
mise run release major
```

This task will:

1. pull the current branch
2. bump `VERSION`
3. commit the version change
4. create an annotated tag `vX.Y.Z`
5. push the branch
6. push the tag

Container publishing is handled by GitHub Actions from `v*` tags.

## Wrapper and runtime behavior

The wrapper runs:

- containerized entrypoint in `docker/entrypoint.sh`
- pipeline implementation in `scripts/run_pipeline.sh`
- supporting Python and shell scripts in `scripts/`

Useful runtime commands:

```sh
build-resume.sh tasks
build-resume.sh version
```

Relevant environment variables:

- `VITA_PIPELINE_IMAGE`
- `VITA_CONTAINER_ENGINE`
- `VITA_SERVE_PORT`
- `VITA_PIPELINE_CACHE_DIR`
- `LOGODEV_TOKEN`

## Bootstrap / local dependency refresh

If you need to refresh local development dependencies outside the container:

```sh
mise bootstrap
```

This will:

- sync Python requirements
- build the local Eventide theme
- install root npm dependencies

This is only needed if you want to test in the local host, but not if you are only testing within the container.

## Practical checklist after non-trivial changes

For changes to the build pipeline, Typst renderer, theme integration, or image:

1. `mise toolkit-image-build`
2. `mise test-toolkit`
3. manual check with at least one real resume
4. if theme changed, make sure the submodule commit and root `package-lock.json` are both updated
