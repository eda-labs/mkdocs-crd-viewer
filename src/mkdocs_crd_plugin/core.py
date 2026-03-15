"""Core CRD parsing and HTML rendering logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import html
import itertools
import json
import re

import yaml


_RENDER_COUNTER = itertools.count()


class CrdRenderError(ValueError):
    """Raised when a CRD cannot be loaded or rendered."""


@dataclass(slots=True)
class FieldNode:
    """Normalized view of a schema field."""

    label: str
    path: str
    field_type: str
    description: str = ""
    required: bool = False
    children: list["FieldNode"] = field(default_factory=list)
    default: Any = None
    enum: list[Any] = field(default_factory=list)
    field_format: str | None = None
    minimum: Any = None
    maximum: Any = None


@dataclass(slots=True)
class Section:
    """Top-level section shown in the viewer."""

    key: str
    title: str
    description: str
    children: list[FieldNode]


@dataclass(slots=True)
class CrdView:
    """Resolved CRD and schema to render."""

    source_path: Path
    kind: str
    group: str
    version: str
    sections: list[Section]


def render_crd_viewer(
    project_root: Path,
    source: str,
    *,
    version: str | None = None,
    title: str | None = None,
    collapsed: bool = False,
    show_status: bool = True,
) -> str:
    """Render a CRD from disk into HTML suitable for MkDocs pages."""

    source_path = _resolve_source_path(project_root, source)
    view = load_crd_view(source_path, version=version, show_status=show_status)
    return _render_view(view, title=title, collapsed=collapsed)


def load_crd_view(
    source_path: Path,
    *,
    version: str | None = None,
    show_status: bool = True,
) -> CrdView:
    """Load a CRD YAML file and normalize the selected schema."""

    if not source_path.exists():
        raise CrdRenderError(f"CRD file not found: {source_path}")

    with source_path.open("r", encoding="utf-8") as handle:
        documents = [doc for doc in yaml.safe_load_all(handle) if isinstance(doc, dict)]

    crds = [doc for doc in documents if doc.get("kind") == "CustomResourceDefinition"]
    if not crds:
        raise CrdRenderError(f"No CustomResourceDefinition documents found in {source_path}")

    if len(crds) > 1:
        available = ", ".join(
            f"{(doc.get('spec') or {}).get('group')}/{((doc.get('spec') or {}).get('names') or {}).get('kind')}"
            for doc in crds
        )
        raise CrdRenderError(
            f"Multiple CustomResourceDefinition documents found in {source_path}. "
            f"Keep one CRD per file. Found: {available}"
        )

    crd = crds[0]
    spec = crd.get("spec") or {}
    selected_kind = (spec.get("names") or {}).get("kind")
    selected_group = spec.get("group")

    versions = spec.get("versions")
    if not isinstance(versions, list) or not versions:
        raise CrdRenderError(f"CRD {selected_kind} in {source_path} does not define spec.versions")

    version_entry = _select_version(versions, version)
    selected_version = version_entry.get("name")
    schema = ((version_entry.get("schema") or {}).get("openAPIV3Schema")) or {}
    if not isinstance(schema, dict) or not schema:
        raise CrdRenderError(
            f"CRD {selected_kind} {selected_version} in {source_path} is missing schema.openAPIV3Schema"
        )

    sections = _build_sections(schema, show_status=show_status)
    if not sections:
        raise CrdRenderError(
            f"CRD {selected_kind} {selected_version} in {source_path} has no renderable spec/status schema"
        )

    return CrdView(
        source_path=source_path,
        kind=selected_kind or "Unknown",
        group=selected_group or "unknown.group",
        version=selected_version or "unknown",
        sections=sections,
    )


def _resolve_source_path(project_root: Path, source: str) -> Path:
    candidate = Path(source)
    if candidate.is_absolute():
        return candidate
    return (project_root / candidate).resolve()


def _select_version(versions: list[dict[str, Any]], requested: str | None) -> dict[str, Any]:
    if requested:
        for version in versions:
            if version.get("name") == requested:
                return version
        available = ", ".join(str(version.get("name")) for version in versions)
        raise CrdRenderError(f"Requested CRD version {requested!r} not found. Available versions: {available}")

    for version in versions:
        if version.get("storage") is True:
            return version

    for version in versions:
        if version.get("served") is True:
            return version

    return versions[0]


def _build_sections(schema: dict[str, Any], *, show_status: bool) -> list[Section]:
    root_properties = schema.get("properties") or {}
    if not isinstance(root_properties, dict):
        return []

    sections: list[Section] = []
    for key, title in (("spec", "SPEC"), ("status", "STATUS")):
        if key == "status" and not show_status:
            continue
        section_schema = root_properties.get(key)
        if not isinstance(section_schema, dict):
            continue
        sections.append(_build_section(key=key, title=title, schema=section_schema))

    if sections:
        return sections

    root_candidates = {
        key: value
        for key, value in root_properties.items()
        if key not in {"apiVersion", "kind", "metadata"} and isinstance(value, dict)
    }
    if not root_candidates:
        return []

    synthetic_schema = {
        "description": schema.get("description", ""),
        "properties": root_candidates,
        "required": [name for name in schema.get("required", []) if name in root_candidates],
    }
    return [_build_section(key="root", title="ROOT", schema=synthetic_schema)]


def _build_section(*, key: str, title: str, schema: dict[str, Any]) -> Section:
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    children = [
        _build_node(name=name, schema=property_schema, path_prefix=key, required=name in required)
        for name, property_schema in properties.items()
        if isinstance(property_schema, dict)
    ]
    return Section(
        key=key,
        title=title,
        description=str(schema.get("description", "")).strip(),
        children=children,
    )


def _build_node(*, name: str, schema: dict[str, Any], path_prefix: str, required: bool) -> FieldNode:
    path = f"{path_prefix}.{name}" if path_prefix else name
    children: list[FieldNode] = []

    properties = schema.get("properties")
    if isinstance(properties, dict) and properties:
        child_required = set(schema.get("required") or [])
        children.extend(
            _build_node(name=child_name, schema=child_schema, path_prefix=path, required=child_name in child_required)
            for child_name, child_schema in properties.items()
            if isinstance(child_schema, dict)
        )

    item_schema = schema.get("items")
    if isinstance(item_schema, dict) and _schema_has_nested_children(item_schema):
        children.append(_build_virtual_node(label="[]", schema=item_schema, path=f"{path}[]"))

    additional = schema.get("additionalProperties")
    if additional is not None:
        children.append(_build_map_node(additional=additional, path=path))

    return FieldNode(
        label=name,
        path=path,
        field_type=_schema_type(schema),
        description=str(schema.get("description", "")).strip(),
        required=required,
        children=children,
        default=schema.get("default"),
        enum=list(schema.get("enum") or []),
        field_format=schema.get("format"),
        minimum=schema.get("minimum"),
        maximum=schema.get("maximum"),
    )


def _build_virtual_node(*, label: str, schema: dict[str, Any], path: str) -> FieldNode:
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    children = [
        _build_node(name=child_name, schema=child_schema, path_prefix=path, required=child_name in required)
        for child_name, child_schema in properties.items()
        if isinstance(child_schema, dict)
    ]

    additional = schema.get("additionalProperties")
    if additional is not None:
        children.append(_build_map_node(additional=additional, path=path))

    item_schema = schema.get("items")
    if isinstance(item_schema, dict) and _schema_has_nested_children(item_schema):
        children.append(_build_virtual_node(label="[]", schema=item_schema, path=f"{path}[]"))

    return FieldNode(
        label=label,
        path=path,
        field_type=_schema_type(schema),
        description=str(schema.get("description", "")).strip(),
        children=children,
        default=schema.get("default"),
        enum=list(schema.get("enum") or []),
        field_format=schema.get("format"),
        minimum=schema.get("minimum"),
        maximum=schema.get("maximum"),
    )


def _build_map_node(*, additional: Any, path: str) -> FieldNode:
    if additional is True:
        return FieldNode(
            label="<key>",
            path=f"{path}.*",
            field_type="any",
            description="Additional map entries are allowed.",
        )

    if not isinstance(additional, dict):
        return FieldNode(
            label="<key>",
            path=f"{path}.*",
            field_type="unknown",
            description="Additional map entries are allowed.",
        )

    node = _build_virtual_node(label="<key>", schema=additional, path=f"{path}.*")
    if not node.description:
        node.description = "Schema for additional map entries."
    return node


def _schema_type(schema: dict[str, Any]) -> str:
    raw_type = schema.get("type")
    if isinstance(raw_type, list):
        return " | ".join(str(item) for item in raw_type)
    if isinstance(raw_type, str):
        if raw_type == "array" and isinstance(schema.get("items"), dict):
            return f"array[{_schema_type(schema['items'])}]"
        return raw_type
    if schema.get("x-kubernetes-int-or-string") is True:
        return "integer | string"

    composite_types = []
    for key in ("oneOf", "anyOf"):
        options = schema.get(key)
        if isinstance(options, list):
            for option in options:
                if isinstance(option, dict) and isinstance(option.get("type"), str):
                    composite_types.append(option["type"])
        if composite_types:
            unique = []
            for item in composite_types:
                if item not in unique:
                    unique.append(item)
            return " | ".join(unique)

    if isinstance(schema.get("properties"), dict) or schema.get("additionalProperties") is not None:
        return "object"
    if isinstance(schema.get("items"), dict):
        return "array"
    if schema.get("enum"):
        return "enum"
    return "unknown"


def _schema_has_nested_children(schema: dict[str, Any]) -> bool:
    return bool(
        isinstance(schema.get("properties"), dict)
        or schema.get("additionalProperties") is not None
        or isinstance(schema.get("items"), dict)
    )


def _render_view(view: CrdView, *, title: str | None, collapsed: bool) -> str:
    viewer_id = _viewer_id(view=view, sequence=next(_RENDER_COUNTER))
    display_title = title or view.kind
    meta = f"{view.group} / {view.version}"
    sections_html = "\n".join(_render_section(viewer_id=viewer_id, section=section) for section in view.sections)

    viewer_html = f"""
<section class="crd-viewer" data-crd-viewer-root id="{viewer_id}">
  <div class="crd-viewer__header">
    <div>
      <p class="crd-viewer__title">{html.escape(display_title)}</p>
      <p class="crd-viewer__meta">{html.escape(meta)}</p>
    </div>
    <button type="button" class="crd-viewer__toggle" data-crd-toggle-all data-expanded="false">Expand All</button>
  </div>
  {sections_html}
</section>
""".strip()

    if not collapsed:
        return viewer_html

    summary = html.escape(display_title)
    return f"""
<details class="crd-viewer__wrapper">
  <summary>{summary}</summary>
  {viewer_html}
</details>
""".strip()


def _render_section(*, viewer_id: str, section: Section) -> str:
    description_html = (
        f'<p class="crd-viewer__section-description">{html.escape(section.description)}</p>' if section.description else ""
    )
    children_html = "\n".join(_render_node(viewer_id=viewer_id, node=node) for node in section.children)
    section_class = f"crd-viewer__section crd-viewer__section--{section.key}"
    return f"""
<section class="{section_class}">
  <p class="crd-viewer__section-title">{html.escape(section.title)}</p>
  {description_html}
  <ul class="crd-viewer__tree">
    {children_html}
  </ul>
</section>
""".strip()


def _render_node(*, viewer_id: str, node: FieldNode) -> str:
    node_id = _node_id(viewer_id=viewer_id, path=node.path)
    content_id = f"{node_id}-content"
    label = html.escape(node.label)
    required_html = '<sup class="crd-viewer__required" title="Required">*</sup>' if node.required else ""
    badge_html = f'<span class="crd-viewer__badge">{html.escape(node.field_type)}</span>'
    anchor_html = f'<a class="crd-viewer__anchor" href="#{node_id}" aria-label="Link to {label}">#</a>'
    facts_html = _render_facts(node)
    description_html = (
        f'<p class="crd-viewer__description">{html.escape(node.description)}</p>' if node.description else ""
    )
    body_html = ""
    if description_html or facts_html:
        body_html = f"""
<div class="crd-viewer__body">
  {description_html}
  {facts_html}
</div>
""".strip()

    children_html = ""
    if node.children:
        nested_nodes = "\n".join(_render_node(viewer_id=viewer_id, node=child) for child in node.children)
        children_html = f"""
<ul class="crd-viewer__children">
  {nested_nodes}
</ul>
""".strip()

    content_html = "\n".join(part for part in (body_html, children_html) if part)
    content_block = f'<div class="crd-viewer__content" id="{content_id}" hidden>{content_html}</div>'
    return f"""
<li class="crd-viewer__item" id="{node_id}">
  <div class="crd-viewer__node" data-crd-node data-open="false">
    <div class="crd-viewer__row">
      <button
        type="button"
        class="crd-viewer__summary"
        data-crd-toggle-node
        aria-expanded="false"
        aria-controls="{content_id}"
      >
        <span class="crd-viewer__chevron" aria-hidden="true"></span>
        <span class="crd-viewer__label">{label}{required_html}</span>
        {badge_html}
      </button>
      {anchor_html}
    </div>
    {content_block}
  </div>
</li>
""".strip()


def _render_facts(node: FieldNode) -> str:
    facts = []
    if node.default is not None:
        facts.append(("default", _format_value(node.default)))
    if node.enum:
        facts.append(("enum", _format_enum(node.enum)))
    if node.field_format:
        facts.append(("format", str(node.field_format)))
    if node.minimum is not None or node.maximum is not None:
        facts.append(("range", _format_range(node.minimum, node.maximum)))

    if not facts:
        return ""

    items = "".join(
        f'<span class="crd-viewer__fact"><strong>{html.escape(name)}:</strong> {html.escape(value)}</span>'
        for name, value in facts
    )
    return f'<div class="crd-viewer__facts">{items}</div>'


def _format_enum(values: list[Any]) -> str:
    rendered = [json.dumps(value, ensure_ascii=True) for value in values]
    if len(rendered) <= 4:
        return ", ".join(rendered)
    preview = ", ".join(rendered[:3])
    remaining = len(rendered) - 3
    return f"{preview}, +{remaining} more"


def _format_range(minimum: Any, maximum: Any) -> str:
    if minimum is None:
        return f"<= {maximum}"
    if maximum is None:
        return f">= {minimum}"
    return f"{minimum} to {maximum}"


def _format_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def _viewer_id(*, view: CrdView, sequence: int) -> str:
    digest = hashlib.sha1(
        f"{view.source_path}:{view.kind}:{view.group}:{view.version}:{sequence}".encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest()[:10]
    return f"crd-viewer-{digest}"


def _node_id(*, viewer_id: str, path: str) -> str:
    path = path.replace("[]", "-items").replace(".*", "-key")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", path).strip("-").lower()
    return f"{viewer_id}-{slug}"
