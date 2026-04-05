# Documentation Site

## Local Preview

```bash
pip install mkdocs-material  # first time only
mkdocs serve
```

Open http://localhost:8000

## Publishing

The docs auto-publish to GitHub Pages via `.github/workflows/docs.yml` on push to main when docs or mkdocs.yml change.

## Adding New Pages

1. Create the markdown file in the appropriate `docs/` subdirectory
2. Add it to the `nav:` section in `mkdocs.yml`
3. Cross-link from related pages
