# Progress: check-ins, photos and Compare

The Progress tab (b90). The seven rules in `CLAUDE.md` apply here too.

**A check-in a day, if you want one (b90).** Asked for by Tommy (2026-11-07):
a tab to the left of Log holding, for any day you choose, a photo, a note and
your weight. Any one of them is a check-in, and there is no daily nag. The tab
lists the days that have one, grouped by month under a year arrow like the
Log's, and tapping a date opens the whole check-in in a sheet. He saw the
concept as eight phone-size mock-ups first and chose one photo per check-in
(not front, side and back).

**The list shows dates, not photos.** The tab opens at the gym, in front of
other people, and progress photos are often taken with a shirt off. So the
list and the card on top carry no thumbnails: a camera and a note icon, the
weight, and the date. A photo is only drawn once its day is tapped.

**The note and the photo's name live in the log; the weight is Body
weight.** A check-in is `store.days[k].prog`: `{ at, note, photo }`, where
`photo` is an id and `note` is up to 600 characters. The weight is the day's
`bw`, the same number the Log's Body weight card plots and trends, so a day
never has two weights. The editor fills it from the day's weigh-in and says
that changing it changes Body weight. An unchanged weight is compared as shown
(`bwShow`), not converted back, so a kg phone that saves without touching it
leaves the pounds exactly as they were. Clearing it takes the weigh-in off,
and the Undo label says so.

**The photo is kept beside the log, never in it.** A photo is a few hundred KB
and the log is about 1 KB a day, so a photo inside the log would reach
localStorage's 5 MB in a few dozen check-ins and make every save write it
again. `photos` keeps it next to the log instead: IndexedDB on the web
(`mntl-dt-photos`, store `photos`, the JPEG Blob under its id) and the app's
own files in the iPhone app (Capacitor Filesystem, `DATA`, which is Documents
on iOS, `mntl-dt-photos/<id>.jpg`). It is shrunk on the phone first: 1280px on
the long side, JPEG at 0.84, never blown up. It goes nowhere else: not to the
relay, not into a backup, not to the Claude viewer's `db`. Save waits for the
photo to be written before it touches the log, and a photo that cannot be
written saves nothing and says so. The web asks `navigator.storage.persist()`
after the first photo, which costs nothing and makes iOS less likely to clear
the site's storage under pressure.

**A photo goes when Undo can no longer reach it.** Replacing a photo, taking
it off, or removing its check-in puts its id in `store.photoBin`, so Undo can
bring it back. The next time the app opens, `emptyPhotoBin()` deletes every id
in the bin that no day names. Only names in the bin are ever deleted, so a log
that is empty or could not be read can never take a photo with it, and a
backup restored before that open still finds its photos.

**One check-in a day; New check-in opens today's.** *New check-in* is always
the plate above the tabs (the bar's one button until b98; `docs/ui.md`, *The
plate*). If today already has a check-in, it opens that one,
says so, and *Change day* goes to an earlier day (never a later one) to fill
one in after the fact. A day chosen that already has a check-in is opened, and
said, rather than written over unseen. What was typed or picked in the editor
comes along to the new day; what was only loaded from the day left behind
stays there. *Edit* from a check-in opens it without *Change day*.

**Saving says so, and lights the row.** Rule 3: the row the save made is lit
for a moment and scrolled on screen, and the bar says *Saved today's check-in*
(or *Changed*, or *Saved the Oct 8 check-in*), with Undo. A save that fails
says nothing of the sort: the save bar is up instead.

**Remove keeps the weight.** Removing a check-in takes its photo and note.
The weight stays, because it is also the day's weigh-in, and removing a
check-in should not quietly take a point off the trend line. The bar says
*Removed today's check-in · its weight stays*, with Undo (rule 6).

**Compare: side by side or a slider.** Any two photos, from the card on top
(first and latest) or from a check-in (against the photo before it, or after
it for the first). Two pickers choose the days, and the earlier one always
stays on the left. The slider lays the later photo over the earlier and clips
it at the line; the range input covers the whole picture, so the drag lands
anywhere on it. Under them: days apart, the change on the scale, and the
change on the trend (`trendAt`), which ignores a single morning's water.

**On the Log: a camera and a ring.** A day with a progress photo has a small
camera at the top left of its cell in the big month, a check-in without one a
small ring, and the legend explains both once the year has any. Nothing is
drawn in the twelve small months, like the checklist dot. The peek gains a
*Progress* line, and *See check-in* opens that check-in on the Progress tab.

**A backup carries the notes and weights, not the photos.** *Send a copy* is
the log, so it has each check-in's note, weight and photo id, but never the
photo. The Backup sheet says so once any check-in has a photo. Restored on
another phone, a check-in whose photo is not there says *This photo isn't on
this phone* rather than showing a broken image or vanishing (rule 7). A
separate way to save the photos themselves is left for later.

**In the iPhone app, photos are files, from shell 1.3 (b91).** The WebView's
own storage is website data to iOS, which may clear it when space runs low,
the reason the log moved to native storage (`docs/architecture.md`). So in
the app photos are files, through `@capacitor/filesystem` 8.1.5, added in
shell 1.3: `DATA`, which is the app's Documents folder on iOS. iOS never
clears that folder to make room, and the phone's own backup includes it, as
it does the log. A shell without the plugin (1.2 and older,
`shellHas("Filesystem")` false) keeps notes and weights and says photos come
with the next update of the app, rather than putting them somewhere they could
be lost. The camera's permission wording in `Info.plist` changed with it: it
used to say pictures "are not kept", and now says barcodes and labels are read
and not kept, and progress photos are kept on the phone and never sent
anywhere. *Choose one* needs no permission of its own (`docs/ios.md`).

**A file already gone counts as deleted.** The plugin refuses to delete a file
that is not there (`OS-PLUG-FILE-0008`), where IndexedDB quietly deletes a
missing key. That refusal would keep the name in the photo bin for good: the
bin lets a name go only once its delete succeeds, and an open that empties the
bin but saves nothing leaves the stored bin naming files already deleted. So
`photos.del` takes that one refusal as done, and any other still fails.

**Seven tabs on a 320px phone.** With Coach switched on there are seven tabs,
and a 320px phone gave each one 43px. Below 341px the tab bar's side padding
drops to 2px, the icon pill to 40px and the label to 9px, so each tab keeps
44px (rule 5) and *PROGRESS* stays inside its own.

**`progress` covers all of it.** The tab's place and the date strip; the
editor (today's weight in it, nothing saved from nothing, a note alone, a
weight alone that is Body weight on the Log, a weight that can't be one, the
X); a photo shrunk to 1280px in IndexedDB and never in the log or a backup,
still there after a restart; a day that already has one; Change day and its
limit; stepping; Compare both ways and from both places; the Log's marks,
legend and peek; Remove, Undo and the bin after the next open; a photo this
phone does not have; kg; the iPhone app with and without the plugin, against
a stand-in bridge that refuses a missing file as the real plugin does, and a
file already gone leaving the bin; and seven tabs at 320px. `darkcheck` opens a check-in and
the editor for contrast, `keys` types into the editor's two fields, and
`mobile`, `hittest` and `handoff` walk the tab.
