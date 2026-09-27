# DOGFOOD 2026 — Full Platform Build Plan (Final)

> **Name**: Hackforge
> **Pitch**: "Run your hackathon without the spreadsheet chaos."
> **Stack**: Python · FastAPI · SQLite · SQLAlchemy · Jinja2 · Vanilla CSS
> **Viewport target**: 1440px desktop-first
> **Design direction**: Linear + GitHub Projects. NOT Devpost.

---

## Visual Language

```
NOT this:          purple gradients · glowing cards · glassmorphism blobs
THIS:              off-white bg · white surfaces · dark text · one accent
```

| Token | Value | Usage |
|---|---|---|
| `--bg` | `#f7f7f5` | Page background |
| `--surface` | `#ffffff` | Cards, panels, sidebar |
| `--border` | `#e4e4e4` | All borders |
| `--text-primary` | `#111111` | Headings, labels |
| `--text-secondary` | `#6b6b6b` | Subtitles, meta |
| `--text-muted` | `#a0a0a0` | Timestamps, placeholders |
| `--accent` | `#2563eb` | One strong blue. Used sparingly. |
| `--accent-subtle` | `#eff6ff` | Accent background tint |
| `--success` | `#16a34a` | Submitted, complete |
| `--warning` | `#d97706` | Draft, in progress |
| `--danger` | `#dc2626` | Disqualified, error |
| `--radius` | `8px` | All corners |
| `--shadow` | `0 1px 3px rgba(0,0,0,0.08)` | Minimal shadow |

**Typography**: Inter (Google Fonts). Size scale: 12 / 14 / 16 / 20 / 24 / 32.

**Components**: `btn`, `badge`, `status-pill`, `table`, `input`, `select`, `progress-bar`, `stat-block`, `sidebar-nav`, `flash`, `modal`.

---

## Two UI Systems

This is not negotiable. Public gallery and the internal app are separate design contexts.

### System A — Public / Participant UI
- Spacious. More padding. Fewer columns.
- Simple top navbar (no sidebar).
- Pages: Landing, Gallery, Project Detail, Login, Register, Participant Workspace

### System B — Internal Application UI
- Dense. Sidebar nav. Data tables. Stats.
- Sidebar changes entirely by role.
- Pages: Organizer Dashboard, Judge Workspace, Admin

**Never force the sidebar onto the public gallery. Never make the gallery look like the admin panel.**

---

## Build Order (revised — UI-first, data-flows outward)

```
1. Design System CSS       → tokens, all components, both layout shells
2. Organizer Dashboard     → the hardest, most information-dense screen
3. Judge Workspace         → the visual centerpiece; determines the whole IA
4. Participant Workspace   → simpler but must feel like a real product
5. Public Gallery + Landing → last, because it's the easiest
6. Backend wiring          → connect all pages to real data
7. Normalization Proof     → JUDGING.md + tools/normalize_fixtures.py
8. API layer               → /api/* JSON endpoints
```

---

## Phase 0 — Project Cleanup (Foundation)

Before any UI work:

- [x] `src/__init__.py`
- [x] `src/auth.py` — `get_current_user()`, `require_role("organizer")` as FastAPI deps
- [x] `src/routers/` — one file per role: `public.py`, `auth.py`, `participant.py`, `judge.py`, `organizer.py`, `api.py`
- [x] Move inline route logic out of `main.py`
- [x] `src/models.py` — added `RubricCriteria`, `AuditLog`, invite tokens, proper relationships
- [x] Acceptance checker still passes after restructure — **all 7 checks PASS, T1+T2 verified**

> **Note on fixture data**: The "One line of what it does." summaries are from `fixtures.json` verbatim.
> That's intentional per the spec — shared fixture data, not real projects. Will look fine with real submissions.

---

## Phase 1 — Design System

All CSS lives in `src/static/style.css`. No frameworks. No utility classes.

### Layout shells

**Shell A — Public (top nav)**
```
┌─────────────────────────────────────────────────────────────────┐
│ Hackforge                          Events   Explore   Sign in   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                        Page content                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Shell B — App (sidebar + topbar)**
```
┌──────────────┬──────────────────────────────────────────────────┐
│ ◈ Hackforge  │  [Breadcrumb]                   User name ▾     │
├──────────────┼──────────────────────────────────────────────────┤
│              │                                                  │
│  Role-aware  │              Page content                        │
│  sidebar     │                                                  │
│  nav         │                                                  │
│              │                                                  │
└──────────────┴──────────────────────────────────────────────────┘
```

### Component inventory

| Component | Description |
|---|---|
| `.btn .btn-primary` | Solid accent fill. Used for primary CTAs only. |
| `.btn .btn-secondary` | Outlined. Used for secondary actions. |
| `.btn .btn-ghost` | No border. Used for destructive/inline actions. |
| `.badge` | Small inline label. Track name, role label. |
| `.status-pill` | `● Draft` `● Submitted` `● Under review` `● Published`. Color-coded dot. |
| `.stat-block` | Big number + small label. Used in dashboard summary row. |
| `.progress-bar` | Thin, labeled. Used in judge progress rows. |
| `.data-table` | Dense, sortable. Thin borders, hover highlight row. |
| `.input` `.select` `.textarea` | Consistent form controls. Clear focus ring (accent color). |
| `.sidebar-nav` | Collapsible sections. Active item highlighted with accent. |
| `.flash` | Top-of-page banner. Auto-dismiss at 4s. Success/error/warning variants. |
| `.modal` | Centered overlay. Confirm dialogs only. |
| `.card` | White surface + border. Used sparingly in public UI. |
| `.event-readiness` | Status checklist: T1 ✓ T2 ◐ T3 ○ |

### Status pills (used everywhere)
```
● Draft          (yellow)
● Submitted      (green)
● Under review   (blue)
● Judged         (purple)
● Published      (green)
● Disqualified   (red)
```

---

## Phase 2 — Organizer Dashboard

**This is the visual centerpiece. Build it before anything else.**

### Sidebar (Organizer)
```
OVERVIEW
  Dashboard

HACKATHON
  Projects
  Teams
  Judges

JUDGING
  Assignments
  Progress
  Results

SETTINGS
  Event
  Rubric
  Members
```

### `/organizer/dashboard` — Overview

```
Overview                                       Sample Hack 2026

┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
│     40     │ │     37     │ │     30     │ │    72%     │
│  Projects  │ │ Submitted  │ │   Judges   │ │  Judging   │
└────────────┘ └────────────┘ └────────────┘ └────────────┘

SUBMISSIONS
────────────────────────────────────────────────────────────
Submitted       ████████████████████████░░░  37 of 40
Draft           ███░░░░░░░░░░░░░░░░░░░░░░░░   3 of 40

JUDGING PROGRESS
────────────────────────────────────────────────────────────
Ada Okonkwo     ██████████████████████  10 / 10  ✓
Wei Lindqvist   ████████████████░░░░░    8 / 10
Priya Nair      ████████░░░░░░░░░░░░░    4 / 10
⚠ Charlie Park  ██░░░░░░░░░░░░░░░░░░░    1 / 10

EVENT READINESS
────────────────────────────────────────────────────────────
T1 Core           ✓ Submissions open
T2 Judging        ◐ 14 of 40 fully judged
Deadline          Sep 28 · 18:00 UTC · 3 days remaining
```

**Score Variance Flags** (inline alert):
```
⚠ 3 projects have high judge disagreement (stddev > 1.5). Worth reviewing.
  → Glass Signal, North Drift, Quiet Anchor
```

### `/organizer/projects` — Table, not cards

```
Projects                                    [ + Add project ]

Search...                    [ Track ▼ ]  [ Status ▼ ]

┌──────────────┬─────────────┬───────────────┬───────────┬──────────────┐
│ Project      │ Team        │ Track         │ Status    │ Scores       │
├──────────────┼─────────────┼───────────────┼───────────┼──────────────┤
│ Glass Signal │ NorthKiln   │ Security      │ Submitted │ 4 / 6        │
│ Small Meadow │ LoudQuarry  │ Accessibility │ Submitted │ 6 / 6        │
│ Deep Compass │ StillTrail  │ Accessibility │ Draft     │ 0 / 6        │
│ ⚠ Duplicate  │ ...         │ ...           │ Submitted │ 2 / 6        │
└──────────────┴─────────────┴───────────────┴───────────┴──────────────┘
```

Click a row → project detail with audit history.

### `/organizer/judges` — Progress table

```
Judges                                      [ + Invite judge ]

┌────────────────┬────────────┬───────────┬─────────────────────────────┐
│ Judge          │ Tracks     │ Progress  │                             │
├────────────────┼────────────┼───────────┼─────────────────────────────┤
│ Ada Okonkwo    │ Accessibility│ 10/10   │ ██████████████████ 100%    │
│ Wei Lindqvist  │ Data, Security│ 8/10   │ ████████████████░░  80%    │
│ Priya Nair     │ Security   │  4/10     │ ████████░░░░░░░░░░   40%   │
└────────────────┴────────────┴───────────┴─────────────────────────────┘
```

Click a judge → their assignments + per-project status.

### `/organizer/results` — Rankings with normalization toggle

```
Results

┌─────────────────────────────────────────────────────────────────────┐
│ Results status                                                      │
│                                                                     │
│ Judging complete  ████████████████████████████████████ 100%        │
│                                                                     │
│ Results are currently hidden from participants.                     │
│                                                                     │
│ [ Preview results ]    [ Export CSV ]    [ Publish results →  ]     │
└─────────────────────────────────────────────────────────────────────┘

RANKING

[ Raw average ]  [ Normalized ← ]          ← toggle changes the table

┌────┬──────────────────┬────────┬───────────┬──────────┐
│ #  │ Project          │ Score  │ Δ Rank    │ Reviews  │
├────┼──────────────────┼────────┼───────────┼──────────┤
│  1 │ QuantumFoo       │ 4.72   │ ▲ +2      │ 10       │
│  2 │ Glass Signal     │ 4.65   │ —         │ 10       │
│  3 │ Deep Compass     │ 4.51   │ ▼ -1      │  9       │
└────┴──────────────────┴────────┴───────────┴──────────┘

Δ Rank = change vs. raw average. Why did QuantumFoo move up?
→ jdg_07 has a baseline of 2.1. Their score of 4 is a strong signal.
   See JUDGING.md for the full normalization method.
```

### `/organizer/audit` — Human-readable log

```
Audit log

[ Export log ]

Sep 25 14:02   Judge Wei Lindqvist scored "Glass Signal" — Functionality: 4, Quality: 3
Sep 25 14:08   Organizer published results for "Sample Hack 2026"
Sep 25 14:15   Participant priya1 edited project "Glass Signal" — changed: summary
Sep 25 09:30   Organizer assigned Wei Lindqvist to track "Security"
```

Not `{"action": "SCORE_SUBMIT", "actor_id": "jdg_02"}`. Plain English sentences.

### `/organizer/rubric` — Configure criteria

```
Scoring criteria

[ + Add criterion ]

┌─────────────────┬────────┬──────────────────────┐
│ Criterion       │ Weight │                       │
├─────────────────┼────────┼──────────────────────┤
│ Functionality   │  40%   │ [ Edit ] [ Remove ]   │
│ Quality         │  30%   │ [ Edit ] [ Remove ]   │
│ Innovation      │  30%   │ [ Edit ] [ Remove ]   │
└─────────────────┴────────┴──────────────────────┘

Weights must sum to 100%.  Current: 100% ✓

Preview: A project scoring 5/5/5 = 5.0  ·  A project scoring 4/5/3 = 4.2
```

---

## Phase 3 — Judge Workspace

**A focused, distraction-free judging UI. Nothing from the organizer dashboard leaks here.**

### Sidebar (Judge)
```
JUDGING

  My assignments
  Completed
```

### `/judge/dashboard`

```
Sample Hack 2026                               7 / 10 reviews

MY ASSIGNMENTS
────────────────────────────────────────────────────────────
  Glass Signal      Security      ● Scored
  Small Meadow      Accessibility ● Scored
  Deep Compass      Accessibility ○ Pending   [ Score → ]
  North Drift       Security      ○ Pending   [ Score → ]
  Quiet Anchor      Climate       ○ Pending   [ Score → ]
```

No overall stats. No other judges' data. Nothing irrelevant.

### `/judge/score/{project_id}` — Scoring workspace

```
← My assignments                              7 / 10 reviews

QuantumFoo
Developer Tools · Team Nightshift

One-line summary of what the project does.

GitHub ↗     Demo ↗

────────────────────────────────────────────────────────────

FUNCTIONALITY (40%)
○ 1 — Poor    ○ 2 — Below avg    ○ 3 — Average    ● 4 — Good    ○ 5 — Excellent

QUALITY (30%)
○ 1           ○ 2               ○ 3              ○ 4           ● 5

INNOVATION (30%)
○ 1           ○ 2               ● 3              ○ 4           ○ 5

Comment (optional)
┌──────────────────────────────────────────────────────────┐
│                                                          │
└──────────────────────────────────────────────────────────┘

                            [ Save draft ]  [ Submit review ]
```

- Radio buttons, not sliders. Radio buttons are unambiguous.
- Criterion weight shown next to label.
- "Submit review" locks the score (editable until organizer closes judging).
- Judge cannot see other judges' scores on this page or anywhere else.

---

## Phase 4 — Participant Workspace

### Sidebar (Participant)
```
MY HACKATHONS

  Overview
  Team
  Submission
```

### `/participant/dashboard`

```
Sample Hack 2026                              Participant ▾

┌─────────────────────────────────────────────────────────┐
│ Your submission                                         │
│                                                         │
│ QuantumFoo                                              │
│ Developer Tools                                         │
│                                                         │
│ ● Draft                                                 │
│                                                         │
│ [ Edit submission → ]                                   │
└─────────────────────────────────────────────────────────┘

Your team: Nightshift
Members: priya1@example.org · member1@example.org
[ Copy invite link ]

Deadline
1d 04h 32m
```

Four questions answered immediately:
1. What hackathon am I in?
2. What is my team?
3. What is my submission status?
4. When is the deadline?

### `/participant/submit` — Submission editor

```
← My Project                                          Save draft

Project details

Project name
┌──────────────────────────────────────────────────────────┐
│ QuantumFoo                                               │
└──────────────────────────────────────────────────────────┘

Track
[ Developer Tools                                    ▼ ]

Summary
┌──────────────────────────────────────────────────────────┐
│                                                          │
│                                                          │
└──────────────────────────────────────────────────────────┘

Repository
[ https://github.com/...                                   ]

Demo URL (optional)
[ https://...                                              ]


                              [ Save draft ]  [ Submit project ]
```

**After deadline, replace form entirely:**
```
┌─────────────────────────────────────────────────────────┐
│ 🔒 Submissions closed                                   │
│                                                         │
│ This event closed on March 1, 2026.                     │
│ Your project has been submitted.                        │
└─────────────────────────────────────────────────────────┘

Project name      QuantumFoo
Track             Developer Tools
Summary           ...
Repository        github.com/...
Submitted         Feb 28, 2026 · 22:14 UTC
```

Backend still enforces `submissions_close`. Frontend is UX, not security.

---

## Phase 5 — Public UI

**Build this last. It's the easiest.**

### Top navbar (Shell A)
```
Hackforge                         Events   Explore   Sign in
```

### `/` — Landing page

```
Hackforge                         Events   Explore   Sign in


        RUN YOUR HACKATHON
        WITHOUT THE SPREADSHEET CHAOS.

        Open-source hackathon submission and judging platform.
        Self-host it. Own the data.

        [ Create Hackathon ]   [ Explore Events ]


   submissions       judging        voting       results
```

No hero image. No animated blobs. No testimonials. No pricing table.
The feature list (4 words each) is enough.

### `/projects` — Gallery

```
Sample Hack 2026
40 projects · 8 tracks

┌──────────────────────────────────────────────────────────┐
│ Search projects...                                       │
└──────────────────────────────────────────────────────────┘

[ All tracks ▼ ]   [ Latest ▼ ]

┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│                  │ │                  │ │                  │
│ (color bar       │ │ (color bar       │ │ (color bar       │
│  from track)     │ │  from track)     │ │  from track)     │
│                  │ │                  │ │                  │
├──────────────────┤ ├──────────────────┤ ├──────────────────┤
│ Glass Signal     │ │ Small Meadow     │ │ Deep Compass     │
│ One-line summary │ │ One-line summary │ │ One-line summary │
│                  │ │                  │ │                  │
│ Security         │ │ Accessibility    │ │ Accessibility    │
│ NorthKiln        │ │ LoudQuarry       │ │ StillTrail       │
│ [ Vote ]         │ │ [ Vote ]         │ │ [ Voted ✓ ]      │
└──────────────────┘ └──────────────────┘ └──────────────────┘

*Note: "Vote" buttons only appear for logged-in participants.*
```

Cards are spacious but not bloated. Track color bar = the only decoration.
Not 15 fields per card. Just: title, one-line summary, track, team.

### `/projects/{id}` — Project detail

```
← Back to gallery

Glass Signal
Security · NorthKiln

One-line summary of what the project does.

Submitted Feb 27, 2026

GitHub ↗     Demo ↗

[ Vote for this project ]

────────────────────────────────────────────────────────────

About

Full description or summary text.

Team

priya1@example.org
member1@example.org
member2@example.org

────────────────────────────────────────────────────────────

Comments

**Wei (Judge)** - Great technical implementation!
**Priya (Participant)** - Love the design and flow.

[ Write a comment...                      ] [ Post ]

────────────────────────────────────────────────────────────

Results will be published when the organizer opens the
results window.
```

After results published → shows normalized score and rank.

---

## Phase 6 — Authentication & Sessions (Local)

- No external dependencies (fully self-hosted).
- Implement local authentication using `passlib` + `bcrypt` storing password hashes in SQLite.
- Remove `?role=` query parameter bypass.
- Build custom `/login` and `/register` form endpoints.
- Enforce protected routes using HTTP-only signed session cookies (JWT or secure tokens).

---

## Phase 7 — Platform Administration (Core Setup)

**Shift away from relying on `fixtures.json`. Organizers need full control in the UI.**

### `GET/POST /organizer/event`
- Form for organizers to set Hackathon Name, Logo, Start/End dates, and Submission Deadlines.

### `GET/POST /organizer/tracks`
- Interface to add, edit, or remove tracks (e.g., "Best Security Hack").
- Ability to set track-specific prizes or rules.

### `GET/POST /organizer/rubric`
- Custom rubric builder to add, remove, and adjust weights for scoring criteria (Functionality, Quality, Innovation, etc.) instead of hardcoded database seed criteria.

---

## Phase 7.5 — Multi-Event Architecture (Option A)

**Transition from a single implicit event to a fully multi-tenant platform.**
- **The "Events Hub"**: Create a global `/organizer/events` page that lists all hackathons an organizer manages, using the generated UI mockup. Includes a "Create Hackathon" button.
- **Router Refactoring**: Update all organizer routes (`/dashboard`, `/projects`, `/judges`, `/results`, `/event`, `/tracks`, `/rubric`) to be scoped with an `event_id` (e.g., `/organizer/{event_id}/dashboard`).
- **Participant/Judge Scoping**: Ensure participant and judge routes similarly use `/{event_id}/...` so users can interact with multiple events concurrently.
- **Sidebar & Links**: Update all template links and the sidebar macro to dynamically inject `{{ event.id }}`.
- **Security Check**: Ensure `db.query()` calls consistently filter by `event_id` instead of using `.first()`.

---

## Phase 8 — Judge & Team Management

### `GET/POST /organizer/assignments` (Organizers)
- UI to invite judges via email.
- Assign judges dynamically to specific tracks or projects so they only see relevant submissions.

### `GET/POST /participant/team` (Participants)
- Team building UI: "Looking for Teammates" board based on skills.
- UI for participants to request to join teams or send team invites securely.

---

## Phase 9 — Normalization Proof (Originally Phase 6)

### `tools/normalize_fixtures.py`

Script that runs on data to prove the math:
- Calculates per-judge mean and stddev.
- Identifies flat scorers → excludes them.
- Z-score normalization applied.
- Final ranking before vs after.

### `JUDGING.md` — The documented proof
- Detailed mathematical documentation of how scores are adjusted for strict/lenient judges.

---

## Phase 10 — API & Final Polish (Originally Phase 8)

```text
GET  /api/projects              Public. All projects after deadline.
GET  /api/projects/{id}         Public. Single project.
GET  /api/judge/scores          Judge auth. Own scores only.
GET  /api/organizer/scores      Organizer auth. All scores.
GET  /api/export.csv            Organizer auth. Full CSV.
GET  /api/results               Public after publish. Final rankings.
GET  /docs                      Auto OpenAPI UI (FastAPI built-in).
```

---

## Phase 11 — T3 Public (Community Features)

- **Community Voting**: Enable public voting (email-gated, link-based, or authenticated).
- **Project Comments**: Allow authenticated users to leave comments on project pages.
- **Results Obfuscation**: Hide results and leaderboards during the active voting window.
- **Ballot Randomization**: Randomize project ordering on the gallery and ballots to prevent bias.
- **Anti-Abuse**: Implement rate limits, duplicate vote detection, and an audit trail for community actions.

---

## Phase 12 — T4 Stretch Goals

- **Advanced APIs & Webhooks**: Expand the REST API and build outgoing webhooks for event triggers.
- **Certificates**: Generate certificates and participation records for attendees.
- **Verifiable Records**: Create signed, publicly verifiable judge participation records.
- **Widgets**: Build an embeddable gallery widget for external sites.
- **Data Portability**: Build full bulk import and export tools for offline migration.

---

*Note: For the legacy API inventory and file structure plan, refer to `old_plan.md`.*
