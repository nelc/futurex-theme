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
            "example.com/a b",
            "example.com/a\u00a0b",
            "a.b:\u0668\u0660",
            "http://[bad",
            "https://[x]y",
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



class CatalogFacetsTest(HelpersTestCase):
    """The catalogue filter bar always lists the five filters; cards and options match on codes, not labels."""

    def test_duration_code_boundaries(self):
        helpers = self.load()
        cases = [(None, ""), ("", ""), ("abc", ""), (0, ""), (-2, ""), (float("nan"), ""),
                 (0.5, "le3"), (3, "le3"), (3.5, "4to5"), (5, "4to5"), (5.1, "ge6"), ("12", "ge6")]
        for hours, expected in cases:
            with self.subTest(hours=hours):
                self.assertEqual(helpers.duration_code(hours), expected)
        self.assertEqual(helpers.duration_bucket(2), "3 hours or less")
        self.assertEqual(helpers.duration_bucket(None), "")

    def test_facet_codes_are_language_neutral_and_drop_unknown_values(self):
        item = program(COURSE_A, learning_mode="self_paced", level="basic", effort_hours=4, has_certificate=True,
                       status="upcoming", start_date="2030-01-05T00:00:00Z")
        expected = {"mode": "self_paced", "level": "basic", "dur": "4to5", "cert": "yes", "status": "upcoming"}
        for lang in ("en", "ar"):
            with self.subTest(lang=lang):
                self.assertEqual(self.load(lang=lang).facet_codes(item), expected)
        unknown = program(COURSE_B, learning_mode="hybrid", level=None, has_certificate=None, status="paused")
        self.assertEqual(self.load().facet_codes(unknown),
                         {"mode": "", "level": "", "dur": "", "cert": "", "status": ""})

    def test_five_filters_are_always_listed_even_with_no_values(self):
        helpers = self.load()
        for programs in ([], None, [program(COURSE_A, status=None)]):
            with self.subTest(programs=programs):
                facets = helpers.catalog_facets(programs)
                self.assertEqual([f["id"] for f in facets], ["mode", "level", "dur", "cert", "status"])
                self.assertTrue(all(f["name"] for f in facets))
                self.assertEqual([f["options"] for f in facets], [[], [], [], [], []])

    def test_a_filter_with_a_single_value_keeps_it_and_options_follow_the_fixed_order(self):
        helpers = self.load()
        programs = [
            program(COURSE_A, level="advanced", effort_hours=8, has_certificate=False, status="closed"),
            program(COURSE_B, level="basic", effort_hours=2, has_certificate=False, status="open"),
        ]
        facets = {f["id"]: f["options"] for f in helpers.catalog_facets(programs)}
        self.assertEqual(facets["mode"], [])
        self.assertEqual(facets["level"], [{"value": "basic", "label": "Basic"},
                                           {"value": "advanced", "label": "Advanced"}])
        self.assertEqual([o["value"] for o in facets["dur"]], ["le3", "ge6"])
        self.assertEqual(facets["cert"], [{"value": "no", "label": "No certificate"}])
        self.assertEqual([o["value"] for o in facets["status"]], ["open", "closed"])

    def test_upcoming_programs_share_one_status_option_whatever_their_start_date(self):
        helpers = self.load(lang="ar")
        programs = [program(COURSE_A, status="upcoming", start_date="2030-01-05T00:00:00Z"),
                    program(COURSE_B, status="upcoming", start_date="2030-02-09T00:00:00Z")]
        status = [f for f in helpers.catalog_facets(programs) if f["id"] == "status"][0]
        self.assertEqual(status["options"], [{"value": "upcoming", "label": "يبدأ قريبًا"}])


class LearnerHomeRedirectTest(HelpersTestCase):
    """The legacy /dashboard under fx-learner goes to the tenant's learner home, and never to itself."""

    def redirect(self, home, path="/dashboard"):
        helpers = self.load()
        if home is not None:
            helpers.settings.LEARNER_HOME_MICROFRONTEND_URL = home
        return helpers.learner_home_redirect(path)

    def test_learner_home_setting_is_the_target(self):
        self.assertEqual(self.redirect("/learner/my"), "/learner/my")
        self.assertEqual(self.redirect(" /learner/my "), "/learner/my")
        self.assertEqual(self.redirect("https://apps.example.sa/learner-dashboard/"),
                         "https://apps.example.sa/learner-dashboard/")

    def test_missing_setting_goes_to_the_catalogue(self):
        for home in (None, "", "   ", 5):
            with self.subTest(home=home):
                self.assertEqual(self.redirect(home), "/courses")

    def test_a_target_that_is_the_dashboard_itself_goes_to_the_catalogue(self):
        # the test stub's reverse('dashboard') is "/dashboard/"
        for home in ("/dashboard", "/dashboard/", "/dashboard?x=1", "/legacy/"):
            with self.subTest(home=home):
                self.assertEqual(self.redirect(home, path="/legacy"), "/courses")

    def test_protocol_relative_target_is_refused(self):
        self.assertEqual(self.redirect("//evil.example/x"), "/courses")


if __name__ == "__main__":
    unittest.main()
