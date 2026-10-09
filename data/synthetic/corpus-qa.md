# Synthetic corpus QA

Corpus SHA-256: `d9c6b02135744c0e13bd00333877676c6b388f99952c4ccb37046dc6794fc4e8`. Cache version: `bbb10fba82c9`.

## Size and threads

Messages: **2,233**. Top-level: **1,773/2,233 (79.4%)**. Threads: **158**. Reply-count distribution: 2 replies: 82, 3 replies: 32, 4 replies: 27, 5 replies: 10, 6 replies: 7.

| Channel | Messages | Top-level | Top-level % |
| --- | ---: | ---: | ---: |
| eng | 454 | 355 | 78.2% |
| product | 441 | 358 | 81.2% |
| ops | 447 | 322 | 72.0% |
| build-help | 443 | 351 | 79.2% |
| random | 448 | 387 | 86.4% |

## Fact coverage

Flag: `0 plants` or `>15 refs`.

| Fact | Plants | Refs | Flag |
| --- | ---: | ---: | --- |
| F01 | 1 | 174 | >15 refs |
| F02 | 1 | 32 | >15 refs |
| F03 | 1 | 93 | >15 refs |
| F04 | 1 | 152 | >15 refs |
| F05 | 1 | 146 | >15 refs |
| F06 | 1 | 21 | >15 refs |
| F07 | 1 | 174 | >15 refs |
| F08 | 1 | 3 |  |
| F09 | 1 | 41 | >15 refs |
| F10 | 1 | 174 | >15 refs |
| F11 | 1 | 63 | >15 refs |
| F12 | 1 | 55 | >15 refs |
| F13 | 1 | 11 |  |
| F14 | 1 | 34 | >15 refs |
| F15 | 1 | 4 |  |
| F16 | 1 | 11 |  |
| F17 | 1 | 12 |  |
| F18 | 1 | 51 | >15 refs |
| F19 | 1 | 75 | >15 refs |
| F20 | 1 | 1 |  |
| F21 | 1 | 53 | >15 refs |
| F22 | 1 | 53 | >15 refs |
| F23 | 1 | 4 |  |
| F24 | 1 | 70 | >15 refs |
| F25 | 1 | 23 | >15 refs |
| F26 | 1 | 48 | >15 refs |
| F27 | 1 | 14 |  |
| F28 | 1 | 31 | >15 refs |
| F29 | 1 | 13 |  |
| F30 | 1 | 3 |  |
| F31 | 1 | 52 | >15 refs |
| F32 | 1 | 1 |  |
| F33 | 2 | 4 |  |
| F34 | 1 | 0 |  |
| F35 | 1 | 0 |  |
| F36 | 1 | 6 |  |
| F37 | 1 | 11 |  |

## Validator findings

Key-token warnings: **0**. Ban-list hits: **0**. Fact IDs leaked into text: **0**.

## Reversal searches

MongoDB/Mongo mentions after 2026-09-14: **5**. Messages asserting MongoDB is current: **0 on review**.

- `synthetic:eng:20260915-01` 2026-09-15T09:12:00+05:30 priya [plants: -; refs: F17] — Quick update: we're staying on Postgres, not Mongo, for the pilot data model. Reporting joins and dedupe rules are cleaner that way. Can someone own the migration check today?
- `synthetic:ops:20260916-08` 2026-09-16T12:10:00+05:30 priya [plants: -; refs: F17,F18] — Decision: for the pilot, we stick with Postgres for reporting and deduping. Mongo is out for now. Nikhil, please keep migration verification on your side and flag anything weird by 2026-09-18.
- `synthetic:build-help:20260918-01` 2026-09-18T09:05:00+05:30 priya [plants: -; refs: F17] — morning folks — quick check: is the Postgres switch fully clean on staging now? last I saw we were moving off mongo, so i want to avoid anyone testing on the old setup by mistake.
- `synthetic:eng:20260918-07` 2026-09-18T11:02:00+05:30 priya [plants: -; refs: F02,F17,F18,F07] — decision: keep Postgres as the prototype DB and avoid reopening MongoDB for this pilot. reason is still reporting joins plus dedup constraints, and the migration path is already in motion. nikhil, please own verification today; arjun, keep validating retries.
- `synthetic:random:20260924-12` 2026-09-24T15:27:00+05:30 arjun [plants: F34; refs: -] — mongo would've let me skip migrations lol

SMS mentions after 2026-09-24: **2**. Messages asserting SMS is current: **0 on review**.

- `synthetic:product:20260925-07` 2026-09-25T10:22:00+05:30 priya ↳20260925-01 [plants: -; refs: F25,F10] — Manual code entry stays. No SMS fallback for pilot. Please keep the screen wording short and direct.
- `synthetic:product:20261001-07` 2026-10-01T10:02:00+05:30 meera ↳20261001-01 [plants: -; refs: F25,F10] — Quick recap from the rehearsal prep: no SMS fallback for the pilot, and manual code entry is the backup for phones with broken cameras. That keeps the runbook simpler.

## Ten random messages (seed 42)

- `synthetic:eng:20260901-04` 2026-09-01T09:27:00+05:30 meera [plants: -; refs: F01,F04,F07] — Checklist for today's backend sync: ⏎ - confirm QR check-in flow still supports the demo scope ⏎ - verify attendance export rows are enough for the success bar ⏎ - note any API changes that affect the dashboard ⏎ Acceptance criteria: ⏎ - no open blockers on the happy path ⏎ - duplicate scan behavior is documented
- `synthetic:product:20260825-07` 2026-08-25T10:16:00+05:30 zoya [plants: -; refs: -] — Training ke liye main 2 volunteer leads ko ping kar dungi. Agar check-in flow simple rahega, toh unko bas scan karna aur fallback manual list use karna sikhana padega. Waise aaj rain ka scene bhi hai, toh latecomers ka chance hai.
- `synthetic:eng:20260914-06` 2026-09-14T09:31:00+05:30 priya ↳20260914-02 [plants: -; refs: F17,F01] — Decision: Postgres replaces MongoDB for the prototype. The switch stays limited to the data layer, and the 2026-10-02 pilot remains on schedule.
- `synthetic:build-help:20260910-10` 2026-09-10T11:22:00+05:30 meera ↳20260910-01 [plants: -; refs: F14] — Acceptance criteria update: ⏎ - given an expired scan, the scanner should continue to return the same expiry error ⏎ - when the fixture time is in UTC, the test must pass consistently ⏎ - no change to the exported attendance row shape ⏎  ⏎ Please paste the exact repro output after the next run.
- `synthetic:build-help:20260909-05` 2026-09-09T10:22:00+05:30 zoya [plants: -; refs: -] — haan, and campus side se bhi ek chhota issue hai: volunteers ko short script chahiye for fallback check-in. main ek simple flow draft kar rahi hoon jisme speaker notes bhi ho, taaki training smooth rahe.
- `synthetic:ops:20260902-14` 2026-09-02T12:22:00+05:30 arjun [plants: -; refs: -] — tiny refactor pushed, nothing user-facing. logs are cleaner now.
- `synthetic:product:20260831-09` 2026-08-31T11:12:00+05:30 priya ↳20260831-02 [plants: -; refs: -] — good. then let's treat that as the current direction unless someone spots a usability miss. ⏎  ⏎ leo, can you post the latest screen link before EOD?
- `synthetic:build-help:20260828-15` 2026-08-28T12:24:00+05:30 nikhil ↳20260828-13 [plants: -; refs: F05] — i can help if needed. also, the health check is still fine after the latest restart, so this looks isolated to the scan handler.
- `synthetic:product:20260924-05` 2026-09-24T10:02:00+05:30 arjun [plants: -; refs: F22] — csv export still on track. columns stay event_id, attendee_id, checked_in_at.
- `synthetic:eng:20260825-14` 2026-08-25T12:22:00+05:30 priya [plants: -; refs: -] — Nice. If that holds for one more round, we can stop touching the backend today and let design polish continue in parallel.

## Evidence messages

Includes every plant/ref for F17, F20, F23, F33, and F36, plus the thread parent for short replies.

### F17 (13 tagged messages)

- `synthetic:eng:20260914-02` 2026-09-14T09:12:00+05:30 priya [plants: F17; refs: -] — We should switch the prototype DB to Postgres. The reporting side is getting messy with exports, and I don't want us fighting the data model during pilot week. Arjun, can you react to that?
- `synthetic:eng:20260914-03` 2026-09-14T09:18:00+05:30 arjun ↳20260914-02 [plants: -; refs: F02,F17,F04] — +1. with mongo it was okay for loose payloads, but the attendance export wants joins way more than i expected. postgres should save us some glue code.
- `synthetic:eng:20260914-04` 2026-09-14T09:22:00+05:30 nikhil ↳20260914-02 [plants: -; refs: F17,F12] — yep, Postgres makes the dedup rule cleaner too. we can put a unique constraint around the scan identity and keep retries auditable without weird app-level hacks.
- `synthetic:eng:20260914-05` 2026-09-14T09:27:00+05:30 meera ↳20260914-02 [plants: -; refs: F17,F04,F01] — Checklist: ⏎ - confirm whether this changes the demo timeline ⏎ - verify exported attendance rows still support the 95% success bar ⏎ - call out any migration work that blocks the QR check-in scope ⏎  ⏎ If the answer is no major slip, I'm fine.
- `synthetic:eng:20260914-06` 2026-09-14T09:31:00+05:30 priya ↳20260914-02 [plants: -; refs: F17,F01] — Decision: Postgres replaces MongoDB for the prototype. The switch stays limited to the data layer, and the 2026-10-02 pilot remains on schedule.
- `synthetic:eng:20260914-10` 2026-09-14T11:05:00+05:30 meera [plants: -; refs: F17,F07,F04,F12] — Acceptance criteria for the DB switch: ⏎ 1) duplicate scans still resolve to the same attendance record ⏎ 2) exported rows still let us measure the pilot success bar ⏎ 3) no regression in the scan event audit trail ⏎  ⏎ Please paste once the migration plan is ready.
- `synthetic:eng:20260914-16` 2026-09-14T13:20:00+05:30 meera [plants: -; refs: F17,F01] — Noted. For today, I only need the migration plan + one screenshot of the attendance row export once it's ready. That keeps us aligned for the 2026-10-02 demo.
- `synthetic:eng:20260915-01` 2026-09-15T09:12:00+05:30 priya [plants: -; refs: F17] — Quick update: we're staying on Postgres, not Mongo, for the pilot data model. Reporting joins and dedupe rules are cleaner that way. Can someone own the migration check today?
- `synthetic:product:20260915-03` 2026-09-15T09:18:00+05:30 arjun [plants: -; refs: F17,F07] — db side is fine for the pilot shape. the join/reporting angle is cleaner now, and dedupe rules are still the same on scans.
- `synthetic:ops:20260916-08` 2026-09-16T12:10:00+05:30 priya [plants: -; refs: F17,F18] — Decision: for the pilot, we stick with Postgres for reporting and deduping. Mongo is out for now. Nikhil, please keep migration verification on your side and flag anything weird by 2026-09-18.
- `synthetic:build-help:20260918-01` 2026-09-18T09:05:00+05:30 priya [plants: -; refs: F17] — morning folks — quick check: is the Postgres switch fully clean on staging now? last I saw we were moving off mongo, so i want to avoid anyone testing on the old setup by mistake.
- `synthetic:eng:20260918-07` 2026-09-18T11:02:00+05:30 priya [plants: -; refs: F02,F17,F18,F07] — decision: keep Postgres as the prototype DB and avoid reopening MongoDB for this pilot. reason is still reporting joins plus dedup constraints, and the migration path is already in motion. nikhil, please own verification today; arjun, keep validating retries.
- `synthetic:random:20260921-10` 2026-09-21T14:02:00+05:30 priya [plants: -; refs: F17,F18] — Decision: we stay with Postgres for the prototype and keep the migration path simple. Reason is the reporting side and dedupe rules are clearer that way. Nikhil, can you own verification on the upgrade path?

### F20 (2 tagged messages)

- `synthetic:product:20260917-01` 2026-09-17T09:10:00+05:30 priya [thread parent; grade 1] [plants: -; refs: -] — Quick scope check for today: are we freezing QR format v2 for the pilot? If yes, I’ll keep the check-in flow aligned with that and avoid extra churn.
- `synthetic:product:20260917-02` 2026-09-17T09:12:00+05:30 meera ↳20260917-01 [plants: F20; refs: -] — yes, do that
- `synthetic:product:20260917-12` 2026-09-17T15:10:00+05:30 meera [plants: -; refs: F20,F10,F19] — Recap from this thread: ⏎ 1) QR format v2 stays frozen for pilot use ⏎ 2) fallback for cracked-camera phones stays manual code entry ⏎ 3) SMS fallback remains in the pilot scope ⏎ 4) manual entry desk support is being kept in volunteer planning ⏎ Next: I’ll collect any last scope objections before the sync.

### F23 (5 tagged messages)

- `synthetic:random:20260922-03` 2026-09-22T09:31:00+05:30 zoya [plants: F23; refs: -] — Kal ke volunteer drill ke liye gate 3 pe 8:15 baje milna hai; main extra lanyards laungi. Sab log time pe aa jana pls, warna line shuffle ho jayegi.
- `synthetic:random:20260923-09` 2026-09-23T11:27:00+05:30 zoya ↳20260923-07 [plants: -; refs: F23] — Waise kal wala volunteer drill gate 3 pe 8:15 baje hua tha. Main extra lanyards le aayi thi, aur jo late hua usko flow phir samjhana pada 😤
- `synthetic:random:20260924-06` 2026-09-24T10:41:00+05:30 zoya [plants: -; refs: F23] — kal hi lab ke baad thoda sa nap lena padega lol. waise gate 3 pe jo 8:15 wala drill tha, uska flow kaafi smooth tha. main aaj volunteer group ko ping kar dungi ki bas calm rehna aur confusion ho to mujhe tag karna.
- `synthetic:random:20260925-03` 2026-09-25T09:34:00+05:30 zoya [plants: -; refs: F23] — Aaj gate 3 ke paas bahut bheed thi, so I took the longer route. Lanyards bag me hain, koi chahiye ho to bolna. Us din wali drill ka scene better tha waise.
- `synthetic:eng:20260930-07` 2026-09-30T10:02:00+05:30 zoya [plants: -; refs: F23,F24] — Gate 3 pe 8:15 wale volunteer drill se lesson yeh hai: manual desk walon ko pehle brief karo, warna line messy ho jaati hai. Main extra lanyards aur volunteer list le aaungi.

### F33 (6 tagged messages)

- `synthetic:random:20260908-11` 2026-09-08T14:02:00+05:30 leo [plants: F33; refs: -] — Wait, isn't the campus demo October 3? I put that on the slide 😅 Anyway, I'm fixing icon alignment now.
- `synthetic:ops:20260908-09` 2026-09-08T14:10:00+05:30 meera [plants: F33; refs: -] — Quick correction from the random chat earlier: the demo date is October 2. Please use that everywhere in ops notes and volunteer instructions.
- `synthetic:ops:20260908-10` 2026-09-08T14:18:00+05:30 leo ↳20260908-09 [plants: -; refs: F33] — +1, I'll update the mockup labels too. october 2 everywhere, got it 👍
- `synthetic:ops:20260908-12` 2026-09-08T14:40:00+05:30 zoya ↳20260908-09 [plants: -; refs: F33] — haan yes, October 2 note ab sab jagah same rakhti hoon. Main volunteer sheet aur desk briefing dono update kar dungi, taaki kisi ko date mix up na ho.
- `synthetic:random:20260917-06` 2026-09-17T10:11:00+05:30 leo ↳20260917-05 [plants: -; refs: F33] — yesss, that scope is nice and tidy ✨ I can make a tiny card for it. also pls no one say october 3 again 🙃
- `synthetic:random:20260917-10` 2026-09-17T12:14:00+05:30 meera [plants: -; refs: F11,F33] — Mini recap: ⏎ 1. hall booking remains confirmed ⏎ 2. six-volunteer roster still due next week ⏎ 3. no one should treat the old October 3 mention as current ⏎ 4. casual scope talk should stay aligned to the check-in + dashboard release

### F36 (7 tagged messages)

- `synthetic:eng:20260929-03` 2026-09-29T09:26:00+05:30 nikhil [thread parent; grade 1] [plants: -; refs: F05] — Staging is healthy again after the origin fix, and /healthz is green. For the pilot, can we freeze deploys after 18:00 IST on 2026-10-01? I'd like a quiet rollout window.
- `synthetic:eng:20260929-08` 2026-09-29T11:22:00+05:30 priya ↳20260929-03 [plants: F36; refs: -] — +1, go with that
- `synthetic:eng:20260929-09` 2026-09-29T11:24:00+05:30 nikhil ↳20260929-03 [plants: -; refs: F36] — got it. will freeze deploys after 18:00 IST on 2026-10-01 and keep the rollout window quiet.
- `synthetic:eng:20260930-09` 2026-09-30T10:22:00+05:30 priya [plants: -; refs: F36] — Deploy freeze after 18:00 IST on 2026-10-01 still stands. If anything breaks after that, we patch only blockers. Nikhil, please own the verification pass once more before we lock it down.
- `synthetic:eng:20260930-15` 2026-09-30T12:05:00+05:30 priya [plants: -; refs: F28,F36] — Thanks all. Current state looks stable: demo scope is unchanged, export is clean, refresh cadence is fixed, and deploys get locked after 18:00 IST tomorrow. Let's keep today boring in a good way.
- `synthetic:eng:20261001-01` 2026-10-01T09:10:00+05:30 priya [plants: -; refs: F36] — Morning all. Let's keep today boring in the best way: pilot demo tomorrow, so I want only the must-fix backend items moving now. Nikhil, can you keep an eye on deploys after 18:00 and shout if anything touches the freeze window?
- `synthetic:ops:20261001-09` 2026-10-01T11:06:00+05:30 priya [plants: -; refs: F36] — One decision for the day: let's keep deploys frozen after 18:00 IST and avoid touching prod unless it's a blocker. Nikhil, can you watch for any late infra noise?
- `synthetic:random:20261001-08` 2026-10-01T12:15:00+05:30 nikhil [plants: -; refs: F36] — deploy freeze is still in place after 18:00 IST today. if anyone needs to test, do it before dinner pls.

## Calls and tokens

Current full-run cache: **242 calls**, **590,138 input + 349,966 output = 940,104 tokens**.
First-attempt pass rate: **89/150 (59.3%)**.
All cached pilot and full-run attempts: **1,129,757 tokens** (714,772 input + 414,985 output).

## Manual repairs

17 channel-days use the versioned `data/synthetic/repairs.yaml` file. It fixes tags, thread shape, banned/non-Latin text, and exact evidence. Raw model responses remain in ignored cache. Database counts are in ingest-report.json.
