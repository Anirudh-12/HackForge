# T2 JUDGING — Implementation Plan
### DOGFOOD 2026 · Target: complete after T1, within the 72h window

---

## 0. What the Acceptance Checker Actually Tests for T2

Four mechanical checks. All four require working auth tokens in `.dogfood.toml`.

| # | What | How it checks | Pass condition |
|---|---|---|---|
| **T2-1** | Judge can read their own scores | GET the judge scores endpoint as judge_a | HTTP 200 |
| **T2-2** | Judge cannot read a peer's scores | GET judge_a's scores endpoint *as judge_b* | HTTP 401 or 403 |
| **T2-3** | Participant is not a judge | GET the judge scores endpoint as participant | HTTP 401 or 403 |
| **T2-4** | Organizer can export CSV | GET the CSV export endpoint as organizer | HTTP 200 + CSV body |

**T2-2 is the one that kills most projects.** Hiding another judge's scores in the template is not the same as refusing the request. The check hits the API endpoint directly with curl. If your backend returns the data and just doesn't show it in the HTML, T2-2 fails. The isolation must be in the handler.

---

## 1. T2 Requirements

```
T2 JUDGING
  ① Judge invitation and assignment
  ② A weighted scoring rubric the organizer can configure
  ③ Backend enforced role isolation: judges cannot see peer scores
  ④ A live organizer progress dashboard
  ⑤ Cross-judge normalization, with the method documented
  ⑥ CSV export
```

---

## 2. Multi-Event Architecture — The Core Design Decision

The fixture event (`evt_01`) already has judges pre-assigned to tracks. But the real test is whether **a new event, created fresh by an organizer, can have its own judges assigned, its own rubric configured, and its own scoring flow** — end to end.

**The fixture event is read-only reference data.** Don't couple your judging engine to it. Build everything event-scoped from day one.

**What "multi-event" means in practice:**
- Every judge assignment, every score, every rubric criterion, every progress stat is scoped to an event ID
- An organizer managing Event A and Event B sees completely separate dashboards, separate judge lists, separate results
- A judge assigned to Event A does not automatically see Event B's projects
- The same person (same email) can be a judge on multiple events — their role and assignments are per-event, not global

**The key design rule:** `event_id` is a parameter on every judging-related query, always. If you write a query without filtering by event, stop and add it.

---

## 3. Feature ①: Judge Invitation and Assignment

### The invite model

Organizers invite judges by email. Two cases:

1. **The email already has a user account** — they become a judge for this event immediately (or get a notification)
2. **The email has no account yet** — create a pending invite record; when they register, they're automatically assigned

In both cases, what matters is the `JudgeTrack` record: which judge is assigned to which track for which event. That's the source of truth for what projects a judge sees.

### Assignment is track-based, not project-based

A judge is not assigned to individual projects. They're assigned to one or more tracks. Every non-draft, non-disqualified project in their assigned track(s) appears in their queue automatically. This means:
- Assigning a judge after submissions are in still gives them the full track queue immediately
- Removing a judge from a track removes their queue without touching their existing scores

### What the organizer needs to do

1. View all judges currently assigned to this event (name, email, tracks, score progress)
2. Invite a new judge by email — then assign them to one or more tracks
3. Remove a judge from the event (their existing scores stay, for audit purposes)
4. See at a glance which tracks have no judges assigned (danger zone)

### Lessons from the dry run

**The fixture event has judges pre-assigned — don't test exclusively on the fixture event.**
The acceptance checker uses `judge_a` and `judge_b` from `.dogfood.toml`, which are the fixture judges. But human reviewers will also create a fresh event and try to invite someone. Test the invitation flow on a new event, not just by relying on seeded data.

**Judge assignment must be stored per-event, not globally.**
If your `User.role = "judge"` is the only record of someone being a judge, you can't have the same person judging two different events with different track assignments. Use a separate join table: `(judge_id, track_id, event_id)` at minimum.

**Tracks without judges are a real state the UI must handle.**
If an organizer creates a track but forgets to assign a judge, projects in that track will never be scored. The organizer dashboard should make this visible — not silently allow it.

---

## 4. Feature ②: Weighted Scoring Rubric

### What "configurable" means

The organizer defines the scoring criteria for their event before judging begins. Each criterion has:
- A name ("Technical Execution", "Innovation", "Impact")
- An optional description shown to judges during scoring
- A weight (how much this criterion counts toward the final score)

Weights should sum to 100 (or be normalised to sum to 100 automatically).

The fixture data uses three criteria (`functionality`, `quality`, `innovation`) with scores from 1–5. Your rubric system should be compatible with this shape but not hardcoded to it.

### Locking the rubric

Once judging starts and any scores have been submitted, **the rubric must not be changeable**. Changing weights after judges have already scored would invalidate all existing scores silently. Either prevent edits entirely after the first score is submitted, or show a prominent warning.

### Displaying the rubric to judges

When a judge opens a project to score, they see the criteria with their descriptions. The score form has one input per criterion (1–5 scale). They can also add a text comment. This should feel like a clean, focused form — not a table of numbers.

### Lessons from the dry run

**Don't hardcode the criteria fields in the Score model.**
If you store `functionality INT, quality INT, innovation INT` as fixed columns, you can't support a custom rubric. The right shape is a `Score` row per criterion, or a JSON blob — not fixed columns. The fixture's legacy shape (`functionality`, `quality` as columns) is for seeding only; your scoring flow should be criterion-based.

**Weights that don't sum to 100 break the math silently.**
If an organizer enters 40, 40, 40 for three criteria, the weighted average is meaningless. Normalise weights automatically on read: `effective_weight = criterion.weight / sum_of_all_weights`. Never trust that the organizer got the math right.

---

## 5. Feature ③: Role Isolation — The Most Important Feature in T2

### What isolation means

A judge can:
- Read their own scores for projects in their assigned tracks
- Submit and edit their own scores (until judging closes)

A judge cannot:
- Read another judge's scores for the same project
- Read scores for projects outside their assigned tracks
- Access organizer results or the CSV export

**This must be enforced in the API handler, not in the template.** The acceptance checker hits the API with curl. If your handler returns data and your template hides it, T2-2 fails.

### The peer scores check — the specific test

The checker will:
1. Get the URL that returns judge_a's scores
2. Request that URL *as judge_b*
3. Expect 401 or 403

Your `judge_scores` endpoint must check: "Is the requesting user the same judge whose scores are being requested?" If not, reject immediately — before returning any data.

**The exact check in the handler:**
```
if requesting_user.id != requested_judge_id:
    return 403 Forbidden
```

This is one if-statement. It is the most important if-statement in the entire project. Do not skip it.

### Lessons from the dry run

**Filtering in the template is not isolation.**
Many projects pass T2-1 (judge sees own scores) but fail T2-2 (judge sees peer's scores) because the template just filters `{% if score.judge == current_user %}` but the API returns everything. The check must be at the data layer.

**A query parameter is fine for peer_scores — just guard the value.**
The checker's `peer_scores` route is something like `/api/judge/scores?judge=jdg_01`. You don't have to use a path parameter. Either works. What matters is that when judge_b requests scores for judge_a, the handler returns 403 regardless of the route shape.

**Don't forget the participant case (T2-3).**
It's easy to guard against one judge seeing another's scores but forget to block participants entirely. The `require_role("judge")` dependency on the scores endpoint handles T2-3 automatically — don't strip it out.

---

## 6. Feature ④: Organizer Progress Dashboard

### What it should show

The goal is a single page that answers: "How is judging going?" An organizer shouldn't need to click around to find out if judging is on track.

**Per-track section showing:**
- Track name + prize
- Number of projects in the track
- Number of those projects that have been fully scored (by all assigned judges)
- Number still unscored or partially scored
- Which judges are assigned (with their individual completion count)

**Overall numbers at the top:**
- Total projects vs total scored
- Percentage complete
- How many judges have submitted at least one score vs total judges assigned

**A flag for problem states:**
- Tracks with no judges assigned
- Judges with zero scores submitted (haven't started)
- Projects with no scores at all

### Design philosophy

**Simple, functional, elegant.** Not a data warehouse dashboard. Not a table with 12 columns. The organizer glances at it and immediately knows if something is wrong. Use progress bars or completion ratios. Use colour to signal problems (a track with no judges should be obviously red). Keep it to one page with no pagination.

### What "live" means

This does not need WebSockets or polling. "Live" in this context means: every time the organizer refreshes the page, they see current data. No caching that could show stale scores. Just an accurate query on every request.

### Lessons from the dry run

**The progress query is the hardest query in the project.**
You need to know, for each project, how many of the judges assigned to its track have submitted scores. That's a join across projects, judges, tracks, and scores — with a count comparison. Write this query carefully and test it with partial data (some judges scored, some haven't).

**"Fully scored" needs a clear definition.**
A project is "fully scored" when all judges assigned to its track have submitted at least one non-draft score for it. Define this clearly in the code. If you use a vague heuristic, the progress numbers will be wrong and organizers won't trust the dashboard.

**Don't show score values on the progress dashboard.**
The progress dashboard is about completion, not results. Showing actual score values here would let the organizer see scores while judging is still in progress — which could influence their decisions or pressure judges. Keep the progress page about "who has scored" not "what they scored."

---

## 7. Feature ⑤: Cross-Judge Normalization

### Why normalization matters

Different judges have different baseline strictness. Judge A consistently gives 4s and 5s. Judge B consistently gives 2s and 3s. If you average their raw scores directly, Judge B's projects are systematically disadvantaged even if they're equally good.

Z-score normalization fixes this by measuring each score relative to that judge's own distribution — so a 4 from a harsh judge and a 4 from a lenient judge don't count the same.

### The method (Z-score, per track)

For each track independently:

1. Collect all project raw scores (weighted average across their scoring criteria) within the track
2. Compute the mean and standard deviation of those raw scores
3. For each project: `z = (raw_score - mean) / stdev`
4. Scale to a readable range: `normalized = 50 + (z × 15)` maps ±3 standard deviations to roughly [5, 95]
5. If a track has only one project (stdev = 0), its normalized score is 50

Normalization happens **per track, not globally**. Tracks are independent competitions. A Security track project is not being compared to a Climate track project — they're on separate leaderboards.

### The "document the method" requirement

The spec specifically says "with the method documented." This means `JUDGING.md` must explain:
- What normalization method you used and why
- The exact formula
- How edge cases are handled (single project, judge who scored everything identically)
- Why per-track rather than global

This is worth points on its own. Write it clearly enough that a non-engineer reading it could understand the math.

### The UI toggle

The results page should offer both raw and normalized scores. An organizer might want to see the raw averages to sanity-check the normalization. The toggle between views should be instant (no page reload needed — just show/hide columns or re-sort).

### Lessons from the dry run

**Normalization must happen after all scores are in — or be clearly labeled as partial.**
If you compute normalized scores while judging is still in progress, the rankings will shift every time a new score comes in. Either compute only after judging closes, or show a clear "LIVE / PARTIAL" label on the results.

**A judge who gave every project the same score breaks Z-score.**
The fixture data has this on purpose ("a judge who gave every project the same score"). If all of a judge's scores are identical, their standard deviation is 0 — division by zero. Handle this: exclude that judge's scores from normalization, or treat their contribution as 0 deviation (their raw score is the mean).

**Document what you exclude.**
If you disqualify projects or exclude certain scores (drafts, incomplete reviews), document that the normalized ranking only includes fully-scored, non-disqualified projects. Honesty here scores points.

---

## 8. Feature ⑥: CSV Export

### What the CSV should contain

One row per project. Columns:

| project_id | title | track | team | raw_score | normalized_score | reviews_count | [one column per judge with their score] |

The organizer should be able to paste this into a spreadsheet and reconstruct the full picture. Include the judge names as column headers, not just IDs.

### Access control

Only organizers can access the CSV export. The acceptance checker tests this (T2-4). Use the same `require_role("organizer")` pattern as everywhere else.

### Format details

- Standard CSV, UTF-8, comma-separated
- Header row always present
- Numeric scores to 2 decimal places
- Empty cells where a judge hasn't scored a project (not 0, not "N/A" — empty)
- Response header: `Content-Type: text/csv` and `Content-Disposition: attachment; filename="results.csv"`

---

## 9. Execution Order

| Phase | Feature | Test before committing |
|---|---|---|
| **0** | Rubric builder — organizer creates criteria with weights | Criteria appear in DB, weights sum correctly |
| **1** | Judge invitation — invite by email, assign to tracks | New judge appears in judge list with track badges |
| **2** | Judge dashboard + scoring form | Judge sees assigned projects; can submit scores per criterion |
| **3** | Role isolation on scores API | curl as peer judge → 403; curl as participant → 403; curl as self → 200 |
| **4** | Scoring engine — raw weighted average per project | Check math manually against fixture scores |
| **5** | Z-score normalization per track | Rankings look reasonable; handle single-project track |
| **6** | Progress dashboard — completion per track and per judge | Accurate with partial scoring data |
| **7** | CSV export | Download works; all required columns present; correct access control |
| **8** | Run acceptance checker | All 4 T2 checks PASS |
| **9** | Write JUDGING.md | Normalization method documented clearly |

---

## 10. T2 Compliance Checklist

**Role isolation (T2-2 and T2-3 — the ones that kill projects)**
- [ ] Judge scores endpoint returns 403 when requesting another judge's scores
- [ ] This check is in the API handler, not in the template
- [ ] Participant gets 401 or 403 on the judge scores endpoint
- [ ] Test with curl directly — not just through the browser

**Judge sees own scores (T2-1)**
- [ ] Judge scores endpoint returns 200 for the requesting judge
- [ ] Scores are scoped to the requesting judge's ID, not all judges

**CSV export (T2-4)**
- [ ] Export endpoint returns 200 with `Content-Type: text/csv`
- [ ] Response body is valid CSV (has headers, has rows)
- [ ] Export is blocked for non-organizer roles

**Human-judged features**
- [ ] Organizer can invite a judge by email on a new event (not just fixture event)
- [ ] Judge can be assigned to one or more tracks on the new event
- [ ] Rubric criteria are configurable (add, remove, set weights)
- [ ] Rubric cannot be edited after first score is submitted (or shows a warning)
- [ ] Progress dashboard shows completion per track and per judge
- [ ] Results page shows both raw and normalized scores
- [ ] JUDGING.md documents the normalization method with the formula

---

## 11. Data That Already Exists (Fixture Event Only)

The fixture event `evt_01` has 30 judges pre-assigned to tracks, 41 projects, and ~120 scores already recorded. This is for seeding and acceptance checking only.

For **manual testing of the invitation and assignment flow**, create a second event fresh through the organizer UI. Invite one of the existing judges (they already have accounts) by their email. Assign them to a track. Submit a score as that judge. Verify the progress dashboard updates and the results show up.

This is the test the human reviewers will run. Make sure it works cleanly.
