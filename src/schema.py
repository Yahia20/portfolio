"""The shape of everything in data/.

Every model forbids unknown keys, so a typo in a YAML file ("titel:") fails the build with the
file and field named, instead of silently disappearing from the site.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

LANGS = ("en", "ar")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Text(Strict):
    """A string in both languages. Both are required: a half-translated site looks broken."""
    en: str
    ar: str

    @field_validator("en", "ar")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty — write both the English and the Arabic")
        return v.strip()

    def get(self, lang: str) -> str:
        return getattr(self, lang)


class OptionalText(Strict):
    """Like Text, but one side may be empty (e.g. a note that only makes sense in English)."""
    en: str = ""
    ar: str = ""

    def get(self, lang: str) -> str:
        return getattr(self, lang).strip()


# --- site.yaml -------------------------------------------------------------------------------

class Link(Strict):
    kind: Literal["linkedin", "github", "mostaql", "kaggle", "website", "video", "live"]
    url: str
    label: Text


class Contact(Strict):
    email: str
    phone: str = ""

    def phone_digits(self) -> str:
        """The number as tel: and wa.me links want it: digits only, with country code."""
        return "".join(ch for ch in self.phone if ch.isdigit())

    links: list[Link]


class Nav(Strict):
    home: Text
    projects: Text
    about: Text
    contact: Text


class Site(Strict):
    base_url: str = ""
    default_lang: Literal["en", "ar"] = "ar"
    title: Text
    description: Text
    nav: Nav
    contact: Contact


# --- profile.yaml ----------------------------------------------------------------------------

class Photo(Strict):
    image: str
    caption: Text
    layout: str = ""   # which design in shot.html draws it; defaults to the image name; "own" = your PNG


class Service(Strict):
    icon: str
    title: Text
    body: Text


class Job(Strict):
    org: Text
    role: Text
    period: Text
    place: Text
    points: list[Text]


class School(Strict):
    org: Text
    degree: Text
    period: Text


class Certification(Strict):
    name: str
    issuer: str
    year: int | None = None


class SkillGroup(Strict):
    group: Text
    items: list[str]


class Language(Strict):
    name: Text
    level: Text


class Profile(Strict):
    name: Text
    role: Text
    location: Text
    availability: Text
    portrait: str = ""
    portrait_alt: Text
    gallery: list[Photo] = []
    headline: Text
    intro: Text
    about: list[Text]
    services: list[Service]
    experience: list[Job]
    education: list[School]
    certifications: list[Certification]
    skills: list[SkillGroup]
    languages: list[Language]


# --- categories.yaml -------------------------------------------------------------------------

class Category(Strict):
    id: str
    icon: str
    name: Text
    description: Text


# --- projects/<slug>.yaml --------------------------------------------------------------------

class Stat(Strict):
    """A headline number. Give `count` to animate it, or `display` for text like '2% → 100%'.
    `display` is per language, because arrows and symbols read the other way in Arabic."""
    count: int | None = None
    prefix: str = ""
    suffix: str = ""
    display: Text | None = None
    label: Text
    note: Text | None = None

    @model_validator(mode="after")
    def one_value(self):
        if (self.count is None) == (self.display is None):
            raise ValueError("give exactly one of `count` or `display`")
        return self


class Image(Strict):
    image: str
    alt: Text


class Step(Strict):
    icon: str
    title: Text
    body: Text


class Section(Strict):
    title: Text
    body: Text


class Results(Strict):
    title: Text
    as_of: Text
    points: list[Text]


class DemoCall(Strict):
    file: str
    title: Text
    story: Text


class Demo(Strict):
    kind: Literal["call-qa"]
    source: str
    title: Text
    intro: Text
    note: OptionalText = OptionalText()
    highlight: str
    highlight_title: Text
    highlight_body: Text
    calls: list[DemoCall]

    @model_validator(mode="after")
    def highlight_is_a_call(self):
        if self.highlight not in {c.file for c in self.calls}:
            raise ValueError(f"highlight '{self.highlight}' is not one of the listed calls")
        return self


class ValueItem(Strict):
    icon: str
    title: Text
    body: Text


class Value(Strict):
    title: Text
    items: list[ValueItem]
    fits: Text


class Limits(Strict):
    title: Text
    items: list[Text]


class Tech(Strict):
    stack: list[str]
    points: list[Text]


class ComparisonTest(Strict):
    id: str
    label: Text
    note: Text


class ComparisonModel(Strict):
    name: Text
    kind: Text
    scores: dict[str, float]      # test id -> share correct, 0..1
    highlight: bool = False


class Comparison(Strict):
    """Several approaches scored on the same tests, drawn as grouped bars."""
    title: Text
    intro: Text
    tests: list[ComparisonTest]
    models: list[ComparisonModel]
    takeaway: Text

    @model_validator(mode="after")
    def every_model_has_every_score(self):
        ids = {t.id for t in self.tests}
        for m in self.models:
            if set(m.scores) != ids:
                raise ValueError(f"model '{m.name.en}' needs a score for each test: {sorted(ids)}")
            if not all(0 <= v <= 1 for v in m.scores.values()):
                raise ValueError(f"model '{m.name.en}': scores are shares between 0 and 1")
        return self


class Examples(Strict):
    """A table of real inputs with each model's answer, read from data/demos/<source>/examples.json."""
    title: Text
    intro: Text
    source: str


class ProjectLink(Strict):
    kind: Literal["github", "live", "video", "article"]
    url: str
    label: Text


class Project(Strict):
    slug: str
    category: str
    status: Literal["live", "completed", "in-progress"]
    featured: bool = False
    order: int = 100
    date: str
    title: Text
    tagline: Text
    client: dict[str, Text] | None = None
    role: Text
    cover: Image
    stats: list[Stat] = []
    problem: Section
    steps: list[Step] = []
    results: Results | None = None
    demo: Demo | None = None
    comparison: Comparison | None = None
    examples: Examples | None = None
    value: Value | None = None
    limits: Limits | None = None
    tech: Tech | None = None
    links: list[ProjectLink] = []
    gallery: list[Photo] = []

    @field_validator("date", mode="before")
    @classmethod
    def date_as_text(cls, v):
        return str(v)
