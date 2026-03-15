"""Core CRD parsing and HTML rendering logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import base64
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
    namespaced: bool
    skeleton_schema: dict[str, Any]
    sections: list[Section]


@dataclass(slots=True)
class SkeletonLine:
    """Rendered YAML line with metadata used for copy payload formatting."""

    text: str
    comment: str | None = None
    enabled: bool = True


def render_crd_viewer(
    project_root: Path,
    source: str,
    *,
    version: str | None = None,
    title: str | None = None,
    collapsed: bool = False,
    show_status: bool = True,
    copy_skeleton: bool = True,
) -> str:
    """Render a CRD from disk into HTML suitable for MkDocs pages."""

    source_path = _resolve_source_path(project_root, source)
    view = load_crd_view(source_path, version=version, show_status=show_status)
    return _render_view(view, title=title, collapsed=collapsed, copy_skeleton=copy_skeleton)


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
    selected_scope = spec.get("scope")

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
        namespaced=_is_namespaced(selected_scope),
        skeleton_schema=_build_skeleton_schema(schema),
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


def _build_skeleton_schema(schema: dict[str, Any]) -> dict[str, Any]:
    root_properties = schema.get("properties") or {}
    if not isinstance(root_properties, dict):
        return {}

    spec_schema = root_properties.get("spec")
    if isinstance(spec_schema, dict):
        return spec_schema

    root_candidates = {
        key: value
        for key, value in root_properties.items()
        if key not in {"apiVersion", "kind", "metadata", "status"} and isinstance(value, dict)
    }
    if not root_candidates:
        return {}

    return {
        "type": "object",
        "properties": root_candidates,
        "required": [name for name in schema.get("required", []) if name in root_candidates],
    }


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


def _is_namespaced(scope: Any) -> bool:
    if isinstance(scope, str):
        return scope.lower() != "cluster"
    return True


def _render_view(view: CrdView, *, title: str | None, collapsed: bool, copy_skeleton: bool) -> str:
    viewer_id = _viewer_id(view=view, sequence=next(_RENDER_COUNTER))
    display_title = title or view.kind
    meta = f"{view.group} / {view.version}"
    sections_html = "\n".join(_render_section(viewer_id=viewer_id, section=section) for section in view.sections)
    actions = [
        '<button type="button" class="crd-viewer__toggle" data-crd-toggle-all data-expanded="false">Expand All</button>'
    ]
    section_attributes = " data-crd-viewer-root"
    if copy_skeleton:
        actions.insert(
            0,
            """<button
        type="button"
        class="crd-viewer__toggle crd-viewer__toggle--icon"
        data-crd-copy-skeleton
        aria-label="Copy YAML skeleton (Shift+Click for full template)"
        title="Copy YAML skeleton (Shift+Click for full template)"
      >
        <span class="crd-viewer__copy-icon" aria-hidden="true">
          <svg viewBox="0 0 16 16" focusable="false" aria-hidden="true">
            <rect x="6" y="2" width="8" height="11" rx="1.5"></rect>
            <path d="M10 13H4.5A1.5 1.5 0 0 1 3 11.5V4"></path>
          </svg>
        </span>
      </button>""",
        )
        minimal_skeleton = _build_skeleton_yaml(view, include_optional=False)
        verbose_skeleton = _build_skeleton_yaml(view, include_optional=True)
        payload = html.escape(_encode_skeleton_payload(minimal_skeleton), quote=True)
        payload_verbose = html.escape(_encode_skeleton_payload(verbose_skeleton), quote=True)
        section_attributes += f' data-crd-skeleton="{payload}" data-crd-skeleton-verbose="{payload_verbose}"'
    actions_html = "\n      ".join(actions)

    header_html = f"""
  <div class="crd-viewer__header">
    <div>
      <p class="crd-viewer__title">{html.escape(display_title)}</p>
      <p class="crd-viewer__meta">{html.escape(meta)}</p>
    </div>
    <div class="crd-viewer__actions">
      {actions_html}
    </div>
  </div>"""

    collapsed_attr = ' data-crd-collapsible data-crd-collapsed="true"' if collapsed else ""
    return f"""
<section class="crd-viewer"{section_attributes}{collapsed_attr} id="{viewer_id}">
  {header_html}
  {sections_html}
</section>
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


def _build_skeleton_yaml(view: CrdView, *, include_optional: bool) -> str:
    required_comment = "required" if include_optional else None
    lines: list[SkeletonLine] = [
        SkeletonLine(f"apiVersion: {view.group}/{view.version}", comment=required_comment),
        SkeletonLine(f"kind: {_yaml_scalar(view.kind)}", comment=required_comment),
        SkeletonLine("metadata:", comment=required_comment),
    ]
    lines.extend(_skeleton_metadata_lines(view, indent=2, include_optional=include_optional))

    spec_lines = _emit_object_fields(
        schema=view.skeleton_schema,
        indent=2,
        include_optional=include_optional,
        parent_enabled=True,
    )
    spec_has_enabled = any(line.enabled for line in spec_lines)
    if spec_has_enabled:
        lines.append(SkeletonLine("spec:", comment=required_comment))
        lines.extend(spec_lines)
    else:
        lines.append(SkeletonLine("spec: {}", comment=required_comment))
        lines.extend(spec_lines)

    if not include_optional:
        lines = [line for line in lines if line.enabled]

    return _render_skeleton_lines(lines)


def _skeleton_metadata_lines(view: CrdView, *, indent: int, include_optional: bool) -> list[SkeletonLine]:
    prefix = " " * indent
    required_comment = "required" if include_optional else None
    metadata: list[SkeletonLine] = [
        SkeletonLine(f"{prefix}name: {_yaml_scalar(f'{_slug_name(view.kind)}-sample')}", comment=required_comment)
    ]
    if view.namespaced:
        metadata.append(
            SkeletonLine(
                f"{prefix}namespace: {_yaml_scalar('default')}",
                comment="optional",
                enabled=include_optional,
            )
        )
    return metadata


def _slug_name(value: str) -> str:
    dashed = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", value)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", dashed).strip("-").lower()
    return slug or "resource"


def _emit_object_fields(
    schema: Any,
    *,
    indent: int,
    include_optional: bool,
    parent_enabled: bool,
) -> list[SkeletonLine]:
    if not isinstance(schema, dict):
        return []

    properties = schema.get("properties")
    required = set(schema.get("required") or [])
    lines: list[SkeletonLine] = []

    if isinstance(properties, dict) and properties:
        for name, property_schema in properties.items():
            if isinstance(property_schema, dict):
                field_required = name in required
                lines.extend(
                    _emit_schema_field(
                        name=name,
                        schema=property_schema,
                        required=field_required,
                        indent=indent,
                        include_optional=include_optional,
                        enabled=parent_enabled and (include_optional or field_required),
                    )
                )
        return lines

    additional = schema.get("additionalProperties")
    if isinstance(additional, dict):
        lines.extend(
            _emit_schema_field(
                name="<key>",
                schema=additional,
                required=False,
                indent=indent,
                include_optional=include_optional,
                enabled=parent_enabled and include_optional,
            )
        )
    elif additional is True:
        prefix = " " * indent
        lines.append(
            SkeletonLine(
                f"{prefix}{_yaml_key('<key>')}: null",
                comment="optional",
                enabled=parent_enabled and include_optional,
            )
        )

    return lines


def _emit_schema_field(
    *,
    name: str,
    schema: dict[str, Any],
    required: bool,
    indent: int,
    include_optional: bool,
    enabled: bool,
) -> list[SkeletonLine]:
    prefix = " " * indent
    comment = _field_comment(required=(required if include_optional else None), schema=schema)
    key = _yaml_key(name)
    schema_type = _skeleton_schema_type(schema)

    if schema_type == "object":
        children = _emit_object_fields(
            schema,
            indent=indent + 2,
            include_optional=include_optional,
            parent_enabled=enabled,
        )
        has_enabled_children = any(line.enabled for line in children)
        if children and has_enabled_children:
            return [SkeletonLine(f"{prefix}{key}:", comment=comment, enabled=enabled), *children]
        if children:
            if enabled:
                return [SkeletonLine(f"{prefix}{key}: {{}}", comment=comment, enabled=True), *children]
            return [SkeletonLine(f"{prefix}{key}:", comment=comment, enabled=False), *children]
        return [SkeletonLine(f"{prefix}{key}: {{}}", comment=comment, enabled=enabled)]

    value = _skeleton_scalar_value(schema, schema_type=schema_type)
    return [SkeletonLine(f"{prefix}{key}: {_yaml_scalar(value)}", comment=comment, enabled=enabled)]


def _skeleton_schema_type(schema: dict[str, Any]) -> str:
    raw_type = schema.get("type")
    if isinstance(raw_type, str):
        return raw_type
    if isinstance(raw_type, list):
        first = next((item for item in raw_type if isinstance(item, str)), None)
        if first:
            return first

    if schema.get("x-kubernetes-int-or-string") is True:
        return "string"

    composite = _first_composite_type(schema)
    if composite:
        return composite

    if _schema_looks_like_object(schema):
        return "object"
    if isinstance(schema.get("items"), dict):
        return "array"
    return "unknown"


def _schema_looks_like_object(schema: dict[str, Any]) -> bool:
    return bool(isinstance(schema.get("properties"), dict) or schema.get("additionalProperties") is not None)


def _first_composite_type(schema: dict[str, Any]) -> str | None:
    for key in ("oneOf", "anyOf"):
        options = schema.get(key)
        if not isinstance(options, list):
            continue
        for option in options:
            if isinstance(option, dict):
                option_type = option.get("type")
                if isinstance(option_type, str):
                    return option_type
    return None


def _skeleton_scalar_value(schema: dict[str, Any], *, schema_type: str) -> Any:
    if "default" in schema:
        return schema["default"]
    if "example" in schema:
        return schema["example"]
    examples = schema.get("examples")
    if isinstance(examples, list) and examples:
        return examples[0]

    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]

    if schema_type == "array":
        return []
    if schema_type == "string":
        return ""
    if schema_type == "integer":
        return 0
    if schema_type == "number":
        return 0
    if schema_type == "boolean":
        return False
    if schema_type == "object":
        return {}
    return None


def _yaml_key(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]+", value):
        return value
    return json.dumps(value, ensure_ascii=True)


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=True)
    return json.dumps(value, ensure_ascii=True)


def _field_comment(*, required: bool | None, schema: dict[str, Any] | None = None) -> str | None:
    notes: list[str] = []
    if required is not None:
        notes.append("required" if required else "optional")
    enum_note = _enum_comment(schema) if schema else None
    if enum_note:
        notes.append(enum_note)
    if not notes:
        return None
    return "; ".join(notes)


def _enum_comment(schema: dict[str, Any]) -> str | None:
    enum = schema.get("enum")
    if not isinstance(enum, list) or len(enum) <= 1:
        return None
    rendered = [json.dumps(value, ensure_ascii=True) for value in enum]
    if len(rendered) <= 4:
        return f"one of: {', '.join(rendered)}"
    preview = ", ".join(rendered[:3])
    remaining = len(rendered) - 3
    return f"one of: {preview}, +{remaining} more"


def _render_skeleton_lines(lines: list[SkeletonLine]) -> str:
    bodies = [_render_skeleton_body(line) for line in lines]
    commented = [body for body, line in zip(bodies, lines, strict=False) if line.comment]
    width = max((len(body) for body in commented), default=0)

    rendered = []
    for line, body in zip(lines, bodies, strict=False):
        if line.comment is None:
            rendered.append(body)
            continue
        padding = " " * (width - len(body) + 2)
        rendered.append(f"{body}{padding}# {line.comment}")
    return "\n".join(rendered) + "\n"


def _render_skeleton_body(line: SkeletonLine) -> str:
    if line.enabled:
        return line.text
    return f"# {line.text}"


def _encode_skeleton_payload(skeleton: str) -> str:
    return base64.b64encode(skeleton.encode("utf-8")).decode("ascii")


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
