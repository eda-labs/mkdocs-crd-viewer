from pathlib import Path
import textwrap

import pytest

from mkdocs_crd_plugin.core import CrdRenderError, load_crd_view, render_crd_viewer


def write_file(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def test_load_crd_view_selects_storage_version(tmp_path: Path) -> None:
    source = tmp_path / "example.yaml"
    write_file(
        source,
        """
        apiVersion: apiextensions.k8s.io/v1
        kind: CustomResourceDefinition
        metadata:
          name: widgets.example.com
        spec:
          group: example.com
          names:
            kind: Widget
            plural: widgets
          scope: Namespaced
          versions:
            - name: v1alpha1
              served: true
              storage: false
              schema:
                openAPIV3Schema:
                  type: object
                  properties:
                    spec:
                      type: object
                      properties:
                        field:
                          type: string
            - name: v1
              served: true
              storage: true
              schema:
                openAPIV3Schema:
                  type: object
                  properties:
                    spec:
                      type: object
                      properties:
                        field:
                          type: integer
        """,
    )

    view = load_crd_view(source)

    assert view.version == "v1"
    assert view.sections[0].children[0].field_type == "integer"


def test_load_crd_view_rejects_multiple_crds_in_single_file(tmp_path: Path) -> None:
    source = tmp_path / "example.yaml"
    write_file(
        source,
        """
        apiVersion: apiextensions.k8s.io/v1
        kind: CustomResourceDefinition
        metadata:
          name: widgets.example.com
        spec:
          group: example.com
          names:
            kind: Widget
            plural: widgets
          versions:
            - name: v1
              served: true
              storage: true
              schema:
                openAPIV3Schema:
                  type: object
                  properties:
                    spec:
                      type: object
        ---
        apiVersion: apiextensions.k8s.io/v1
        kind: CustomResourceDefinition
        metadata:
          name: gadgets.example.com
        spec:
          group: example.com
          names:
            kind: Gadget
            plural: gadgets
          versions:
            - name: v1
              served: true
              storage: true
              schema:
                openAPIV3Schema:
                  type: object
                  properties:
                    spec:
                      type: object
        """,
    )

    with pytest.raises(CrdRenderError, match="Multiple CustomResourceDefinition documents found"):
        load_crd_view(source)


def test_render_crd_viewer_outputs_spec_status_and_metadata(tmp_path: Path) -> None:
    source = tmp_path / "example.yaml"
    write_file(
        source,
        """
        apiVersion: apiextensions.k8s.io/v1
        kind: CustomResourceDefinition
        metadata:
          name: widgets.example.com
        spec:
          group: example.com
          names:
            kind: Widget
            plural: widgets
          versions:
            - name: v1
              served: true
              storage: true
              schema:
                openAPIV3Schema:
                  type: object
                  properties:
                    spec:
                      type: object
                      description: WidgetSpec defines the desired state.
                      required:
                        - size
                      properties:
                        size:
                          type: string
                          enum: [small, medium]
                          description: Selected size.
                        labels:
                          type: object
                          additionalProperties:
                            type: string
                    status:
                      type: object
                      description: WidgetStatus defines the observed state.
                      properties:
                        phase:
                          type: string
        """,
    )

    html = render_crd_viewer(project_root=tmp_path, source="example.yaml", collapsed=True)

    assert "SPEC" in html
    assert "STATUS" in html
    assert "<summary>Widget</summary>" in html
    assert "Selected size." in html
    assert "enum" in html
    assert "&lt;key&gt;" in html


def test_scalar_array_renders_inline_without_items_child(tmp_path: Path) -> None:
    source = tmp_path / "example.yaml"
    write_file(
        source,
        """
        apiVersion: apiextensions.k8s.io/v1
        kind: CustomResourceDefinition
        metadata:
          name: fabrics.example.com
        spec:
          group: example.com
          names:
            kind: Fabric
            plural: fabrics
          versions:
            - name: v1alpha1
              served: true
              storage: true
              schema:
                openAPIV3Schema:
                  type: object
                  properties:
                    spec:
                      type: object
                      properties:
                        leafNodeSelector:
                          type: array
                          items:
                            type: string
        """,
    )

    html = render_crd_viewer(project_root=tmp_path, source="example.yaml")

    assert "array[string]" in html
    assert ">items<" not in html
