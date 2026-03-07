# Resume Toolkit - JSONresume/BibTeX to HTML/PDF

- [Requirements](#orge0cfd3e)
- [Quick Start](#org90b52ae)
- [Output Layout](#org1334766)
- [Main Commands](#org8964c26)
  - [`build` (default)](#org6cb0f47)
  - [`fetch-logos`](#orgd64b9f2)
  - [`update-certs`](#orgdc97180)
  - [`update-pub-numbers`](#orgeb8b253)
  - [Other passthrough subcommands](#org23204b4)
- [Environment Variables](#orgc2ef02d)
- [Under the Hood](#org79da12a)
  - [Automated Tests](#org487a931)

---

This project provides a reusable build pipeline for generating:

-   Resume HTML (from JSON Resume, using a customized version of [jsonresume-theme-even](https://github.com/rbardini/jsonresume-theme-even))
-   Resume PDF (from Typst generated from JSON Resume and using the [brilliant-cv](https://typst.app/universe/package/brilliant-cv) Typst template)
-   Publications HTML (from BibTeX)
-   Publications PDF (from LaTeX/BibTeX, using [AwesomeCV](https://github.com/posquit0/Awesome-CV), so it looks the same as the resume PDF)
-   Aggregated publications BibTeX

The recommended interface is the wrapper script `build-resume.sh`, which runs everything inside a [Docker image](https://hub.docker.com/repository/docker/zzamboni/resume-toolkit/settings).


<a id="orge0cfd3e"></a>

## Requirements and installation

-   Docker
-   A file in [JSON Resume](https://jsonresume.org/) format
-   Optional BibTeX file(s) for publications

If no BibTeX files are provided, the publications output is skipped.

To install, download the [build-resume.sh](https://github.com/zzamboni/resume-toolkit/blob/main/build-resume.sh) script and make it executable:

``` sh
wget https://raw.githubusercontent.com/zzamboni/resume-toolkit/refs/heads/main/build-resume.sh
chmod a+rx build-resume.sh
```

The first time the script runs, it will download the Docker image automatically.

<a id="org90b52ae"></a>

## Quick Start

Build a Resume + publications:

```sh
./build-resume.sh resume.json pubs-src/publications.bib
```

Build, watch changes, and serve output:

```sh
./build-resume.sh resume.json pubs-src/publications.bib --watch --serve
```

Then open:

-   `http://localhost:8080`


<a id="org1334766"></a>

## Output Layout

Default output base directory:

-   `build/<resume-stem>/`

Generated files:

-   `build/<resume-stem>/vita/index.html`
-   `build/<resume-stem>/vita/<resume-stem>.typ`
-   `build/<resume-stem>/vita/<resume-stem>.pdf`
-   `build/<resume-stem>/vita/publications/index.html` (if BibTeX provided)
-   `build/<resume-stem>/vita/publications/<resume-stem>-pubs.pdf` (if BibTeX provided)
-   `build/<resume-stem>/vita/publications/<resume-stem>-pubs.bib` (if BibTeX provided)


<a id="org8964c26"></a>

## Main Commands


<a id="org6cb0f47"></a>

### `build` (default)

These are equivalent:

```sh
./build-resume.sh build resume.json pubs-src/publications.bib
./build-resume.sh resume.json pubs-src/publications.bib
```

Options:

-   `--out <dir>`: output base directory
-   `--pubs-url <url>`: online publications URL for PDF footer
-   `--watch`: rebuild on input changes
-   `--serve`: start HTTP server (implies `--watch`)

If no BibTeX files are provided on the command line, the pipeline can read them from `publications[].bibfiles` in your JSON resume:

```json
"publications": [
  {
    "name": "Full list online",
    "url": "/vita/publications/",
    "authors": ["Diego Zamboni"],
    "bibfiles": ["pubs.bib", "patents.bib"]
  }
]
```

`bibfiles` entries are resolved relative to the JSON resume file location. If `--bib` arguments are provided, they take precedence.

If one publication entry has `"inline_in_pdf"`, the resume PDF embeds the aggregated publications list directly using Typst's `#cv-publication(...)` support. HTML publications generation is unchanged.

-   If `"inline_in_pdf": true`, defaults are used:
    -   `ref-style: "ieee"`
    -   `ref-full: true`
    -   `key-list: []`
-   You can also pass a dictionary, and its keys/values are forwarded to `bibliography(...)`, for example:

```json
"inline_in_pdf": {
  "ref-style": "ieee",
  "ref-full": true,
  "key-list": []
}
```

```json
"publications": [
  {
    "name": "Full list online",
    "url": "/vita/publications/",
    "authors": ["Diego Zamboni"],
    "bibfiles": ["pubs.bib"],
    "inline_in_pdf": true
  }
]
```

Note: inlining entries only works in the PDF output for now. It's recommended to leave a "link entry" like the above so that the HTML output links to the separate publications page.


<a id="orgd64b9f2"></a>

### `fetch-logos`

Download company/institution logos from the resume file into `assets/logos/` in your working directory. Uses [logo.dev](https://www.logo.dev/) to fetch logos. You need to create an API key and provide the publishable key in the `LOGODEV_TOKEN` environment variable, or using the `--token` flag.

If matching logo files are found under `assets/logos/`, the `build` step will include them automatically in the generated PDF. You can also provide/update the images by hand with the appropriate name.

```sh
./build-resume.sh fetch-logos resume.json
```

Options:

-   `--overwrite`
-   `--dry-run`
-   `--token <token>` (or set `LOGODEV_TOKEN`)


<a id="orgdc97180"></a>

### `update-certs`

Sync certificates from Credly into your JSON resume. This replaces any entries in the `certificates` section of the JSONresume file that have a `url` field pointing to `credly.com`. Other entries are left untouched.

```sh
./build-resume.sh update-certs <credly-username> resume.json
```

Options:

-   `--include-expired`
-   `--include-non-cert-badges`
-   `--sort <date_desc|date_asc|name>` (default `date_desc`)


<a id="orgeb8b253"></a>

### `update-pub-numbers`

Update publication reference numbers in your JSON resume using the generated publications HTML anchors.

```sh
./build-resume.sh update-pub-numbers resume.json
```

Options:

-   `--html <path>` (defaults to `build/<resume-stem>/vita/publications/index.html`)


<a id="org23204b4"></a>

### Other passthrough subcommands

You can also call container entrypoint commands directly, for example:

```sh
./build-resume.sh tasks
./build-resume.sh shell
```

`tasks` lists the `mise` tasks available inside the container (you can add `--hidden` to see internal tasks), and `shell` gives you an interactive shell inside the container.

## Even theme extensions

The version of jsonresume-theme-even used by this toolkit supports the following additional options (described also in [jsonresume-them-even PR#33](https://github.com/rbardini/jsonresume-theme-even/pull/33)):

### Icons

By default, [Feather icons](https://feathericons.com/) are used for the profiles. You can also use [Font Awesome icons](https://fontawesome.com/) by setting the `.meta.themeOptions.icons` resume field to "fontawesome":

```json
{
  "meta": {
    "themeOptions": {
      "icons": "fontawesome"
    }
  }
}
```

### Certificate badges and notes

If a [certificate](https://docs.jsonresume.org/schema#certificates) entry contains an `image` field, it is used as the URL of an image to display next to the entry as a badge for the certificate.

If a certificate entry contains only `name` and optionally `url` but no `issuer` or `date`, it is considered as a "note" entry and rendered at the top of the list in a different format (for example to link to a full list).

### Grouping projects by type

If the `.meta.themeOptions.projectsByType` is `true`, project entries are rendered as separate sections according to their `type` field, instead of as a single section.

### Sections

#### Ordering

You can override what sections are displayed, and in what order, via the `.meta.themeOptions.sections` resume field.

Here's an example with all available sections in their default order:

```json
{
  "meta": {
    "themeOptions": {
      "sections": [
        "work",
        "volunteer",
        "education",
        "projects",
        "awards",
        "certificates",
        "publications",
        "skills",
        "languages",
        "interests",
        "references"
      ]
    }
  }
}
```

Any sections not in the above list are not registered and won't be displayed in the final render.

#### Custom Labels

You can override the default section labels. Particularly useful if you want to translate a resume into another language.

```json
{
  "meta": {
    "themeOptions": {
      "sectionLabels": {
        "work": "Jobs",
        "projects": "Projekter"
      }
    }
  }
}
```

If `.meta.themeOptions.projectsByType` is `true`, you can also break out project types into individually ordered sections by using `projects:<type>` entries. For example:

```json
{
  "meta": {
    "themeOptions": {
      "projectsByType": true,
      "sections": ["work", "projects:application", "projects:library", "skills"],
      "sectionLabels": {
        "projects:application": "Apps",
        "projects:library": "Libraries"
      }
    }
  }
}
```

### Table of contents

You can enable a floating table of contents on the right side of the screen by setting `.meta.themeOptions.showTableOfContents` to `true`:

```json
{
  "meta": {
    "themeOptions": {
      "showTableOfContents": true
    }
  }
}
```

The table of contents automatically includes links to all resume sections that have content, plus a "Top" link to return to the beginning of the document. The active section is highlighted as you scroll through the resume. The table of contents is automatically hidden on smaller screens and in print mode.

### Floating links

You can add floating action links in the bottom-right corner by setting `.meta.themeOptions.links` to an array of `{ name, url, icon }` objects. The `icon` name is looked up in FontAwesome.

```json
{
  "meta": {
    "themeOptions": {
      "links": [
        { "name": "PDF", "url": "/vita/zamboni-vita.pdf", "icon": "file-pdf" },
        { "name": "GitHub", "url": "https://github.com/zzamboni", "icon": "github" }
      ]
    }
  }
}
```

<a id="orgc2ef02d"></a>

## Environment Variables

-   `VITA_PIPELINE_IMAGE`: Docker image (default: `zzamboni/resume-toolkit:latest`)
-   `VITA_SERVE_PORT`: serve port (default: `8080`)
-   `VITA_PIPELINE_CACHE_DIR`: host cache dir for container caches
-   `LOGODEV_TOKEN`: token used by `fetch-logos`


<a id="org79da12a"></a>

## Under the Hood

The wrapper runs:

-   containerized entrypoint in `docker/entrypoint.sh`
-   pipeline script `scripts/run_pipeline.sh`
-   supporting converters in `scripts/`

The container uses a customized version of `themes/jsonresume-theme-even` as a git submodule, cloned from <https://github.com/zzamboni/jsonresume-theme-even/tree/feat-multiple-features>.

Clone with submodules enabled:

```sh
git clone --recurse-submodules https://github.com/zzamboni/resume-toolkit.git
```

If you already cloned without submodules:

```sh
git submodule update --init --recursive
```

All the `build-resume.sh` functionality is implemented through `mise` tasks inside the container. If you want to run these on your host machine and not inside the container, make sure you have [mise](https://mise.jdx.dev/) installed, then you can check out this repository and initialize the mise environment:

``` sh
git clone https://github.com/zzamboni/resume-toolkit.git
cd resume-toolkit
mise trust .
mise install
HUSKY=0 NPM_CONFIG_IGNORE_SCRIPTS=true mise run bootstrap
```

You can then run the `mise` tasks directly, with the same parameters described above for `build-resume.sh`, e.g.:

``` sh
mise build resume.json pubs-src/publications.bib --watch --serve
mise fetch-logos resume.json
mise update-certs <credly-username> resume.json
```

You can build the Docker image locally with:

``` sh
mise pipeline-image-build
```

Use `mise tasks --hidden` to see all the tasks, including development and testing:

``` sh
Name                  Description
bootstrap             Install/update project dependencies (Python + npm)
build                 Run CV + publications pipeline
docker-shell          Open an interactive shell in the Docker image
fetch-logos           Fetch company/education logos from JSON resume into /work assets
pipeline-docker       Run pipeline through standalone Docker image
pipeline-image-build  Build standalone pipeline Docker image
test-container        Run container integration tests
update-certs          Update certificates from credly
update-pub-numbers    Update publication reference numbers in JSON resume
```

<a id="org487a931"></a>

### Automated Tests

Container integration tests live under `tests/container/` and validate:

-   exposed task list
-   end-to-end build outputs
-   logo-fetch command wiring

Run tests:

```sh
tests/container/test_container.sh
```

Optionally test a specific image:

```sh
tests/container/test_container.sh myorg/vita-pipeline:latest
```

Or via mise:

```sh
mise run test-container
```
