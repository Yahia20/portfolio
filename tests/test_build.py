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


def _build(tmp_path, monkeypatch, profile_edit=None):
    monkeypatch.setattr(build, "DIST", tmp_path)
    site, profile, categories, projects = build.load_all()
    if profile_edit:
        profile = profile_edit(profile)
    build.render_all(build.make_env(), site, profile, categories, projects)
    return tmp_path


def test_unapproved_testimonial_is_not_published(tmp_path, monkeypatch):
    out = _build(tmp_path, monkeypatch)
    _, profile, _, _ = build.load_all()
    for q in profile.testimonials:
        if not q.approved:
            for lang in ("en", "ar"):
                assert q.name.get(lang) not in (out / f"{lang}/index.html").read_text(encoding="utf-8")


def test_approved_testimonial_appears_on_the_home_page(tmp_path, monkeypatch):
    from schema import Testimonial, Text
    quote = Testimonial(quote=Text(en="Great work.", ar="عمل رائع."), name=Text(en="A. Person", ar="أ. شخص"),
                        title=Text(en="Manager", ar="مدير"), approved=True)
    out = _build(tmp_path, monkeypatch, lambda p: p.model_copy(update={"testimonials": [quote]}))
    assert "Great work." in (out / "en/index.html").read_text(encoding="utf-8")
    assert "عمل رائع." in (out / "ar/index.html").read_text(encoding="utf-8")


def test_service_pointing_to_a_missing_project_is_refused(monkeypatch):
    real = build._load

    def fake(path, model):
        obj = real(path, model)
        if path.name == "profile.yaml":
            obj.services[0].proof = ["no-such-project"]
        return obj

    monkeypatch.setattr(build, "_load", fake)
    with pytest.raises(build.DataError, match="no-such-project"):
        build.load_all()


def test_share_tags_use_full_urls(tmp_path, monkeypatch):
    out = _build(tmp_path, monkeypatch)
    site, *_ = build.load_all()
    home = (out / "en/index.html").read_text(encoding="utf-8")
    assert f'<meta property="og:image" content="{site.base_url}/assets/og/en.png">' in home
    project = (out / "en/projects/document-reader/index.html").read_text(encoding="utf-8")
    assert f'content="{site.base_url}/assets/projects/document-reader/en/cover.png"' in project


def test_cv_is_offered_and_exists(tmp_path, monkeypatch):
    out = _build(tmp_path, monkeypatch)
    site, *_ = build.load_all()
    assert (ROOT / "assets" / site.cv).exists()
    for page in ("en/about/index.html", "ar/contact/index.html"):
        assert f'assets/{site.cv}" download' in (out / page).read_text(encoding="utf-8")


def test_cv_data_is_valid():
    build.load_cv()
