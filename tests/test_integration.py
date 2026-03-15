from pathlib import Path
import subprocess
import sys

from bs4 import BeautifulSoup


def test_demo_site_builds(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    site_dir = tmp_path / "site"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mkdocs",
            "build",
            "-f",
            str(repo_root / "demo" / "mkdocs.yml"),
            "-d",
            str(site_dir),
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

    html = (site_dir / "index.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    viewers = soup.select("[data-crd-viewer-root]")
    assert len(viewers) >= 5
    assert len({viewer.get("id") for viewer in viewers}) == len(viewers)

    # Top viewer: full inline with spec + status
    top_viewer = viewers[0]
    assert top_viewer.select_one("[data-crd-toggle-all]") is not None
    assert top_viewer.select_one("[data-crd-copy-skeleton]") is not None
    assert top_viewer.get("data-crd-skeleton")
    assert top_viewer.get("data-crd-skeleton-verbose")
    assert "SPEC" in top_viewer.get_text()
    assert "STATUS" in top_viewer.get_text()
    assert "Fabric" in top_viewer.get_text()
    assert "items" not in top_viewer.get_text()

    # Settings preview includes a pinned version example.
    pinned_viewer = next((viewer for viewer in viewers if "Pinned version: v1alpha1" in viewer.get_text()), None)
    assert pinned_viewer is not None
    assert "STATUS" in pinned_viewer.get_text()

    # Spec-only examples should not render STATUS.
    spec_only_viewers = [viewer for viewer in viewers if "Spec only" in viewer.get_text()]
    assert spec_only_viewers
    for viewer in spec_only_viewers:
        assert "STATUS" not in viewer.get_text()

    # Collapsed render should exist and be spec-only.
    collapsed_viewer = next((viewer for viewer in viewers if "Collapsed + spec only" in viewer.get_text()), None)
    assert collapsed_viewer is not None
    assert collapsed_viewer.has_attr("data-crd-collapsible")
    assert collapsed_viewer.get("data-crd-collapsed") == "true"
    assert "Collapsed + spec only" in collapsed_viewer.get_text()
    assert "SPEC" in collapsed_viewer.get_text()
    assert "STATUS" not in collapsed_viewer.get_text()

    assets = {tag.get("href") for tag in soup.select('link[rel="stylesheet"]')}
    scripts = {tag.get("src") for tag in soup.select("script[src]")}
    assert "assets/mkdocs-crd-viewer/crd-viewer.css" in assets
    assert "assets/mkdocs-crd-viewer/crd-viewer.js" in scripts
