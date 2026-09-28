import json
import pytest
from fastapi.testclient import TestClient
from src.models import Event, Track, RubricCriteria, Project
from src.db import SessionLocal


def test_event_creation_with_registration_dates_and_rubrics(client: TestClient, auth_cookies):
    # Test wizard event creation with separate registration timeline, 1 side quest with dates, and 100% rubrics
    data = {
        "name": "Frontier AI Sprint 2026",
        "tagline": "Build next-generation autonomous models",
        "description": "Full description of frontier hackathon.",
        "event_starts": "2026-12-01T09:00",
        "event_ends": "2026-12-05T18:00",
        "registrations_open": "2026-11-15T00:00",
        "registrations_close": "2026-11-30T23:59",
        "submissions_open": "2026-12-01T09:00",
        "submissions_close": "2026-12-04T18:00",
        "judging_open": "2026-12-04T18:00",
        "judging_close": "2026-12-05T12:00",
        "results_date": "2026-12-05T17:00",
        "tracks_json": json.dumps([
            {"name": "Agentic Reasoning", "prize": "$5,000"}
        ]),
        "prizes_json": json.dumps([
            {"title": "1st Place - Grand Champion", "amount": "$10,000", "desc": "Cash + compute"}
        ]),
        "side_quests_json": json.dumps([
            {
                "title": "Best UI Polish Bounty",
                "prize": "$500",
                "desc": "Delightful UX",
                "starts_at": "2026-12-01T09:00",
                "ends_at": "2026-12-03T18:00"
            }
        ]),
        "rubrics_json": json.dumps([
            {"name": "Innovation & Originality", "weight": 30},
            {"name": "Technical Execution", "weight": 30},
            {"name": "Impact", "weight": 20},
            {"name": "Polish", "weight": 20}
        ])
    }

    resp = client.post("/organizer/events", data=data, cookies=auth_cookies["organizer"], follow_redirects=False)
    assert resp.status_code == 303
    evt_id = resp.headers["location"].split("/")[-2]

    db = SessionLocal()
    try:
        event = db.get(Event, evt_id)
        assert event is not None
        assert event.name == "Frontier AI Sprint 2026"
        assert event.tagline == "Build next-generation autonomous models"
        assert event.registrations_open is not None
        assert event.registrations_close is not None
        assert event.submissions_open is not None

        # Verify side quests with timeline
        quests = event.side_quests_list
        assert len(quests) == 1
        assert quests[0]["title"] == "Best UI Polish Bounty"
        assert quests[0]["starts_at"] == "2026-12-01T09:00"

        # Verify rubrics
        criteria = db.query(RubricCriteria).filter_by(event_id=evt_id).all()
        assert len(criteria) == 4
        assert sum(c.weight for c in criteria) == 100
        assert any(c.name == "Innovation & Originality" and c.weight == 30 for c in criteria)
    finally:
        db.close()


def test_trackless_open_innovation_event_support(client: TestClient, auth_cookies):
    # Hackathons can have NO tracks (open innovation)
    data = {
        "name": "Open Innovation Mega Hack",
        "tagline": "Open innovation with no track divisions",
        "description": "General competition open to all themes.",
        "tracks_json": "",  # Empty tracks
        "prizes_json": json.dumps([{"title": "Open Innovation Grand Prize", "amount": "$5,000", "desc": "Overall"}]),
        "side_quests_json": "[]",
        "rubrics_json": json.dumps([{"name": "General Excellence", "weight": 100}])
    }
    resp = client.post("/organizer/events", data=data, cookies=auth_cookies["organizer"], follow_redirects=False)
    assert resp.status_code == 303
    evt_id = resp.headers["location"].split("/")[-2]

    db = SessionLocal()
    try:
        tracks = db.query(Track).filter_by(event_id=evt_id).all()
        from src.queries import upsert_membership
        upsert_membership(db, evt_id, "jdg_01", "judge")
        db.commit()

        # Judge dashboard should load without crashing even if 0 tracks
        judge_resp = client.get(f"/judge/{evt_id}/dashboard", cookies=auth_cookies["judge_a"])
        assert judge_resp.status_code == 200
    finally:
        db.close()


def test_event_settings_get_and_post_full_parity(client: TestClient, auth_cookies):
    # Create an initial event
    data = {
        "name": "Settings Test Hackathon",
        "tagline": "Initial Tagline",
        "tracks_json": json.dumps([{"name": "Initial Track", "prize": "$1,000"}]),
        "prizes_json": json.dumps([{"title": "1st Prize", "amount": "$2,000", "desc": "Cash"}]),
        "side_quests_json": json.dumps([{"title": "Initial Quest", "prize": "$200", "desc": "Criteria"}]),
        "rubrics_json": json.dumps([
            {"name": "Core Tech", "weight": 50},
            {"name": "Design", "weight": 50}
        ])
    }
    create_resp = client.post("/organizer/events", data=data, cookies=auth_cookies["organizer"], follow_redirects=False)
    evt_id = create_resp.headers["location"].split("/")[-2]

    # Test GET settings page
    settings_page_resp = client.get(f"/organizer/{evt_id}/event", cookies=auth_cookies["organizer"])
    assert settings_page_resp.status_code == 200
    assert "Hackathon Settings" in settings_page_resp.text
    assert "Identity &amp; Branding" in settings_page_resp.text or "Identity & Branding" in settings_page_resp.text
    assert "Schedules &amp; Timelines" in settings_page_resp.text or "Schedules & Timelines" in settings_page_resp.text
    assert "Prizes &amp; Tracks" in settings_page_resp.text or "Prizes & Tracks" in settings_page_resp.text
    assert "Scoring Rubrics" in settings_page_resp.text
    assert "Remove All Track Prizes" in settings_page_resp.text

    # Test POST save changes (Updating all fields with parity)
    update_data = {
        "name": "Settings Test Hackathon - Updated",
        "tagline": "Updated Glorious Tagline",
        "event_starts": "2026-11-10T10:00",
        "event_ends": "2026-11-15T18:00",
        "registrations_open": "2026-11-01T00:00",
        "registrations_close": "2026-11-09T23:59",
        "submissions_open": "2026-11-10T10:00",
        "submissions_close": "2026-11-14T23:59",
        "judging_open": "2026-11-15T00:00",
        "judging_close": "2026-11-15T15:00",
        "results_date": "2026-11-15T18:00",
        "description_markdown": "Brand new markdown description.",
        "rules_markdown": "Brand new rules.",
        "prizes_json": json.dumps([
            {"title": "Grand Gold Champion", "amount": "$8,000", "desc": "1st place overall"},
            {"title": "Silver Runner-Up", "amount": "$3,000", "desc": "2nd place overall"}
        ]),
        "tracks_json": json.dumps([
            {"name": "AI Track (No Prize)", "prize": ""},
            {"name": "DevTools Track (No Prize)", "prize": ""}
        ]),
        "side_quests_json": json.dumps([
            {
                "title": "Speedrun Bounty",
                "prize": "$750",
                "desc": "First project to submit",
                "starts_at": "2026-11-10T10:00",
                "ends_at": "2026-11-11T10:00"
            }
        ]),
        "rubrics_json": json.dumps([
            {"name": "Technical Depth", "weight": 40},
            {"name": "Usability", "weight": 30},
            {"name": "Innovation", "weight": 30}
        ])
    }

    save_resp = client.post(f"/organizer/{evt_id}/event", data=update_data, cookies=auth_cookies["organizer"], follow_redirects=False)
    assert save_resp.status_code == 303

    db = SessionLocal()
    try:
        updated_evt = db.get(Event, evt_id)
        assert updated_evt.name == "Settings Test Hackathon - Updated"
        assert updated_evt.tagline == "Updated Glorious Tagline"
        assert updated_evt.registrations_open is not None
        assert updated_evt.prizes_list[0]["title"] == "Grand Gold Champion"
        assert len(updated_evt.prizes_list) == 2

        # Check track prizes were cleared/removed
        tracks = db.query(Track).filter_by(event_id=evt_id).all()
        assert len(tracks) == 2
        assert all(t.prize is None or t.prize == "" for t in tracks)

        # Check side quest timeline
        quests = updated_evt.side_quests_list
        assert len(quests) == 1
        assert quests[0]["title"] == "Speedrun Bounty"
        assert quests[0]["starts_at"] == "2026-11-10T10:00"

        # Check rubrics updated to 40 + 30 + 30 = 100
        criteria = db.query(RubricCriteria).filter_by(event_id=evt_id).all()
        assert len(criteria) == 3
        assert sum(c.weight for c in criteria) == 100
    finally:
        db.close()


def test_organizer_dashboard_components(client: TestClient, auth_cookies):
    # Check dashboard topbar dropdown structure and progress bar fill
    resp = client.get("/organizer/events", cookies=auth_cookies["organizer"])
    assert resp.status_code == 200
    # Topbar dropdown has event-dropdown-list with scrollable container and Create New button
    assert "eventDropdown" in resp.text
    assert "event-dropdown-list" in resp.text
    assert "Create New Hackathon" in resp.text
