import json
import pytest
from fastapi.testclient import TestClient


def test_profile_role_tag_and_tabs(client: TestClient, auth_cookies):
    # Organizer profile
    profile_resp = client.get("/profile", cookies=auth_cookies["organizer"])
    assert profile_resp.status_code == 200
    assert "Organizer" in profile_resp.text
    assert "tab-btn-overview" in profile_resp.text
    assert "tab-btn-projects" in profile_resp.text
    assert "tab-btn-activity" in profile_resp.text
    assert "tab-btn-settings" in profile_resp.text


def test_event_creation_wizard_and_schema(client: TestClient, auth_cookies):
    # Organizer visits events page
    resp = client.get("/organizer/events", cookies=auth_cookies["organizer"])
    assert resp.status_code == 200
    assert "createEventModal" in resp.text
    assert "wizard-step-node" in resp.text

    # Post new event using wizard payload
    data = {
        "name": "Global Autonomous Agent Challenge",
        "tagline": "Build state-of-the-art AI agent collectives",
        "description": "Full description of autonomous agents hackathon.",
        "event_starts": "2026-11-01T09:00",
        "event_ends": "2026-11-05T18:00",
        "submissions_open": "2026-11-01T09:00",
        "submissions_close": "2026-11-04T18:00",
        "judging_open": "2026-11-04T18:00",
        "judging_close": "2026-11-05T12:00",
        "results_date": "2026-11-05T17:00",
        "tracks_json": json.dumps([
            {"name": "Multi-Agent Swarms", "prize": "$4,000"},
            {"name": "Autonomous Tool Use", "prize": "$3,000"}
        ]),
        "prizes_json": json.dumps([
            {"title": "Grand Prize", "amount": "$15,000", "desc": "1st place overall"}
        ]),
        "side_quests_json": json.dumps([
            {"title": "Best Latency Bounty", "prize": "$1,000", "desc": "Lowest response time"}
        ])
    }
    post_resp = client.post("/organizer/events", data=data, cookies=auth_cookies["organizer"], follow_redirects=False)
    assert post_resp.status_code == 303
    assert "/organizer/evt_" in post_resp.headers["location"]


def test_explore_page_controls_and_filters(client: TestClient):
    resp = client.get("/explore")
    assert resp.status_code == 200
    assert "filterHackathons" in resp.text
    assert "setEventsView" in resp.text
    assert "btn-events-grid" in resp.text
    assert "btn-events-detailed" in resp.text


def test_gallery_page_controls_and_navigation(client: TestClient):
    resp = client.get("/projects")
    assert resp.status_code == 200
    assert "history.back()" in resp.text
    assert "btn-projects-grid" in resp.text
    assert "btn-projects-list" in resp.text
    assert "setProjectsView" in resp.text
