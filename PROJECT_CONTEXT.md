# Resume Toolkit and Eventide: Development Context

Prepared on 2026-10-16 as a handoff for a ChatGPT project or another development assistant. This document combines the development conversation, checked-out source, documentation, and local git history. Version numbers below describe this checkout; they are not claims about the latest upstream releases.

## Purpose and Background

Diego Zamboni originally maintained his CV in Org mode with LaTeX/Tectonic output, then moved to JSON Resume. The initial work is described in https://zzamboni.org/post/porting-my-cv-from-org-latex-to-json-resume/ . The build tooling subsequently became a reusable open-source project, independent of Diego's personal CV and publication data.

The main goal is to maintain one JSON Resume file, optionally accompanied by BibTeX and images, and generate a coherent personal CV website and professionally formatted PDFs. Users should be able to run the toolkit against arbitrary resumes without installing the rendering dependencies on their host.

Repositories and examples:

- Toolkit: https://github.com/zzamboni/resume-toolkit
- HTML theme: https://github.com/zzamboni/jsonresume-theme-eventide
- Published CV: https://zzamboni.org/vita/
- Theme editor/demo: https://zzamboni.github.io/jsonresume-theme-eventide/
- Default container: `ghcr.io/zzamboni/resume-toolkit:latest`

## Current Checkout

- Toolkit `VERSION`: `0.7.1`; main has subsequent runtime-maintenance and dependency changes.
- Eventide package version: `0.29.12`.
- Eventide submodule commit: `e7f4426d5fe89f537c1c15accfce55dd2805e086`, with commits after the `v0.29.12` tag. Package version and exact source revision are therefore distinct.
- Typst binary pin: `0.15.1` in `Dockerfile`.
- Typst packages: brilliant-cv `4.1.0`, fontawesome `0.6.2`, pergamon `0.8.0`.
- Container base: `node:24-alpine`.
- Host development Python pin: `3.14.7`.
- Root npm dependencies: local Eventide via `file:themes/jsonresume-theme-eventide` and `resumed` via `^6.1.0`.
- Toolkit and theme have separate maintenance and release workflows; Eventide is a git submodule, not an ordinary copied directory.

## Design Principles and Decisions

- Keep content independent of the toolkit. Do not hardcode personal names, paths, publication keys, institutions, or credentials.
- Prefer JSON Resume schema fields. Preserve useful existing extensions without inventing unnecessary alternatives to standard fields.
- Put resume-specific configuration in JSON under `meta`, rather than requiring code or template edits.
- Treat omitted configuration differently from explicitly empty values where documented. For example, missing floating links enables defaults; `links: []` suppresses them.
- Keep Eventide usable as an independent JSON Resume theme. Toolkit-specific defaults and filename substitutions belong in JSON preprocessing before theme rendering.
- Reuse section order, labels, and project grouping between HTML and PDF where practical.
- Keep generated Typst configuration inline and documents easy to inspect. Avoid separate metadata TOML and content module dependencies. Images and generated BibTeX resources remain external assets, and Typst package imports remain necessary.
- Simplicity matters. Extracting Python-generated Typst into a template system was considered and deferred because the additional machinery did not justify itself.
- No brilliant-cv v3 compatibility is required: packages are bundled with the container, so the renderer can target the selected v4 release directly.
- Preserve the established visual design and align related outputs, especially the CV and standalone publications navigation.
- Developer conveniences should remain separate from the public wrapper when their purpose is only toolkit development.

## Outputs and Architecture

Typical input is `resume.json`, optional BibTeX files, and an adjacent `assets/` directory. Default output is:

```text
build/<resume-stem>/
  .pipeline-state/<resume-stem>/
    <resume-stem>.normalized.json
    ... stage hash stamps ...
  vita/
    index.html
    <resume-stem>.typ
    <resume-stem>.pdf
    assets/
      profile/
      logos/
      badges/
    <resume-stem>-vita.bib              # when needed for inline PDF bibliography
    publications/                      # when BibTeX sources are present
      index.html
      <resume-stem>-pubs.typ
      <resume-stem>-pubs.pdf
      <resume-stem>-pubs.bib
```

Main components:

| Path | Responsibility |
| --- | --- |
| `build-resume.sh` | Host wrapper: engine selection, mounts, user mapping, optional image pull, port selection, TTY handling |
| `docker/entrypoint.sh` | Public subcommands, serving/watching, runtime environment, version output |
| `scripts/run_pipeline.sh` | Shell entry to the Python pipeline |
| `scripts/run_pipeline.py` | Normalize JSON, locate inputs/assets, orchestrate stages and incremental rebuilds |
| `scripts/render_cv.sh` | Render HTML through Resumed and the explicitly selected bundled Eventide theme |
| `scripts/render_typst_cv.py` | JSON-to-Typst conversion, PDF layout, shared publication helpers |
| `scripts/render_typst_publications.py` | Standalone publications Typst, reusing CV helpers |
| `scripts/build_publications.py` | Parse/aggregate/filter BibTeX and render standalone HTML |
| `templates/publications.html.j2` | Standalone publications page markup, styling, navigation |
| `scripts/update_inline_pubs.py` | Write selected bibliography entries into schema-compatible JSON publications |
| `scripts/update_pub_numbers.py` | Synchronize publication reference numbers using generated HTML anchors |
| `scripts/fetch_company_logos.py` | Fetch work/education logos and optionally update JSON image URLs |
| `scripts/update-certs-from-credly.py` | Sync public Credly certifications |
| `scripts/render_fa_icon.mjs` | Resolve Font Awesome icons from npm packages |
| `scripts/inject_dev_reload.py` | Development preview reload support |
| `themes/jsonresume-theme-eventide/` | Independently maintained HTML theme submodule |
| `tests/container/` | End-to-end tests and fixtures |

Incremental builds use content hashes for files, directories, and option strings. Outputs and hash stamps must both exist to skip a stage. Changes to renderers, assets, configuration, and relevant inputs should invalidate affected stages. Check hash inputs whenever adding a new dependency to a render stage.

Normal builds preprocess a generated JSON copy rather than modifying the user's source. Commands named `update-*` deliberately modify the source JSON.

Two portable examples live under `samples/`: `example-resume/` is synthetic and exercises varied structures; `john-doe-brilliantcv/` converts the English Brilliant-CV sample CV to JSON Resume, with bibliography, profile, and appropriately named logos. Its scope is the CV, not the sample cover letter. Earlier conversation paths `sample/` and `sample2/` predate this organization.

## Public Commands and Container Behavior

```sh
build-resume.sh [--pull] [build] resume.json [publications.bib ...] [--out DIR] [--watch] [--serve]
build-resume.sh fetch-logos resume.json [--overwrite] [--dry-run] [--update-json] [--token TOKEN]
build-resume.sh update-logos resume.json [--overwrite] [--dry-run] [--token TOKEN]
build-resume.sh update-certs USERNAME resume.json [flags]
build-resume.sh update-inline-pubs resume.json [publications.bib ...]
build-resume.sh update-pub-numbers resume.json [--html PATH]
build-resume.sh version
build-resume.sh tasks
build-resume.sh shell
```

Build options also include `--pubs-url`, `--cv-url`, `--no-fetch-logos`, and a logo token option. Consult actual `--help` and entrypoint parsing when extending the interface; keep wrapper and entrypoint command lists synchronized.

- `build` is the default subcommand.
- `--serve` implies watching. The HTTP server exposes the output base and reports the `/vita/` URL.
- The default port is 8080. The wrapper tests localhost ports and increments until one appears available, allowing concurrent previews. Selection is a probe, not an atomic port reservation.
- The server binds to `0.0.0.0` inside the container; the wrapper publishes to host `127.0.0.1`. This distinction is necessary for Podman connectivity.
- Prefer Docker when its executable exists, otherwise Podman; override with `VITA_CONTAINER_ENGINE`.
- Docker runs with the current UID/GID. Podman uses `--userns keep-id` plus the current UID/GID and a `:Z` work-directory mount for SELinux. Preserve host ownership and the ability to alternate engines without cleaning output.
- Do not reintroduce recursive ownership changes or rootless namespace mappings that produce host files owned by subordinate IDs.
- `--pull` is opt-in. Pull failure warns and continues using a local image if available. Routine builds do not deliberately refresh an already present image.
- The work mount is the current directory at `/work`; files must be accessible within that mount.
- Forward `LOGODEV_TOKEN` explicitly into the container. Merely setting it on the host is insufficient without forwarding.
- Wrapper TTY allocation requires both stdin and stdout to be terminals (`[[ -t 0 && -t 1 ]]`). Allocating a container TTY for redirected output caused the pretty version output to leak into pipes.
- `version` reports toolkit, Eventide, brilliant-cv, fontawesome, pergamon, Node, Python, and Typst versions. A terminal gets grouped/color output; a pipe or redirect gets flat `name version` lines. The entrypoint also respects `NO_COLOR`.
- Watchexec produces messages such as `[Command was successful]`; these are not pipeline-authored success messages.

Relevant environment variables include `VITA_PIPELINE_IMAGE`, `VITA_CONTAINER_ENGINE`, `VITA_SERVE_PORT`, `VITA_PIPELINE_CACHE_DIR`, and `LOGODEV_TOKEN`. Internally, `VITA_TOOLKIT_ROOT`, `VITA_WORKDIR`, `VITA_ASSETS_DIR`, and inline bibliography/URL variables connect pipeline stages. Verify actual use before assuming a variable affects every stage.

## JSON Normalization and Shared Configuration

The toolkit explicitly selects Eventide for HTML rendering even if `meta.theme` requests another theme. This is intentional: the packaged pipeline relies on the bundled theme.

Before HTML rendering:

- A single publications entry with `bibfiles` is recognized as the generated-publications configuration entry. More than one is an error.
- Missing or blank generated-publication `name` defaults to `Full list online`; missing or blank `url` defaults to `publications/`.
- If `meta.themeOptions.links` is absent, add a PDF link and, when a JSON `bibfiles` entry exists, a publications-page link. The implementation currently bases that second default on the JSON entry, so CLI-only bibliography inputs deserve separate consideration.
- Respect explicitly provided links, including `[]`.
- If `meta.themeOptions.footer_right` is absent, set `Powered by [resume-toolkit](https://github.com/zzamboni/resume-toolkit)`. Respect explicit values.
- Expand `<resume>` and `<publications>` in floating-link URLs to the main and standalone publication filename stems. Theme changes are not needed for this substitution.

The PDF renderer also consumes Eventide's `sections`, `sectionLabels`, and `projectsByType`. `projects:<type>` identifiers allow individual project groups to be ordered and labeled.

## Bibliography Model and Selection Rules

Configuration belongs in one special `publications[]` entry:

```json
{
  "publications": [
    {
      "name": "Full list online",
      "url": "publications/",
      "authors": ["Example Person"],
      "bibfiles": ["publications.bib"],
      "bibentries": ["example2024paper"],
      "bibkeywords": ["selected", "important"]
    }
  ],
  "meta": {
    "publicationsOptions": {
      "inline_in_pdf": {
        "ref-style": "ieee",
        "ref-full": true,
        "ref-sorting": "ydnt"
      },
      "full_standalone_list": true,
      "full_standalone_list_title": "Publications"
    }
  }
}
```

- JSON `bibfiles` paths are relative to the JSON file. Explicit command-line BibTeX inputs take precedence.
- Selection is a union: an entry matches an explicit key OR any selected keyword. With no selectors, use all entries.
- `full_standalone_list` defaults to `true`: standalone HTML, PDF, and aggregated BibTeX contain the full source list, while inline PDF entries use the selected subset.
- When `full_standalone_list` is `false`, standalone outputs use the filtered subset too.
- Keep a separate filtered inline bibliography resource. A previous bug reused the full standalone aggregate and accidentally put every entry inline.
- `full_standalone_list_title` defaults to `Publications` and supplies the independent standalone title when the full standalone mode applies. The setting is a string; an early request mistakenly referred to enabling that title key as a boolean.
- `inline_in_pdf: true` enables defaults: IEEE/numeric style, full selected bibliography, sorting `ydnt`. An object customizes `ref-style`, `ref-full`, and `ref-sorting`.
- `ref-full` is Pergamon's inclusion control within the provided bibliography; it is distinct from the toolkit's full-versus-filtered standalone policy. Examine the internal key predicate when combining `ref-full: false` with keyword-only selection.
- The old public `inline_in_pdf.key-list` fallback was deliberately removed. User selection belongs in `bibentries`; an internal generated Typst key list still exists.
- Inline PDF bibliography rendering uses Pergamon and replaces rendering of ordinary individual JSON publication entries in that mode. The generated-publications note/link should remain available.
- HTML CV inline publications are materialized by `update-inline-pubs`, keeping bibliography processing out of the theme. It preserves the configuration entry and regenerates other entries with only JSON Resume publication fields: `name`, `publisher`, `releaseDate`, `url`, `summary`.
- `update-pub-numbers` updates links/reference numbers based on generated standalone publication anchors. Keep anchor and numbering conventions consistent.

`pubSections` is unset/false for one list, true for default keyword sections, or an array for custom order/selection. `pubSectionTitles` overrides labels. Default section keys are `book`, `editorial`, `thesis`, `refereed`, `techreport`, `presentations`, `invited`, `patent`, `other`. PDF generation suppresses empty configured sections where it can inspect the resource.

Standalone floating links live under `meta.publicationsOptions.links`; absent means PDF and BibTeX links, `[]` means none. `<publications>` and `<resume>` substitutions are supported. Icons accept plain names or Font Awesome class-style names.

The standalone HTML palette uses the same five `meta.themeOptions.colors` roles as Eventide. All links, visited or unvisited, should use the accent color. Its mobile navigation was ported from Eventide to retain the same appearance and behavior.

## PDF Rendering, Layout, and URLs

`render_typst_cv.py` supports the standard JSON Resume sections and a set of deliberate extensions. Standard-schema coverage was a development goal, but do not assume every possible field combination is covered by tests.

Layout configuration uses `meta.pdfthemeOptions.layout`, recursively merged with `DEFAULT_PDF_THEME_LAYOUT`. Historical defaults originated in brilliant-cv metadata. The current Python defaults are the source of truth; the renderer does not load the sample's TOML at runtime.

Important defaults include A4, skyblue accent, Source Sans 3 body font, Roboto header font, small entry/section spacing, left-aligned header, logos enabled, and footer enabled without page counters.

Special options:

- `layout.summary_title`: false by default; render the Summary heading only when true and summary content exists.
- `layout.highlighted` and `layout.letters`: retained toolkit JSON keys, passed only when supplied. V4 output maps them to `cv-section(..., highlight: "first-letters"/"none", highlight-letters: N)`.
- `meta.pdfthemeOptions.cv_url`: canonical link in the CV footer.
- `meta.pdfthemeOptions.pubs_url`: canonical link in the standalone publications footer.
- `--cv-url` and `--pubs-url` override JSON values.

`meta.site.url` supplies the public CV base URL. Resolve relative explicit URLs and Markdown link destinations against it only for PDF rendering; retain useful relative navigation in HTML. This includes links such as `publications/#pub-some-key` embedded in highlights or note descriptions. Preserve fragments and already absolute links.

`meta.pdfthemeOptions.visible_urls` defaults to `["notes"]`. Supported categories are `notes`, `profiles`, `projects`, `all`, and `none`. An empty array disables visible suffixes. Visible suffixes use compact display text, generally without HTTP(S) scheme or a trailing slash, but retain the full link target. They must themselves be clickable.

Note URL behavior must be consistent across certification notes, generated-publication notes, and Markdown project notes. Previously one path omitted suffixes and another emitted nonclickable text. Pass resume/config context explicitly to rendering helpers; missing `resume_data` parameters caused runtime NameErrors in projects and certifications.

Additional rendering decisions and regressions to preserve:

- Escape user text before interpreting it as Typst markup. A literal `C#` in a work highlight previously entered Typst code mode and failed compilation. Test real text containing punctuation and Markdown.
- Work accepts `company` as an alternative to `name`, matching common resumes in the wild. Never group unrelated work entries just because their organization name is empty.
- Missing locations are emitted explicitly as empty strings where necessary, preventing brilliant-cv's `Location` placeholder. Avoid indexing empty location lists during grouping.
- Missing/unavailable profile photos disable `display_profile_photo`; do not show the package's default photo.
- Education descriptions use `list(...)`: optional summary string or summary list first, then joined courses, then score/GPA. Education `highlights` support was added and deliberately reverted to stay close to the schema. The existing summary extension remains supported.
- References use `quote`; include attribution only if a name exists.
- Certificate notes link their actual `name`, rather than fixed English text such as “Full list available at Credly.” Some PDF note detection remains historical/text-specific; check the renderer before assuming it matches Eventide's structural detection exactly.
- Without badge images, ordinary certifications use `cv-honor`. If any ordinary certification has a usable image, render all ordinary certifications with `cv-entry`; use an empty box logo placeholder for entries without badges to preserve alignment. This superseded an earlier mixed bullet/grid design.
- Work/education logos are discovered by organization/institution name. Do not assume HTML and PDF use the same image lookup path: HTML supports entry `image` URLs, while PDF work/education currently looks for local named logos.
- Standalone publications PDF should retain the owner's name and suppress the profile photo. Historically the requested header was name-only; recheck v4 behavior if extra personal information appears.

## brilliant-cv v4 Migration

The migration replaced v3.3.0 with v4.1.0. Local sample/source checkouts named `brilliant-cv/`, `brilliant-cv-v3/`, and `brilliant-CV/` were used during development as references. These are development aids, not required runtime inputs.

- Keep the inline metadata dictionary and generated document approach.
- The old custom `cv-section` override implemented sticky headings. It was removed after upstream incorporated the behavior; use the package's implementation.
- Rename emitted section parameters to `highlight` and `highlight-letters`. The user-facing JSON compatibility keys remain `highlighted` and `letters`.
- Empty keywords must be an array/tuple (`()`), not a Typst content sequence (`[]`). The v4 injection helper calls array methods, so a content value fails with “element sequence has no method len.” The current metadata emits `inject.injected_keywords_list: ()`.
- Shared helper changes affect both the CV and standalone publication exporters. Update both and compile both.
- Packages are pinned together with renderers and container caches, so no v3 runtime fallback is needed.

## Images, Logos, and Credly

Asset source precedence is explicit `VITA_ASSETS_DIR`, then `assets/` next to the JSON file, then the working directory's `assets/`, then the toolkit assets fallback. This was fixed after the same sample rendered differently depending on the invocation directory. Preserve JSON-adjacent assets as the first automatic choice.

PDF local logos are named exactly for the company or institution, with supported extensions including PNG/JPEG/SVG/WebP/GIF. The Brilliant-CV-derived sample includes matching logos.

Remote images without filename extensions must use response content type to choose a suitable extension. Normalize filenames using the URL path, without query strings and unsafe characters. Credly badge filenames use their image identifiers. GitHub avatar URLs returning JPEG were a real regression case: saving them as PNG caused Typst decoding errors.

Automatic logo fetching runs when source logo assets are missing. Missing `LOGODEV_TOKEN` warns and allows the build to continue. `--no-fetch-logos` disables both automatic fetching and its warning.

- `fetch-logos` downloads logos, supports overwrite/dry-run/token, and can write Logo.dev URLs into work/education `image` fields with `--update-json`.
- `update-logos` is the same operation with JSON updating enabled by default, following the `update-*` naming convention.
- Logo.dev requests were standardized to PNG output.
- `update-certs` consumes public Credly data, replaces entries whose URLs identify Credly, and preserves unrelated certificates. Options control expired/non-cert badges and sorting.
- Credly PNG badges are often transparent. The HTML fix belongs in Eventide CSS: a white rounded background behind the badge, preserving its image content. Altering the PDF renderer did not address the original HTML issue.
- Never include actual tokens or private personal data in examples, tests, summaries, or commits.

## Eventide Theme History and Scope

Eventide began as extensive changes to `jsonresume-theme-even`, originally developed on `feat-multiple-features` and proposed upstream. The changes became large enough to justify an independently maintained fork. The name “Eventide” evokes evening and acknowledges Even without implying superiority or official succession.

Eventide retains a flat, CSS-grid-based CV design with generous whitespace, responsive layout, and light/dark palettes. It is not a toolkit-specific template. It can be installed from npm, loaded by Resumed/resume-cli, or used through its stdin-to-HTML CLI.

Theme capabilities developed or extended during this work:

- Markdown in text fields.
- Configurable colors with `background`, `dimmed`, `primary`, `secondary`, `accent`; each accepts light and optional dark values. One value applies in both modes.
- Font Awesome and optional Feather icons; floating icons accept simple names or style-prefixed class strings.
- Certificate badges and work/education image logos.
- Project grouping by `type`, with individually selectable/labeled `projects:<type>` sections.
- Shared section selection/order and `sectionLabels` overrides.
- A floating table of contents with active-section tracking and a Top entry; enabled by default and disabled with `showTableOfContents: false`.
- A hamburger/full-screen ToC on narrow screens, with Escape/link/backdrop close behavior and responsive state reset.
- Floating action links, hidden on narrow screens until the navigation overlay opens; navigation controls are hidden in print.
- Lightweight note entries for certificates and publications, and description-only project notes.
- Configurable Markdown footers: `footer_left` defaults to owner/year; `footer_right` defaults to Eventide attribution. The toolkit supplies its own right-side default during normalization.
- An interactive browser editor with JSON editing and live preview, published separately through GitHub Pages.

Certificate notes structurally have `name` and optional `url`, but no issuer/date/image. Publication notes have `name` and optional `url`, but no publisher/releaseDate/summary. Render these before regular entries using small metadata/body-sized text, not publication/certificate title typography.

Visual alignment was a recurring issue: certificate and publication notes must align vertically with their section titles just like simple project notes. Merely changing heading tags or font size fixed one aspect and broke another. Current `.note-entry` styling uses flex alignment and a minimum height tied to the heading scale. Compare actual output at desktop and mobile sizes before declaring alignment fixed.

Theme source structure:

- `index.js`: `render(resume)` plus PDF rendering hints for consumers; imports bundled CSS/JS.
- `components/`: render functions for sections, header/footer, links/icons, navigation.
- `assets/page.css` and `assets/page.js`: layout, responsiveness, menus, active-section tracking, duration behavior.
- `utils/markdown.js` and `utils/colors.js`: shared formatting/configuration.
- `editor/`: browser editor and its Vite build.
- `test/index.test.js` and snapshots: rendering, HTML validation, and focused behavior checks.

Build outputs include ESM, CommonJS, UMD, and TypeScript declarations. `schema.d.ts` is generated from the installed JSON Resume schema during prebuild. The npm package distributes `bin/` and `dist/`.

## Development, Tests, and Release Workflows

Toolkit commands:

```sh
mise bootstrap
mise toolkit-image-build
mise toolkit-image-build --no-cache
mise toolkit-image-build --no-cache-filter prewarm
mise toolkit-image-build --no-test
mise test-toolkit
mise test-toolkit ghcr.io/zzamboni/resume-toolkit:latest
```

`toolkit-image-build` refreshes the root npm lockfile, builds with `PREWARM_CACHE=1`, and normally runs integration tests. Refreshing the lockfile is necessary because npm validates the local theme dependency's current manifest even with `npm ci --omit=dev`. Updating only the theme submodule previously caused large lock mismatch failures.

```sh
mise refresh-root-lock
```

The helper runs `npm install --package-lock-only --ignore-scripts`. Preserve reproducible `npm ci` installs in the container instead of papering over mismatches with unconstrained installs there.

The Dockerfile separates base, downloader, runtime, theme builder, prewarm, and final stages. It builds the theme, installs runtime dependencies, bundles fonts, and primes Typst package caches. CI must supply `PREWARM_CACHE=1` as local builds do. Python inside the image comes from Alpine `apk`, not from the host mise pin.

`tests/container/test_container.sh` exercises the actual wrapper against an image. This checkout has 19 consecutively numbered cases covering pipeline outputs, bibliography modes/filters/labels/links, logo wiring, visible URLs, company aliases/empty grouping, and literal-hash escaping. Expected Typst package imports read `typst-package-versions.json`, avoiding hardcoded old versions. Failed tests preserve their temporary work directory for investigation.

Use real resumes as well as synthetic fixtures: several bugs only appeared with missing fields, extensionless photos, unusual work data, and Markdown notes. Container tests passing does not prove every renderer branch is covered.

Theme development is separate:

```sh
cd themes/jsonresume-theme-eventide
npm ci
npm run build
npm run dev
npm run build-editor
npm run type-check
npm run format -- --check
npm test -- --run
```

Theme `prepare` installs Husky hooks and builds. Pre-commit runs lint-staged; pre-push runs tests. `npm test` alone starts Vitest watch mode. CI verifies types, formatting, and coverage. Stale local dependencies can explain formatting differences from CI; start with `npm ci`.

Snapshot-only whitespace changes caused repeated failures during note work. If the resulting HTML is intentional and valid, update/review snapshots rather than repeatedly distorting correct rendering to satisfy an obsolete fixture.

Update the theme in its own repository first, then select the intended commit/tag in the toolkit submodule, commit the submodule pointer, refresh the root lockfile, and rebuild/test. `.gitmodules` still specifies `branch = feat-multiple-features`; do not assume the tracking branch is `main` or that a submodule update automatically chooses the latest npm release.

Developer preview restart support lives in `dev_serve.py`. It forwards arguments to `build-resume.sh`, watches the local image ID, and restarts after rebuilds. It evolved from shell code because signal handling, forced TTY allocation, and orphan containers were troublesome. Current source/help still contains old `dev-serve.sh` references although that shell path is absent in this checkout; check the real entry point before documenting invocations. This helper watches local image changes, not remote registry updates.

## Version Management and Publishing

Toolkit release flow:

```sh
mise run release patch
mise run release minor
mise run release major
```

The task pulls the branch, updates `VERSION`, commits `Release vX.Y.Z`, creates an annotated `vX.Y.Z` tag, and pushes branch/tags. Review its actual behavior before running: releasing is a publishing operation. Maintain human-readable `ChangeLog.md` entries grouped by dated release, with one user-facing feature/fix per bullet. Preserve previously published entries when adding missing or upcoming releases.

GitHub Actions builds/tests and publishes releases to GHCR and Docker Hub. Publishing occurs for `v*` tags, with `latest` retained and no branch/SHA publication tags. Current metadata also generates semantic-version aliases. Tag and VERSION must match. Manual dispatch can build/test without publishing. GHCR uses the automatic Actions `GITHUB_TOKEN` with `packages: write`; public package visibility is a registry setting.

Eventide releases use `npm version patch|minor|major`, push the commit and annotated version tag, and publish to npm through a workflow that verifies tag/package agreement and provenance. Its own mise release task wraps that process. Toolkit releases do not publish Eventide.

Version update tasks:

```sh
mise run update-node-version
mise run update-python-version
mise run update-runtime-versions
mise run update-typst-version
mise run update-typst-package-versions
mise run update-all-versions
```

- `typst-package-versions.json` centralizes all three managed Typst package versions. Renderers, reported versions, cache prewarming, and relevant tests read it.
- Typst binary update checks GitHub releases and edits `ARG TYPST_VERSION`.
- Typst package update checks the official package repository for every configured package.
- `runtime-versions.json` records Node major and host Python version; updater scripts edit it together with the corresponding Dockerfile/mise declaration.
- Node update selects the latest LTS major from the official release index. Patch updates within that major are inherited when the base image is refreshed.
- Python update selects the newest supported stable branch and latest actual final release from the Python release metadata, excluding prereleases.
- These are explicitly invoked maintenance tasks, not a scheduled update service. Rebuild and test after updates.
- The Python updater does not pin or update Alpine's Python package independently. Do not describe it as controlling the container Python version.
- The current root Dependabot config checks Python/uv and GitHub Actions weekly. Theme npm dependencies are maintained in the theme repository. The root does use Resumed, but there is currently no root npm update entry; monitoring Resumed separately remains a maintenance consideration.

## Development Guidelines and User Preferences

- Read `AGENTS.md`, `DEVELOPMENT.md`, and the relevant repository's documentation before changes.
- Keep shell/Python helpers straightforward, use strict shell mode, explicit paths, and generic naming. Match existing style.
- Prefer small, focused edits; preserve unrelated work and never discard user changes.
- Update public CLI parsing/help and tests together when adding commands or flags.
- Prefer schema-compatible data; keep extensions documented. Missing data should suppress placeholders rather than crash or display package sample content.
- Track shared-helper callers across CV and standalone PDF scripts; past refactors left stale imports and undefined variables in one caller.
- Test behavior through the container wrapper for container-facing changes. For UI work inspect actual generated HTML and responsive layouts; snapshots alone do not establish visual correctness.
- Keep source JSON unchanged during builds. Clearly distinguish updating commands from rendering commands.
- Avoid rebuilding identical metadata assumptions in multiple places. Version centralization and pre-render normalization are deliberate simplifications.
- Documentation ownership: toolkit README explains user configuration and toolkit effects; theme README owns theme behavior; each DEVELOPMENT.md owns its maintainer workflows. Avoid duplicating entire theme option documentation in the toolkit.
- The user prefers practical implementation, concise communication, and complete verification. When asked only for ideas or explanations, do not modify files.
- Commit messages should have a short imperative subject. When asked for a release/feature message, describe the overall user benefit, not a file-by-file inventory.
- Generated `build/` artifacts normally stay out of git. Do not commit credentials, personal private input, or obsolete generated asset directories.

## Historical Milestones

- `v0.1.0`: reusable toolkit separated from personal content; JSON-driven bibliography sources; standalone Typst publications PDF; configurable publication links.
- `v0.2.x`: expanded schema rendering, configurable PDF layout, references/education/certification improvements, samples, assets and automatic logo fetching, bibliography sorting and filtering, shared publication colors.
- `v0.3.x`: full standalone versus filtered inline publications; JSON inline-publication updates; canonical/visible PDF URLs and footer URLs; better defaults and robustness for real-world resumes; brilliant-cv 3.3.0.
- `v0.4.x`: Eventide fork adoption; opt-in image pulling; GHCR publishing and default image migration.
- `v0.5.x`: logo URL injection/update-logos; mobile publications navigation; theme/footer and maintenance improvements.
- `v0.6.x`: Docker/Podman interoperability and Typst text escaping fixes.
- `v0.7.x`: brilliant-cv v4 migration, centralized package pins and update tooling, improved version reporting, maintainer documentation, and runtime maintenance tasks.

Use `git log`, tags, and `ChangeLog.md` for exact release boundaries. The changelog currently stops at v0.7.0 even though VERSION is 0.7.1.

## Known Context Gaps and Follow-up Considerations

These are observations for a future maintainer, not work requested by this handoff:

- Some README PDF layout examples still reflect pre-v4 defaults (including section highlight placement). Prefer current renderer code and upstream v4 signatures when reconciling them.
- The package loader still has a hardcoded brilliant-cv `3.3.0` fallback if its version JSON cannot be read. That is a stale implementation detail, not a supported v3 compatibility mode; normal containers include the version file.
- The Dockerfile downloads x86_64 Linux-musl Typst/watchexec binaries explicitly. macOS wrapper compatibility does not imply a native ARM64 container build.
- Several updater scripts use GNU-style `sed -i`, `sort -V`, or Bash features. Host-side maintainer portability needs separate verification from normal container use on macOS.
- Runtime version state duplicates values in Dockerfile/mise. Updaters synchronize them; builds do not dynamically read the runtime JSON as configuration.
- The host cache directory option is initialized by the wrapper, but verify actual mount behavior before promising persistent cache semantics. Package cache prewarming inside the image is explicit.
- A requested name-only publications header may need checking against current v4 emitted metadata, which reuses personal information.
- Eventide note rendering and PDF note rendering need consistent outcomes despite separate detection paths.
- Theme tests cover more than the initial three snapshot/HTML checks; use the current test source rather than old conversation counts.
- Historical proposals, such as printing the publications PDF when the browser prints HTML or extracting Typst into templates, should not be assumed implemented.

Both checked-in `.codex` marker files are empty. No additional Codex transcript was obtained from those files. This document is grounded in the supplied conversation, source inspection, local commit history, and project documentation; it does not assert that the full integration suite was rerun when preparing the handoff.
