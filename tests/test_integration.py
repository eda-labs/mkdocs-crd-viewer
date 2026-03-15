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
    assert len(viewers) == 2
    assert len({viewer.get("id") for viewer in viewers}) == 2

    # First viewer: full inline with spec + status
    inline_viewer = viewers[0]
    assert inline_viewer.select_one("[data-crd-toggle-all]") is not None
    assert "SPEC" in inline_viewer.get_text()
    assert "STATUS" in inline_viewer.get_text()
    assert "Fabric" in inline_viewer.get_text()
    assert "items" not in inline_viewer.get_text()

    # Second viewer: collapsed, spec only (show_status=False)
    collapsed_wrapper = soup.select_one("details.crd-viewer__wrapper")
    assert collapsed_wrapper is not None
    collapsed_viewer = collapsed_wrapper.select_one("[data-crd-viewer-root]")
    assert collapsed_viewer is not None
    assert "SPEC" in collapsed_viewer.get_text()
    assert "STATUS" not in collapsed_viewer.get_text()

    assets = {tag.get("href") for tag in soup.select('link[rel="stylesheet"]')}
    scripts = {tag.get("src") for tag in soup.select("script[src]")}
    assert "assets/mkdocs-crd-plugin/crd-viewer.css" in assets
    assert "assets/mkdocs-crd-plugin/crd-viewer.js" in scripts
