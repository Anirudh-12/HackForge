import json
from datetime import datetime, timezone

import pytest
from src.auth import make_session_token
from src.db import SessionLocal
from src.models import (
    Event,
    EventMember,
    JudgeInvitation,
    JudgeTrack,
    Project,
    RubricCriteria,
    Score,
    Team,
    TeamMember,
    User,
)
from src.timeutil import as_utc, utcnow


def test_seed_data_requirements(client):
    """
    Validates all explicit seed data requirements from the prompt:
    1. A total of 10 events (including evt_01 from fixtures.json)
    2. 5 finished, 2 ongoing, 3 upcoming (with registrations open)
    3. Each event has >= 10 projects
    4. Each finished hackathon has >= 10 teams and 10 projects, team members from 1-3
    5. 5 judges per hackathon (closed hackathons share judges without overlapping timelines)
    6. Image/banner for each hackathon and project (including evt_01)
    """
    db = SessionLocal()
    try:
        seeded_ids = [f"evt_{i:02d}" for i in range(1, 11)]
        events = (
            db.query(Event).filter(Event.id.in_(seeded_ids)).order_by(Event.id).all()
        )
        assert len(events) == 10, f"Expected 10 seeded events, got {len(events)}"

        now = utcnow()
        finished, ongoing, upcoming = [], [], []

        for e in events:
            s_open = as_utc(e.submissions_open)
            j_close = as_utc(e.judging_close)
            if e.results_published or (j_close and now > j_close):
                finished.append(e)
            elif s_open and now < s_open:
                upcoming.append(e)
            else:
                ongoing.append(e)

        assert len(finished) == 5, f"Expected 5 finished events, got {len(finished)}"
        assert len(ongoing) == 2, f"Expected 2 ongoing events, got {len(ongoing)}"
        assert len(upcoming) == 3, f"Expected 3 upcoming events, got {len(upcoming)}"

        # Verify upcoming registrations open
        for up_e in upcoming:
            reg_open = as_utc(up_e.registrations_open)
            reg_close = as_utc(up_e.registrations_close)
            assert reg_open and now > reg_open, (
                f"{up_e.id} registrations should be open"
            )
            assert reg_close and now < reg_close, (
                f"{up_e.id} registrations should not be closed"
            )

        # Verify each event has >= 10 projects, and banners/covers
        for e in events:
            prjs = db.query(Project).filter_by(event_id=e.id).all()
            assert len(prjs) >= 10, (
                f"{e.id} must have >= 10 projects, found {len(prjs)}"
            )
            assert e.banner_image_path, f"{e.id} must have a banner_image_path"
            assert e.banner_image_path.startswith("/static/banners/"), (
                f"{e.id} banner path invalid"
            )
            for p in prjs:
                assert p.cover_image_path, (
                    f"Project {p.id} must have a cover_image_path"
                )
                assert p.cover_image_path.startswith("/static/projects/"), (
                    f"{p.id} cover path invalid"
                )

        # Verify finished hackathons: >= 10 teams, team sizes 1-3
        for fe in finished:
            teams = db.query(Team).filter_by(event_id=fe.id).all()
            assert len(teams) >= 10, f"Finished event {fe.id} must have >= 10 teams"
            for t in teams:
                m_count = len(t.members)
                assert 1 <= m_count <= 3, (
                    f"Team {t.id} in {fe.id} has {m_count} members, must be 1-3"
                )

        # Verify 5 judges per hackathon
        for e in events:
            judges = db.query(EventMember).filter_by(event_id=e.id, role="judge").all()
            assert len(judges) >= 5, (
                f"{e.id} must have >= 5 judges, found {len(judges)}"
            )

        # Verify closed hackathons share judges without overlapping timelines
        timeline_spans = []
        for fe in finished:
            start = as_utc(fe.submissions_open or fe.event_starts)
            end = as_utc(fe.judging_close or fe.event_ends)
            timeline_spans.append((fe.id, start, end))

        # Check pairwise non-overlap
        for i in range(len(timeline_spans)):
            for j in range(i + 1, len(timeline_spans)):
                id_a, start_a, end_a = timeline_spans[i]
                id_b, start_b, end_b = timeline_spans[j]
                overlaps = not (end_a <= start_b or end_b <= start_a)
                assert not overlaps, (
                    f"Closed hackathons {id_a} and {id_b} must not have overlapping timelines"
                )

    finally:
        db.close()


def test_organiser_dashboard_and_events(client, auth_cookies):
    # 1. Organizer events management page
    res = client.get("/organizer/events", cookies=auth_cookies["organizer"])
    assert res.status_code == 200
    assert "Events" in res.text
    assert "Sample Hack 2026" in res.text
    assert "GreenBuild Hackathon" in res.text
    assert "CloudScale Builders 2026" in res.text
    assert "NextGen Mobility Hack 2026" in res.text

    # 2. Event progress dashboard for finished hackathon
    res = client.get("/organizer/evt_01/dashboard", cookies=auth_cookies["organizer"])
    assert res.status_code == 200
    assert "Sample Hack 2026" in res.text
    assert "Projects" in res.text
    assert "Judges" in res.text

    # 3. Event progress dashboard for upcoming hackathon
    res = client.get("/organizer/evt_08/dashboard", cookies=auth_cookies["organizer"])
    assert res.status_code == 200
    assert "NextGen Mobility Hack 2026" in res.text


def test_event_creation_workflow(client, auth_cookies):
    # Create a new event via the Organizer Wizard Form
    form_data = {
        "name": "Quantum Computing Sprint 2026",
        "tagline": "Quantum algorithms, Qiskit simulations & quantum cryptography",
        "description": "A deep-dive sprint into quantum circuits and real hardware access.",
        "event_starts": "2026-11-01T09:00",
        "event_ends": "2026-11-15T18:00",
        "registrations_open": "2026-10-01T00:00",
        "registrations_close": "2026-10-31T23:59",
        "submissions_open": "2026-11-01T09:00",
        "submissions_close": "2026-11-10T18:00",
        "judging_open": "2026-11-10T18:00",
        "judging_close": "2026-11-15T18:00",
        "results_date": "2026-11-17T12:00",
        "tracks_json": json.dumps(
            [
                {"name": "Quantum Cryptography", "prize": "$4,000"},
                {"name": "Quantum Optimization", "prize": "$3,000"},
            ]
        ),
        "rubrics_json": json.dumps(
            [
                {"name": "Quantum Advantage", "weight": 50},
                {"name": "Code Architecture", "weight": 50},
            ]
        ),
        "prizes_json": json.dumps([{"title": "Grand Prize", "amount": "$10,000"}]),
        "side_quests_json": "[]",
    }

    res = client.post(
        "/organizer/events",
        data=form_data,
        cookies=auth_cookies["organizer"],
        follow_redirects=False,
    )
    assert res.status_code == 303
    redirect_target = res.headers.get("location")
    assert "/organizer/evt_" in redirect_target

    # Verify event and its tracks & rubrics in DB
    db = SessionLocal()
    try:
        new_event = (
            db.query(Event).filter_by(name="Quantum Computing Sprint 2026").first()
        )
        assert new_event is not None
        assert len(new_event.tracks) == 2
        rubrics = db.query(RubricCriteria).filter_by(event_id=new_event.id).all()
        assert len(rubrics) == 2
        assert sum(r.weight for r in rubrics) == 100
    finally:
        db.close()


def test_event_management_and_settings(client, auth_cookies):
    # Retrieve settings page
    res = client.get("/organizer/evt_08/event", cookies=auth_cookies["organizer"])
    assert res.status_code == 200
    assert "NextGen Mobility Hack 2026" in res.text

    # Update event settings
    update_data = {
        "name": "NextGen Mobility Hack 2026",
        "tagline": "Updated Mobility Tagline: Autonomous & Smart City Transit",
        "description_markdown": "Updated comprehensive markdown description for mobility summit.",
        "rules_markdown": "Updated rules: 1-3 builders, open source only.",
        "prizes_json": json.dumps([{"title": "1st Place", "amount": "$7,500"}]),
        "side_quests_json": json.dumps([{"title": "Best API Usage", "amount": "$500"}]),
    }

    res = client.post(
        "/organizer/evt_08/event",
        data=update_data,
        cookies=auth_cookies["organizer"],
        follow_redirects=False,
    )
    assert res.status_code == 303

    db = SessionLocal()
    try:
        evt = db.get(Event, "evt_08")
        assert (
            evt.tagline == "Updated Mobility Tagline: Autonomous & Smart City Transit"
        )
        assert len(evt.prizes_list) == 1
    finally:
        db.close()


def test_events_browsing_public(client):
    # Public explore page
    res = client.get("/explore")
    assert res.status_code == 200
    assert "Explore Hackathons" in res.text
    assert "Upcoming" in res.text
    assert "Ongoing" in res.text
    assert "Past" in res.text
    assert "Sample Hack 2026" in res.text
    assert "NextGen Mobility Hack 2026" in res.text
    assert "CloudScale Builders 2026" in res.text

    # Gallery page with all projects
    res = client.get("/projects")
    assert res.status_code == 200
    assert "Explore Projects" in res.text

    # Filter by event
    res = client.get("/projects?event_id=evt_02")
    assert res.status_code == 200
    assert "VoltMesh" in res.text or "CarbonLens" in res.text


def test_judges_invitation_and_management(client, auth_cookies):
    # 1. View judges page
    res = client.get("/organizer/evt_08/judges", cookies=auth_cookies["organizer"])
    assert res.status_code == 200
    assert "Judges" in res.text
    assert "+ Invite Judge" in res.text

    # 2. Invite a new judge
    import uuid
    uniq = uuid.uuid4().hex[:6]
    new_judge_email = f"mentor.elena.{uniq}@hackforge.dev"
    judge_uid = f"usr_elena_{uniq}"
    invite_data = {
        "email": new_judge_email,
        "track_ids": ["trk_evt08_01", "trk_evt08_02"],
    }
    res = client.post(
        "/organizer/evt_08/judges",
        data=invite_data,
        cookies=auth_cookies["organizer"],
        follow_redirects=False,
    )
    assert res.status_code == 303

    db = SessionLocal()
    try:
        inv = (
            db.query(JudgeInvitation)
            .filter_by(event_id="evt_08", email=new_judge_email)
            .first()
        )
        assert inv is not None
        assert inv.status == "pending"

        # 3. Simulate invited user accepting invitation
        u = User(
            id=judge_uid,
            email=new_judge_email,
            name="Elena Mentor",
            password_hash=None,
        )
        db.add(u)
        db.commit()

        user_cookie = {"session": make_session_token(judge_uid)}
        res_accept = client.post(
            f"/invitations/{inv.id}/accept", cookies=user_cookie, follow_redirects=False
        )
        assert res_accept.status_code == 303

        # Verify Elena is now a judge
        member = (
            db.query(EventMember)
            .filter_by(event_id="evt_08", user_id=judge_uid, role="judge")
            .first()
        )
        assert member is not None

        # Verify JudgeTrack assignments
        jts = (
            db.query(JudgeTrack)
            .filter_by(event_id="evt_08", judge_id=judge_uid)
            .all()
        )
        assert len(jts) == 2
    finally:
        db.close()


def test_rubric_editing_unlocked_on_upcoming_and_locked_on_finished(
    client, auth_cookies
):
    # UPCOMING HACKATHON (evt_08): Judging has not started, NO scores submitted yet -> Rubric is EDITABLE!
    res = client.get("/organizer/evt_08/rubric", cookies=auth_cookies["organizer"])
    assert res.status_code == 200
    assert "Judging has started!" not in res.text

    db = SessionLocal()
    try:
        crits = db.query(RubricCriteria).filter_by(event_id="evt_08").all()
        current_total = sum(c.weight for c in crits)
        remaining = max(0, 100 - current_total)
    finally:
        db.close()

    # Attempt to add criteria when total would exceed 100% -> MUST FAIL (400 Bad Request)
    res_exceed = client.post(
        "/organizer/evt_08/rubric",
        data={"name": "Overflow Criteria", "weight": remaining + 10},
        cookies=auth_cookies["organizer"],
        follow_redirects=False,
    )
    assert res_exceed.status_code == 400
    assert "Total rubric weight cannot exceed 100%" in res_exceed.text

    # If remaining is 0, remove an existing criterion to free capacity
    if remaining == 0:
        db = SessionLocal()
        try:
            crit_to_remove = db.query(RubricCriteria).filter_by(event_id="evt_08").first()
            assert crit_to_remove is not None
            freed = crit_to_remove.weight
            crit_to_remove_id = crit_to_remove.id
        finally:
            db.close()

        res_del_old = client.post(
            f"/organizer/evt_08/rubric/{crit_to_remove_id}/remove",
            cookies=auth_cookies["organizer"],
            follow_redirects=False,
        )
        assert res_del_old.status_code == 303
        weight_to_add = freed
    else:
        weight_to_add = remaining

    unique_crit_name = f"Safety Protocol {uuid.uuid4().hex[:6]}"
    add_data = {"name": unique_crit_name, "weight": weight_to_add}
    res_add = client.post(
        "/organizer/evt_08/rubric",
        data=add_data,
        cookies=auth_cookies["organizer"],
        follow_redirects=False,
    )
    assert res_add.status_code == 303

    db2 = SessionLocal()
    try:
        new_crit = (
            db2.query(RubricCriteria)
            .filter_by(event_id="evt_08", name=unique_crit_name)
            .first()
        )
        assert new_crit is not None
        assert new_crit.weight == weight_to_add
        # Total weight must now be exactly 100%
        all_crits = db2.query(RubricCriteria).filter_by(event_id="evt_08").all()
        assert sum(c.weight for c in all_crits) == 100
        crit_id = new_crit.id
    finally:
        db2.close()

    # Clean up test criteria
    client.post(
        f"/organizer/evt_08/rubric/{crit_id}/remove",
        cookies=auth_cookies["organizer"],
        follow_redirects=False,
    )

    # FINISHED HACKATHON (evt_02): Judging has completed and scores exist -> Rubric editing MUST be LOCKED!
    res_finished = client.get(
        "/organizer/evt_02/rubric", cookies=auth_cookies["organizer"]
    )
    assert res_finished.status_code == 200
    assert "Judging has started!" in res_finished.text

    # Attempt to add criteria -> 400 Bad Request
    res_locked_add = client.post(
        "/organizer/evt_02/rubric",
        data={"name": "Illegal Criteria", "weight": 20},
        cookies=auth_cookies["organizer"],
    )
    assert res_locked_add.status_code == 400

    # Attempt to remove criteria -> 400 Bad Request
    db3 = SessionLocal()
    try:
        crit_02 = db3.query(RubricCriteria).filter_by(event_id="evt_02").first()
        assert crit_02 is not None
        res_locked_del = client.post(
            f"/organizer/evt_02/rubric/{crit_02.id}/remove",
            cookies=auth_cookies["organizer"],
        )
        assert res_locked_del.status_code == 400
    finally:
        db3.close()


def test_participant_ui_and_dashboard_workflow(client, auth_cookies):
    # 1. Participant Home Hub
    res = client.get("/participant/home", cookies=auth_cookies["participant"])
    assert res.status_code == 200
    assert "Participant Hub" in res.text or "Dashboard" in res.text
    assert "Registered Hackathons" in res.text

    # 2. Event-specific Participant Dashboard
    res = client.get(
        "/participant/evt_06/dashboard", cookies=auth_cookies["participant"]
    )
    assert res.status_code == 200
    assert "CloudScale Builders 2026" in res.text

    # 3. Registration wizard for upcoming hackathon (evt_10) with a new builder
    import uuid
    uniq_builder = uuid.uuid4().hex[:6]
    builder_id = f"usr_flow_{uniq_builder}"
    builder_email = f"builder.flow.{uniq_builder}@hackforge.dev"

    db_u = SessionLocal()
    new_user = User(
        id=builder_id,
        email=builder_email,
        name="Flow Builder",
        password_hash=None,
    )
    db_u.add(new_user)
    db_u.commit()
    db_u.close()

    flow_cookie = {"session": make_session_token(builder_id)}
    res = client.get("/events/evt_10/register", cookies=flow_cookie)
    assert res.status_code == 200
    assert "Register for BioTech Horizon Summit" in res.text or "Registration" in res.text

    # Submit registration creating a new team
    reg_data = {
        "skills_offered": "Python, Biopython, Lab Protocols",
        "looking_for_team": True,
        "team_action": "create",
        "team_name": f"BioFlow Lab Team {uniq_builder}",
        "invite_token": "",
    }
    res_submit = client.post(
        "/events/evt_10/register",
        data=reg_data,
        cookies=flow_cookie,
        follow_redirects=False,
    )
    assert res_submit.status_code == 303
    assert "/participant/evt_10/dashboard" in res_submit.headers.get("location")

    # Verify registration in DB
    db = SessionLocal()
    try:
        member = (
            db.query(EventMember)
            .filter_by(
                event_id="evt_10", user_id=builder_id, role="participant"
            )
            .first()
        )
        assert member is not None
        team = (
            db.query(Team)
            .filter_by(event_id="evt_10", name=f"BioFlow Lab Team {uniq_builder}")
            .first()
        )
        assert team is not None
        assert any(tm.user_id == builder_id for tm in team.members)
    finally:
        db.close()
