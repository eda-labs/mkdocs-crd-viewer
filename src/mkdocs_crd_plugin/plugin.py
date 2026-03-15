"""MkDocs plugin for registering CRD viewer assets."""

from __future__ import annotations

from pathlib import Path
import shutil

from importlib import resources
from mkdocs.config import config_options as c
from mkdocs.plugins import BasePlugin


class CrdViewerPlugin(BasePlugin):
    """Copy bundled assets into the built site and register them with MkDocs."""

    config_scheme = (
        ("asset_dir", c.Type(str, default="assets/mkdocs-crd-plugin")),
    )

    def on_config(self, config):  # type: ignore[override]
        asset_dir = self.config["asset_dir"].strip("/")
        css_path = f"{asset_dir}/crd-viewer.css"
        js_path = f"{asset_dir}/crd-viewer.js"

        extra_css = list(config.get("extra_css", []))
        extra_javascript = list(config.get("extra_javascript", []))

        if css_path not in extra_css:
            extra_css.append(css_path)
        if js_path not in extra_javascript:
            extra_javascript.append(js_path)

        config["extra_css"] = extra_css
        config["extra_javascript"] = extra_javascript
        return config

    def on_post_build(self, *, config, **kwargs):  # type: ignore[override]
        asset_dir = self.config["asset_dir"].strip("/")
        site_dir = Path(config["site_dir"])
        destination_dir = site_dir / asset_dir
        destination_dir.mkdir(parents=True, exist_ok=True)

        asset_root = resources.files("mkdocs_crd_plugin.assets")
        for asset_name in ("crd-viewer.css", "crd-viewer.js"):
            source = asset_root.joinpath(asset_name)
            with resources.as_file(source) as source_path:
                shutil.copyfile(source_path, destination_dir / asset_name)
