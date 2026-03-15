---
title: CRD Viewer
---

# CRD Viewer Plugin

Render Kubernetes **CustomResourceDefinition** schemas as interactive, expandable reference documentation — directly in your MkDocs pages.

!!! tip "Try it"
    Click on any field below to expand its children. Use **Expand All** to open the full tree at once.

## Fabric

The `Fabric` resource models a leaf-spine network fabric in EDA.
It declares the set of leaf and spine nodes, inter-switch link policy,
address allocation, and routing protocols that make up the underlay and overlay.

-{{ crd_viewer("crds/fabrics.eda.nokia.com.yaml", title="Fabric", show_status=True) }}-

### Example resource

```yaml
apiVersion: fabrics.eda.nokia.com/v1alpha1
kind: Fabric
metadata:
  name: myfabric-1
  namespace: eda
spec:
  leafs:
    leafNodeSelector:
      - eda.nokia.com/role=leaf
  spines:
    spineNodeSelector:
      - eda.nokia.com/role=spine
  interSwitchLinks:
    linkSelector:
      - eda.nokia.com/role=interSwitch
    unnumbered: IPV6
  systemPoolIPV4: systemipv4-pool
  underlayProtocol:
    protocol:
      - EBGP
    bgp:
      asnPool: asn-pool
  overlayProtocol:
    protocol: EBGP
```

## Usage

This project currently exposes one macro, `crd_viewer(...)`, with multiple call patterns.

Add the plugin to your `mkdocs.yml` and call the macro from any page:

=== "Macro call"

    -{{% raw %}}-
    ```jinja
    -{{ crd_viewer("path/to/crd.yaml") }}-
    ```
    -{{% endraw %}}-

=== "mkdocs.yml"

    ```yaml
    plugins:
      - crd-viewer
      - macros:
          modules:
            - mkdocs_crd_plugin.macros
    ```

| Parameter      | Type   | Default          | Description                               |
| -------------- | ------ | ---------------- | ----------------------------------------- |
| `path`         | string | —                | Path to the CRD YAML file                 |
| `version`      | string | storage version  | CRD version to render                     |
| `title`        | string | kind name        | Display title                             |
| `collapsed`    | bool   | `False`          | Wrap in a collapsible `<details>` element |
| `show_status`  | bool   | `True`           | Include the status section                |

### Settings preview

Use this section to compare how each setting changes the rendered output.

#### 1. Default output

-{{% raw %}}-
```jinja
-{{ crd_viewer("crds/fabrics.eda.nokia.com.yaml") }}-
```
-{{% endraw %}}-

-{{ crd_viewer("crds/fabrics.eda.nokia.com.yaml") }}-

#### 2. Pin version

-{{% raw %}}-
```jinja
-{{ crd_viewer("crds/fabrics.eda.nokia.com.yaml", version="v1alpha1", title="Pinned version: v1alpha1") }}-
```
-{{% endraw %}}-

-{{ crd_viewer("crds/fabrics.eda.nokia.com.yaml", version="v1alpha1", title="Pinned version: v1alpha1") }}-

#### 3. Hide status section

-{{% raw %}}-
```jinja
-{{ crd_viewer("crds/fabrics.eda.nokia.com.yaml", title="Spec only", show_status=False) }}-
```
-{{% endraw %}}-

-{{ crd_viewer("crds/fabrics.eda.nokia.com.yaml", title="Spec only", show_status=False) }}-

#### 4. Collapsed view

-{{% raw %}}-
```jinja
-{{ crd_viewer("crds/fabrics.eda.nokia.com.yaml", title="Collapsed + spec only", collapsed=True, show_status=False) }}-
```
-{{% endraw %}}-

-{{ crd_viewer("crds/fabrics.eda.nokia.com.yaml", title="Collapsed + spec only", collapsed=True, show_status=False) }}-
