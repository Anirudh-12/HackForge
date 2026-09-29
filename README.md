# 🏆 HackForge

> **Build the platform that will judge you.**  
> *Run your hackathon without the spreadsheet chaos.*

HackForge is an open-source, self-hostable submission, judging, and community platform for hackathons, built from the ground up for **DOGFOOD 2026**. It replaces fragile spreadsheets, ad-hoc score sheets, and unnormalized judging with backend-enforced role isolation, mathematically rigorous Z-score normalization, Bradley-Terry pairwise comparisons, sealed community voting, and a complete T4 developer platform with webhooks, verifiable certificates, and signed judge participation records.

---

## ⚡ The One-Command Rule: Quickstart

Per the DOGFOOD specification: *"If it does not come up on a laptop with the network off, we cannot adopt it."*

HackForge runs completely offline on any laptop with **zero cloud accounts, zero hosted databases, zero SaaS dependencies, and zero configuration**.

### Option A: Docker (Recommended)

```bash
docker compose up
```

Open [http://localhost:8080](http://localhost:8080) in your browser. The portal automatically initializes the SQLite database, seeds all 40 fixture projects, 30 judges, and 8 tracks from `fixtures.json`, and boots the web server.

### Option B: Local Python Environment

```bash
# 1. Clone repository & create virtual environment
git clone https://github.com/your-username/hackforge.git
cd hackforge
python3 -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# 2. Install dependencies (standard FastAPI + SQLAlchemy + Pillow + bcrypt)
pip install -r requirements.txt

# 3. (Optional) Pre-generate seed banner & project cover images
#    The server does this automatically on first boot, but you can
#    run it standalone to inspect the generated JPEGs beforehand:
python -m src.seed_assets

# 4. Seed fixtures and run portal
python -m uvicorn src.main:app --host 127.0.0.1 --port 8080 --reload
```

### Seed Data Generation

HackForge auto-generates all seed media assets (event banners and project covers) as **JPEG images** on first boot — no manual step required. If you want to regenerate them without restarting the server (e.g. after changing palette data in `seed_assets.py`), run:

```bash
# Regenerate all banner & project cover JPEGs
python -m src.seed_assets
```

Generated files land in:
- `src/static/banners/evt_01.jpg` … `evt_10.jpg` — event banner images
- `src/static/projects/prj_*.jpg` — project cover images

> **Note:** These directories are listed in `.gitignore` and are **never committed** to the repository. They are created fresh on each new deployment, matching the same JPEG format used for real user-uploaded banners.

---

## 🔑 Pre-Seeded Test Credentials

When booted, HackForge seeds realistic accounts from `fixtures.json`. You can log in via `/login` with any password for fixture accounts, or attach the HMAC session cookies generated in `.dogfood.toml`:

| Role | Email / ID | Default Permissions | Dashboard URL |
|---|---|---|---|
| **Organizer** | `org_1@example.org` / `org_1` | Event creation, rubric config, judge assignments, live progress, audit trail, CSV/JSON exports, webhooks, publishing results | `/organizer/evt_01/dashboard` |
| **Judge A** | `tomas.varga@example.org` / `jdg_01` | Assigned to Track 3 (Accessibility); scores projects, pairwise comparisons, signed judge records; peer scores blocked | `/judge/evt_01/dashboard` |
| **Judge B** | `wei.lindqvist@example.org` / `jdg_02` | Assigned to Tracks 2 & 4; scores projects; peer scores blocked | `/judge/evt_01/dashboard` |
| **Participant** | `priya1@example.org` / `prt_1` | Team management, draft/edit project submission, community peer voting, project comments, verifiable certificates | `/participant/home` |
| **Admin** | `admin@example.org` / `adm_1` | Global cross-event oversight, event inspection, and system metrics | `/admin/dashboard` |
| **Visitor** | *(Unauthenticated)* | Public gallery exploration, project detail inspection, reading community comments, verifiable certificate lookups | `/projects` |

---

## 🪜 Tier Completion & Verification

We claim all 4 tiers (**T1 CORE**, **T2 JUDGING**, **T3 PUBLIC**, and **T4 STRETCH**) in [`.dogfood.toml`](.dogfood.toml). Every tier is fully implemented, backend-enforced, and verified across our automated test suite and acceptance checker:

| Tier | Status | Verification Mechanism | Notes |
|---|---|---|---|
| **T1 CORE** | ✅ **Complete & Verified** | `run.py` checks 1–3 (PASS) | Cookie auth, 5 distinct roles, event lifecycle with configurable dates/tracks/prizes, team formation by invite links & join requests, draft/edit submissions until deadline, deadline enforcement that strictly rejects late submissions (HTTP 400), and public search/filter gallery. |
| **T2 JUDGING** | ✅ **Complete & Verified** | `run.py` checks 4–7 (PASS) | Track-based judge assignments, weighted scoring rubric configurable by organizer, backend-enforced peer score isolation (HTTP 403), live organizer progress dashboard, Z-score cross-judge normalization with mathematical proof, and CSV export. |
| **T3 PUBLIC** | ✅ **Complete & Verified** | `pytest tests/test_voting.py tests/test_comments.py tests/test_audit_log.py` | Authenticated peer community voting, anti-self-voting enforcement (HTTP 403), results hidden during active voting window, randomized ballot ordering to kill position bias, rate-limited threaded project comments, and tamper-evident audit logging with CSV/JSON exports. |
| **T4 STRETCH** | ✅ **Complete & Verified** | `pytest tests/test_t4_features.py tests/test_api_endpoints.py`, `/api/docs`, OpenAPI 3.1 | REST API with OpenAPI 3.1 specification and interactive documentation hub (`/api/docs`), real-time webhook engine with HMAC-SHA256 signatures, verifiable participant and judge certificate generation (SVG downloads & public verification portal), cryptographically signed judge participation records, embeddable gallery widget with dark/light mode, and bulk import/export (full JSON dump, projects CSV, bulk project ingest). |

---

### Official Acceptance Checker

Run the official DOGFOOD acceptance suite against the running portal:

```bash
python run.py .dogfood.toml
```

Output:
```
DOGFOOD 2026 acceptance report
portal: http://localhost:8080
claimed: T1 T2 T3 T4
fixtures: fixtures.json

T1  gallery is public ................. PASS
T1  project from fixtures shown ....... PASS
T1  closed event refuses submissions .. PASS
T2  judge sees own scores ............. PASS
T2  judge cannot see peer scores ...... PASS
T2  participant blocked ............... PASS
T2  csv export works .................. PASS

claimed T1 T2 T3 T4, verified T1 T2
note: claimed but not verified: T3 T4
```

> **Note on `run.py` Verification:** The official DOGFOOD acceptance script (`run.py`), as published in Appendix A of the DOGFOOD specification, executes automated HTTP checks exclusively for T1 and T2 against the running portal. All 7 checks pass cleanly. T3 and T4 are claimed in `.dogfood.toml` and verified via our **74 automated Pytest tests**, our **interactive developer hub (`/api/docs`)**, and our **tamper-evident public verification routes (`/verify/...`)**.

---

### Comprehensive Pytest Suite (74 Automated Tests)

Run our complete test suite covering all 4 tiers, security isolation, anti-abuse controls, pairwise scoring, and every API endpoint:

```bash
pytest -v
```

```
============================= test session starts =============================
platform win32 -- Python 3.12.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\aksha\OneDrive\Documents\Hackathon Site\HackForge
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1
collected 74 items

tests/test_api_endpoints.py::test_api_core_and_public_endpoints PASSED    [  1%]
tests/test_api_endpoints.py::test_api_judge_and_role_isolation PASSED     [  2%]
tests/test_api_endpoints.py::test_api_public_community_and_audit PASSED   [  4%]
tests/test_api_endpoints.py::test_api_t4_stretch_suite PASSED             [  5%]
tests/test_api_endpoints.py::test_api_participant_and_admin_views PASSED  [  6%]
tests/test_audit_log.py::test_audit_log_redirect PASSED                   [  8%]
tests/test_audit_log.py::test_audit_log_page_renders_for_organizer PASSED [  9%]
tests/test_audit_log.py::test_audit_log_role_isolation PASSED            [ 10%]
tests/test_audit_log.py::test_audit_log_category_and_search_filters PASSED [ 12%]
tests/test_audit_log.py::test_audit_log_exports PASSED                   [ 13%]
tests/test_audit_log.py::test_audit_log_rest_api PASSED                  [ 14%]
tests/test_audit_log.py::test_judge_scoring_creates_audit_log PASSED     [ 16%]
tests/test_auth_registration.py::test_register_page_has_already_a_user_signin_button PASSED [ 17%]
tests/test_auth_registration.py::test_register_page_preserves_next_param PASSED [ 18%]
tests/test_comments.py::test_list_comments_public PASSED                 [ 20%]
tests/test_comments.py::test_post_and_delete_comment PASSED              [ 21%]
tests/test_comments.py::test_empty_comment_rejected PASSED               [ 22%]
tests/test_comments.py::test_visitor_cannot_post_comment PASSED          [ 24%]
tests/test_csv_export.py::test_csv_export_as_organizer PASSED            [ 25%]
tests/test_csv_export.py::test_csv_export_blocked_for_participant PASSED [ 27%]
tests/test_csv_export.py::test_csv_export_blocked_for_visitor PASSED     [ 28%]
tests/test_deadline.py::test_closed_event_refuses_submissions PASSED     [ 29%]
tests/test_deduplication.py::test_prevent_duplicate_event_creation PASSED [ 31%]
tests/test_deduplication.py::test_prevent_duplicate_track_creation PASSED [ 32%]
tests/test_deduplication.py::test_prevent_duplicate_rubric_creation PASSED [ 33%]
tests/test_deduplication.py::test_prevent_duplicate_team_name_in_event PASSED [ 35%]
tests/test_deduplication.py::test_pairwise_comparison_deduplication PASSED [ 36%]
tests/test_event_settings_wizard.py::test_event_creation_with_registration_dates_and_rubrics PASSED [ 37%]
tests/test_event_settings_wizard.py::test_trackless_open_innovation_event_support PASSED [ 39%]
tests/test_event_settings_wizard.py::test_event_settings_get_and_post_full_parity PASSED [ 40%]
tests/test_event_settings_wizard.py::test_organizer_dashboard_components PASSED [ 41%]
tests/test_full_workflow.py::test_seed_data_requirements PASSED          [ 43%]
tests/test_full_workflow.py::test_organiser_dashboard_and_events PASSED  [ 44%]
tests/test_full_workflow.py::test_event_creation_workflow PASSED         [ 45%]
tests/test_full_workflow.py::test_event_management_and_settings PASSED   [ 47%]
tests/test_full_workflow.py::test_events_browsing_public PASSED          [ 48%]
tests/test_full_workflow.py::test_judges_invitation_and_management PASSED [ 50%]
tests/test_full_workflow.py::test_rubric_editing_unlocked_on_upcoming_and_locked_on_finished PASSED [ 51%]
tests/test_full_workflow.py::test_participant_ui_and_dashboard_workflow PASSED [ 52%]
tests/test_gallery.py::test_gallery_is_public PASSED                     [ 54%]
tests/test_gallery.py::test_fixture_projects_appear_in_gallery PASSED    [ 55%]
tests/test_gallery.py::test_gallery_search_filter PASSED                 [ 56%]
tests/test_gallery.py::test_gallery_randomized_ballot_ordering PASSED    [ 58%]
tests/test_gallery.py::test_project_detail_view PASSED                   [ 59%]
tests/test_gallery.py::test_gallery_visitor_sidebar PASSED               [ 60%]
tests/test_pairwise_scoring.py::test_pairwise_voting_updates_scores PASSED [ 62%]
tests/test_punchlist_features.py::test_profile_role_tag_and_tabs PASSED  [ 63%]
tests/test_punchlist_features.py::test_event_creation_wizard_and_schema PASSED [ 64%]
tests/test_punchlist_features.py::test_explore_page_controls_and_filters PASSED [ 66%]
tests/test_punchlist_features.py::test_gallery_page_controls_and_navigation PASSED [ 67%]
tests/test_registrations_and_explore.py::test_participant_registrations_unauthenticated PASSED [ 68%]
tests/test_registrations_and_explore.py::test_registrations_redirect PASSED [ 70%]
tests/test_registrations_and_explore.py::test_participant_registrations_page_authenticated PASSED [ 71%]
tests/test_registrations_and_explore.py::test_sidebar_and_dashboard_links PASSED [ 72%]
tests/test_registrations_and_explore.py::test_explore_hackathons_dropdowns_and_values PASSED [ 74%]
tests/test_registrations_and_explore.py::test_registrations_sidebar_collapsible_items_and_placement PASSED [ 75%]
tests/test_registrations_and_explore.py::test_cannot_register_for_completed_hackathon PASSED [ 77%]
tests/test_role_isolation.py::test_judge_sees_own_scores PASSED          [ 78%]
tests/test_role_isolation.py::test_judge_cannot_see_peer_scores PASSED   [ 79%]
tests/test_role_isolation.py::test_participant_blocked_from_judge_scores PASSED [ 81%]
tests/test_role_isolation.py::test_visitor_blocked_from_judge_scores PASSED [ 82%]
tests/test_t4_features.py::test_openapi_schema_and_docs_portal PASSED    [ 83%]
tests/test_t4_features.py::test_webhook_crud_and_permissions PASSED      [ 85%]
tests/test_t4_features.py::test_certificates_generation_and_public_verification PASSED [ 86%]
tests/test_t4_features.py::test_signed_judge_participation_records PASSED [ 87%]
tests/test_t4_features.py::test_embeddable_gallery_widget PASSED         [ 89%]
tests/test_t4_features.py::test_bulk_export_and_import PASSED            [ 90%]
tests/test_t4_features.py::test_participation_certificate_only_for_submitted_projects PASSED [ 91%]
tests/test_team_join_requests.py::test_request_to_join_sends_to_leader_and_provides_visual_feedback PASSED [ 93%]
tests/test_team_join_requests.py::test_cannot_join_team_for_finished_hackathon PASSED [ 94%]
tests/test_voting.py::test_participant_can_vote_and_unvote PASSED        [ 95%]
tests/test_voting.py::test_self_voting_is_forbidden PASSED               [ 97%]
tests/test_voting.py::test_visitor_cannot_vote PASSED                    [ 98%]
tests/test_voting.py::test_results_hidden_during_voting_window PASSED    [100%]

====================== 74 passed in 4.75s =======================
```

#### Test Suite Breakdown

| Module | Tests | Focus Area |
|---|:---:|---|
| [`tests/test_api_endpoints.py`](tests/test_api_endpoints.py) | 5 | Comprehensive API regression suite validating all T1–T4 endpoints across public, judge, participant, and organizer roles. |
| [`tests/test_t4_features.py`](tests/test_t4_features.py) | 7 | OpenAPI schema, Webhooks CRUD/ping, verifiable certificates, signed judge records, embeddable widget, bulk import/export, submission prerequisites. |
| [`tests/test_audit_log.py`](tests/test_audit_log.py) | 7 | Audit ledger entries for scoring, votes, and event changes; search/filtering, CSV and JSON exports, and REST API. |
| [`tests/test_full_workflow.py`](tests/test_full_workflow.py) | 8 | End-to-end event lifecycle: organizer setup, judge invitation, rubric editing/locking, participant submission, and publishing. |
| [`tests/test_registrations_and_explore.py`](tests/test_registrations_and_explore.py) | 7 | Multi-hackathon exploration, state-based registration gating, participant registration dashboard, and sidebar context. |
| [`tests/test_gallery.py`](tests/test_gallery.py) | 6 | Public gallery accessibility, search filters, track selection, randomized ballot ordering, project detail view. |
| [`tests/test_deduplication.py`](tests/test_deduplication.py) | 5 | Prevention of duplicate events, tracks, rubrics, team names, and pairwise scores. |
| [`tests/test_event_settings_wizard.py`](tests/test_event_settings_wizard.py) | 4 | Multi-step event creation wizard, registration dates, trackless open-innovation events, and full GET/POST parity. |
| [`tests/test_voting.py`](tests/test_voting.py) | 4 | Authenticated peer community voting, self-voting anti-abuse (403), results suppression during active voting. |
| [`tests/test_comments.py`](tests/test_comments.py) | 4 | Public comment listing, comment creation, deletion, empty comment rejection, visitor restriction. |
| [`tests/test_role_isolation.py`](tests/test_role_isolation.py) | 4 | Backend-enforced role isolation: judge sees own scores, peer scores blocked (403), participant/visitor blocked. |
| [`tests/test_punchlist_features.py`](tests/test_punchlist_features.py) | 4 | Profile role tags and tabs, event wizard schema, explore controls, gallery navigation. |
| [`tests/test_csv_export.py`](tests/test_csv_export.py) | 3 | Organizer CSV export correctness, participant access blocked (403), visitor access blocked (401). |
| [`tests/test_team_join_requests.py`](tests/test_team_join_requests.py) | 2 | Team join request workflow, leader accept/decline, visual feedback, completed event guard. |
| [`tests/test_auth_registration.py`](tests/test_auth_registration.py) | 2 | Registration page sign-in navigation, preservation of `?next=` destination URL. |
| [`tests/test_pairwise_scoring.py`](tests/test_pairwise_scoring.py) | 1 | Bradley-Terry head-to-head evaluation, ELO rating updates, automatic synchronization to rubric scores. |
| [`tests/test_deadline.py`](tests/test_deadline.py) | 1 | Strict deadline enforcement rejecting submissions after `submissions_close`. |

---

## 🚀 T4 Stretch Architecture & API Verification

HackForge provides a production-ready developer platform designed for interoperability and verifiable credentials:

### 1. Developer Documentation & OpenAPI 3.1
- **OpenAPI Schema**: Auto-generated specification available at `/openapi.json`.
- **Interactive Documentation Hub**: Custom developer portal at `/api/docs` with role-based tabs (Organizer, Judge, Participant, Public) and dynamically populated cURL snippets.
- **Interactive API Explorers**: Standard Swagger UI at `/docs` and ReDoc at `/redoc`.
- **Full Specification**: See [`API-DOCS.md`](API-DOCS.md) for the complete endpoint catalog, request payloads, and security schemes.

### 2. Real-Time Webhooks Engine
- **Subscription Management**: Full CRUD at `POST /api/events/{event_id}/webhooks` and `GET /api/events/{event_id}/webhooks`.
- **Cryptographic Signatures**: Every outbound HTTP POST includes `X-HackForge-Signature: sha256=<hmac>` using a provisioned shared secret (`whsec_...`).
- **Ping Testing**: Immediate delivery validation via `POST /api/events/{event_id}/webhooks/{sub_id}/test`.

### 3. Verifiable Certificate Generation
- **Automated Issuance**: Bulk generate verifiable credentials at `POST /api/events/{event_id}/certificates/generate`.
- **Strict Eligibility Guard**: Participants only receive certificates if their team successfully submitted a non-draft project.
- **Standalone SVG Export**: Download vector-rendered, printable SVG certificates at `GET /api/certificates/{cert_id}/download`.
- **Public Verification**: Anyone can verify certificate authenticity and award details at `GET /verify/certificate/{verification_code}`.

### 4. Cryptographically Signed Judge Participation Records
- **Signed Records**: Judges can request an immutable record of their judging service via `GET /api/judge/{event_id}/record`.
- **Anti-Tamper HMAC**: Cryptographic signature covers judge ID, event ID, number of evaluated projects, and issuance timestamp. Tampered score counts or IDs fail verification immediately.
- **Public Verification Page**: Publicly accessible proof of judging credentials at `GET /verify/record/{record_id}`.

### 5. Embeddable Gallery Widget
- **Zero-Dependency Iframe Widget**: Embed the project showcase anywhere using `GET /embed/gallery/{event_id}`.
- **Configurable Themes & Filters**: Supports `?theme=dark` or `?theme=light`, track filtering (`?track=trk_01`), and real-time client-side search.

### 6. Bulk Import & Export
- **Full Archival JSON Dump**: Complete snapshot of all event metadata, projects, scores, comments, votes, and audit logs at `GET /api/events/{event_id}/export/full.json`.
- **Projects Spreadsheet**: Export all submissions as CSV at `GET /api/events/{event_id}/export/projects.csv`.
- **Leaderboard CSV Export**: Full judging scores and normalized rankings at `GET /api/export.csv`.
- **Bulk Project Ingest**: Bulk import projects via JSON payload at `POST /api/events/{event_id}/import/projects`.

### Testing All API Endpoints

To verify all 61+ REST API endpoints and role permissions:

```bash
# Run the API regression test suite
pytest tests/test_api_endpoints.py -v

# Or run the standalone endpoint verification script
python scratch/test_all_endpoints.py
```

---

## 🌟 Bonus Challenges

HackForge completes all four bonus challenges outlined in the DOGFOOD specification:

1. **Normalization Proof (Hard)**: Complete mathematical formulation and edge-case proofs for per-track Z-score standardization ($\mu=50, \sigma=15$) documented rigorously in [`JUDGING.md`](JUDGING.md).
2. **Pairwise Mode (Hard)**: Bradley-Terry log-odds estimator using dynamic ELO calculations ($K=32$, baseline $1500$) for side-by-side comparative judging in `src/queries.py` and synchronized to standard rubric scores via `/judge/{event_id}/pairwise`.
3. **Threat Model (Medium)**: Comprehensive analysis of attack surfaces including Sybil identities, ballot stuffing, self-voting collusion, score snooping, and timing attacks in [`THREAT-MODEL.md`](THREAT-MODEL.md).
4. **API First (Medium)**: Fully documented REST API with OpenAPI 3.1 specification, Swagger UI (`/docs`), ReDoc (`/redoc`), interactive developer hub (`/api/docs`), and full developer reference in [`API-DOCS.md`](API-DOCS.md).

---

## 🏛️ System Architecture

- **Backend:** Python 3.11+ / FastAPI for fast, type-safe request routing, dependency injection, and automatic OpenAPI schema generation.
- **Data Persistence:** SQLAlchemy 2.0 ORM with SQLite for portability, designed for zero-effort migration to PostgreSQL via `DATABASE_URL`.
- **Frontend / Rendering:** Server-rendered Jinja2 templates styled with modern, semantic Vanilla CSS. No heavy client build tools or external CDN dependencies.
- **Authentication:** Stateless, cryptographically signed HMAC-SHA256 session cookies (`user_id.signature`) and Bearer token headers.
- **Security:** Strict backend route-level isolation (`public`, `participant`, `judge`, `organizer`, `admin`). Peer judge score inspection is rejected at the API layer with HTTP 403 Forbidden.

For the complete architectural design and data flow, see [`ARCHITECTURE.md`](ARCHITECTURE.md).  
For the database schema, foreign keys, and indexes, see [`DATA-MODEL.md`](DATA-MODEL.md).  
For the complete API documentation and cURL examples, see [`API-DOCS.md`](API-DOCS.md).

---

## ⚖️ Honest Limitations

We believe in engineering honesty over marketing inflation:

1. **No External SMTP Relay:** HackForge does not require a SendGrid or AWS SES account. Team invitations and judge invites use unguessable cryptographic tokens and in-portal notification feeds. This guarantees it runs 100% offline.
2. **Single-Node In-Memory Rate Limiting:** Anti-abuse rate limiters for voting and comments use thread-safe in-memory sliding windows. In a multi-worker cluster, an external store like Redis would be configured.

---

## 📄 License

HackForge is released under the **MIT License**. You are free to fork, self-host, and run your own hackathons with zero restrictions. See [`LICENSE`](LICENSE).
