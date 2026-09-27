# 🛡️ HackForge — Threat Model & Anti-Abuse Defense

> **Formal security architecture and threat defenses for DOGFOOD 2026.**  
> *Addresses the Threat Model (Medium) bonus challenge.*

---

## 1. Threat Landscape & Security Objectives

Hackathons represent adversarial, high-stakes environments where prize pools, prestige, and job opportunities incentivize dishonest behavior. A hackathon platform must defend the integrity of three distinct phases:
1. **Submission Phase:** Preventing deadline circumvention and unauthorized project tampering.
2. **Judging Phase:** Enforcing blind, independent evaluations and preventing score leakage between peer judges.
3. **Public Community Phase:** Neutralizing Sybil attacks, ballot stuffing, self-voting collusion, and bandwagon voting bias.

---

## 2. Threat Vector Analysis & Mitigation Matrix

| Threat Vector | Adversary Profile | Impact | Architectural Mitigation in HackForge |
|---|---|---|---|
| **Sybil Account Flooding** | Disgruntled or automated participants | Skewed community rankings | Authentication required; only registered `participant` role can vote; 50-vote cap per participant per event. |
| **Ballot Stuffing (Double-Voting)** | Malicious voter | Inflated vote counts | Database-level `UniqueConstraint(user_id, project_id)` + sliding-window rate limiting (max 15 vote actions/min). |
| **Self-Voting Collusion** | Participant team | Unfair competitive edge | Backend checks `user_team(user_id, event_id) == project.team_id`; returns HTTP 403 Forbidden. |
| **Peer Judge Score Snooping** | Compromised or curious judge | Groupthink, biased scoring, collusion | Backend-enforced role isolation: `/api/judge/scores?judge=peer_id` returns HTTP 403. Peer scores are never exposed. |
| **Bandwagon Voting Bias** | Casual community voters | Top/early projects get disproportionate votes | **Results Hiding:** Tallies sealed until organizer publishes. **Randomized Ballots:** Shuffled display order per user session. |
| **Late Submission Bypass** | Procrastinating participants | Unfair development time | Hard UTC comparisons in database query layer (`now > submissions_close` returns HTTP 4xx). |
| **Comment Spam & XSS Injection** | Malicious visitor / bot | Defacement, credential theft | Strict HTML sanitization (`html.escape`), 2000-char max, sliding-window rate limiter (10 comments/5 min). |
| **Tampering & Repudiation** | Rogue organizers / judges | Disputed winner announcements | Immutable append-only `AuditLog` capturing actor, action, timestamp, and target entity for all mutations. |

---

## 3. Detailed Architectural Defenses

### 3.1 Defense Against Sybil Attacks & Ballot Stuffing
In open public hackathons, adversaries frequently attempt to automate hundreds of email signups to vote up their projects.
1. **Role Gating:** Community voting endpoints (`POST /api/projects/{id}/vote`) are not accessible to visitors. The user must be authenticated and possess an `EventMember` record with role `participant` for that specific event.
2. **Database-Level Unique Constraints:** Rather than relying solely on application-layer `if/else` checks, the database schema enforces:
   ```python
   __table_args__ = (UniqueConstraint("user_id", "project_id", name="uq_vote_user_project"),)
   ```
   Even in concurrent race-condition scenarios, the database engine enforces idempotency and rejects duplicates.
3. **Per-Participant Ballot Caps:** To prevent a compromised participant account from voting for all projects, `src/routers/voting.py` enforces a strict ceiling of at most 50 community votes per participant per event.

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
This check is evaluated before any database transaction, rejecting self-votes and logging the attempt to the audit log.

### 3.3 Defense Against Peer Judge Snooping & Scoring Collusion
A critical requirement of DOGFOOD 2026 (Rule 9) is backend-enforced role isolation:
- Judges must evaluate projects independently without being influenced by peer scores.
- In `src/routers/judge.py`, when a judge requests scores, the backend queries *only* that judge's assigned user ID:
  ```python
  if requested_judge_id and requested_judge_id != current_user.id:
      raise HTTPException(status_code=403, detail="Forbidden: judges cannot inspect peer scores")
  ```
- Automated testing in `tests/test_role_isolation.py` and `run.py` verifies that `judge_b` querying `judge_a`'s endpoint receives HTTP 403 Forbidden.

### 3.4 Defense Against Bandwagon Voting (Results Hiding & Randomized Ballots)
When vote tallies are visible, voters suffer from **herd behavior**, overwhelmingly voting for existing front-runners. Furthermore, projects appearing first alphabetically receive significantly more views.
HackForge deploys a two-pronged defense:
1. **Sealed Ballot Window:** Vote counts are masked in all JSON endpoints and template renders (`vote_count: null`, `results_hidden: true`) until the organizer explicitly toggles `results_published = True`.
2. **Session-Deterministic Ballot Randomization:**
   ```python
   user_seed = user.id if user else (request.client.host or "seed")
   rng = random.Random(user_seed)
   shuffled = list(projects)
   rng.shuffle(shuffled)
   ```
   This eliminates position bias across the entire gallery while maintaining consistent pagination for an individual reviewer during their session.

### 3.5 Defense Against Comment Abuse & XSS
User-submitted project feedback is sanitized against persistent Cross-Site Scripting (XSS):
- All incoming comment strings are stripped and escaped via `html.escape()`.
- Maximum length is clamped to 2000 characters.
- Anti-spam sliding window restricts users to 10 comments per 5 minutes (`HTTP 429 Too Many Requests`).
- Deletion rights are strictly restricted to the original comment author or event organizers.

### 3.6 Non-Repudiation & Audit Trail
Every security-sensitive state mutation is recorded in `audit_logs`:
- User registration and role assignments
- Project creation, edits, and final submissions
- Rubric score submissions and conflict-of-interest declarations
- Community votes cast, unvoted, and comment deletions

Organizers have full visibility into the timeline, providing verifiable post-mortem accountability in the event of disputed outcomes.
