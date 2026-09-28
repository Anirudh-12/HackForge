# 🛡️ HackForge — Threat Model & Anti-Abuse Defense

> **Formal security architecture and threat defenses for DOGFOOD 2026.**  
> *Addresses the Threat Model (Medium) and T1–T4 Enterprise Security Requirements.*

---

## 1. Threat Landscape & Security Objectives

Hackathons represent adversarial, high-stakes environments where prize pools, prestige, and job opportunities incentivize dishonest behavior. A hackathon platform must defend the integrity of all phases of an event:
1. **Submission Phase:** Preventing deadline circumvention, unauthorized project tampering, and duplicate team/project collisions.
2. **Judging Phase:** Enforcing blind, independent evaluations, pairwise comparison consistency, and preventing score leakage between peer judges.
3. **Public Community Phase:** Neutralizing Sybil attacks, ballot stuffing, self-voting collusion, comment XSS, and bandwagon voting bias.
4. **Integration & Credential Phase (T4):** Defending real-time webhooks against spoofing/replay attacks, preventing certificate counterfeiting, and guaranteeing tamper-evident auditability.

---

## 2. Threat Vector Analysis & Mitigation Matrix

| Threat Vector | Adversary Profile | Impact | Architectural Mitigation in HackForge |
|---|---|---|---|
| **Sybil Account Flooding** | Disgruntled or automated participants | Skewed community rankings | Authentication required; only registered `participant` role can vote; strict **1-vote cap** per participant per event. |
| **Ballot Stuffing (Double-Voting)** | Malicious voter | Inflated vote counts | Database-level `UniqueConstraint("user_id", "event_id", name="uq_vote_user_event")` + thread-safe sliding-window rate limiting (max 10 actions/60s). Submitting a new project vote moves the ballot atomically; re-voting toggles/unvotes. |
| **Self-Voting Collusion** | Participant team | Unfair competitive edge | Backend checks `user_team(db, user.id, event.id).id == project.team_id`; returns HTTP 403 Forbidden. |
| **Peer Judge Score Snooping** | Compromised or curious judge | Groupthink, biased scoring, collusion | Backend-enforced role isolation: `/api/judge/scores?judge=peer_id` returns HTTP 403 Forbidden. Peer scores are never exposed. |
| **Bandwagon Voting Bias** | Casual community voters | Top/early projects get disproportionate votes | **Results Hiding:** Tallies sealed until organizer publishes (`vote_count: null`, `results_hidden: true`). **Randomized Ballots:** Shuffled display order per user session seed (`random.Random(user_seed)`). |
| **Late Submission Bypass** | Procrastinating participants | Unfair development time | Hard UTC comparisons in database query layer (`now > submissions_close` returns HTTP 4xx). |
| **Comment Spam & XSS Injection** | Malicious visitor / bot | Defacement, credential theft | Strict HTML sanitization (`html.escape`), 2000-char max, thread-safe sliding-window rate limiter (10 comments/5 min). Author/organizer deletion only. |
| **Duplicate Entity Injection** | Careless or abusive users | State corruption, confusion | Normalized database & route-level deduplication: case-insensitive uniqueness checks on event names, track names, team names, and rubric criteria per event. |
| **Tampering & Repudiation** | Rogue organizers / judges | Disputed winner announcements | Immutable append-only `AuditLog` capturing actor, action, timestamp, and target entity for all mutations. Organizer audit viewer with CSV and JSON exports. |
| **Webhook Delivery Spoofing & Replay** | Man-in-the-middle / external attacker | Unauthorized external actions | HMAC-SHA256 signature verification header (`X-HackForge-Signature: sha256=...`), unique UUID delivery tracking (`X-HackForge-Delivery`), delivery logging to `WebhookDelivery`. |
| **Certificate & Credential Forgery** | Dishonest attendee or judge | False credentials, resume fraud | Tamper-evident verification codes (`CERT-PRT-...`, `CERT-JDG-...`), submission eligibility checks (`_is_certificate_eligible`), and master HMAC-signed judge records (`/verify/record/{id}`). |
| **Unauthorized Bulk Data Scraping** | Competitor / scraper | Leaked private drafts or scores | Organizer/Admin role checks strictly guarding `/api/events/{id}/export/full.json`, CSV exports, and audit endpoints. |

---

## 3. Detailed Architectural Defenses

### 3.1 Defense Against Sybil Attacks & Ballot Stuffing
In open public hackathons, adversaries frequently attempt to automate accounts to vote up their projects.
1. **Role Gating:** Community voting endpoints (`POST /api/projects/{id}/vote`) are not accessible to visitors or unassigned roles. The user must be authenticated and possess an `EventMember` record with role `participant` (or `admin`) for that specific event.
2. **Database-Level Unique Constraints:** Rather than relying solely on application-layer checks, the database schema strictly enforces a single ballot per event:
   ```python
   class Vote(Base):
       __tablename__ = "votes"
       __table_args__ = (
           UniqueConstraint("user_id", "event_id", name="uq_vote_user_event"),
       )
   ```
   Even under concurrent race-condition scenarios, the database engine enforces idempotency and rejects duplicate votes.
3. **Atomic Ballot Transfer & Unvoting:** 
   - When a participant votes for project $A$, a `Vote` record is created.
   - If the participant subsequently votes for project $B$, the existing vote is atomically moved to project $B$, updating `project_id` and logging the transfer to `AuditLog`.
   - If the participant votes for project $A$ again, the vote is toggled off (unvoted).
   - An explicit `DELETE /api/projects/{project_id}/vote` endpoint is also supported.
4. **Sliding-Window Rate Limiting:** To prevent script flooding, `_check_rate_limit(user.id, "vote", max_requests=10, window_seconds=60.0)` enforces a maximum of 10 voting actions per minute using a thread-safe in-memory sliding window, returning `HTTP 429 Too Many Requests` on breach.

### 3.2 Defense Against Self-Voting & Team Collusion
Team members naturally attempt to vote for their own submissions:
```python
team = user_team(db, user.id, event.id)
if team and team.id == project.team_id:
    raise HTTPException(
        status_code=403,
        detail="Self-voting is strictly prohibited: you cannot vote for your own team's project",
    )
```
This check is evaluated before any database transaction, rejecting self-votes with `HTTP 403 Forbidden` and recording the attempt in the event audit ledger.

### 3.3 Defense Against Peer Judge Snooping & Scoring Collusion
A critical requirement of DOGFOOD 2026 (Rule 9) is backend-enforced role isolation:
- Judges must evaluate projects independently without being influenced by peer scores.
- In `src/routers/judge.py`, when a judge requests scores, the backend queries *only* that judge's assigned user ID:
  ```python
  @router.get("/api/judge/scores")
  def get_judge_scores(
      request: Request,
      judge: str = None,
      db: Session = Depends(get_db),
      user: User = Depends(require_role("judge")),
  ):
      if judge and judge != user.id:
          raise HTTPException(status_code=403, detail="cannot view peer scores")
      ...
  ```
- Automated testing in `tests/test_role_isolation.py` and acceptance checkers verify that `judge_b` querying `judge_a`'s endpoint receives `HTTP 403 Forbidden`.

### 3.4 Defense Against Bandwagon Voting (Results Hiding & Randomized Ballots)
When vote tallies are visible, voters suffer from **herd behavior**, overwhelmingly voting for existing front-runners. Furthermore, projects appearing first alphabetically receive significantly more views.
HackForge deploys a two-pronged defense:
1. **Sealed Ballot Window:** Vote counts are masked in all JSON endpoints and template renders (`vote_count: null`, `results_hidden: true`) until the organizer explicitly toggles `results_published = True`.
2. **Session-Deterministic Ballot Randomization:**
   ```python
   if sort == "random":
       rng = random.Random(user_seed) if user_seed else random.Random()
       shuffled = list(projects)
       rng.shuffle(shuffled)
       return shuffled
   ```
   This eliminates position bias across the entire gallery while maintaining consistent pagination for an individual reviewer during their session.

### 3.5 Defense Against Comment Abuse & XSS
User-submitted project feedback is sanitized against persistent Cross-Site Scripting (XSS):
- All incoming comment strings are stripped and escaped server-side via `html.escape()`.
- Maximum length is clamped to 2,000 characters.
- Anti-spam sliding window restricts users to 10 comments per 5 minutes (`HTTP 429 Too Many Requests`).
- Deletion rights (`DELETE /api/projects/{project_id}/comments/{comment_id}`) are strictly restricted to the original comment author or event organizers/admins.

### 3.6 Non-Repudiation & Audit Trail
Every security-sensitive state mutation is recorded in `audit_logs`:
- User registration, role assignments, and team invitations/join requests.
- Project creation, drafts, cover image uploads, and final submissions.
- Rubric score submissions, conflict-of-interest declarations, and pairwise comparisons.
- Community votes cast, moved, toggled, and comment additions/deletions.
- Webhook creation, deletion, certificate generation, and bulk imports.

Organizers have full visibility into the timeline through the Compliance Ledger (`/organizer/{event_id}/audit`) with dedicated filtering by category and search queries, as well as CSV and JSON export routes (`/organizer/{event_id}/audit/export.csv`, `/organizer/{event_id}/audit/export.json`, `/api/events/{event_id}/audit`).

### 3.7 Webhook Security & Tamper-Evident Credentials (T4)
1. **HMAC-SHA256 Webhook Verification:**  
   Every outgoing webhook HTTP POST delivery (`dispatch_webhook`) is signed with the subscriber's private shared secret:
   $$\text{Signature} = \text{"sha256="} \,\|\, \text{HMAC-SHA256}(\text{secret}, \text{payload\_bytes})$$
   Endpoints verify origin authenticity and payload integrity using constant-time comparison (`hmac.compare_digest`).
2. **Signed Judge Participation Records:**  
   To prevent judges from inflating their evaluation portfolios, judge records are cryptographically signed using a server master secret:
   $$\text{Signature} = \text{HMAC-SHA256}(\text{SERVER\_SECRET}, \text{judge\_id} \,\|\, \text{":"} \,\|\, \text{event\_id} \,\|\, \text{":"} \,\|\, \text{scores\_count} \,\|\, \text{":"} \,\|\, \text{timestamp})$$
   Any modification to scores or timestamp invalidates the signature verified at `/verify/record/{record_id}`.
3. **Certificate Eligibility Gating:**  
   Participation certificates cannot be forged or prematurely issued: `_is_certificate_eligible()` requires that the participant's team has submitted an active, non-draft, non-disqualified project in that event before any certificate can be generated, viewed, downloaded as SVG, or verified at `/verify/certificate/{code}`.
