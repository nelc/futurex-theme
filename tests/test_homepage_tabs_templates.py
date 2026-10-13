"""Render tests for the Indigo homepage tabs (featured-courses section).

Mako plus minimal stubs for the platform imports; no Open edX needed.
Run:  python -m unittest discover -s tests -v      (needs `pip install mako`)
Regenerate the no-tabs baseline from ORIGINAL templates (pre-tabs checkout):
      python tests/test_homepage_tabs_templates.py --baseline-from <templates-root>
"""

import datetime
import json
import sys
import types
import unittest
from html.parser import HTMLParser
from pathlib import Path

from mako.lookup import TemplateLookup

HERE = Path(__file__).parent
THEME_ROOT = HERE.parent / "tutorindigo" / "templates" / "indigo" / "lms" / "templates"
BASELINE_DIR = HERE / "fixtures" / "baseline"
SECTION = "/fx_templates/fx_page/_section_featured_courses_v1.html"
LANG = {"code": "en"}


def _install_stubs():
    """Stand-ins for the edx-platform / Django modules the templates import."""

    def mod(name, **attrs):
        module = types.ModuleType(name)
        module.__dict__.update(attrs)
        sys.modules[name] = module
        return module

    mod("django")
    mod("django.utils")
    mod(
        "django.utils.translation",
        gettext=lambda text: text,
        get_language=lambda: LANG["code"],
    )
    mod("django.urls", reverse=lambda name, args=None: "/courses/%s/about" % args[0])
    mod("django.conf", settings=types.SimpleNamespace())
    mod("futurex_openedx_extensions")
    mod("futurex_openedx_extensions.helpers")
    mod(
        "futurex_openedx_extensions.helpers.tenants",
        get_config_current_request=lambda keys: {},
    )
    for name in ("lms", "lms.djangoapps", "lms.djangoapps.branding"):
        mod(name)
    mod("lms.djangoapps.branding.api")
    sys.modules["lms.djangoapps.branding"].api = sys.modules[
        "lms.djangoapps.branding.api"
    ]


_install_stubs()


class Course:
    def __init__(self, idx, open_=True, ended=False):
        self.id = "course-v1:org+C%02d+run" % idx
        self.start = datetime.datetime(2026, 1, 1)
        self.advertised_start = None
        self.display_name_with_default = "Course %02d" % idx
        self.display_number_with_default = "C%02d" % idx
        self.display_org_with_default = "org"
        self.course_image_url = "/img/%d.png" % idx
        self._open, self._ended = open_, ended

    def is_enrollment_open(self):
        return self._open

    def has_ended(self):
        return self._ended


def make_courses(count, closed=()):
    return [Course(i, open_=i not in closed) for i in range(count)]


def cid(idx):
    return Course(idx).id


def render(root, courses, grid, tabs=None, lang="en"):
    LANG["code"] = lang
    lookup = TemplateLookup(
        directories=[str(HERE / "stubs"), str(root)], input_encoding="utf-8"
    )
    contents = {
        "title": {"en": "T"},
        "description": {"en": "D"},
        "div_id": "feat",
        "grid_type": grid,
    }
    if tabs is not None:
        contents["tabs"] = tabs
    return lookup.get_template(SECTION).render(
        page_contents=contents,
        courses=courses,
        settings=types.SimpleNamespace(FEATURES={"COURSES_ARE_BROWSABLE": True}),
        marketing_link=lambda name: "/courses",
        LANGUAGE_CODE=lang,
    )


def make_tabs(n, courses_per_tab=3):
    """n tabs; tab i holds courses 2i .. 2i+courses_per_tab-1 (overlapping on purpose)."""
    items = [
        {
            "id": "t%d" % i,
            "enabled": True,
            "name": {"ar": "تبويب %d" % i, "en": "Tab %d" % i},
            "course_ids": [cid(j) for j in range(i * 2, i * 2 + courses_per_tab)],
        }
        for i in range(n)
    ]
    return {"enabled": True, "items": items}


class Page(HTMLParser):
    """Collects the pills, card ids and bar/status attributes from rendered output."""

    def __init__(self, html):
        super().__init__()
        self.pills, self.cards, self.bar, self.status = [], [], None, None
        self._pill = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "div" and "data-fx-tabs-bar" in a:
            self.bar = a
        elif tag == "button" and "data-fx-tab" in a:
            self._pill = {
                "id": a["data-fx-tab"],
                "pressed": a.get("aria-pressed"),
                "ids": a.get("data-fx-ids"),
                "label": "",
            }
            self.pills.append(self._pill)
        elif tag == "p" and "data-fx-tabs-status" in a:
            self.status = a
        elif "data-fx-course-id" in a:
            self.cards.append(a["data-fx-course-id"])

    def handle_data(self, data):
        if self._pill is not None:
            self._pill["label"] += data

    def handle_endtag(self, tag):
        if tag == "button":
            self._pill = None


CASES = [(n, g) for n in (0, 1, 20) for g in ("categorised", "max-3", "max-9", "all")]


def fixture_path(n, grid):
    return BASELINE_DIR / ("%d-%s.html" % (n, grid))


class NoTabsOutputUnchanged(unittest.TestCase):
    """Baseline = output of the ORIGINAL templates (pre-tabs)."""

    def test_no_tabs_key(self):
        for n, grid in CASES:
            with self.subTest(n=n, grid=grid):
                self.assertEqual(
                    render(THEME_ROOT, make_courses(n), grid),
                    fixture_path(n, grid).read_text(),
                )

    def test_tabs_disabled_or_malformed(self):
        variants = [
            {"enabled": False, "items": make_tabs(2)["items"]},
            {"items": make_tabs(2)["items"]},
            {"enabled": "true", "items": make_tabs(2)["items"]},
            {"enabled": True},
            {"enabled": True, "items": "nope"},
            {"enabled": True, "items": [None, 5, {"enabled": True}]},
            "garbage",
            [],
        ]
        for n in (0, 1, 20):
            for tabs in variants:
                with self.subTest(n=n, tabs=tabs):
                    self.assertEqual(
                        render(THEME_ROOT, make_courses(n), "categorised", tabs),
                        fixture_path(n, "categorised").read_text(),
                    )

    def test_non_categorised_grids_render_no_tabs(self):
        for n in (1, 20):
            for grid in ("max-3", "max-9", "all"):
                with self.subTest(n=n, grid=grid):
                    self.assertEqual(
                        render(THEME_ROOT, make_courses(n), grid, make_tabs(3)),
                        fixture_path(n, grid).read_text(),
                    )


class TabsRendering(unittest.TestCase):
    def test_matrix_courses_by_tabs(self):
        for n in (0, 1, 20):
            for tabs_n in range(7):
                with self.subTest(courses=n, tabs=tabs_n):
                    tabs = make_tabs(tabs_n)
                    page = Page(
                        render(THEME_ROOT, make_courses(n), "categorised", tabs)
                    )
                    shown = [
                        t["id"]
                        for t in tabs["items"]
                        if any(c in {cid(i) for i in range(n)} for c in t["course_ids"])
                    ]
                    self.assertEqual(len(page.cards), n if shown else 0)
                    if not shown:
                        self.assertEqual(page.pills, [])
                        self.assertIsNone(page.bar)
                        continue
                    self.assertEqual([p["id"] for p in page.pills], ["all"] + shown)
                    self.assertIn("hidden", page.bar)  # revealed by JS only

    def test_all_first_pressed_and_localised(self):
        pills = Page(
            render(THEME_ROOT, make_courses(5), "categorised", make_tabs(2))
        ).pills
        self.assertEqual(
            (pills[0]["id"], pills[0]["pressed"], pills[0]["label"]),
            ("all", "true", "All"),
        )
        self.assertTrue(all(p["pressed"] == "false" for p in pills[1:]))
        ar = Page(
            render(THEME_ROOT, make_courses(5), "categorised", make_tabs(2), lang="ar")
        ).pills
        self.assertEqual((ar[0]["label"], ar[1]["label"]), ("الكل", "تبويب 0"))

    def test_membership_and_card_ids(self):
        tabs = make_tabs(2)
        tabs["items"][1]["course_ids"] = [
            cid(1),
            cid(4),
            "course-v1:no+such+run",
            7,
            None,
        ]
        page = Page(render(THEME_ROOT, make_courses(6), "categorised", tabs))
        self.assertEqual(page.cards, [cid(i) for i in range(6)])
        self.assertEqual(json.loads(page.pills[1]["ids"]), [cid(0), cid(1), cid(2)])
        self.assertEqual(
            json.loads(page.pills[2]["ids"]), [cid(1), cid(4), "course-v1:no+such+run"]
        )

    def test_course_in_several_tabs_is_allowed(self):
        tabs = {
            "enabled": True,
            "items": [
                dict(id=i, enabled=True, name={"en": i}, course_ids=[cid(0)])
                for i in ("a", "b")
            ],
        }
        pills = Page(render(THEME_ROOT, make_courses(2), "categorised", tabs)).pills
        self.assertEqual(
            [json.loads(p["ids"]) for p in pills[1:]], [[cid(0)], [cid(0)]]
        )

    def test_closed_or_ended_ids_are_ignored_and_all_ended_tab_hidden(self):
        courses = make_courses(4, closed={1, 2})
        courses[3]._ended = True
        tabs = {
            "enabled": True,
            "items": [
                {
                    "id": "dead",
                    "enabled": True,
                    "name": {"en": "Dead"},
                    "course_ids": [cid(1), cid(2), cid(3)],
                },
                {
                    "id": "mixed",
                    "enabled": True,
                    "name": {"en": "Mixed"},
                    "course_ids": [cid(0), cid(1), cid(3)],
                },
            ],
        }
        page = Page(render(THEME_ROOT, courses, "categorised", tabs))
        self.assertEqual([p["id"] for p in page.pills], ["all", "mixed"])
        self.assertEqual(
            page.cards, [cid(0)]
        )  # only open, not-ended courses are rendered at all

    def test_invalid_items_are_skipped(self):
        def item(id_, name, enabled=True, ids=None):
            return {
                "id": id_,
                "enabled": enabled,
                "name": name,
                "course_ids": [cid(0)] if ids is None else ids,
            }

        tabs = {
            "enabled": True,
            "items": [
                item("off", {"en": "Off"}, enabled=False),
                item("noname", {}),
                item("all", {"en": "Fake all"}),
                item("ok", {"en": "Ok"}),
                item("ok", {"en": "Dup"}),
                item("", {"en": "Empty id"}),
                item("nolist", {"en": "N"}, ids="x"),
            ],
        }
        pills = Page(render(THEME_ROOT, make_courses(2), "categorised", tabs)).pills
        self.assertEqual(
            [(p["id"], p["label"]) for p in pills], [("all", "All"), ("ok", "Ok")]
        )

    def test_names_and_ids_are_escaped(self):
        evil = '<script>alert(1)</script>"><img src=x onerror=alert(2)>'
        tabs = {
            "enabled": True,
            "items": [
                {
                    "id": evil,
                    "enabled": True,
                    "name": {"en": evil},
                    "course_ids": [cid(0)],
                }
            ],
        }
        html = render(THEME_ROOT, make_courses(2), "categorised", tabs)
        self.assertNotIn("<img src=x", html)
        self.assertNotIn("<script>alert(1)", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        pill = Page(html).pills[1]
        self.assertEqual(
            (pill["id"], pill["label"]), (evil, evil)
        )  # round-trips as text, not markup

    def test_live_region_and_script_present_only_with_visible_tabs(self):
        with_tabs = render(THEME_ROOT, make_courses(3), "categorised", make_tabs(1))
        status = Page(with_tabs).status
        self.assertEqual(status["aria-live"], "polite")
        self.assertIn("{count}", status["data-fx-tabs-status-text"])
        self.assertIn("history.replaceState", with_tabs)
        self.assertNotIn(
            "history.replaceState", render(THEME_ROOT, make_courses(3), "categorised")
        )


def write_baseline(root):
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    for n, grid in CASES:
        fixture_path(n, grid).write_text(render(Path(root), make_courses(n), grid))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--baseline-from":
        write_baseline(sys.argv[2])
    else:
        unittest.main()
