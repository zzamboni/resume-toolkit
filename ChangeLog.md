# ChangeLog

(AI-generated from git log, human-polished)

## 2026-03-26 - v0.3.4
- Updated brilliant-cv used for PDF rendering from 3.1.2 to 3.3.0.

## 2026-03-25 — v0.3.3
- Improved remote image handling so profile photos without a file extension are saved with the correct image format and cleaner filenames.
- Suppressed brilliant-cv fallback placeholders for missing work and education locations by rendering them as empty values in the PDF output.
- Ensured the HTML CV is always rendered with the bundled `jsonresume-theme-even` theme, even when the source JSON specifies a different theme.
- Added intelligent default floating links to the HTML CV, including a PDF link and, when available, a link to the standalone publications page.
- Suppressed the default profile photo in the PDF output when no profile image is available.
- Added support for `work.company` as an alternative to `work.name` in PDF rendering and prevented empty-company work entries from being grouped together.

## 2026-03-25 — v0.3.2
- Restored the resume owner's name in the standalone publications PDF header while keeping the extra info fields hidden.

## 2026-03-24 — v0.3.1
- Made note-style publications and certifications render more consistently in the PDF output.
- Added `meta.site.url` so relative links are converted to absolute URLs in PDF output while remaining relative in HTML.
- Added `meta.pdfthemeOptions.visible_urls` to optionally show compact printable URLs for notes, profiles, and projects in PDFs.
- Added `meta.pdfthemeOptions.pubs_url` and `meta.pdfthemeOptions.cv_url` to place canonical links in the PDF footers.

## 2026-03-22 — v0.3.0
- Added `bibentries` and `bibkeywords` filters so inline publications can be selected from BibTeX sources by entry key or keyword.
- Added `full_standalone_list` controls so the full bibliography can remain available on the standalone publications page while a filtered subset is shown inline in the CV.
- Added `full_standalone_list_title` to give the standalone publications page and PDF their own title independent of the CV section label.
- Added the `update-inline-pubs` command to write the selected BibTeX entries back into the JSON Resume `publications` section for HTML rendering.
- Added a `mise release` task to update the project version, create a release tag, and push it.
- Improved the publications footer so a configured publications URL is rendered clearly in its own line.

## 2026-03-21 — v0.2.2
- Made the publications HTML page follow the same configurable color scheme as the main HTML CV theme.
- Bundled the Font Awesome license files required by the generated assets.

## 2026-03-19 — v0.2.1
- Renamed inline publication key selection from `ref-keys` to `bibentries` and added `bibkeywords` filtering for BibTeX sources.

## 2026-03-19 — v0.2.0
- Added placeholder support for `<resume>` and `<publications>` in configured links so generated filenames can be referenced without hardcoding them.
- Added support for local profile images and improved local asset resolution.
- Expanded Typst/PDF rendering to cover the full JSON Resume schema while preserving the toolkit's custom extensions.
- Added JSON configuration for brilliant-cv layout options, including section heading controls and summary title handling.
- Rendered references as quotes in the PDF output.
- Improved certificate rendering in the PDF, including better handling of entries with and without badge images.
- Added automatic logo downloading when logo assets are missing, with a way to disable it explicitly.
- Added configurable sorting for inline PDF bibliographies.
- Added bundled sample resumes.
- Improved local asset lookup and icon fallback behavior.

## 2026-03-11 — v0.1.0
- Added support for specifying BibTeX sources directly in the JSON Resume file and for rendering publications inline in the PDF CV.
- Added `meta.publicationsOptions` so publications behavior can be configured from the JSON input.
- Added standalone publications PDF generation with Typst (before it was still done with LaTeX).
- Reworked the Docker image build to reduce runtime size and improve caching controls.
- Moved BibTeX source configuration into the `publications` section so generated publications content is driven by the resume data itself.
- Added configurable floating links for the publications HTML page.
- Switched publications floating-link icons to embedded Font Awesome SVGs resolved from npm packages.
- Added support for Font Awesome style-prefixed icon names in the bundled HTML theme.
- Separated toolkit from content so it's reusable with arbitrary JSONresume files.
