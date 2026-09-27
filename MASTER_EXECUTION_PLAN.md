# Master Execution Workflow

This document outlines the strict execution loop we will follow to implement the hackathon judging portal across all phases (T1, T2, T3). It ensures that our UI/UX perfectly matches the mockups in `PLAN.md` and that every feature is tested and version-controlled.

## The Execution Loop

For every single task in our checklists (T1_PLAN.md, T2_PLAN.md, T3_PLAN.md), we will execute the following 4-step loop:

### Step 1: Implement & Align with Design
*   Pick the next unchecked task from the checklist.
*   Cross-reference the task with the UI/UX mockups in `PLAN.md`. Our implementation must strictly follow the visual hierarchy, minimal aesthetic, and sidebar layouts defined there.
*   Write the backend logic (models, routes) and frontend templates (HTML/CSS).

### Step 2: Live Testing (Chrome)
*   **Crucial Step:** Before moving on, we will test the implementation live.
*   We will ensure the local development server is running (`docker compose up` or `uvicorn`).
*   We will use the **Browser Subagent** (or manual Chrome testing) to open the URL, click through the flow, and visually verify that it matches `PLAN.md`.
*   We will also verify backend constraints (e.g., trying to access judge pages as a participant and expecting a 403 error).

### Step 3: Git Commit
*   Once testing confirms the feature works flawlessly, we commit it to the repository immediately.
*   **Commit format:** `git commit -m "feat(T1): [Task Name]"` (e.g., `feat(T1): implement gallery URL without auth`).
*   This ensures we have a clean audit trail and can easily roll back if a later step breaks something.

### Step 4: Check Off Task
*   Update the markdown checklist (e.g., mark `[x] Gallery URL returns HTTP 200 with no auth header` in `T1_PLAN.md`).
*   Move to the next task in the loop.

## Design Philosophy (from `PLAN.md`)
Always keep these principles from `PLAN.md` in mind during Step 1:
*   **Zero Clutter:** No global dashboards. The interface is strictly role-isolated.
*   **High Contrast:** Use distinct states for completed vs. pending tasks.
*   **ASCII/Terminal Aesthetic:** Clean, typography-focused, mono-spaced where appropriate, with clear boundaries.

---
**Ready to begin.** When you are ready, we will start with the very first unchecked task in `T1_PLAN.md`, implement it, test it in the browser, commit it, and move on!
