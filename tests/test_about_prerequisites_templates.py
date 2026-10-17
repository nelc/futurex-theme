"""Render tests for the Indigo course About page: prerequisites list, completed marks, effort hours.

Mako plus minimal stubs for the platform imports and a fake ORM that counts queries; no Open edX needed.
Run:  python -m unittest discover -s tests -v      (needs `pip install mako`)
"""

import datetime
import sys
import types
import unittest
from pathlib import Path

from mako.lookup import TemplateLookup

HERE = Path(__file__).parent
THEME_ROOT = HERE.parent / "tutorindigo" / "templates" / "indigo" / "lms" / "templates"
ABOUT = "/courseware/course_about.html"
QUERIES = []  # one entry per fake ORM query, e.g. "overviews" / "certificates"


def _mod(name, **attrs):
    """Create the stub module, or only ADD missing names to one another test file installed (never overwrite)."""
    module = sys.modules.get(name) or types.ModuleType(name)
    for key, value in attrs.items():
        module.__dict__.setdefault(key, value)
    sys.modules[name] = module
    return module


class _Rows(list):
    def values_list(self, *_fields, flat=False):
        return list(self)


class _Overviews:
    """Fake CourseOverview.objects: knows courses P1..P4 only."""

    @staticmethod
    def filter(id__in):
        QUERIES.append("overviews")
        return [
            types.SimpleNamespace(id=key, display_name="Name of %s" % key)
            for key in id__in
            if key in ("P1", "P2", "P3", "P4")
        ]


class _Certificates:
    """Fake GeneratedCertificate.objects: P1 downloadable, P2 notpassing, for the user named 'learner'."""

    ROWS = [("learner", "P1", "downloadable"), ("learner", "P2", "notpassing")]

    @staticmethod
    def filter(user, course_id__in, status):
        QUERIES.append("certificates")
        return _Rows(
            course for name, course, state in _Certificates.ROWS
            if name == user.name and course in course_id__in and state == status
        )


def _reverse(name, args=None):
    return "/courses/%s/about" % args[0] if args else "/" + name


def _install_stubs():
    for name in ("django", "django.utils", "django.conf", "lms", "lms.djangoapps", "common", "common.djangoapps",
                 "openedx", "openedx.core", "openedx.core.lib", "openedx.core.djangolib",
                 "openedx.core.djangoapps", "openedx.core.djangoapps.content",
                 "openedx.core.djangoapps.content.course_overviews", "lms.djangoapps.certificates",
                 "lms.djangoapps.courseware", "common.djangoapps.edxmako", "eox_nelp"):
        _mod(name)
    _mod("six")
    _mod("django.utils.translation", gettext=lambda text: text, pgettext=lambda ctx, text: text,
         get_language=lambda: "en")
    _mod("django.urls", reverse=_reverse)
    _mod("django.conf", settings=types.SimpleNamespace(FEATURES={}))
    _mod("lms.djangoapps.courseware.courses", get_course_about_section=lambda request, course, section: request.sections.get(section, ""))
    _mod("common.djangoapps.edxmako.shortcuts", marketing_link=lambda name: "/")
    _mod("openedx.core.djangolib.js_utils", js_escaped_string=lambda text: text)
    _mod("openedx.core.djangolib.markup", clean_dangerous_html=lambda text: text, HTML=str, Text=str)
    _mod("openedx.core.lib.courses", course_image_url=lambda course: "")
    _mod("openedx.core.djangoapps.content.course_overviews.models", CourseOverview=types.SimpleNamespace(objects=_Overviews))
    _mod("lms.djangoapps.certificates.data", CertificateStatuses=types.SimpleNamespace(downloadable="downloadable"))
    _mod("lms.djangoapps.certificates.models", GeneratedCertificate=types.SimpleNamespace(objects=_Certificates))
    _mod("eox_nelp.effort", format_effort_hours=lambda effort: "FMT(%s)" % effort)


def render(prereqs, user=None, effort="", sections=None):
    """Render the real About template; `user=None` is an anonymous visitor."""
    _install_stubs()  # re-added per render: another test file may have replaced shared modules since import
    urls = sys.modules["django.urls"]
    saved_reverse, urls.reverse = urls.reverse, _reverse  # this page also reverses name-only routes
    del QUERIES[:]
    lookup = TemplateLookup(directories=[str(HERE / "stubs"), str(THEME_ROOT)], input_encoding="utf-8")
    sections = dict(sections or {}, effort=effort)
    visitor = user or types.SimpleNamespace(is_authenticated=False, name=None)
    course = types.SimpleNamespace(
        id="MAIN", display_name_with_default="Main", display_number_with_default="MAIN", display_org_with_default="org",
        start=datetime.datetime(2026, 1, 1), end=None, advertised_start=None, start_date_is_still_default=False,
    )
    try:
        return _render_about(lookup, course, sections, visitor, prereqs)
    finally:
        urls.reverse = saved_reverse


def _render_about(lookup, course, sections, visitor, prereqs):
    return lookup.get_template(ABOUT).render(
        course=course, request=types.SimpleNamespace(sections=sections, path="/"), user=visitor,
        registered=False, active_reg_button=False, is_shib_course=False, can_enroll=True, invitation_only=False,
        is_course_full=False, show_courseware_link=False, course_target="/", staff_access=False, studio_url=None,
        is_cosmetic_price_enabled=False, course_price=None, ecommerce_checkout=False, single_paid_mode=None,
        sidebar_html_enabled=False, allow_anonymous=True, course_image_urls={"large": "/x.png"}, LANGUAGE_CODE="en",
        pre_requisite_courses=[{"key": key, "display": "org %s" % key} for key in prereqs],
    )


LEARNER = types.SimpleNamespace(is_authenticated=True, name="learner")


class PrerequisitesSection(unittest.TestCase):
    def test_hidden_when_there_are_none_and_no_query(self):
        html = render([], LEARNER)
        self.assertNotIn("prerequisite-course", html)
        self.assertEqual(QUERIES, [])

    def test_lists_every_prerequisite_with_name_and_same_tenant_link(self):
        html = render(["P1", "P2", "P3"])
        for key in ("P1", "P2", "P3"):
            self.assertIn('<a href="/courses/%s/about">Name of %s</a>' % (key, key), html)
        self.assertEqual(html.count("prerequisite-list-item"), 3)
        self.assertLess(html.index("Name of P1"), html.index("Name of P3"))

    def test_single_prerequisite(self):
        html = render(["P4"])
        self.assertEqual(html.count("prerequisite-list-item"), 1)

    def test_anonymous_gets_no_marks_and_no_certificate_query(self):
        html = render(["P1", "P2", "P3"])
        self.assertNotIn("is-completed", html)
        self.assertEqual(QUERIES, ["overviews"])

    def test_learner_marks_only_downloadable_certificates_with_one_query_each(self):
        html = render(["P1", "P2", "P3"], LEARNER)
        self.assertEqual(html.count("is-completed"), 1)
        self.assertEqual(html.count("prerequisite-check"), 1)
        self.assertEqual(html.count('<span class="sr">Completed</span>'), 1)
        self.assertLess(html.index("is-completed"), html.index("Name of P2"))  # the mark belongs to P1
        self.assertEqual(QUERIES, ["overviews", "certificates"])

    def test_missing_course_is_skipped_and_logged(self):
        with self.assertLogs(level="ERROR") as logs:
            html = render(["P1", "GONE", "P3"], LEARNER)
        self.assertEqual(html.count("prerequisite-list-item"), 2)
        self.assertIn("GONE", logs.output[0])

    def test_all_prerequisites_missing_hides_the_section(self):
        with self.assertLogs(level="ERROR"):
            html = render(["GONE"], LEARNER)
        self.assertNotIn("prerequisite-course", html)

    def test_free_text_requirements_row_is_kept(self):
        html = render(["P1"], sections={"prerequisites": "<p>Hand typed</p>"})
        self.assertIn('class="important-dates-item-text prerequisites"', html)


class EffortRow(unittest.TestCase):
    def test_effort_goes_through_the_hours_formatter(self):
        self.assertIn('effort">FMT(4:30)<', render([], effort="4:30"))

    def test_no_effort_no_row(self):
        self.assertNotIn("Estimated Effort", render([]))


if __name__ == "__main__":
    unittest.main()
