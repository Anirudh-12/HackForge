# Data Model

Hackforge is built to support multiple hackathons concurrently on the same installation.

## Core Entities

- **Event:** The top-level root. Holds open/close dates.
- **User:** A global account (email/password).
- **EventMember:** A join table assigning a `User` a role (`participant`, `judge`, `organizer`) for a specific `Event`.

## Submissions

- **Team:** Scoped to an `Event`. Has an `invite_token` for seamless onboarding.
- **TeamMember:** Join table for `User` to `Team`.
- **Project:** Scoped to an `Event` and `Team`. Has an `is_draft` flag and tracks submission timestamps.

## Judging

- **Track:** Categories within an `Event`.
- **Score:** Records a judge's assessment of a project (schema to be formalized in T2).
