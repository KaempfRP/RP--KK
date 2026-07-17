"""Smoke tests — quick sanity checks."""

import os
import pytest

from jinja2 import Environment, FileSystemLoader


pytestmark = pytest.mark.smoke

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def test_imports():
    """All src modules are importable."""
    import src.ted_api
    import src.rss_sources
    import src.dedup
    import src.render
    import src.scoring


def test_db_init(tmp_path):
    """seen.db is created without error."""
    from src.dedup import init_db

    db_path = str(tmp_path / "smoke_test.db")
    init_db(db_path)
    assert os.path.exists(db_path)


def test_template_exists():
    """index.html.j2 exists and is parseable."""
    template_dir = os.path.join(PROJECT_ROOT, "templates")
    assert os.path.exists(os.path.join(template_dir, "index.html.j2"))

    env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
    template = env.get_template("index.html.j2")
    assert template is not None


def test_docs_dir():
    """docs/ directory exists or can be created."""
    docs_dir = os.path.join(PROJECT_ROOT, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    assert os.path.isdir(docs_dir)


def test_main_runs_with_mocked_sources(tmp_path, monkeypatch):
    """main() runs without exception when all sources return empty."""
    from src import dedup

    db_path = str(tmp_path / "smoke_main.db")
    docs_dir = str(tmp_path / "docs")
    os.makedirs(docs_dir, exist_ok=True)

    monkeypatch.setattr("src.ted_api.fetch_ted", lambda: [])
    monkeypatch.setattr("src.rss_sources.fetch_rss_sources", lambda: [])
    monkeypatch.setattr("src.dedup.DB_PATH", db_path)
    monkeypatch.setattr("src.render.DOCS_DIR", docs_dir)

    from src.dedup import init_db
    init_db(db_path)

    from main import main
    main()
