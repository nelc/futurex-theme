"""Tests for the fx-learner theme helpers (tutorindigo/templates/fx-learner/.../fx_learner/helpers.html).

The helpers are plain module-level Python inside a Mako template, so they are tested through the compiled
template module. Mako plus minimal stubs for the platform imports; no Open edX needed.
Run:  python -m unittest discover -s tests -v      (needs `pip install mako`)
"""

import sys
import types
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

from mako.template import Template

HERE = Path(__file__).parent
HELPERS = (
    HERE.parent / "tutorindigo" / "templates" / "fx-learner" / "lms" / "templates" / "fx_learner" / "helpers.html"
)

COURSE_A = "course-v1:org+A+run"
COURSE_B = "course-v1:org+B+run"


def program(course_id, category_ids=(), **extra):
    data = {"id": course_id, "title": "Program " + course_id[-5], "about_url": "/courses/%s/about" % course_id,
            "category_ids": list(category_ids), "status": "open", "price": None}
    data.update(extra)
    return data


def home_config(tab_items):
    return {"pages_home": {"sections": [{
        "type": "featured_courses_v1", "visible": True, "tabs": {"enabled": True, "items": tab_items},
    }]}}


TABS = [{"id": "tab-1", "enabled": True, "name": {"ar": "القيادة", "en": "Leadership"}, "course_ids": [COURSE_A]}]


class Course:
    def __init__(self, course_id):
        self.id = course_id
        self.display_name_with_default = "Course"
        self.course_image_url = None
        self.effort = None
        self.enrollment_start = None
        self.start = None

    def is_enrollment_open(self):
        return True


class HelpersTestCase(unittest.TestCase):
    """Loads helpers.html with stubbed platform modules; `plugin` is the learner_theme helper module (or None)."""

    def load(self, plugin=None, config=None, lang="en"):
        def mod(name, **attrs):
            module = types.ModuleType(name)
            module.__dict__.update(attrs)
            return module

        self.config = config or {}
        self.lang = {"code": lang}
        helpers_pkg = mod("futurex_openedx_extensions.helpers")
        stubs = {
            "django": mod("django"),
            "django.conf": mod("django.conf", settings=types.SimpleNamespace()),
            "django.urls": mod("django.urls", reverse=lambda name, args=None: "/%s/%s" % (name, (args or [""])[0])),
            "django.utils": mod("django.utils", timezone=types.SimpleNamespace(now=lambda: None)),
            "django.utils.translation": mod("django.utils.translation", get_language=lambda: self.lang["code"]),
            "futurex_openedx_extensions": mod("futurex_openedx_extensions"),
            "futurex_openedx_extensions.helpers": helpers_pkg,
            "futurex_openedx_extensions.helpers.tenants": mod(
                "futurex_openedx_extensions.helpers.tenants",
                get_config_current_request=lambda keys: {"values": {key: self.config.get(key) for key in keys}},
            ),
        }
        if plugin is not None:
            helpers_pkg.learner_theme = plugin
            stubs["futurex_openedx_extensions.helpers.learner_theme"] = plugin
        patcher = mock.patch.dict(sys.modules, stubs)
        patcher.start()
        self.addCleanup(patcher.stop)
        return Template(filename=str(HELPERS), input_encoding="utf-8").module


class CatalogCategoriesTest(HelpersTestCase):
    """Tabs/badges and the programs' category_ids must come from one id space (review finding 1)."""

    def test_new_plugin_categories_label_the_plugin_ids(self):
        plugin = types.SimpleNamespace(
            get_learner_theme_catalog=lambda request: [program(COURSE_A, ["leadership"]), program(COURSE_B, [7])],
            get_learner_theme_categories=lambda request: [
                {"id": "leadership", "name": {"ar": "القيادة", "en": "Leadership"}},
                {"id": 7, "name": {"ar": "التقنية", "en": "Technology"}},
                {"id": "leadership", "name": {"en": "Duplicate"}},
                {"id": "nameless", "name": {}},
                {"id": "all", "name": {"en": "Reserved id"}},
                "junk",
            ],
        )
        helpers = self.load(plugin, home_config(TABS), lang="ar")
        programs, categories = helpers.catalog_view(object())
        self.assertEqual(categories, [{"id": "leadership", "name": "القيادة"}, {"id": "7", "name": "التقنية"}])
        self.assertEqual([p["category_ids"] for p in programs], [["leadership"], ["7"]])

    def test_plugin_without_categories_helper_uses_home_tabs_for_both(self):
        plugin = types.SimpleNamespace(
            get_learner_theme_catalog=lambda request: [program(COURSE_A, ["leadership"]), program(COURSE_B, [])],
        )
        helpers = self.load(plugin, home_config(TABS))
        programs, categories = helpers.catalog_view(object())
        self.assertEqual(categories, [{"id": "tab-1", "name": "Leadership"}])
        self.assertEqual([p["category_ids"] for p in programs], [["tab-1"], []])

    def test_failing_categories_helper_uses_home_tabs_for_both(self):
        def boom(request):
            raise RuntimeError("boom")

        plugin = types.SimpleNamespace(
            get_learner_theme_catalog=lambda request: [program(COURSE_A, ["leadership"])],
            get_learner_theme_categories=boom,
        )
        helpers = self.load(plugin, home_config(TABS))
        with self.assertLogs(level="ERROR"):
            programs, categories = helpers.catalog_view(object())
        self.assertEqual(categories, [{"id": "tab-1", "name": "Leadership"}])
        self.assertEqual(programs[0]["category_ids"], ["tab-1"])

    def test_no_plugin_keeps_the_view_course_list_and_home_tabs(self):
        helpers = self.load(None, home_config(TABS))
        programs, categories = helpers.catalog_view(object(), [Course(COURSE_A), Course(COURSE_B)])
        self.assertEqual(categories, [{"id": "tab-1", "name": "Leadership"}])
        self.assertEqual([p["category_ids"] for p in programs], [["tab-1"], []])
        self.assertTrue(all(p["_fallback"] for p in programs))


class PriceTextTest(HelpersTestCase):
    """"Free" only when the backend looked at every paid mode; amounts carry their currency (finding 2)."""

    def test_new_backend(self):
        helpers = self.load()
        cases = [
            ({"price": None, "currency": None}, "Free"),
            ({"price": 0, "currency": "SAR"}, "Free"),
            ({"price": Decimal("0.00"), "currency": "SAR"}, "Free"),
            ({"price": Decimal("300.00"), "currency": "sar"}, "300 SAR"),
            ({"price": "150.5", "currency": "USD"}, "150.50 USD"),
            ({"price": 250, "currency": None}, "250"),
            ({"price": "abc", "currency": "SAR"}, ""),
            ({"price": -5, "currency": "SAR"}, ""),
        ]
        for data, expected in cases:
            with self.subTest(data=data):
                self.assertEqual(helpers.price_text(data), expected)

    def test_arabic(self):
        helpers = self.load(lang="ar")
        self.assertEqual(helpers.price_text({"price": Decimal("300.00"), "currency": "SAR"}), "300 ريال")
        self.assertEqual(helpers.price_text({"price": None, "currency": None}), "مجانًا")

    def test_older_backend_never_claims_free(self):
        helpers = self.load()
        self.assertEqual(helpers.price_text({"price": None}), "")
        self.assertEqual(helpers.price_text({"price": Decimal("250.00")}), "250")

    def test_view_fallback_never_claims_free(self):
        helpers = self.load()
        self.assertEqual(helpers.price_text({"price": None, "currency": None, "_fallback": True}), "")


class SafeUrlTest(HelpersTestCase):
    """Tenant-config URLs are printed in href only through safe_url (finding 4)."""

    def test_entity_site_url(self):
        for raw, expected in [
            ("https://example.sa", "https://example.sa"),
            ("/about", "/about"),
            ("javascript:alert(1)", ""),
            (" JavaScript:alert(1)", ""),
            ("data:text/html,x", ""),
            ("//evil.example", ""),
            ({"x": 1}, ""),
            (None, ""),
        ]:
            with self.subTest(raw=raw):
                helpers = self.load(config={"entity_identity": {"site_url": raw}})
                self.assertEqual(helpers.entity()["site_url"], expected)

    def test_safe_url_adds_https_to_a_link_saved_without_a_scheme(self):
        helpers = self.load()
        for raw, expected in [
            ("www.example.sa", "https://www.example.sa"),
            ("example.com/path?a=1", "https://example.com/path?a=1"),
            ("x.com/name", "https://x.com/name"),
            ("sub.domain.org:8443/x", "https://sub.domain.org:8443/x"),
            ("  www.example.sa  ", "https://www.example.sa"),
            ("/about", "/about"),
            ("#faq", "#faq"),
            ("http://example.sa/x", "http://example.sa/x"),
            ("HTTPS://example.sa", "HTTPS://example.sa"),
            ("mailto:user@example.com", "mailto:user@example.com"),
            ("tel:+966110000000", "tel:+966110000000"),
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(helpers.safe_url(raw), expected)

    def test_safe_url_still_rejects_everything_that_is_not_a_plain_host(self):
        helpers = self.load()
        for raw in [
            "javascript:alert(1)",
            "JaVaScRiPt:x",
            "data:text/html,x",
            "//evil.com",
            "/\\evil.com",
            "vbscript:x",
            "www.exa mple.sa",
            "example.com/a b",
            "example.com\tx",
            "www.example.sa\njavascript:alert(1)",
            "java\nscript:alert(1)",
            "javascript:alert(1).com",
            "user@example.com",
            "faq",
            "example.com:abc",
            "evil:example.com",
            "example.com:123456",
            "",
            "   ",
            None,
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(helpers.safe_url(raw), "")

    def test_safe_links_drops_unsafe_targets_and_keeps_the_rest_untouched(self):
        helpers = self.load()
        links = [
            {"link": "/courses", "new_tab": "", "link_title": {"en": "Programs"}},
            {"link": "javascript:alert(1)", "new_tab": ""},
            {"link": "https://example.sa/x", "new_tab": 'target="_blank" rel="noopener"'},
            {"link": {"not": "a string"}},
            "junk",
        ]
        self.assertEqual(helpers.safe_links(links), [links[0], links[2]])
        social = [{"provider": "x", "value": "https://x.com/a"}, {"provider": "x", "value": "vbscript:x"}]
        self.assertEqual(helpers.safe_links(social, "value"), [social[0]])
        self.assertEqual(helpers.safe_links(None), [])
        bare = [{"link": "www.example.sa/x", "new_tab": ""}]
        self.assertEqual(helpers.safe_links(bare), [{"link": "https://www.example.sa/x", "new_tab": ""}])


if __name__ == "__main__":
    unittest.main()
