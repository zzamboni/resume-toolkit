# Repository Guidelines

## Project Structure

- `build-resume.sh` is the public host wrapper for Docker/Podman.
- `docker/entrypoint.sh` implements container commands and preview serving/watching.
- `scripts/run_pipeline.sh` delegates to `scripts/run_pipeline.py`, which normalizes JSON, resolves inputs/assets, and manages incremental builds.
- `scripts/render_cv.sh` renders HTML with the bundled Eventide theme; `scripts/render_typst_cv.py` and `scripts/render_typst_publications.py` generate Typst/PDF.
- `scripts/build_publications.py` and `templates/publications.html.j2` build standalone publications HTML/BibTeX.
- Other `scripts/` helpers fetch logos, synchronize Credly certificates, update JSON publications, and maintain dependency versions.
- `themes/jsonresume-theme-eventide/` is an independently maintained git submodule.
- `samples/` contains portable example resumes, bibliography files, and assets. User assets can live next to the input JSON.
- `typst-package-versions.json` holds Typst package pins; `runtime-versions.json` tracks the Node major and host development Python version.
- `dev_serve.py` restarts a development preview when the local container image changes.
- `build/` is generated output and should generally not be committed.

Read `DEVELOPMENT.md` for maintainer workflows and `README.md` for user configuration. `PROJECT_CONTEXT.md` is a historical handoff; verify version numbers and behavior against current source. Eventide's own README and DEVELOPMENT.md describe its independent configuration and workflows.

## Commands and Verification

- Public interface: `./build-resume.sh <resume.json> [bibfiles...] [--out <dir>] [--watch] [--serve]`.
- Other public commands include `fetch-logos`, `update-logos`, `update-certs`, `update-inline-pubs`, `update-pub-numbers`, `version`, and `tasks`; use `--help` for flags.
- `mise toolkit-image-build` refreshes the root npm lockfile, builds with cache prewarming, and runs integration tests. This maintainer task currently invokes Docker explicitly, even though the public wrapper also supports Podman.
- `mise test-toolkit [image]` or `tests/container/test_container.sh [image]` tests an existing image. Rebuild first when testing source changes.
- `mise refresh-root-lock` synchronizes the root npm lockfile after theme dependency changes.
- `mise bootstrap` installs host development dependencies; ordinary container users do not need it.
- `mise tasks ls` lists both user and maintainer tasks.
- Version maintenance: `mise update-all-versions`, or individual runtime/Typst updater tasks documented in DEVELOPMENT.md.
- Release: `mise release patch|minor|major` updates VERSION, commits, tags, and pushes. Run only when releasing is requested.

The container suite covers pipeline outputs, bibliography selection/sectioning, logo wiring, PDF URL rendering, work aliases/grouping, and Typst escaping. Expected package versions come from `typst-package-versions.json`. Failed runs preserve temporary output for inspection.

For renderer changes, check relevant fixtures and at least one real or bundled resume. Compile both CV and standalone publications PDFs when changing shared Typst helpers. For HTML changes, inspect desktop/mobile output as well as tests.

## Design and Coding Guidelines

- Keep content independent of tooling; avoid personal/project-specific hardcoding.
- Prefer standard JSON Resume fields while preserving documented extensions.
- Normal builds modify a generated normalized JSON copy. Only explicit updating commands should modify user input.
- Distinguish omitted options from explicit empty values, particularly floating links and footer overrides.
- Keep toolkit-specific defaults and filename substitutions in preprocessing; Eventide must remain independently usable.
- Preserve full standalone bibliography versus filtered inline bibliography behavior; selectors match explicit keys OR keywords.
- Target the bundled brilliant-cv v4 package. Keep metadata inline and use upstream section behavior rather than restoring the old sticky-section workaround.
- Escape user text for Typst and handle missing fields without package placeholders or accidental grouping under empty names.
- Keep wrapper/entrypoint parsing and help synchronized when adding commands or flags.
- Include new stage dependencies in incremental-build hashes.
- Preserve Docker/Podman host file ownership, SELinux mount behavior, port binding, and plain version output through pipes.
- Shell scripts use `set -euo pipefail`; prefer explicit paths and small changes matching surrounding style.
- The toolkit has no dedicated formatter. Eventide uses Prettier, TypeScript checks, Vitest, and HTML validation; follow its own development guide.

## Theme Changes

Develop and verify Eventide in its own repository/submodule. Use `npm ci`, `npm run build`, `npm run type-check`, `npm run format -- --check`, and `npm test -- --run` as appropriate. Review intentional snapshot changes rather than changing correct output just to match stale snapshots.

Commit theme changes in that repository, then record the intended submodule commit and refreshed root `package-lock.json` in the toolkit. Check `.gitmodules` before assuming a tracking branch. Keep theme option documentation in the theme README and toolkit-specific integration behavior in the toolkit README.

## Commits, Documentation, and Security

- Use short, imperative commit subjects and keep changes focused.
- PRs should describe behavior, validation performed, and screenshots for visible HTML changes when relevant.
- ChangeLog entries describe user-facing features/fixes under dated releases; preserve published entries.
- Preserve unrelated user changes; do not commit generated build output unless requested.
- Credly sync uses public data. Never commit private data, credentials, or Logo.dev tokens (`LOGODEV_TOKEN`).
