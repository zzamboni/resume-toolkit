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
- `runtime-versions.json` tracks the container Node major and the host development Python pin; updater scripts synchronize Dockerfile/mise declarations

User configuration belongs in [README.md](README.md). Eventide configuration and
maintenance have their own guides in the theme submodule. [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)
captures development history and design decisions; its version snapshot is not a
replacement for current manifests.

The normal development loop is:

1. change toolkit code and/or the vendored theme
2. build the image locally
3. run the container integration tests
4. test one or two real resumes manually

## Prerequisites

Required tools:

- `mise`
- Docker for the current `toolkit-image-build` task, which invokes `docker` explicitly
- `git`

The public wrapper also supports Podman. Local dependency installation and theme
builds require Node.js/npm; version updaters require curl/jq and the shell tools
used in their scripts. Some helpers use GNU-style commands, so maintainer-task
portability on macOS needs separate verification from container usage.

Initialize the theme before building:

```sh
git submodule update --init --recursive
```

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

- `mise toolkit-image-build` (use `--no-cache` when needed)
- `mise test-toolkit`
- `mise run release patch|minor|major` (defaults to a patch bump)
- `mise run update-all-versions`
- `mise run update-runtime-versions`
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
- local and CI builds enable `PREWARM_CACHE=1` to bundle the Typst package cache
- `--no-cache` reruns build layers; use Docker's `--pull` separately when you need
  to refresh the base image, for example `docker build --pull --build-arg PREWARM_CACHE=1 -t ghcr.io/zzamboni/resume-toolkit:latest .`

### Restarting previews after image rebuilds

From the toolkit root, forward preview arguments through the Python helper:

```sh
python3 dev_serve.py samples/example-resume/example-resume.json --serve
```

It watches the local image ID and restarts the wrapper after a rebuild, forwarding
its arguments and stopping the preview container during cleanup. Rebuild in another
terminal, optionally using `mise watch toolkit-image-build`. The helper uses
`VITA_PIPELINE_IMAGE`, `VITA_CONTAINER_ENGINE`, and `VITA_DEV_SERVE_POLL_INTERVAL`
(default two seconds). It watches local image changes, not remote registry tags.

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

Tests run against an image, not the current source tree. Rebuild after source
changes. Failed runs retain a temporary directory for inspection. Package-version
expectations read `typst-package-versions.json` rather than duplicating pins.

After larger PDF or theme changes, also test manually with one or two real
resumes:

```sh
./build-resume.sh samples/example-resume/example-resume.json --serve
./build-resume.sh samples/john-doe-brilliantcv/john-doe-brilliantcv.json --serve
```

## Publishing the sample to GitHub Pages

`.github/workflows/pages.yml` builds the John Doe Brilliant-CV sample using a
Docker image built from the current checkout, including the pinned Eventide
submodule. It publishes HTML, PDFs, bibliography and assets at
<https://zzamboni.github.io/resume-toolkit/>. The `vita/` output directory is
uploaded as the site root, so its relative links work under the project URL.
PDF footer URLs use the base URL returned by GitHub Pages.

One-time setup: in repository **Settings → Pages → Build and deployment**, set
**Source** to **GitHub Actions** before the first deployment. The workflow uses
the built-in `GITHUB_TOKEN`; no registry or Logo.dev secrets are needed.

Pushes to `main` rebuild and deploy when the sample, workflow, or toolkit build
dependencies change. Unrelated documentation changes do not trigger a build.
Matching pull requests build and upload a Pages artifact without deploying.
Use **Actions → Deploy sample to GitHub Pages → Run workflow** on `main` to
rebuild manually, including after changing the Pages configuration. Manual runs
on other branches only build. Docker Buildx caches use a separate `pages` scope.

The build checks that the CV and publications HTML/PDF, profile image, BibTeX
and publications JSON outputs are present before uploading. Generated files
and pipeline state are not committed.

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

Check for local theme changes before switching revisions. The submodule is pinned
to a commit, which can be newer than its package version tag. `.gitmodules`
currently names `feat-multiple-features` as its tracking branch; inspect it before
using remote-tracking updates. Record the intended submodule pointer and refreshed
root lockfile in the toolkit commit.

Theme validation and editor/release commands are documented in
[the theme development guide](themes/jsonresume-theme-eventide/DEVELOPMENT.md).
For a theme change, use `npm ci`, build, type-check, check formatting, and run
`npm test -- --run` in that directory. Review snapshot updates when intentional
rendering or whitespace changes alter expected HTML.

The root lockfile refresh is required because the local theme manifest can change
the dependency graph even for `npm ci --omit=dev`. Keep reproducible clean installs
in the container rather than replacing them to bypass a stale lockfile.

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

To check every configured package against the official Typst package repository:

```sh
mise run update-typst-package-versions
```

The renderer targets brilliant-cv v4. Shared helpers serve both PDF exporters, so
compile both outputs after package or renderer changes. Keep generated metadata
inline; the old custom sticky `cv-section` workaround is no longer needed.

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

The Python pin controls host development through mise. Python inside the container
comes from Alpine's `python3` package and is not pinned by this JSON file. Node's
container pin selects a major; refreshing the base image supplies newer patch
versions within that major.

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

`mise run update-all-versions` runs both runtime updaters, the Typst binary updater,
and the Typst package updater. These are manually invoked checks, not scheduled
updates. Review the resulting diff before building and committing. Root Dependabot
currently checks uv and GitHub Actions; theme npm dependencies are maintained in
the theme repository, and root Resumed updates need separate attention.

## Releasing

Toolkit releases are driven by the `VERSION` file and a git tag.

Before releasing, finish validation, commit intended changes, and add user-facing
release notes to `ChangeLog.md`. The release task commits only the VERSION change;
it does not prepare changelog entries or commit other work.

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

Container publishing is handled by GitHub Actions from `v*` tags. CI verifies that
the tag matches VERSION, builds/tests, and publishes to GHCR and Docker Hub with
version aliases and `latest`. Branch/SHA tags are not published. Manual workflow
dispatch builds/tests without publishing. Eventide has its own npm release
workflow; releasing the toolkit does not release the theme.

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

Docker is preferred when available; set `VITA_CONTAINER_ENGINE=podman` to select
Podman explicitly. Preserve Podman's keep-id mapping and SELinux mount labeling
when editing the wrapper. Both engines should create output owned by the host
user. Serving binds to all container interfaces but publishes only on localhost.

`version` uses terminal formatting only when stdout is a terminal and NO_COLOR is
unset. The wrapper allocates a TTY only when both stdin and stdout are terminals,
so pipes and redirects retain flat `name version` output.

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

1. Run `mise toolkit-image-build`, which includes integration tests unless `--no-test` is supplied.
2. Run `mise test-toolkit` separately if testing an existing image or if the build skipped tests.
3. Check at least one real or bundled resume manually, including desktop/mobile HTML for visual changes.
4. If the theme changed, include its submodule commit and refreshed root `package-lock.json`.
5. If a pipeline stage gains inputs or options, update its incremental-build hash dependencies and relevant regression coverage.

