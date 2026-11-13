"""Macros' ways to log food: Ask an agent, Log numbers and Scan.

Since b98 they are on the plate's sheet (mntl-dt.html, *waysOpen*,
docs/ui.md, *The plate*): the plate above the tabs says Log food, and a press
on it brings up the three ways, each with a line saying what it is for. A
suite reaches one the way a person does, the plate and then the way:

    import logways
    logways.open_way(p, "numbers")   # Log numbers: #fCal, #fPro, #addFood
    logways.open_way(p, "estimate")  # Ask an agent: #estText, #runEst
    logways.press(p, "estimate")     # the plate, then that button, whatever
                                     # it does: opens a folded way, folds an
                                     # open one
    logways.scan(p)                  # the plate, then Scan
    logways.states(p)                # {"numbers": "false", "estimate": "true"}

open_way opens its box only if it is folded, so calling it twice is harmless.
The sheet stands outside #view and its buttons keep their state (aria-expanded)
while it is hidden, which is what states() reads. The Macros tab must be
showing, with no other sheet over it and the keyboard away: the plate is in
the dock, and goes with it.
"""


UP = "#waysSheet:not([hidden])"


def sheet(p):
    """Bring up the plate's sheet, if it is not up already."""
    if not p.locator(UP).count():
        p.click("#plate")
        p.wait_for_timeout(150)


def shut(p):
    if p.locator(UP).count():
        p.click("#waysClose")
        p.wait_for_timeout(100)


def open_way(p, w, wait=250):
    sel = '#waysSheet [data-logway="%s"]' % w
    if p.get_attribute(sel, "aria-expanded") == "false":
        sheet(p)
        p.click(sel)
    else:
        shut(p)
    p.wait_for_timeout(wait)


def press(p, w, wait=250):
    sheet(p)
    p.click('#waysSheet [data-logway="%s"]' % w)
    p.wait_for_timeout(wait)


def scan(p, wait=0):
    sheet(p)
    p.click("#waysSheet [data-scanway]")
    if wait:
        p.wait_for_timeout(wait)


def states(p):
    """Which ways are open. The sheet's buttons stand in the page whether or
    not the sheet is showing, and carry it."""
    return p.evaluate("()=>Object.fromEntries([...document.querySelectorAll('#waysSheet [data-logway]')]"
                      ".map(b=>[b.dataset.logway,b.getAttribute('aria-expanded')]))")
