# MkDocs CRD Plugin

`mkdocs-crd-plugin` renders Kubernetes CRD schemas as an inline, expandable tree view inside MkDocs pages.

It is designed to work with `mkdocs-macros-plugin`, so documentation authors can reference a CRD file from Markdown and get a schema browser similar to `crd.eda.dev`.

## Install

```bash
uv sync
```

In your `mkdocs.yml`:

```yaml
plugins:
  - search
  - crd-viewer
  - macros:
      modules:
        - mkdocs_crd_plugin.macros
```

Then use the macro in Markdown:

```md
-{{ crd_viewer("crds/fabrics.eda.nokia.com.yaml", kind="Fabric") }}-
```

## Quick Test

Run the demo site locally:

```bash
uv run mkdocs serve -f demo/mkdocs.yml
```

Run the automated tests:

```bash
uv run pytest
```
