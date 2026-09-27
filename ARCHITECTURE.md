# Architecture

Hackforge uses a standard server-rendered HTML architecture.

- **Backend:** FastAPI (Python)
- **Database:** SQLite with SQLAlchemy ORM
- **Templates:** Jinja2
- **Styling:** Vanilla CSS (no Tailwind, no utility classes)

## Isolation by Design

To ensure strong security and role isolation, we use route-level segregation:
- `src/routers/public.py` (No Auth)
- `src/routers/participant.py` (Participant Auth)
- `src/routers/organizer.py` (Organizer Auth)
- `src/routers/judge.py` (Judge Auth)

This prevents accidental data leakage (e.g., passing the wrong object to a template) because the endpoints themselves strictly enforce access controls and fetch data directly based on the user's role context.
