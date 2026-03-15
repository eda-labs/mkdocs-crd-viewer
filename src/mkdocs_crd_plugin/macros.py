"""mkdocs-macros entrypoint for CRD viewer rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import render_crd_viewer


def define_env(env: Any) -> None:
    """Register macros for mkdocs-macros-plugin."""

    @env.macro
    def crd_viewer(
        path: str,
        group: str | None = None,
        kind: str | None = None,
        version: str | None = None,
        title: str | None = None,
        collapsed: bool = False,
        show_status: bool = True,
    ) -> str:
        project_root = _project_root(env)
        return render_crd_viewer(
            project_root=project_root,
            source=path,
            group=group,
            kind=kind,
            version=version,
            title=title,
            collapsed=collapsed,
            show_status=show_status,
        )


def _project_root(env: Any) -> Path:
    config = getattr(env, "conf", None)
    config_file_path = _config_value(config, "config_file_path")
    if config_file_path:
        return Path(config_file_path).resolve().parent

    docs_dir = _config_value(config, "docs_dir")
    if docs_dir:
        return Path(docs_dir).resolve().parent

    return Path.cwd()


def _config_value(config: Any, key: str) -> Any:
    if config is None:
        return None
    if hasattr(config, "get"):
        return config.get(key)
    return getattr(config, key, None)

