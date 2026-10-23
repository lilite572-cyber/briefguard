# Browser acceptance — interaction checks completed, remaining limits recorded

Latest browser supplement (2026-10-23): all 18 case/method selections passed at
1280 px; thumbnail seeking, playback, truth toggle and asset loading passed,
without console errors or horizontal overflow. Workbench requirements entry,
invalid-budget blocking, command copying and JSON download passed.
Exact scope and remaining gaps: [browser.json](../results/verification_final/browser.json).
Earlier viewport limitations below describe the earlier session.

This checklist is for an actual browser session. `scripts/check_demo.py` checks
saved data and image pixels; it does not execute or visually inspect the UI.
A real in-app browser session on 2026-10-22 exercised the live owner-started
server after the earlier binding restriction. Evidence, tested HTML hash and
remaining limits are in [verification_browser](../results/verification_browser/status.json).
The tested viewport was 639 CSS pixels wide. Requests for 390 and 1280 pixels
did not change the effective viewport and are not counted as tested.

From the repository root in a normal terminal:

```bash
python3 -m http.server --bind 127.0.0.1 8765 --directory demo
```

Open `http://127.0.0.1:8765`, open Developer Tools (Console and Network), and
disable the network cache while checking. Record the exact commit (`git rev-parse HEAD`),
browser/version, viewport, date, reviewer and any failures. Do not mark a row
passed merely because a file exists or a screenshot looks plausible.

| Check | Expected behavior | Status |
| --- | --- | --- |
| Initial load | Replay/synthetic/no-live-inference labels, negative study conclusion, three summary cards; no console errors or failed required assets | Passed at 639 px; see saved scope |
| All six examples × three method buttons | Correct brief, case identifier and method selection; eight evidence thumbnails and eight timeline marks per method | Passed |
| Playback and pause | Frames advance, pause holds the displayed frame, timecode stays within 0–4 seconds | Passed |
| Scrub and selected thumbnail | Slider and thumbnail click show the indicated integer frame; cursor and timestamp agree | Passed |
| Timeline click | Clicking selects the corresponding bounded frame | Center click passed (frame 47); edge clicks untested |
| Event boundary | With truth enabled, a violation appears at `start_frame`, remains through `end_frame - 1`, and is absent at `end_frame` | Passed |
| Truth toggle | Event shading and truth badge switch together; this replay is explanatory, not the blinded annotation tool | Passed |
| Findings and false approvals | Comparison and evidence panel agree with the chosen case/method in `demo/data.json`; a pass states that unseen frames may still violate | Passed |
| Fast switching | Rapidly switch cases/methods during playback; final sprite, brief and evidence all belong to the latest case | Passed |
| Resource/console inspection | No uncaught exception or missing thumbnails | 144 thumbnails loaded; console errors/warnings empty. Full network interception untested |
| Narrow screen (390 px) and desktop | Controls reachable; no page overflow | 639 px passed after grid fix; 390/1280 px unverified |
| Missing sprite | Use DevTools request blocking on one sprite URL and reload/select it: an explicit replay error appears; restore blocking afterwards | Pending |

Do not edit the bundled evidence to simulate a network failure. A browser check
does not establish agreement with human judgments: complete the separate blinded
review described in `human_review.md` for that purpose. Keep human decisions blank
until the reviewer has actually inspected the clips.

Save the completed checklist separately (for example under the generated acceptance
directory), including actual observed errors. If a defect is fixed, repeat the affected
checks and record both the original failure and the new revision.
