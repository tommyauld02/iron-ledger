"""The Gym tab's bottom bar: Training at, Add movement and the rest timer.

Since b87 each is a box folded until its button in the bar is pressed, the way
Macros folds its ways in (mntl-dt.html, *gymWay*, docs/gym.md). A suite that
uses what is inside one opens it first, the way a person would:

    import gymways
    gymways.move(p)         # Add movement: #mSel, #mNew, #mDrop, #addLift
    gymways.gym(p)          # Training at: [data-gym], #editGyms, the ask
    gymways.rest(p)         # the rest timer: #restBtn, #restClock — and a
                            # press on a folded one starts the count too

Each opens its box only if it is folded, so calling it twice is harmless, and
each says whether the box is open afterwards. The Gym tab must be showing.
"""


def open_way(p, w):
    sel = '#ctxMain [data-gymway="%s"]' % w
    if p.locator(sel + '[aria-expanded="false"]').count():
        p.click(sel)
        p.wait_for_timeout(250)
    return p.locator(sel + '[aria-expanded="true"]').count() == 1


def move(p):
    return open_way(p, "move")


def gym(p):
    return open_way(p, "gym")


def rest(p):
    return open_way(p, "rest")
