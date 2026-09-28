# HackForge REST API & Developer Documentation
### DOGFOOD 2026 · T1 through T4 Complete Specification

---

## 1. Overview & Architecture

HackForge is an open-source, self-hostable hackathon submission and judging platform. Built on **FastAPI**, **SQLAlchemy**, and **SQLite**, it provides a high-performance REST API designed with **strict backend-enforced role isolation**, **tamper-evident audit logging**, **real-time HMAC-signed webhooks**, and **verifiable credentials**.

### Core Tenets:
1. **The One-Command Offline Rule**: Fully operable offline with zero external dependencies (`docker compose up` starts a fully functional, seeded portal with 10 multi-state hackathons and official DOGFOOD fixtures).
2. **Backend-Enforced Role Isolation**: Access controls exist in HTTP route handlers and database queries, never merely hidden on the frontend.
3. **Cryptographic Integrity**: Signed judge participation records and verifiable certificates resist tampering and Sybil manipulation.
4. **Developer-First Design**: OpenAPI 3.1 schema auto-generation, interactive Swagger UI (`/docs`), and a custom, role-tailored documentation portal (`/api/docs`).

---

## 2. Authentication & Role Permissions Matrix

HackForge supports two authentication protocols:

### A. Session Cookie (Browser & Acceptance Checker)
Attach the cookie header printed at portal boot or obtained during `/login`:
```http
Cookie: session=org_1.bc826db9afa5c5272756f589e832f78160fce069fea518188662894734bba206
```

### B. Bearer Authorization Header (Programmatic API)
Attach the session token as a bearer token:
```http
Authorization: Bearer org_1.bc826db9afa5c5272756f589e832f78160fce069fea518188662894734bba206
```

### Persona Permission Matrix

| Operation / Scope | Visitor | Participant | Judge | Organizer | Admin |
|---|:---:|:---:|:---:|:---:|:---:|
| Browse Public Gallery (`/projects`) | ✅ | ✅ | ✅ | ✅ | ✅ |
| View Public Project Details (`/projects/{id}`) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Public Record / Cert Verification (`/verify/...`) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Embed Gallery Widget (`/embed/gallery/{id}`) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Register for Event (`/events/{id}/register`) | ❌ | ✅ | ✅ | ✅ | ✅ |
| Submit Project (`/projects/new`, `/participant/{id}/submit`) | ❌ | ✅ | ❌ | ❌ | ✅ |
| Request to Join Team (`/participant/{id}/request_join`)| ❌ | ✅ | ❌ | ❌ | ✅ |
| Accept / Decline Join Requests (`/participant/...`) | ❌ | ✅ (Leader)| ❌ | ❌ | ✅ |
| Cast Community Peer Vote (`/api/projects/{id}/vote`) | ❌ | ✅ | ❌ | ❌ | ✅ |
| Revoke Community Vote (`DELETE /api/projects/{id}/vote`)| ❌ | ✅ | ❌ | ❌ | ✅ |
| Post Project Comment (`/api/projects/{id}/comments`) | ❌ | ✅ | ✅ | ✅ | ✅ |
| Read Own Scores (`/api/judge/scores`) | ❌ | ❌ | ✅ | ✅ | ✅ |
| Read Peer Judge Scores (`/api/judge/scores?judge=...`) | ❌ | ❌ | **403** | ✅ | ✅ |
| Pairwise Evaluation (`/judge/{id}/pairwise`) | ❌ | ❌ | ✅ | ✅ | ✅ |
| Generate Signed Judging Record (`/api/judge/{id}/record`) | ❌ | ❌ | ✅ | ✅ | ✅ |
| View / Download Certificate (`/api/certificates/{id}/download`)| ❌ | ✅ (Eligible)| ✅ | ✅ | ✅ |
| View Live Judging Dashboard (`/organizer/{id}/dashboard`) | ❌ | ❌ | ❌ | ✅ | ✅ |
| Export Results CSV (`/api/export.csv`) | ❌ | ❌ | ❌ | ✅ | ✅ |
| Export Projects CSV (`/api/events/{id}/export/projects.csv`)| ❌ | ❌ | ❌ | ✅ | ✅ |
| Full Event JSON Export (`/api/events/{id}/export/full.json`)| ❌ | ❌ | ❌ | ✅ | ✅ |
| Inspect & Export Audit Logs (`/api/events/{id}/audit`)| ❌ | ❌ | ❌ | ✅ | ✅ |
| Manage Webhooks (`/api/events/{id}/webhooks`) | ❌ | ❌ | ❌ | ✅ | ✅ |
| Bulk Import Projects (`/api/events/{id}/import/projects`) | ❌ | ❌ | ❌ | ✅ | ✅ |
| Bulk Generate Certificates (`/api/events/{id}/certificates/generate`)| ❌ | ❌ | ❌ | ✅ | ✅ |

---

## 3. Endpoints Catalog by Role

### 3.1. Organizer Endpoints

#### 1. Export CSV Leaderboard
*   **Path**: `GET /api/export.csv`
*   **Auth**: Organizer or Admin session
*   **Response**: `text/csv` attachment with columns:
    `project_id, title, track, team, raw_score, normalized_score, reviews_count, [judge_names...]`
*   **cURL Example**:
    ```bash
    curl -X GET "http://localhost:8080/api/export.csv" \
      -H "Cookie: session=<organizer_token>"
    ```

#### 2. Export Projects CSV
*   **Path**: `GET /api/events/{event_id}/export/projects.csv`
*   **Auth**: Organizer or Admin session
*   **Response**: `text/csv` spreadsheet export with metadata, summaries, repositories, demo links, and tech stacks.

#### 3. Full Event Archival JSON Export (T4)
*   **Path**: `GET /api/events/{event_id}/export/full.json`
*   **Auth**: Organizer or Admin session
*   **Response**: `application/json` full database dump including metadata, tracks, criteria, projects, judge scores, comments, community votes, and audit ledger.
*   **cURL Example**:
    ```bash
    curl -X GET "http://localhost:8080/api/events/evt_01/export/full.json" \
      -H "Cookie: session=<organizer_token>"
    ```

#### 4. Bulk Import Projects (T4)
*   **Path**: `POST /api/events/{event_id}/import/projects`
*   **Auth**: Organizer or Admin session
*   **Payload**: JSON array of project definitions:
    ```json
    [
      {
        "title": "Quantum DB",
        "summary": "Lightweight distributed consensus engine",
        "tech_stack": "Rust, SQLite",
        "repo_url": "https://github.com/example/quantum-db"
      }
    ]
    ```
*   **Response**: `{"success": true, "imported_count": 1, "message": "Successfully imported 1 projects"}`

#### 5. Bulk Generate Verifiable Certificates (T4)
*   **Path**: `POST /api/events/{event_id}/certificates/generate`
*   **Auth**: Organizer or Admin session
*   **Response**: Bulk creates `Certificate` records with tamper-evident verification codes (`CERT-PRT-...` and `CERT-JDG-...`). Automatically purges ineligible participant records where no project was submitted.

#### 6. Audit Log Inspection & Export
*   **Path**: `GET /api/events/{event_id}/audit`
*   **Auth**: Organizer or Admin session
*   **Query Parameters**: `q` (free-text search), `category` (`auth`, `projects`, `scoring`, `voting`, `admin`)
*   **Export Endpoints**:
    *   `GET /organizer/{event_id}/audit/export.csv`
    *   `GET /organizer/{event_id}/audit/export.json`

---

### 3.2. Judge Endpoints

#### 1. Inspect Assigned Evaluations
*   **Path**: `GET /api/judge/scores`
*   **Auth**: Assigned Judge session
*   **Response**: Returns the judge's assigned projects, rubric criteria, and current score evaluations.
*   **cURL Example**:
    ```bash
    curl -X GET "http://localhost:8080/api/judge/scores" \
      -H "Cookie: session=<judge_a_token>"
    ```

#### 2. Peer Score Isolation Enforcement (T2 Acceptance Check)
*   **Path**: `GET /api/judge/scores?judge=jdg_01`
*   **Auth**: When requested as a peer judge (e.g. `judge_b`), the backend returns **HTTP 403 Forbidden**.
*   **Rationale**: Prevents score anchoring, collusion, and bias.

#### 3. Pairwise Evaluation & Auto-Sync
*   **Paths**:
    *   `GET /judge/{event_id}/pairwise`: Returns pairwise comparison interface with intelligent min-load pair selection and 50% presentation side randomization.
    *   `POST /judge/{event_id}/pairwise`: Submits head-to-head decision (`winner_id`, `loser_id`), updates Bradley-Terry ELO, and immediately synchronizes to standard rubric `Score` records (`sync_pairwise_scores`).

#### 4. Cryptographically Signed Judge Participation Record (T4)
*   **Path**: `GET /api/judge/{event_id}/record`
*   **Auth**: Assigned Judge session
*   **Response**:
    ```json
    {
      "id": "rec_3a8f10b2c1",
      "event_id": "evt_01",
      "event_name": "Sample Hack 2026",
      "judge_id": "jdg_01",
      "judge_name": "Ada Okonkwo",
      "scores_count": 14,
      "tracks_judged": "Developer tools",
      "issued_at": "2026-09-28T15:30:00Z",
      "signature": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "is_valid": true,
      "verification_url": "http://localhost:8080/verify/record/rec_3a8f10b2c1"
    }
    ```

---

### 3.3. Participant Endpoints

#### 1. Project Submission & Drafts (T1)
*   **Path**: `POST /projects/new` or `POST /participant/{event_id}/submit`
*   **Auth**: Registered participant session belonging to a team
*   **Deadline Enforcement**: If `submissions_close` has passed, returns `HTTP 400 Bad Request` ("Submissions are closed").
*   **Payload (JSON or multipart/form-data)**:
    ```json
    {
      "title": "HackForge",
      "summary": "Self-hostable judging platform",
      "repo_url": "https://github.com/dogfood/hackforge",
      "demo_url": "https://hackforge.demo.app",
      "tech_stack": "Python, FastAPI, Jinja2, SQLite",
      "is_draft": false
    }
    ```

#### 2. Team Join Requests & Invitations
*   `POST /participant/{event_id}/request_join`: Sends join request to team leader.
*   `POST /participant/{event_id}/requests/{request_id}/accept`: Leader accepts request, adding user to team.
*   `POST /participant/{event_id}/requests/{request_id}/decline`: Leader declines request.
*   `POST /participant/{event_id}/requests/{request_id}/cancel`: User cancels pending request.

#### 3. Community Peer Voting (T3)
*   **Path**: `POST /api/projects/{project_id}/vote`
*   **Auth**: Registered participant session
*   **Anti-Abuse Controls**:
    *   **Single Ballot Per Event**: Enforced by database constraint `uq_vote_user_event`.
    *   **Atomic Ballot Transfer**: Voting for another project moves the vote atomically; re-voting toggles/unvotes.
    *   **Self-Voting Prohibition**: Blocked with `HTTP 403 Forbidden`.
    *   **Rate Limiting**: Max 10 requests / 60 seconds (`HTTP 429 Too Many Requests`).
*   **Explicit Revocation**: `DELETE /api/projects/{project_id}/vote`

#### 4. Query Vote Status (T3 Results Isolation)
*   **Path**: `GET /api/projects/{project_id}/vote-status`
*   **Results Hiding**: If `results_published` is `False`, `vote_count` returns `null` to eliminate premature disclosure.

#### 5. Project Comments & Discussion (T3)
*   **Path**: `POST /api/projects/{project_id}/comments`
*   **Auth**: Authenticated session
*   **Payload**: `{"content": "Brilliant architecture and clean code!"}`
*   **Sanitization**: All HTML entities escaped server-side via `html.escape()`. Max 2,000 characters.
*   **Deletion**: `DELETE /api/projects/{project_id}/comments/{comment_id}` restricted to author or event organizers.

---

### 3.4. Public & Embed Endpoints

#### 1. Public Project Gallery
*   **Path**: `GET /projects`
*   **Auth**: None (completely public)
*   **Query Parameters**:
    *   `q`: Free-text search in title/summary
    *   `track`: Track filter
    *   `tech`: Technology stack filter
    *   `sort=random`: Deterministic session-seeded ballot shuffle (T3)

#### 2. Embeddable Gallery Widget (T4)
*   **Path**: `GET /embed/gallery/{event_id}`
*   **Auth**: None (designed for `<iframe>` embedding)
*   **Query Parameters**:
    *   `theme=dark` or `theme=light`
    *   `track=<track_id>`
    *   `limit=<int>`
*   **Embedding Snippet**:
    ```html
    <iframe 
      src="http://localhost:8080/embed/gallery/evt_01?theme=dark" 
      width="100%" 
      height="700" 
      frameborder="0" 
      style="border-radius: 12px; border: 1px solid #334155;">
    </iframe>
    ```

#### 3. Public Verification Routes
*   `GET /verify/record/{record_id}`: Validates cryptographic HMAC signature of judge participation records.
*   `GET /verify/certificate/{code}`: Validates authenticity and awards of attendee credentials.

#### 4. Certificate SVG Download
*   `GET /api/certificates/{cert_id}/download`: Returns a standalone, vector-rendered SVG certificate suitable for export and printing.

---

## 4. Webhooks Specification (T4)

HackForge allows organizers to subscribe external endpoints to real-time hackathon events.

### Registration
*   **Path**: `POST /api/events/{event_id}/webhooks`
*   **Payload**:
    ```json
    {
      "target_url": "https://api.sponsor.com/hackforge/webhook",
      "events": "project.submitted,score.submitted,results.published"
    }
    ```
*   **Response**: Returns subscription ID and shared secret:
    ```json
    {
      "id": "sub_9f81a20c",
      "event_id": "evt_01",
      "target_url": "https://api.sponsor.com/hackforge/webhook",
      "secret": "whsec_728a9b1c3d4e...",
      "events": "project.submitted,score.submitted,results.published",
      "is_active": true,
      "created_at": "2026-09-28T15:35:00Z"
    }
    ```

### Signature Verification Headers
Every webhook HTTP POST delivery includes:
*   `User-Agent`: `HackForge-Webhook-Engine/1.0`
*   `X-HackForge-Event`: The event type (e.g. `project.submitted`)
*   `X-HackForge-Delivery`: Unique delivery UUID
*   `X-HackForge-Signature`: `sha256=<hmac_hex_digest>`

### Verification Implementation Example (Python)
```python
import hmac
import hashlib


def verify_hackforge_webhook(
    secret: str, raw_body: bytes, signature_header: str
) -> bool:
    """Verifies that the webhook payload originated from HackForge."""
    expected_sig = (
        "sha256="
        + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(signature_header, expected_sig)
```

### Verification Implementation Example (Node.js)
```javascript
const crypto = require('crypto');

function verifyWebhook(secret, rawBody, signatureHeader) {
  const hmac = crypto.createHmac('sha256', secret);
  const digest = 'sha256=' + hmac.update(rawBody).digest('hex');
  return crypto.timingSafeEqual(Buffer.from(digest), Buffer.from(signatureHeader));
}
```

---

## 5. Interactive Documentation Hub (`/api/docs`)

HackForge ships with an interactive, role-tailored API documentation portal located at `/api/docs`:
- **Role Tabs**: Switch between Organizer, Judge, Participant, and Public views (`?role=organizer|judge|participant|public`).
- **Contextual cURL Generators**: When logged in, cURL code snippets are dynamically populated with your active session token.
- **Copy-to-Clipboard**: One-click command copying for rapid terminal testing.

---

## 6. Error Code Standards

HackForge adheres to standard RFC HTTP status codes:

| Code | Name | Scenario |
|:---:|---|---|
| **200** | OK | Request succeeded; body returned |
| **201** | Created | Resource created successfully |
| **303** | See Other | Redirect after successful HTML form submission |
| **400** | Bad Request | Malformed payload, closed submission deadline, or duplicate name collision |
| **401** | Unauthorized | Missing or expired authentication token/cookie |
| **403** | Forbidden | Insufficient permissions (judge accessing peer scores, non-participant voting, self-voting) |
| **404** | Not Found | Target event, project, user, certificate, or webhook not found |
| **429** | Too Many Requests | Rate limit exceeded (sliding-window abuse prevention for voting and comments) |
| **500** | Internal Error | Unhandled server error |
