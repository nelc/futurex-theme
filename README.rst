FutureX Indigo, a comprehensive Open edX theme
===============================================

A NELC / FutureX comprehensive theme for `Open edX <https://openedx.org>`__, built as a
flattened version of the `Indigo <https://github.com/overhangio/tutor-indigo>`__ theme.

.. image:: ./screenshots/01-landing-page.png
    :alt: Platform landing page

On top of the base Indigo styling, this theme adds **dynamic, per-tenant rendering**
("theme_v2"): the landing page, static pages, header, footer, and visual identity are
rendered at request time from configuration that is authored in the **theme designer**
(admin UI) and served by
`futurex-openedx-extensions <https://github.com/nelc/futurex-openedx-extensions>`__. This
logic lives in the ``fx_templates/`` subtree, documented below.

Installation
------------

Enable the theme like any Open edX comprehensive theme — point
``COMPREHENSIVE_THEME_DIRS`` at this repository and set ``indigo`` as the active theme
(e.g. ``tutor local do settheme indigo`` when running under Tutor). See the upstream
`tutor-indigo <https://github.com/overhangio/tutor-indigo>`__ project for the stock Indigo
options (``INDIGO_*`` color settings, dark-mode toggle, etc.).

The ``fx_templates`` architecture
----------------------------------

The dynamic theme lives in
``tutorindigo/templates/indigo/lms/templates/fx_templates/``. These are Mako templates
that render theme content from per-tenant configuration instead of hardcoded markup, so a
tenant administrator can change the site's pages and branding from the theme designer
without code changes.

Data flow
~~~~~~~~~

::

    theme designer (admin UI)
        → per-tenant config, stored & served by futurex-openedx-extensions
        → read at render time via futurex_openedx_extensions.helpers.tenants
              get_config_current_request()   # page / header / footer / branding config
              get_fx_theme_css_override()    # CSS override and/or dev CSS
        → Mako fx_templates
        → rendered HTML

``fx_static_content.html``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The shared helper library. It is imported as the ``fx_static`` namespace by the other
templates and provides the Mako ``<%def>`` helpers used to fetch configuration values and
resolve language-aware strings. Every other ``fx_*`` template builds on it.

Page / section engine (``fx_page/``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``fx_page/page.html`` is the dispatcher. Given a ``page_name`` and a list of
``allowed_sections``, it reads that page's config, iterates its ``sections`` list, and for
each visible section whose ``type`` is allowed it includes ``_section_<type>.html``
(passing the section data as ``page_contents``). Unknown or unsupported types fall back to
``_section_invalid.html``.

Each section type has its own partial, suffixed ``_v1`` to denote a versioned section
schema. Available types: ``hero_section``, ``two_columns``, ``side_image``,
``featured_courses``, ``static_metrics_section``, ``live_metrics_section``,
``faq_section``, and ``paragraph_section``.

Top-level partials
~~~~~~~~~~~~~~~~~~~

- ``fx_home.html`` — renders the home page through the section engine.
- ``fx_custom_page_template.html`` — renders configurable ``/p/<slug>`` custom pages.
- ``fx_head_extra.html`` — injects per-tenant branding (colors, meta, social image) into ``<head>``.
- ``fx_css_override.html`` — loads CSS override and the dev-CSS cookie mechanism.
- ``fx_header_navbar_links.html`` — header navigation links from config.
- ``fx_footer_links.html`` / ``fx_footer_social_links.html`` — footer link sections and social icons.
- ``fx_language_selector.html`` — language selector driven by the tenant's language settings.
- ``temporary_paragon_fix.html`` — stopgap Paragon CSS-variable fix.

Integration points
~~~~~~~~~~~~~~~~~~~

Where the base theme calls into ``fx_templates`` (paths under
``tutorindigo/templates/indigo/lms/templates/``):

- ``index.html`` → ``fx_home.html``
- ``head-extra.html`` → ``fx_head_extra.html`` + ``fx_css_override.html``
- ``footer.html`` → ``fx_footer_links.html`` + ``fx_footer_social_links.html``
- ``header/*`` → ``fx_header_navbar_links.html`` and ``fx_language_selector.html``
- ``static_templates/*.html`` → inherit ``main.html`` and include ``fx_page/page.html`` with a ``page_name``
- ``static_templates/fx_custom_page.html`` → ``fx_custom_page_template.html``

Adding a new section type
~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Add the type name to the allowed-sections list in ``fx_static_content.html``.
2. Create ``fx_page/_section_<type>.html`` taking a ``page_contents`` argument.
3. Have the theme designer emit a section of that ``type`` in the page config.

Styling
-------

To customize the static stylesheets, modify the Sass files in
``tutorindigo/templates/indigo/lms/static/sass/`` and
``tutorindigo/templates/indigo/cms/static/sass/`` — the ``_extras.scss`` files hold most
rules. Theme images live under ``tutorindigo/templates/indigo/lms/static/images/`` (and
the ``cms`` equivalent); replace them with your own to rebrand. Per-tenant CSS can also be
supplied at runtime through the theme designer (see ``fx_css_override.html`` above).

License
-------

This work is licensed under the terms of the
`GNU Affero General Public License (AGPL) <https://github.com/overhangio/tutor-indigo/blob/release/LICENSE.txt>`_.
