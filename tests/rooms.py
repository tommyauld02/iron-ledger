"""Opening a tab by its name, Pantry included.

Since b99 Pantry is not a tab of its own: it is the second section of Macros,
reached through the switch at the top of the sheet (mntl-dt.html,
*foodSegHtml*; docs/pantry.md, *Pantry is a section of Macros*). A suite that
walks the tabs by name, or goes to Pantry the way it always did, opens them
through here, as a person does:

    import rooms
    rooms.go(p, "gym")       # the Gym tab
    rooms.go(p, "pantry")    # the Macros tab, then Pantry on the switch

Choosing Pantry scrolls the page so the switch sits at the top of the screen
(the list starts under a picture most of a screen tall). go() waits for that
to finish, so what is measured next is measured on a page standing still.

Like a tab press, a press on the switch redraws the section even when it is
already showing, which is what a suite pressing "the Pantry tab" twice to get
a clean screen relies on.
"""

PANTRY = '[data-fseg="pantry"]'
LEDGER = '[data-fseg="macros"]'
MACROS_TAB = '.tabs button[data-tab="macros"]'


def settle(p, tries=40):
    """Wait until the page has stopped scrolling."""
    last = None
    for _ in range(tries):
        y = p.evaluate("() => Math.round(window.scrollY)")
        if y == last:
            return
        last = y
        p.wait_for_timeout(70)


def go(p, tab, wait=0, **kw):
    if tab == "pantry":
        # the switch is only on the Macros tab, in either of its sections
        if not p.locator(PANTRY).count():
            p.click(MACROS_TAB, **kw)
            p.wait_for_timeout(120)
        p.click(PANTRY, **kw)
        p.wait_for_timeout(120)
        settle(p)
    else:
        p.click('.tabs button[data-tab="%s"]' % tab, **kw)
    if wait:
        p.wait_for_timeout(wait)


def showing(p):
    """Which tab is on screen, by the name suites use: 'pantry' for Macros'
    second section, otherwise the selected tab."""
    if p.locator(PANTRY + '[aria-pressed="true"]').count():
        return "pantry"
    return p.evaluate("() => { var b = document.querySelector('.tabs button[aria-selected=\"true\"]'); return b ? b.dataset.tab : null; }")
