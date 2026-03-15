# MkDocs CRD Viewer

`mkdocs-crd-viewer` renders Kubernetes CRD schemas as interactive, expandable tree views inside MkDocs pages.

The package provides:
- `crd-viewer` MkDocs plugin for CSS/JS asset wiring.
- `crd_viewer(...)` macro for rendering CRD schemas from Markdown.

## Install

```bash
uv sync
```

Or install directly from GitHub with `uv add`:

```bash
uv add "mkdocs-crd-viewer @ git+https://github.com/eda-labs/mkdocs-crd-viewer@main"
```

Replace `@main` with a tag if you want a fixed release (for example `@v0.1.0`).

## Configure

In your `mkdocs.yml`:

```yaml
plugins:
  - search
  - crd-viewer
  - macros:
      modules:
        - mkdocs_crd_viewer.macros
```

If you need custom Jinja delimiters, the demo config in `demo/mkdocs.yml` shows a working setup with `-{{ ... }}-`.

## Macro Reference

There is currently one macro:

```python
crd_viewer(path, version=None, title=None, collapsed=False, show_status=True, copy_skeleton=True)
```

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `path` | `str` | required | Relative or absolute path to a CRD YAML file. Relative paths resolve from the MkDocs project root. |
| `version` | `str \| None` | storage version | CRD version to render. Falls back to storage, then served, then first entry. |
| `title` | `str \| None` | selected kind | Override the viewer title. |
| `collapsed` | `bool` | `False` | Render the viewer in an initially collapsed state. |
| `show_status` | `bool` | `True` | Include the `status` schema section when available. |
| `copy_skeleton` | `bool` | `True` | Show an icon-only copy action that copies a verbose scaffold with aligned `# required` / `# optional` comments (status is never included). |

Each file should contain exactly one `CustomResourceDefinition` document.

## Usage Patterns

Default call:

```jinja
-{{ crd_viewer("crds/fabrics.eda.nokia.com.yaml") }}-
```

Select a specific version and custom title:

```jinja
-{{ crd_viewer("crds/fabrics.eda.nokia.com.yaml", version="v1alpha1", title="Fabric (v1alpha1)") }}-
```

Collapsed/spec-only view:

```jinja
-{{ crd_viewer("crds/fabrics.eda.nokia.com.yaml", collapsed=True, show_status=False) }}-
```

## Plugin Configuration

`crd-viewer` accepts:

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `asset_dir` | `str` | `assets/mkdocs-crd-viewer` | Output path (inside `site_dir`) for `crd-viewer.css` and `crd-viewer.js`. |

## Demo and Tests

Run the demo site:

```bash
uv run mkdocs serve -f demo/mkdocs.yml
```

Run tests:

```bash
uv run pytest
```
