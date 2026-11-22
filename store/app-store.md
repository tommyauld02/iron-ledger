# App Store listing: MNTL D&T

What goes into App Store Connect for the first App Store version, field by
field, so it can be pasted rather than written on the spot. Each `##` heading
is the field's name in App Store Connect, and the text under it is what goes
in the box. `tests/legal.py` checks every field against Apple's limits and
checks that the URLs are the ones the app links to.

Screenshots are made by `tools/make-screenshots.py` into `store/screenshots/`
(not committed: run the tool to get them).

Kept true to the app: nothing here may promise something it does not do, and
nothing may promise weight loss or a health result (App Review 1.4.1). Read
the Privacy Policy before changing anything about what leaves the phone.

## Name

MNTL D&T: Diet & Training

## Subtitle

Workout log & macro tracker

## Promotional Text

Free, with no account and no ads. Log your lifts and your macros in one place, and keep every bit of it on your phone.

## Description

Your gym log and your macros in one app. No account, no ads, no tracking: your log stays on your phone.

MNTL is short for mental: show up, push, write it down. MNTL D&T (diet and training) is for people who lift and want every set and every gram of protein in one place, without signing up for anything.

TRAINING
• Plan your week: name your own training days and the movements in each.
• Log a set with one tap. Last time's sets sit beside today's, so you always know the number to beat.
• A workout clock, a lap for each movement, and a rest timer that can buzz you even with the phone locked.
• Supersets, drop sets and other techniques, notes on any movement, and more than one gym.
• A recovery body map shows which muscles you've worked this week and which are rested.

DIET
• Ask an agent: say what you ate in your own words ("two eggs and toast") and get the calories and macros back.
• Scan a barcode: US grocery brands are looked up on your phone.
• Read a nutrition label with the camera, right on your phone.
• Your pantry: save foods and meals once, add them again with a tap.
• Calories and protein, carbs and fat if you want them, water and body weight.
• Hit your protein goal and the plates turn gold.
• A goal calculator to set your targets (estimates only, not medical advice).
• A daily checklist for your supplements.

CARDIO AND PROGRESS
• Log cardio and set a goal by minutes, distance, calories, sessions or steps.
• Steps and weigh-ins from Apple Health: with your permission, MNTL D&T reads your daily step count and your weight. It never writes to Apple Health.
• Progress check-ins: a photo, a note and your weight. Compare two photos side by side. Photos stay on your phone.

YOURS, AND PRIVATE
• Everything you log stays on your phone. There's no account and no copy on a server.
• Back up or move to a new phone with Send a copy.
• Works offline. Only Ask an agent needs a connection, and it asks your permission before it sends anything.
• Write a routine for a friend or a client and share it as a code.

For adults 18 and over. MNTL D&T is a log, not medical advice. Talk to a doctor or registered dietitian before changing your diet or training.

Privacy Policy: https://tommyauld02.github.io/iron-ledger/privacy.html
Terms of Use: https://tommyauld02.github.io/iron-ledger/terms.html

## Keywords

calorie,counter,protein,gym,weightlifting,strength,barcode,nutrition,meal,fitness,cardio,steps,reps

## Support URL

https://tommyauld02.github.io/iron-ledger/support.html

## Privacy Policy URL

https://tommyauld02.github.io/iron-ledger/privacy.html

## Copyright

2026 Thomas Alexander Auld

## App Review Notes

MNTL D&T is a gym and macro log. There is no account and no sign-in: everything is stored on the phone.

1. On first open the app asks for a birth date. Enter any date 18 or more years ago. It is an adult-only app because the AI service behind Ask an agent only allows adult users.
2. Gym tab: tap Add movement, name one, then fill in a set row and tap its check to log it. A haptic tap confirms each set. Tap Rest timer, start it, choose Buzz at 1:00 and lock the phone: the alert still arrives (a local notification).
3. Macros tab: tap the plate button, then Ask an agent, and type a food in your own words, for example "two eggs and toast". The first time, the app asks permission before it sends anything; the text and the country setting go to Google Gemini through our relay. Everything else in the app works offline.
4. Macros tab, plate button, Scan: reads a barcode with the camera. Settings, Grocery brands downloads the US brand list once (about 8 MB) so lookups happen on the phone.
5. Cardio tab: Connect Apple Health reads the daily step count only. Log tab, body weight card: Connect Apple Health reads body weight only. The app never writes to Apple Health.
6. Progress tab: a check-in can hold a photo (camera or photo library), which is stored only on the phone.
7. Hold the app icon for four quick actions: Log food, Ask an agent, Start workout and Scan a barcode.

Privacy: no analytics, no ads, no tracking. The only data that leaves the phone is the food text typed into Ask an agent, after the user has said yes.
