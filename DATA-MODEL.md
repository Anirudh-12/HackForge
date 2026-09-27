# 🗄️ HackForge — Data Model & Schema Specification

> **Comprehensive schema documentation, relational constraints, and import/export paths.**

---

## 1. Overview

HackForge uses a relational schema managed through SQLAlchemy 2.0. The architecture is explicitly **multi-event**, allowing a single running instance to manage multiple hackathons simultaneously. All core entities (`teams`, `projects`, `tracks`, `rubric_criteria`, `votes`, `scores`) are strictly scoped to an `event_id`.

```mermaid
erDiagram
    User ||--o{ EventMember : "holds"
    Event ||--o{ EventMember : "contains"
    Event ||--o{ Track : "defines"
    Event ||--o{ Team : "hosts"
    Event ||--o{ Project : "showcases"
    Event ||--o{ RubricCriteria : "evaluates via"
    
    Team ||--o{ TeamMember : "comprises"
    User ||--o{ TeamMember : "joins"
    Team ||--o| Project : "owns"
    Track ||--o{ Project : "categorizes"
    
    User ||--o{ JudgeTrack : "assigned"
    Track ||--o{ JudgeTrack : "monitored"
    
    User ||--o{ Score : "grades"
    Project ||--o{ Score : "receives"
    RubricCriteria ||--o{ Score : "evaluates"
    
    User ||--o{ Vote : "casts"
    Project ||--o{ Vote : "accumulates"
    
    User ||--o{ Comment : "authors"
    Project ||--o{ Comment : "receives"
```

---

## 2. Table Specifications

### 2.1 Identity & Access Control

#### `users`
Global user directory across the instance.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `VARCHAR` | Primary Key | e.g., `usr_01`, `org_1`, `jdg_01` |
| `email` | `VARCHAR` | Unique, Not Null, Index | User contact email |
| `name` | `VARCHAR` | Not Null | Display name |
| `password_hash`| `VARCHAR` | Nullable | Bcrypt hash. `NULL` denotes seeded fixture account |
| `bio` | `TEXT` | Nullable | Biography |
| `github_url` | `VARCHAR` | Nullable | GitHub profile link |
| `linkedin_url`| `VARCHAR` | Nullable | LinkedIn profile link |
| `skills` | `VARCHAR` | Nullable | Comma-delimited skill list |

#### `events`
Independent hackathon workspaces.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `VARCHAR` | Primary Key | e.g., `evt_01` |
| `name` | `VARCHAR` | Not Null | Event title |
| `submissions_open` | `DATETIME(TZ)` | Nullable | UTC submission opening |
| `submissions_close`| `DATETIME(TZ)` | Nullable | UTC hard submission deadline |
| `judging_open` | `DATETIME(TZ)` | Nullable | UTC judging start |
| `judging_close` | `DATETIME(TZ)` | Nullable | UTC judging conclusion |
| `results_published`| `BOOLEAN` | Not Null, Default `False` | State flag sealing/unsealing scores & community votes |
| `banner_image_path`| `VARCHAR` | Nullable | Event banner media path |
| `description_markdown`| `TEXT` | Nullable | Overview content |
| `rules_markdown` | `TEXT` | Nullable | Hackathon rules |

#### `event_members`
Scoping of user roles per hackathon.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `INTEGER` | Primary Key, Autoincrement | |
| `event_id` | `VARCHAR` | FK -> `events.id`, Index | Target event |
| `user_id` | `VARCHAR` | FK -> `users.id`, Index | Target user |
| `role` | `VARCHAR` | Not Null | `visitor`, `participant`, `judge`, `organizer`, `admin` |
| `looking_for_team` | `BOOLEAN` | Not Null, Default `False` | Team matchmaking beacon |
| `skills_offered` | `TEXT` | Nullable | Skills offered for matchmaking |

*Unique Constraint:* `(event_id, user_id)` prevents conflicting role assignments in a single event.

---

### 2.2 Teams & Submissions

#### `tracks`
Competition categories within an event.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `VARCHAR` | Primary Key | e.g., `trk_01` |
| `event_id` | `VARCHAR` | FK -> `events.id`, Index | |
| `name` | `VARCHAR` | Not Null | Track title (e.g., "Developer Tools") |
| `prize` | `TEXT` | Nullable | Track prize description |

#### `teams`
Participant project teams.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `VARCHAR` | Primary Key | e.g., `team_01` |
| `event_id` | `VARCHAR` | FK -> `events.id`, Index | |
| `name` | `VARCHAR` | Not Null | Team name |
| `invite_token` | `VARCHAR` | Unique, Nullable | Unguessable join token for onboarding |

#### `team_members`
Membership join table.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `INTEGER` | Primary Key, Autoincrement | |
| `team_id` | `VARCHAR` | FK -> `teams.id`, Index | |
| `user_id` | `VARCHAR` | FK -> `users.id`, Index | |

*Unique Constraint:* `(team_id, user_id)` prevents duplicate member joins.

#### `projects`
Hackathon project submissions.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `VARCHAR` | Primary Key | e.g., `prj_01` |
| `event_id` | `VARCHAR` | FK -> `events.id`, Index | |
| `team_id` | `VARCHAR` | FK -> `teams.id`, Index | One project per team |
| `track_id` | `VARCHAR` | FK -> `tracks.id`, Nullable | |
| `title` | `VARCHAR` | Not Null | Project title |
| `summary` | `TEXT` | Not Null, Default `""` | Markdown project description |
| `repo_url` | `VARCHAR` | Nullable | Source repository URL |
| `demo_url` | `VARCHAR` | Nullable | Working deployment URL |
| `cover_image_path`| `VARCHAR` | Nullable | Preview card image |
| `tech_stack` | `TEXT` | Nullable | Comma-delimited technologies |
| `is_draft` | `BOOLEAN` | Not Null, Default `True` | Draft status flag |
| `submitted_at` | `DATETIME(TZ)` | Nullable | UTC timestamp of submission |
| `is_disqualified`| `BOOLEAN` | Not Null, Default `False` | Disqualification flag |

---

### 2.3 Judging Engine

#### `rubric_criteria`
Configurable scoring criteria with arbitrary weightings.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `VARCHAR` | Primary Key | e.g., `crit_01` |
| `event_id` | `VARCHAR` | FK -> `events.id`, Index | |
| `name` | `VARCHAR` | Not Null | Criterion name (e.g., "Technical Depth") |
| `weight` | `INTEGER` | Not Null | Integer weight (e.g., 40) |

#### `judge_tracks`
Track assignment mapping for judges.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `INTEGER` | Primary Key, Autoincrement | |
| `event_id` | `VARCHAR` | FK -> `events.id`, Index | |
| `judge_id` | `VARCHAR` | FK -> `users.id`, Index | |
| `track_id` | `VARCHAR` | FK -> `tracks.id`, Index | |

*Unique Constraint:* `(event_id, judge_id, track_id)` prevents redundant assignments.

#### `scores`
Judicial evaluation matrix.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `INTEGER` | Primary Key, Autoincrement | |
| `event_id` | `VARCHAR` | FK -> `events.id`, Index | |
| `judge_id` | `VARCHAR` | FK -> `users.id`, Index | |
| `project_id`| `VARCHAR` | FK -> `projects.id`, Index | |
| `criteria_id`| `VARCHAR` | FK -> `rubric_criteria.id` | |
| `value` | `INTEGER` | Not Null | Score value (1–5 scale) |
| `comment` | `TEXT` | Nullable | Qualitative judge notes |
| `conflict_of_interest` | `BOOLEAN` | Not Null, Default `False` | COI flag excluding score from normalization |

*Unique Constraint:* `(judge_id, project_id, criteria_id)` prevents duplicate scores per criterion.

#### `pairwise_comparisons`
Bradley-Terry pairwise judgments.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `INTEGER` | Primary Key, Autoincrement | |
| `event_id` | `VARCHAR` | FK -> `events.id`, Index | |
| `judge_id` | `VARCHAR` | FK -> `users.id`, Index | |
| `winner_project_id`| `VARCHAR` | FK -> `projects.id` | Victor of side-by-side comparison |
| `loser_project_id` | `VARCHAR` | FK -> `projects.id` | Defeated project |
| `criteria_id` | `VARCHAR` | FK -> `rubric_criteria.id`, Nullable | |
| `created_at` | `DATETIME(TZ)` | Not Null, Default `func.now()` | Timestamp of judgment |

---

### 2.4 Community & Anti-Abuse (T3)

#### `votes`
Peer community voting records.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `INTEGER` | Primary Key, Autoincrement | |
| `event_id` | `VARCHAR` | FK -> `events.id`, Index | |
| `user_id` | `VARCHAR` | FK -> `users.id`, Index | Participant voter |
| `project_id`| `VARCHAR` | FK -> `projects.id`, Index | Recipient project |
| `created_at`| `DATETIME(TZ)` | Not Null, Default `func.now()` | Timestamp of vote |

*Unique Constraint:* `(user_id, project_id)` enforces duplicate-detection at database level (max 1 vote per project per voter).

#### `comments`
Public project feedback and discussion.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `INTEGER` | Primary Key, Autoincrement | |
| `event_id` | `VARCHAR` | FK -> `events.id`, Index | |
| `user_id` | `VARCHAR` | FK -> `users.id`, Index | Author |
| `project_id`| `VARCHAR` | FK -> `projects.id`, Index | Target project |
| `content` | `TEXT` | Not Null | Sanitized markdown / text |
| `created_at`| `DATETIME(TZ)` | Not Null, Default `func.now()` | Post timestamp |

#### `audit_logs`
Immutable compliance log.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `INTEGER` | Primary Key, Autoincrement | |
| `event_id` | `VARCHAR` | Nullable, Index | Associated event |
| `actor_id` | `VARCHAR` | Nullable | User ID initiating mutation |
| `message` | `TEXT` | Not Null | Human-readable action description |
| `created_at`| `DATETIME(TZ)` | Not Null, Default `func.now()` | Exact timestamp of event |

---

## 3. Data Import & Export Paths

### 3.1 Ingestion: `fixtures.json`
On boot, `src/seed.py` parses `fixtures.json` and loads all entities transactionally:
1. Event `evt_01` created with dates and rules.
2. Tracks `trk_01` through `trk_08` loaded.
3. Judges `jdg_01` through `jdg_30` inserted with assigned track mappings in `judge_tracks`.
4. Projects `prj_01` through `prj_40` seeded alongside their respective teams and authors.
5. Scores generated across all criteria, establishing the baseline distribution for cross-judge normalization tests.

### 3.2 Egress: CSV & Relational Dumps
1. **Organizer CSV Export (`/api/export.csv`):**  
   Dynamically aggregates project metadata, track, team name, raw average score, Z-score normalized score, pairwise ELO rating, total review count, community vote tally, and individual scores for every participating judge.
2. **Database Backup:**  
   Because SQLite stores all tables in a single file (`data/hackforge.db`), snapshotting, backing up, or migrating the entire platform is as simple as copying that single file.

### 3.3 PostgreSQL Migration Path
The codebase strictly adheres to standard SQLAlchemy 2.0 types without SQLite-proprietary syntax. Switching to PostgreSQL in production requires only configuring the environment variable:
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/hackforge
```
No schema or code modifications are required.
