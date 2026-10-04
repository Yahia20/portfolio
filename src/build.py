"""Build the site from data/ into dist/.

    python src/build.py            # validate data, render every page in both languages
    python src/build.py --shots    # also render the project images (PNG) with headless Chrome
    python src/build.py --serve    # build, then preview on http://localhost:8000

Pages use relative links only, so dist/ works from any host, any sub-path, or straight off disk.
"""
from __future__ import annotations

import argparse
import http.server
import json
import shutil
import subprocess
import sys
from datetime import date
from functools import partial
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import LANGS, Category, Profile, Project, Site  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SRC = ROOT / "src"
DIST = ROOT / "dist"
ASSETS = ROOT / "assets"

SHOT_SIZE = (1200, 675)
CHROME_PATHS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path("/usr/bin/google-chrome"),
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
]

# Labels for the call-QA demo. The reports themselves are in Arabic; these label the UI.
CRITERIA = {
    "greeting": {"en": "Greeting", "ar": "التحية والافتتاح"},
    "listening": {"en": "Listening", "ar": "الإنصات وفهم المشكلة"},
    "resolution": {"en": "Solving the problem", "ar": "حل المشكلة"},
    "policy_compliance": {"en": "Following policy", "ar": "الالتزام بسياسة الشركة"},
    "closing": {"en": "Closing the call", "ar": "إنهاء المكالمة"},
}
SENTIMENT = {
    "positive": {"en": "Positive", "ar": "إيجابي"},
    "neutral": {"en": "Neutral", "ar": "محايد"},
    "negative": {"en": "Negative", "ar": "سلبي"},
}

# Fixed interface strings. Content lives in data/; this is only chrome around it.
UI = {
    "skip": {"en": "Skip to content", "ar": "تخطَّ إلى المحتوى"},
    "switch_lang": {"en": "العربية", "ar": "English"},
    "theme": {"en": "Switch light / dark", "ar": "تبديل الوضع الفاتح / الداكن"},
    "see_work": {"en": "See my work", "ar": "شاهد أعمالي"},
    "get_in_touch": {"en": "Get in touch", "ar": "تواصل معي"},
    "featured": {"en": "Featured project", "ar": "المشروع المميز"},
    "read_story": {"en": "Read the full story", "ar": "اقرأ القصة كاملة"},
    "what_i_do": {"en": "What I can help with", "ar": "ما الذي أستطيع مساعدتك فيه"},
    "all": {"en": "All", "ar": "الكل"},
    "projects_intro": {
        "en": "Each project is written for the people who would use it: what the problem was, what I built, and what changed.",
        "ar": "كل مشروع مكتوب لمن سيستخدمه: ما المشكلة، ماذا بنيت، وما الذي تغيّر.",
    },
    "status": {
        "live": {"en": "Live", "ar": "يعمل فعليًا"},
        "completed": {"en": "Completed", "ar": "مكتمل"},
        "in-progress": {"en": "In progress", "ar": "قيد التنفيذ"},
    },
    "client": {"en": "Client", "ar": "العميل"},
    "my_role": {"en": "My role", "ar": "دوري"},
    "how": {"en": "How it works", "ar": "كيف يعمل"},
    "step": {"en": "Step", "ar": "الخطوة"},
    "score": {"en": "Score", "ar": "التقييم"},
    "evidence": {"en": "Evidence", "ar": "الدليل"},
    "overall": {"en": "Overall", "ar": "التقييم العام"},
    "resolved": {"en": "Resolved", "ar": "تم الحل"},
    "yes": {"en": "Yes", "ar": "نعم"},
    "no": {"en": "No", "ar": "لا"},
    "mood": {"en": "Customer mood", "ar": "مزاج العميل"},
    "flagged": {"en": "Sent to a supervisor", "ar": "مُحالة للمشرف"},
    "not_flagged": {"en": "No review needed", "ar": "لا تحتاج مراجعة"},
    "strengths": {"en": "What went well", "ar": "نقاط القوة"},
    "improve": {"en": "What to improve", "ar": "نقاط التحسين"},
    "transcript": {"en": "Read the call", "ar": "اقرأ المكالمة"},
    "call_reason": {"en": "Why they called", "ar": "سبب الاتصال"},
    "team_title": {"en": "The team summary", "ar": "ملخص الفريق"},
    "team_sub": {
        "en": "Average score for each skill across the six calls, weakest first. The top of this list is next week's training.",
        "ar": "متوسط كل مهارة في المكالمات الست، من الأضعف. أول هذه القائمة هو تدريب الأسبوع القادم.",
    },
    "team_table": {"en": "Show as a table", "ar": "اعرضها كجدول"},
    "skill": {"en": "Skill", "ar": "المهارة"},
    "average": {"en": "Average (out of 5)", "ar": "المتوسط (من 5)"},
    "calls_scored": {"en": "calls scored", "ar": "مكالمات قُيّمت"},
    "avg_score": {"en": "average score", "ar": "متوسط التقييم"},
    "flagged_n": {"en": "sent to a supervisor", "ar": "أُحيلت للمشرف"},
    "tech_title": {"en": "Technical details", "ar": "التفاصيل التقنية"},
    "tech_hint": {"en": "For engineers and recruiters", "ar": "للمهندسين ومسؤولي التوظيف"},
    "gallery": {"en": "Images", "ar": "الصور"},
    "back_projects": {"en": "All projects", "ar": "كل المشاريع"},
    "experience": {"en": "Experience", "ar": "الخبرة"},
    "education": {"en": "Education", "ar": "التعليم"},
    "certs": {"en": "Certifications", "ar": "الشهادات"},
    "skills": {"en": "Skills", "ar": "المهارات"},
    "languages": {"en": "Languages", "ar": "اللغات"},
    "photos": {"en": "Photos", "ar": "صور"},
    "contact_title": {"en": "Let's talk about your project", "ar": "لنتحدث عن مشروعك"},
    "contact_body": {
        "en": "Tell me what you're trying to fix or find out. I'll reply with a clear plan: the steps, the timeline, and what it would cost to run.",
        "ar": "أخبرني بما تحاول إصلاحه أو معرفته. سأرد عليك بخطة واضحة: الخطوات، والمدة، وتكلفة التشغيل.",
    },
    "email_me": {"en": "Email me", "ar": "راسلني"},
    "call_me": {"en": "Call", "ar": "اتصل"},
    "whatsapp": {"en": "WhatsApp", "ar": "واتساب"},
    "copy": {"en": "Copy", "ar": "نسخ"},
    "copied": {"en": "Copied", "ar": "تم النسخ"},
    "elsewhere": {"en": "Find me elsewhere", "ar": "تجدني أيضًا على"},
    "made_with": {"en": "Built by hand, from a data file per project.", "ar": "مبني يدويًا، من ملف بيانات لكل مشروع."},
    "not_found": {"en": "This page doesn't exist.", "ar": "هذه الصفحة غير موجودة."},
    "message": {"en": "Message", "ar": "الرسالة"},
    "right_answer": {"en": "Right answer", "ar": "الإجابة الصحيحة"},
    "correct": {"en": "correct", "ar": "صحيحة"},
    "show_all": {"en": "All messages", "ar": "كل الرسائل"},
    "show_disagree": {"en": "Where the models disagree", "ar": "حيث تختلف النماذج"},
    "out_of": {"en": "out of", "ar": "من"},
    "go_home": {"en": "Go to the home page", "ar": "اذهب للرئيسية"},
    "open_image": {"en": "Open image", "ar": "افتح الصورة"},
    "close": {"en": "Close", "ar": "إغلاق"},
}


# --- loading & validation --------------------------------------------------------------------

class DataError(Exception):
    pass


def _load(path: Path, model):
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        if isinstance(raw, list):
            return [model.model_validate(item) for item in raw]
        return model.model_validate(raw)
    except ValidationError as exc:
        lines = [f"{path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}:"]
        for err in exc.errors():
            where = " → ".join(str(p) for p in err["loc"]) or "(top level)"
            hint = ""
            if err["type"] == "extra_forbidden" and " " in str(err["loc"][-1]):
                # `{ en: A, B, ar: C }` — YAML split the text at its comma.
                hint = '  ← text with a comma inside { en: ..., ar: ... } must be in "double quotes"'
            lines.append(f"  {where}: {err['msg']}{hint}")
        raise DataError("\n".join(lines)) from None


def load_all():
    site = _load(DATA / "site.yaml", Site)
    profile = _load(DATA / "profile.yaml", Profile)
    categories = _load(DATA / "categories.yaml", Category)
    project_files = sorted((DATA / "projects").glob("*.yaml"))
    projects = [_load(p, Project) for p in project_files]

    problems: list[str] = [
        f"projects/{path.name}: file name must match slug '{p.slug}' (rename it to {p.slug}.yaml)"
        for path, p in zip(project_files, projects) if path.stem != p.slug
    ]
    cat_ids = [c.id for c in categories]
    if len(set(cat_ids)) != len(cat_ids):
        problems.append("categories.yaml: two categories share an id")
    slugs = [p.slug for p in projects]
    if len(set(slugs)) != len(slugs):
        problems.append("projects/: two projects share a slug")

    for p in projects:
        f = f"projects/{p.slug}.yaml"
        if p.category not in cat_ids:
            problems.append(f"{f}: category '{p.category}' is not in categories.yaml ({', '.join(cat_ids)})")
        if p.examples:
            folder = DATA / "demos" / p.examples.source
            for needed in ("examples.json", "labels.yaml"):
                if not (folder / needed).exists():
                    problems.append(f"{f}: examples need {folder.relative_to(ROOT)}/{needed}")
        if p.demo:
            reports = DATA / "demos" / p.demo.source / "reports"
            for call in p.demo.calls:
                if not (reports / f"{call.file}.json").exists():
                    problems.append(f"{f}: demo call '{call.file}' has no report in {reports.relative_to(ROOT)}")

    if profile.portrait and not (ASSETS / "img" / "profile" / profile.portrait).exists():
        problems.append(f"profile.yaml: portrait '{profile.portrait}' not found in assets/img/profile/")
    for photo in profile.gallery:
        if not (ASSETS / "img" / "profile" / photo.image).exists():
            problems.append(f"profile.yaml: gallery image '{photo.image}' not found in assets/img/profile/")

    if problems:
        raise DataError("\n".join(problems))

    projects.sort(key=lambda p: (cat_ids.index(p.category), p.order, p.slug))
    return site, profile, categories, projects


def load_demo(project: Project, lang: str) -> dict:
    """Compact, page-ready view of the demo reports, embedded into the project page as JSON."""
    demo = project.demo
    folder = DATA / "demos" / demo.source
    calls = []
    for c in demo.calls:
        rep = json.loads((folder / "reports" / f"{c.file}.json").read_text(encoding="utf-8"))
        a = rep["analysis"]
        scores = [
            {"key": s["criterion"], "label": CRITERIA[s["criterion"]][lang], "score": s["score"], "evidence": s["evidence"]}
            for s in a["scores"]
        ]
        percent = round(100 * sum(s["score"] for s in scores) / (5 * len(scores)), 1) if scores else 0
        calls.append({
            "id": c.file,
            "title": c.title.get(lang),
            "story": c.story.get(lang),
            "percent": percent,
            "resolved": a["resolved"],
            "flagged": a["escalation_needed"],
            "mood": SENTIMENT[a["customer_sentiment"]][lang],
            "reason": a["call_reason"],
            "summary": a["summary"],
            "scores": scores,
            "strengths": a["strengths"],
            "improvements": a["improvements"],
            "transcript": rep["transcript"],
        })

    per: dict[str, list[int]] = {}
    for call in calls:
        for s in call["scores"]:
            per.setdefault(s["key"], []).append(s["score"])
    team = sorted(
        ({"key": k, "label": CRITERIA[k][lang], "average": round(sum(v) / len(v), 2)} for k, v in per.items()),
        key=lambda r: r["average"],
    )
    return {
        "calls": calls,
        "team": team,
        "count": len(calls),
        "average": round(sum(c["percent"] for c in calls) / len(calls), 1),
        "flagged": sum(c["flagged"] for c in calls),
        "highlight": demo.highlight,
    }


def load_examples(project: Project, lang: str) -> dict:
    """The examples table: each message, the right answer, and what every model said."""
    folder = DATA / "demos" / project.examples.source
    raw = json.loads((folder / "examples.json").read_text(encoding="utf-8"))
    labels = yaml.safe_load((folder / "labels.yaml").read_text(encoding="utf-8"))
    missing = {m["expected"] for m in raw["messages"]} - set(labels)
    if missing:
        raise DataError(f"{folder.relative_to(ROOT)}/labels.yaml: no label for {sorted(missing)}")

    def name(intent):
        return labels.get(intent, {}).get(lang, intent)

    models = [{"id": m["id"], "name": m["name"][lang]} for m in raw["models"]]
    rows = []
    for msg in raw["messages"]:
        answers = [{"model": m["id"], "label": name(msg["predictions"][m["id"]]),
                    "ok": msg["predictions"][m["id"]] == msg["expected"]} for m in raw["models"]]
        rows.append({"text": msg["text"], "expected": name(msg["expected"]), "answers": answers,
                     "disagree": len({a["ok"] for a in answers}) > 1})
    totals = {m["id"]: sum(a["ok"] for r in rows for a in r["answers"] if a["model"] == m["id"]) for m in models}
    return {"models": models, "rows": rows, "totals": totals, "n": len(rows)}


# --- rendering --------------------------------------------------------------------------------

def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(SRC / "templates"),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["tojson_safe"] = lambda v: json.dumps(v, ensure_ascii=False).replace("</", "<\\/")
    return env


def page_path(lang: str, kind: str, slug: str = "") -> str:
    """Path of a page relative to dist/, always ending in index.html."""
    return {
        "home": f"{lang}/index.html",
        "projects": f"{lang}/projects/index.html",
        "project": f"{lang}/projects/{slug}/index.html",
        "about": f"{lang}/about/index.html",
        "contact": f"{lang}/contact/index.html",
    }[kind]


def render_all(env: Environment, site, profile, categories, projects) -> list[str]:
    written: list[str] = []
    used_cats = [c for c in categories if any(p.category == c.id for p in projects)]
    featured = next((p for p in projects if p.featured), projects[0] if projects else None)
    cat_by_id = {c.id: c for c in categories}

    for lang in LANGS:
        other = "ar" if lang == "en" else "en"

        def ui(key, sub=None, _lang=lang):
            v = UI[key] if sub is None else UI[key][sub]
            return v[_lang]

        def render(template: str, kind: str, slug: str = "", **ctx):
            rel = page_path(lang, kind, slug)
            depth = rel.count("/")
            root = "../" * depth
            html = env.get_template(template).render(
                lang=lang, other=other, dir="rtl" if lang == "ar" else "ltr",
                t=lambda text: text.get(lang), ui=ui, root=root, kind=kind,
                here=page_path(lang, kind, slug).removesuffix("index.html"),
                there=page_path(other, kind, slug).removesuffix("index.html"),
                site=site, profile=profile, categories=used_cats, cat_by_id=cat_by_id,
                projects=projects, featured=featured, year=date.today().year, **ctx,
            )
            out = DIST / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding="utf-8")
            written.append(rel)

        render("home.html", "home")
        render("projects.html", "projects")
        render("about.html", "about")
        render("contact.html", "contact")
        for p in projects:
            demo = load_demo(p, lang) if p.demo else None
            examples = load_examples(p, lang) if p.examples else None
            render("project.html", "project", p.slug, project=p, demo=demo, examples=examples, criteria=CRITERIA)

    # Language chooser at the root: remembered choice → browser language → site default.
    (DIST / "index.html").write_text(
        env.get_template("root.html").render(site=site), encoding="utf-8"
    )
    (DIST / "404.html").write_text(
        env.get_template("404.html").render(site=site, ui=UI), encoding="utf-8"
    )
    written += ["index.html", "404.html"]

    if site.base_url:
        base = site.base_url.rstrip("/")
        urls = "".join(f"<url><loc>{base}/{p.removesuffix('index.html')}</loc></url>" for p in written if p.endswith("index.html") and "/" in p)
        (DIST / "sitemap.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
            encoding="utf-8",
        )
    return written


def copy_static():
    shutil.copytree(SRC / "static", DIST / "static", dirs_exist_ok=True)
    if ASSETS.exists():
        shutil.copytree(ASSETS, DIST / "assets", dirs_exist_ok=True)


# --- project images ---------------------------------------------------------------------------

def find_chrome() -> Path | None:
    return next((p for p in CHROME_PATHS if p.exists()), None)


def render_shots(env: Environment, site, profile, projects) -> list[Path]:
    """Render each project's gallery images as 1200×675 pages, then photograph them.
    The same data feeds the site and the images, so they never disagree."""
    chrome = find_chrome()
    if not chrome:
        raise SystemExit("--shots needs Chrome or Edge installed")
    made: list[Path] = []
    tpl = env.get_template("shot.html")
    for p in projects:
        for lang in LANGS:
            demo = load_demo(p, lang) if p.demo else None
            examples = load_examples(p, lang) if p.examples else None
            for item in p.gallery:
                if item.layout == "own":      # a real screenshot dropped into assets/, not drawn here
                    continue
                name = item.layout or item.image.removesuffix(".png")
                html_path = DIST / "shots" / p.slug / lang / f"{name}.html"
                html_path.parent.mkdir(parents=True, exist_ok=True)
                html_path.write_text(tpl.render(
                    lang=lang, dir="rtl" if lang == "ar" else "ltr", t=lambda x, _l=lang: x.get(_l),
                    ui=lambda k, s=None, _l=lang: (UI[k] if s is None else UI[k][s])[_l],
                    shot=name, project=p, demo=demo, examples=examples, profile=profile, site=site, root="../../../",
                    width=SHOT_SIZE[0], height=SHOT_SIZE[1],
                ), encoding="utf-8")
                png = ASSETS / "projects" / p.slug / lang / item.image
                png.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run([
                    str(chrome), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=2", f"--window-size={SHOT_SIZE[0]},{SHOT_SIZE[1]}",
                    "--virtual-time-budget=8000", f"--screenshot={png}", html_path.as_uri(),
                ], check=True, capture_output=True, timeout=120)
                made.append(png)
                print(f"  image  {png.relative_to(ROOT)}")
    return made


# --- entry point ------------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shots", action="store_true", help="also render project images with headless Chrome")
    ap.add_argument("--serve", action="store_true", help="preview on http://localhost:8000 after building")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    try:
        site, profile, categories, projects = load_all()
    except DataError as exc:
        print("The data has problems — nothing was built:\n")
        print(exc)
        return 1

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    env = make_env()
    copy_static()
    if args.shots:
        render_shots(env, site, profile, projects)
        copy_static()  # pick up the fresh images
    pages = render_all(env, site, profile, categories, projects)
    print(f"built {len(pages)} pages · {len(projects)} project(s) · {len(LANGS)} languages → {DIST.relative_to(ROOT)}/")

    if args.serve:
        handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
        print(f"preview: http://localhost:{args.port}/   (Ctrl+C to stop)")
        http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
