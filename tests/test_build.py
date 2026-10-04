from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import build  # noqa: E402
from schema import Project  # noqa: E402


def test_real_data_is_valid():
    site, profile, categories, projects = build.load_all()
    assert projects, "no projects found"
    assert sum(p.featured for p in projects) == 1  # the home page shows exactly one


def test_template_matches_the_schema():
    # The template is what a new project starts from; it must never drift from the schema.
    raw = yaml.safe_load((ROOT / "data/projects/_template.yaml.example").read_text(encoding="utf-8"))
    Project.model_validate(raw)


def test_missing_translation_is_refused(tmp_path):
    bad = tmp_path / "x.yaml"
    raw = yaml.safe_load((ROOT / "data/projects/_template.yaml.example").read_text(encoding="utf-8"))
    raw["title"] = {"en": "Only English"}
    bad.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(build.DataError, match=r"title → ar"):
        build._load(bad, Project)


def test_comma_split_by_yaml_gets_a_hint(tmp_path):
    src = (ROOT / "data/projects/_template.yaml.example").read_text(encoding="utf-8")
    bad = tmp_path / "x.yaml"
    bad.write_text(src.replace('role: { en: "What I did.", ar:', "role: { en: Built it, then ran it, ar:"), encoding="utf-8")
    with pytest.raises(build.DataError, match="must be in \"double quotes\""):
        build._load(bad, Project)


def test_every_page_is_built_in_both_languages_with_the_right_direction(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "DIST", tmp_path)
    site, profile, categories, projects = build.load_all()
    pages = build.render_all(build.make_env(), site, profile, categories, projects)

    for lang, direction in (("en", "ltr"), ("ar", "rtl")):
        mine = [p for p in pages if p.startswith(f"{lang}/")]
        assert len(mine) == 4 + len(projects)  # home, projects, about, contact + one per project
        for rel in mine:
            html = (tmp_path / rel).read_text(encoding="utf-8")
            assert f'<html lang="{lang}" dir="{direction}">' in html
            other = "ar" if lang == "en" else "en"
            assert (tmp_path / rel.replace(f"{lang}/", f"{other}/", 1)).exists()  # the language switch has a target
