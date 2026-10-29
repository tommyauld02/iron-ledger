"""Every page a suite opens has answered the age check: 18 or older.

Since b79 the app asks before anything else (mntl-dt.html, *the age check*),
and every suite but one is testing something behind it. Importing this makes
each browser context those suites create carry the app's stand-in for that
answer, window.IRON_LEDGER_ADULT, which the app reads only when the log holds
no answer of its own. Nothing is written to the log, so a fixture's saved data
is exactly what the suite wrote.

    import answered      # first, before any context is created

tests/agecheck.py does not import it: it is the suite that answers the check
itself. Ask an agent's permission is fakeai.phone()'s, since only a page that
can reach the stand-in relay ever asks it.
"""
from playwright.sync_api import Browser

ADULT_SCRIPT = "window.IRON_LEDGER_ADULT=true;"

_new_context = Browser.new_context
_new_page = Browser.new_page


def new_context(self, *a, **k):
    ctx = _new_context(self, *a, **k)
    ctx.add_init_script(ADULT_SCRIPT)
    return ctx


def new_page(self, *a, **k):
    # A page made straight off the browser has a context of its own, created
    # out of reach of new_context above; it is still on about:blank here, so
    # the script runs from its first navigation.
    page = _new_page(self, *a, **k)
    page.context.add_init_script(ADULT_SCRIPT)
    return page


Browser.new_context = new_context
Browser.new_page = new_page
