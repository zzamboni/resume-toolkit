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

The recommended interface is the wrapper script `build-resume.sh`, which runs everything inside a Docker image.


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
./build-resume.sh fetch-logos resume.json --overwrite
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

The \`mise\` tasks are intentionally minimal and user-facing:

-   `build`
-   `fetch-logos`
-   `update-certs`

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
