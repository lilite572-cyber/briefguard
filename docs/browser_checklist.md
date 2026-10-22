# Browser acceptance — still pending

This checklist is for an actual browser session. `scripts/check_demo.py` checks
saved data and image pixels; it does not execute or visually inspect the UI.
The authoring environment denied localhost binding and `file://` browser access,
so no successful browser check is claimed from that environment.

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
| Initial load | Replay/synthetic/no-live-inference labels, negative study conclusion, three summary cards; no console errors or failed required assets | Pending |
| All six examples × three method buttons | Correct brief, case identifier and method selection; eight evidence thumbnails and eight timeline marks per method | Pending |
| Playback and pause | Frames advance, pause holds the displayed frame, timecode stays within 0–4 seconds | Pending |
| Scrub and selected thumbnail | Slider and thumbnail click show the indicated integer frame; cursor and timestamp agree | Pending |
| Timeline click | Clicking left/middle/right selects the corresponding bounded frame; no index outside 0–95 | Pending |
| Event boundary | With truth enabled, a violation appears at `start_frame`, remains through `end_frame - 1`, and is absent at `end_frame` | Pending |
| Truth toggle | Event shading and truth badge switch together; this replay is explanatory, not the blinded annotation tool | Pending |
| Findings and false approvals | Comparison and evidence panel agree with the chosen case/method in `demo/data.json`; a pass states that unseen frames may still violate | Pending |
| Fast switching | Rapidly switch cases/methods during playback; final sprite, brief and evidence all belong to the latest case | Pending |
| Resource/console inspection | No uncaught exception, missing sprite/thumbnail, or unexpected external request during all selections | Pending |
| Narrow screen (390 px) and desktop | Controls are reachable, text is readable, cards do not overlap; table can scroll horizontally | Pending |
| Missing sprite | Use DevTools request blocking on one sprite URL and reload/select it: an explicit replay error appears; restore blocking afterwards | Pending |

Do not edit the bundled evidence to simulate a network failure. A browser check
does not establish agreement with human judgments: complete the separate blinded
review described in `human_review.md` for that purpose. Keep human decisions blank
until the reviewer has actually inspected the clips.

Save the completed checklist separately (for example under the generated acceptance
directory), including actual observed errors. If a defect is fixed, repeat the affected
checks and record both the original failure and the new revision.
