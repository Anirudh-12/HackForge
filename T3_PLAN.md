# T3 PUBLIC & COMMUNITY — Implementation Plan
### DOGFOOD 2026 · Target: Complete after T2, within the 72h window

---

## 0. What Evaluators Actually Test for T3

In DOGFOOD 2026, the acceptance checker script (`run.py`) verifies the automated baseline for T1 and T2. For T3, judges inspect code architecture, backend role enforcement, schema correctness, and live platform behavior. A clean, defensible T3 that withstands manual penetration testing, automated scripts, and edge cases will win the scoring category **Judging Integrity (25%)** and **Tier Completion and Correctness (40%)**.

| # | Feature | Mechanism | Evaluation Verification |
|---|---|---|---|
| **T3-1** | Authenticated Peer Voting | Restricted strictly to active event participants | Non-participants (visitors, judges, other events) receive HTTP 403. Participants can vote for 1 project. |
| **T3-2** | Strict Results Hiding | Vote tallies suppressed while voting window is open | `GET /projects` and `GET /api/projects/{id}/vote-status` return `vote_count: null` until results are published. |
| **T3-3** | Randomized Ballot Ordering | Deterministic session/user-seeded shuffle | Projects are ordered unpredictably to eliminate early-submission visibility bias. |
| **T3-4** | Project Comments & Moderation | Server-sanitized discussion threads | Anyone can read, participants/organizers can post, authors & organizers can delete. |
| **T3-5** | Anti-Abuse & Audit Trail | Rate limits, self-voting blocks, audit logs | Cannot vote for own team, max 10 votes/min, all actions recorded in `AuditLog`. |

---

## 1. T3 Requirements Specification

```
T3 PUBLIC
  ① Community voting: authenticated peer-voting mechanism
  ② Project comments with moderation controls
  ③ Results hidden during the voting window
  ④ Randomized project ordering on ballots
  ⑤ Anti-abuse: rate limits, duplicate detection, audit trail
```

---

## 2. Architecture & Design Rationale

### Why Authenticated Peer Voting?
Rule 4 and the "One Command Rule" of DOGFOOD 2026 explicitly state:
> *"docker compose up must start a fully functional, seeded portal on localhost with zero external dependencies. No cloud accounts, no hosted databases, no external APIs, no authentication as a service."*

External email-magic-link voting systems require SMTP relays, transactional email services (SendGrid/Mailgun), or external captcha services that fail completely in an offline environment (`docker compose up` with network off). 

**Our Solution: Authenticated Peer Voting**
1. Community voting is gated to registered participants in the specific hackathon.
2. Each participant receives **one active vote** per hackathon event.
3. Participants can seamlessly change their vote (move vote to another project) or revoke it, but can never hold more than one vote concurrently.
4. Organizers can configure whether community voting is enabled for their event via the Event Settings toggle (`community_voting_enabled`).

### Zero-Leak Results Hiding
A common pitfall in hackathons is returning the vote count in the API payload and simply hiding the number in CSS or JavaScript. A simple `curl` or browser DevTools inspection reveals the winner prematurely.
- **Backend Quarantine**: In `src/routers/voting.py` and `src/routers/public.py`, the backend checks `event.results_published`.
- If `results_published` is `False`, the backend explicitly serializes `vote_count = None` (or omits it entirely) for all participants and visitors. Only organizers and admins can view live vote metrics.

### Ballot Randomization
When browsing a gallery to vote, projects submitted first or listed alphabetically gain an unfair visual advantage (the primacy effect).
- When a user requests the voting ballot (`GET /projects?sort=random`), the platform deterministically shuffles project order using a seed derived from the user's ID or IP.
- This gives each user a consistent ordering during their browsing session while ensuring no project consistently appears at the top across the participant pool.

---

## 3. Database Schema & Data Integrity

### `Vote` Table
Enforces single-vote invariant directly at the storage layer via a composite unique constraint:
```python
class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uq_vote_user_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
```

### `Comment` Table
Threaded feedback on submitted projects:
```python
class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
```

### `AuditLog` Table
Immutable operational ledger recording all high-consequence community interactions:
```python
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
```

---

## 4. API Endpoints Specification

### 1. Vote Status
*   **Method**: `GET /api/projects/{project_id}/vote-status`
*   **Auth**: Optional (visitor returns `can_vote: false, reason: "Login required"`)
*   **Response**:
    ```json
    {
      "voted": true,
      "can_vote": true,
      "already_voted_project_id": "prj_01",
      "reason": null,
      "results_hidden": true,
      "community_voting_enabled": true,
      "vote_count": null
    }
    ```

### 2. Cast or Toggle Vote
*   **Method**: `POST /api/projects/{project_id}/vote`
*   **Auth**: Participant session cookie required
*   **Logic**:
    *   If user has not voted: creates `Vote` record.
    *   If user already voted for this project: removes vote (toggles off).
    *   If user voted for a different project: moves vote atomically to this project.
    *   Appends entry to `AuditLog`.

### 3. Revoke Vote
*   **Method**: `DELETE /api/projects/{project_id}/vote`
*   **Auth**: Participant session cookie required
*   **Logic**: Deletes existing `Vote` record and logs to `AuditLog`.

### 4. List Comments
*   **Method**: `GET /api/projects/{project_id}/comments`
*   **Auth**: Public (no auth required)
*   **Response**: Array of comments with author profile information and `can_delete` flag.

### 5. Post Comment
*   **Method**: `POST /api/projects/{project_id}/comments`
*   **Auth**: Authenticated session required
*   **Validation**: Max 2,000 characters, non-empty, HTML entities escaped via `html.escape()`.

### 6. Delete Comment
*   **Method**: `DELETE /api/projects/{project_id}/comments/{comment_id}`
*   **Auth**: Author or Event Organizer/Admin

---

## 5. Anti-Abuse & Security Defenses

### A. Self-Voting Prevention
A participant cannot vote for a project belonging to their own team:
```python
team = user_team(db, user.id, event.id)
if team and team.id == project.team_id:
    raise HTTPException(
        status_code=403,
        detail="Self-voting is strictly prohibited: you cannot vote for your own team's project"
    )
```

### B. In-Memory Sliding Window Rate Limiter
Prevents rapid automated voting or comment spam:
*   **Vote Actions**: Max 10 requests per 60-second sliding window.
*   **Comments**: Max 10 requests per 300-second sliding window.
*   Exceeding thresholds returns HTTP `429 Too Many Requests`.

### C. XSS Neutralization
All user-submitted comment strings are sanitized using Python's standard `html.escape()` before persistence, preventing stored cross-site scripting attacks.

### D. Audit Logging
Every vote cast, vote moved, vote revoked, comment added, and comment deleted records an `AuditLog` entry detailing:
*   Timestamp (`UTC`)
*   Actor user ID and Name
*   Target project ID and Title
*   Action description

---

## 6. Frontend UX Walkthrough

1. **Gallery Card Vote Button**:
   *   Unauthenticated: Shows "Sign in to vote" tooltip.
   *   Own Project: Button disabled with "Your Project" badge.
   *   Available: Clean interactive pill button with heart icon.
   *   Active Vote: Glowing accent color with "Voted" label.
2. **Project Detail Page Comments**:
   *   Chronological discussion thread with user avatar, name, and relative timestamp.
   *   Instant deletion button for comment authors and hackathon organizers.
3. **Organizer Dashboard**:
   *   Real-time community voting tally viewable exclusively by organizers under the Results tab.
   *   Option to award a distinct "Community Choice" prize.

---

## 7. Automated Test Coverage

The test suite in `tests/test_voting.py` and `tests/test_comments.py` validates all T3 rules:
*   `test_participant_can_cast_vote`: Authenticated participant casts vote successfully.
*   `test_self_voting_is_forbidden`: Returns HTTP 403 when voting for own team project.
*   `test_visitor_cannot_vote`: Unauthenticated requests receive HTTP 401/403.
*   `test_vote_toggling_and_switching`: User can toggle vote off or move vote between projects.
*   `test_results_hidden_in_api`: Vote count remains `null` when `results_published` is false.
*   `test_comment_creation_and_xss_escaping`: Script tags are safely escaped.
*   `test_comment_deletion_permissions`: Authors and organizers can delete comments; strangers cannot.
*   `test_rate_limiting`: Rapid requests trigger HTTP 429.
