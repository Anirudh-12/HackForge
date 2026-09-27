# T1 CORE — Implementation Plan
### DOGFOOD 2026 · 72h window: Fri 25 Sep 18:00 UTC → Mon 28 Sep 18:00 UTC

---

## 0. What the Acceptance Checker Actually Tests

The checker only runs **3 mechanical T1 checks**. Everything else — auth, roles, teams, prizes — is judged by a human reading your code and watching your demo. Know which is which.

| # | What | How it checks | Pass condition |
|---|---|---|---|
| **T1-1** | Gallery is public | Hits the gallery URL with no auth header | HTTP 200 |
| **T1-2** | Gallery shows fixture projects | Reads the raw HTML body of that response | At least one fixture project title is in the HTML |
| **T1-3** | Closed event refuses submissions | POSTs to your submit URL as a participant | HTTP 4xx — not a redirect, not a 200 |

**Prioritise these three above all else.** A clean T1-1/2/3 with a half-built team page beats a beautiful team page that fails T1-3.

---

## 1. T1 Requirements

```
T1 CORE
  ① Authentication and sessions
  ② A real role model: visitor, participant, judge, organizer, admin
  ③ Event creation with configurable dates, tracks and prizes
  ④ Team formation by invite link
  ⑤ Project submission with draft and edit until the deadline
  ⑥ Deadline enforcement that actually holds
  ⑦ Public gallery with search and filter
```

---

## 2. Lessons Learned — What Will Bite You-from past experience

These are hard-won lessons from a full dry run of this build. Not theory — things that actually broke.

---

### 🔴 Checker Killers — Silent Fails

**When the submission endpoint returns a redirect instead of an error status**
When an event is closed and someone POSTs to submit, the natural instinct is to redirect them to an error page. A browser handles that gracefully. The acceptance checker does not — it reads the HTTP status code directly and a 303 redirect is not a 4xx. The check will FAIL with no obvious reason unless you run the checker yourself first.

> **Lesson:** When a deadline has passed, the POST handler must return an actual error status code (4xx). Never a redirect. Build this check into the handler itself, not into a redirect chain.

---

**When gallery content is rendered by JavaScript**
The checker fetches the gallery URL and reads the raw response body as plain text. If your frontend makes an API call after load to fetch projects and inserts them into the DOM via JavaScript, the checker sees the HTML shell with no project titles in it.

> **Lesson:** Project titles must be in the server-rendered HTML. Render them in your template engine on the server, not client-side. This is one place where a "modern" SPA approach actively hurts you.

---

**When the gallery accidentally requires login**
If you apply an auth guard to the gallery route out of habit — or because your middleware catches everything — the checker gets a redirect to the login page and T1-1 fails.

> **Lesson:** The public gallery is the one route that must be completely open. No auth whatsoever. Test it yourself with no cookies before running the checker.

---

### 🟠 Things That Break Mid-Build

**Timezone drift in deadline enforcement**
Your database stores datetimes in UTC. Your machine runs in a local timezone. If your deadline comparison uses the local clock instead of UTC, you can be off by hours. In a timezone like IST (UTC+5:30) that's a 5.5 hour window where something that should be "closed" reads as "open" or vice versa.

> **Lesson:** Always compare datetimes in UTC. Pick one convention at the start and enforce it everywhere — models, handlers, seed scripts, all of it.

---

**Schema changes not reflected after the DB already exists**
Most ORMs (including SQLAlchemy) only create tables that don't exist yet — they don't alter existing ones. If you add a column to a model after the database file was already created, the column is silently absent at runtime. You only find out when a query crashes with an obscure "no such column" error.

> **Lesson:** During active development, delete and recreate the database any time you change the schema. Don't assume `create_all` will pick up your changes — it won't.

---

**Using the wrong Python environment**
You might have multiple Python installations (system Python, conda, venv). If the server starts with the wrong one, any dependency that lives only in the venv will crash at import with a `ModuleNotFoundError`. The server appears to start but dies immediately on the first request.

> **Lesson:** Always be explicit about which Python and which server binary you're using. Always verify your dependencies are importable before running the server for the first time after a fresh environment setup.

TO DO:Create venv using python 3.13 version and make sure it is activated before running the server.
---

**Post-login redirects landing on 404**
After login, the server redirects each role to their home page. If those home pages are scoped to an event ID (e.g. a judge's dashboard for a specific event) but the redirect URL is hardcoded to a generic path, every login in the system ends on a 404. The entire app looks broken even though the only thing wrong is one redirect string.

> **Lesson:** Build the post-login redirect logic correctly — looking up the actual event from the database and constructing the real URL — before you build anything else. It touches every role, so a bug here breaks all manual testing immediately.

---

### 🟡 Design Traps

**Forgetting to pass event context into every template**
When routes are scoped to an event, every template needs the event object to generate correct nav links and breadcrumbs. It's easy to pass it for the first few routes and then forget it on others. The result is Jinja2 `UndefinedError` at render time, or worse — silently broken links that point to the wrong URLs.

> **Lesson:** Make it a non-negotiable rule: every template response includes the event in its context, always. Consider a helper function that builds the base context so you can't accidentally skip it.

---

**Invite tokens that are guessable or reused**
For team formation by invite link, the token in the URL needs to be unguessable. Sequential IDs, short hex strings, or anything derived from predictable data can be brute-forced. The spec scores on integrity and adoptability — showing you thought about this earns points.

> **Lesson:** Use a cryptographically random token of sufficient length (UUID4 or equivalent). Generate a new one only on explicit request; don't regenerate silently on every page load.

---

**Seeded test users not being accepted at login**
The fixture data includes users that were never asked to set a password. If your login handler only accepts users with a stored password hash, all fixture logins fail. This blocks every test flow that depends on logging in as a specific role.

> **Lesson:** Handle the "no password hash" case explicitly in your login handler. Test users should be accepted regardless of what password is entered. Keep this clearly commented so it doesn't get accidentally removed.

---

**Submitting the same project twice**
If a participant visits the submit page, submits, then visits again and submits once more, you get two project rows for the same team. The gallery shows duplicates, the results page double-counts scores. This is easy to overlook when you're testing happy paths.

> **Lesson:** The submit handler should check whether this team already has a project for this event. If it does, update it — never insert a second one. This is an upsert, and it needs to be there from day one.

---

### 🟢 Easy to Miss, Quick to Fix

**Config tokens going stale after a server restart**
The acceptance checker reads session tokens from your config file and uses them directly as auth headers. If those tokens were generated with one server secret but the server now uses a different one, they're invalid. All checker tests that require auth will fail.

> **Lesson:** After every fresh server start, verify your config tokens match the ones the server actually issued. Your seed script should print them; copy them across before running the checker.

---

**ORM objects accessed after the session closes**
If you pass a database object to a template and the template accesses a related object (e.g. a project's track), but the database session has already been closed, you get a `DetachedInstanceError`. This is especially subtle because it only happens on certain render paths, not all of them.

> **Lesson:** Either load relationships eagerly on the query (so they're already in memory), or make sure all attribute access happens within the request lifecycle before the session closes.

---

**Fixture data transformed in the seed script**
The acceptance checker looks for exact fixture titles in the gallery HTML. If your seed script cleans, trims, transforms, or skips any of the fixture project data, those titles won't appear and T1-2 fails.

> **Lesson:** Load fixture data exactly as provided. Don't normalise, don't sanitise, don't truncate. The fixture file is input — treat it as-is.

---

## 3. Execution Order

Build in this order. Each phase has a clear test you can run before moving on. Commit after each phase passes.

| Phase | Feature | Test before committing |
|---|---|---|
| **0** | Environment setup — verify deps, clean DB, start server | Server boots and prints seed output |
| **1** | Auth + roles — login works, each role lands on a real page | Login as each role; no 404s |
| **2** | Track + prize configuration | Create a track with a prize; it appears in the list |
| **3** | Submission form + deadline enforcement | POST to the submit URL with a closed event → must get 4xx |
| **4** | Team formation — create, invite, join, leave | Full flow: create team, generate link, open link as another user, join |
| **5** | Public gallery — search + filter | Gallery returns 200 with no auth; fixture titles in the HTML |
| **6** | Run the acceptance checker | All 3 T1 checks PASS |
| **7** | Write documentation | README, architecture notes, acceptance report committed |

**Total time estimate: ~3 hours.** That leaves ~69 hours for T2.

---

## 4. Data Model Decisions

Design the schema to satisfy T1 and T2 from the start. Adding columns later means dropping and recreating the DB every time.

- **Event** holds dates (`submissions_open`, `submissions_close`, `judging_open`, `judging_close`) and a `results_published` flag
- **Track** has a `prize` field — nullable text, free-form
- **User** has a nullable `password_hash` — null means seeded test user, any password accepted
- **Team** has a nullable `invite_token` — generated on demand, not at team creation
- **Project** has `is_draft`, `submitted_at`, and `is_disqualified` — all needed before T2
- **Score** has a `UNIQUE` constraint on `(judge_id, project_id, criteria_id)` — prevents duplicate scoring at the DB level
- **AuditLog** is cheap to add now and earns points on integrity — log every state change

---

## 5. T1 Compliance Checklist

Run this before declaring T1 done.

**Gallery (T1-1 + T1-2)**
- [ ] Gallery URL returns HTTP 200 with no auth header
- [ ] No auth guard on the gallery route
- [ ] At least one fixture project title appears in the raw HTML
- [ ] Project titles are rendered server-side, not fetched by JavaScript

**Deadline enforcement (T1-3)**
- [ ] POST to the submission URL with a closed event returns a 4xx status
- [ ] The check is in the backend handler, not just a frontend message
- [ ] Deadline comparison uses UTC consistently
- [ ] An unauthenticated POST to the submit URL returns 401

**Everything else (human-judged)**
- [ ] All 5 roles can log in and land on a real page
- [ ] Organizer can create an event with tracks and prizes
- [ ] Participant can form a team, generate an invite link, share it
- [ ] A second participant can join via the link
- [ ] Participant can submit a project while the event is open, save as draft, edit
- [ ] Gallery has working search (by title) and filter (by track)
