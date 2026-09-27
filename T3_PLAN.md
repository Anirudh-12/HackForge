# T3 Implementation Plan: Public / Community Phase

## Overview
For the T3 phase, we are implementing **Peer Voting** as our community voting mechanism. By restricting voting strictly to authenticated participants, we solve the botting and abuse problem elegantly while maintaining strict compliance with the "no external dependencies" rule. We will also introduce project comments and randomized ballot ordering.

## 1. Database Model Updates
We need two new tables in `src/models.py`:

*   **`Vote` Table:**
    *   `id` (Primary Key)
    *   `participant_id` (Foreign Key -> User)
    *   `project_id` (Foreign Key -> Project)
    *   `created_at` (Timestamp)
    *   *Constraint:* Unique index on `(participant_id, project_id)` to prevent double voting.

*   **`Comment` Table:**
    *   `id` (Primary Key)
    *   `author_id` (Foreign Key -> User)
    *   `project_id` (Foreign Key -> Project)
    *   `content` (Text)
    *   `created_at` (Timestamp)

## 2. Backend Logic (FastAPI)

### Voting Logic
*   **Endpoint:** `POST /api/projects/{project_id}/vote`
*   **Authentication:** Must be logged in as a `participant`.
*   **Validation Rules (Anti-Abuse):**
    1.  **No Self-Voting:** `if current_user.team_id == project.team_id: raise HTTPException(403)`
    2.  **No Double Voting:** Ensure the user hasn't already voted for this project (or limit to X total votes depending on hackathon rules, typically 1 vote per person).
*   **Results Hiding:** The `GET /api/projects` endpoint must **not** return the vote count to participants or the public. Vote counts are strictly isolated and only calculated in the Organizer Dashboard.

### Ballot Randomization
*   **Endpoint:** `GET /api/projects`
*   **Logic:** When rendering the gallery for voting, the projects must be returned in a randomized order so that projects submitted first don't get an unfair visibility advantage. (e.g., using `ORDER BY RANDOM()` in SQL or shuffling the list in Python).

### Comments
*   **Endpoint:** `POST /api/projects/{project_id}/comments` (Authenticated)
*   **Endpoint:** `GET /api/projects/{project_id}/comments` (Public)

## 3. Frontend Updates

*   **Public Gallery / Dashboard:**
    *   Add a "Vote" button on project cards. The button should only appear if the user is logged in as a participant.
    *   Disable the "Vote" button if the project belongs to the current user's team.
    *   Provide clear visual feedback (e.g., button turns green and says "Voted") when a vote is cast.
*   **Project Details Modal/Page:**
    *   Add a comments section where anyone can read comments, and logged-in users can post comments.
*   **Organizer Dashboard Updates:**
    *   Add a "Peer Voting Results" column to the results table so organizers can see the community favorites separate from the Judge scores.

## 4. Testing Strategy
*   Ensure a participant can vote for a peer.
*   Ensure a participant gets a `403 Forbidden` if they try to vote for their own project.
*   Ensure non-logged-in users (or regular public visitors) cannot cast votes.
*   Ensure a project's vote tally is completely hidden from the public gallery JSON responses.
