"""Render the pages of a website inside an Odoo process with no HTTP server.

What a script of the ``-u`` has instead of the GET the upgrade lines do: the real router,
with no server listening. A page that combines and still fails to render — a ``t-field`` to a
field that is gone, a ``t-call`` to a template that was deleted — only shows up here.

Nothing is imported from ``odoo.tests``: importing it outside test mode logs an ERROR, and
that leaves runbot red. Its ``MockRequest`` does not work for this either: ``render`` is a
lambda that renders nothing, ``httprequest`` and the router are mocks, and the ``DotDict``
session makes ``safe_eval`` warn.

Written from the simulation nmr ran on a 20.0 base for task 79519, where of four website
copies the sound one came back on and the three broken ones stayed archived.
"""

import logging

_logger = logging.getLogger(__name__)

RENDER_OK = "ok"
# Nothing listens on it: the router only needs a well-formed URL.
BASE_URL = "http://localhost/"
# What the browser gets without an error page.
OK_CODES = (301, 302, 303, 403, 404)


def _fake_request(env, site, path):
    """A request of an anonymous visitor of ``site`` for ``path``, with the real router.

    ``load_all_views`` is not optional: while the registry is not ready — which is where a
    script of the ``-u`` runs — Odoo leaves out of the combined arch every view without an
    xmlid of a loaded module, and the website copies have none. Without it every page renders
    and the gate lets everything through.
    """
    from contextlib import contextmanager

    import odoo.http
    from odoo.http._facade import HTTPRequest
    from odoo.http.requestlib import Request
    from odoo.http.session import Session, get_default_session
    from odoo.tools import lazy
    from werkzeug.test import EnvironBuilder

    @contextmanager
    def _request():
        lang_code = site.default_lang_id.code or "en_US"
        page_env = env(
            user=site.user_id,
            context=dict(env.context, website_id=site.id, load_all_views=True, lang=lang_code),
        )
        page_site = site.with_env(page_env)
        environ = EnvironBuilder(
            path=path, base_url=BASE_URL, environ_base={"REMOTE_ADDR": "127.0.0.1"}
        ).get_environ()
        request = Request(HTTPRequest(environ))
        request.type = "http"
        request.params = {}
        request.session = Session(
            dict(get_default_session(), context={"lang": ""}, force_website_id=page_site.id), "upgrade", new=True
        )
        request.db = page_env.cr.dbname
        request.registry = page_env.registry
        request.env = page_env
        request.lang = page_env["res.lang"]._get_data(code=lang_code)
        request.is_frontend = True
        request.is_frontend_multilang = True
        request.website = page_site
        request.website_routing = page_site.id
        if hasattr(page_site, "_get_and_cache_current_cart"):
            request.cart = lazy(page_site._get_and_cache_current_cart)
            request.pricelist = lazy(page_site._get_and_cache_current_pricelist)
            request.fiscal_position = lazy(page_site._get_and_cache_current_fiscal_position)

        token = odoo.http.request_var.set(request)
        try:
            yield request
        finally:
            odoo.http.request_var.reset(token)

    return _request()


def website_paths(env):
    """The pages to check: the same ones the upgrade line 2490 asks for."""
    paths = ["/", "/contactus"]
    if env["ir.module.module"].search_count([("name", "=", "website_sale"), ("state", "=", "installed")]):
        paths += ["/shop", "/shop/cart"]
        product = env["product.template"].search([("is_published", "=", True)], limit=1)
        if product:
            paths.append(product.website_url)
        category = env["product.public.category"].search([], limit=1)
        if category:
            paths.append("/shop/category/%s" % env["ir.http"]._slug(category))
    return paths


def render_page(env, site, path):
    """``RENDER_OK``, or why the page fails to render."""
    from odoo.models import BaseModel
    from werkzeug.exceptions import HTTPException, NotFound

    try:
        with _fake_request(env, site, path) as request:
            captured = {}

            def capture(template, qcontext=None, **kwargs):
                captured.update(template=template, values=dict(qcontext or {}, response_template=template))
                return "captured"

            request.render = capture
            try:
                rule, args = request.env["ir.http"]._match(path)
            except NotFound:
                # A website.page has no controller route: Odoo serves it on the fallback.
                if not request.env["ir.http"]._serve_page():
                    return "%s (404)" % RENDER_OK
            else:
                for key, value in list(args.items()):
                    if isinstance(value, BaseModel):
                        args[key] = value.with_env(request.env)
                rule.endpoint(**args)
            if "template" not in captured:
                return "%s (no qweb)" % RENDER_OK
            request.env["ir.ui.view"]._render_template(captured["template"], captured["values"])
            return RENDER_OK
    except HTTPException as e:
        return RENDER_OK if e.code in OK_CODES else "HTTP %s" % e.code
    except Exception as e:
        first_line = str(e).splitlines()[0][:200] if str(e) else ""
        return "%s: %s" % (type(e).__name__, first_line)


def render_website(env, site):
    """``RENDER_OK`` if every page of ``site`` renders, else the first failure with its path."""
    for path in website_paths(env):
        result = render_page(env, site, path)
        if not result.startswith(RENDER_OK):
            return "%s -> %s" % (path, result)
    return RENDER_OK
