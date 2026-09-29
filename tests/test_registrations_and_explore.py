import pytest
from fastapi.testclient import TestClient


def test_participant_registrations_unauthenticated(client: TestClient):
    response = client.get("/participant/registrations", follow_redirects=False)
    assert response.status_code == 303
    assert "/login" in response.headers["location"]


def test_registrations_redirect(client: TestClient):
    response = client.get("/registrations", follow_redirects=False)
    assert response.status_code == 303
    assert "/participant/registrations" in response.headers["location"]


def test_participant_registrations_page_authenticated(client: TestClient, auth_cookies):
    cookies = auth_cookies["participant"]
    response = client.get("/participant/registrations", cookies=cookies)
    assert response.status_code == 200
    assert "My Hackathon Registrations" in response.text
    # Total registrations stat should be present
    assert "Total Registered" in response.text
    assert "Active &amp; Ongoing" in response.text or "Active & Ongoing" in response.text
    assert "Projects Submitted" in response.text
    # Should display cards with workspaces
    assert "Open Workspace" in response.text
    # Should have filtering controls
    assert "All Hackathons" in response.text
    assert 'id="regSearchInput"' in response.text
    assert 'id="regSortSelect"' in response.text


def test_sidebar_and_dashboard_links(client: TestClient, auth_cookies):
    cookies = auth_cookies["participant"]
    # Check participant home dashboard
    response = client.get("/participant/home", cookies=cookies)
    assert response.status_code == 200
    # Sidebar "My Registrations" button must link to /participant/registrations
    assert 'href="/participant/registrations"' in response.text
    # "View all" above registrations section must link to /participant/registrations
    assert 'href="/participant/registrations"' in response.text
    # Registrations stat card must redirect to /participant/registrations
    assert '<a href="/participant/registrations" class="stat-card"' in response.text


def test_explore_hackathons_dropdowns_and_values(client: TestClient, auth_cookies):
    cookies = auth_cookies["participant"]
    response = client.get("/explore", cookies=cookies)
    assert response.status_code == 200

    # Check for all required dropdown menus:
    # 1. All Tracks
    assert 'id="filterTrack"' in response.text
    assert "<option value=\"all\">All Tracks</option>" in response.text
    # Ensure options have values populated
    assert 'value="developer tools"' in response.text.lower() or 'value="climate"' in response.text.lower()

    # 2. All Locations
    assert 'id="filterLocation"' in response.text
    assert "<option value=\"all\">All Locations</option>" in response.text
    assert 'value="san francisco' in response.text.lower() or 'value="bangalore' in response.text.lower() or 'value="online' in response.text.lower()

    # 3. Online / Offline (Format)
    assert 'id="filterFormat"' in response.text
    assert 'value="online"' in response.text
    assert 'value="in-person"' in response.text
    assert 'value="hybrid"' in response.text

    # 4. Prize pool
    assert 'id="filterPrize"' in response.text
    assert 'value="5000"' in response.text
    assert 'value="10000"' in response.text

    # 5. Any date
    assert 'id="filterDate"' in response.text
    assert 'value="this_week"' in response.text
    assert 'value="this_month"' in response.text

    # 6. Status filter tabs (All, Upcoming, Ongoing, Past)
    assert 'data-filter="all"' in response.text
    assert 'data-filter="upcoming"' in response.text
    assert 'data-filter="ongoing"' in response.text
    assert 'data-filter="past"' in response.text
    assert "All Hackathons" in response.text
    assert "Upcoming" in response.text
    assert "Ongoing" in response.text

    # 7. Sort by Start date (soonest)
    assert 'id="filterSort"' in response.text
    assert 'value="start_soonest"' in response.text

    # Check that event cards have rich data attributes for interactive filtering
    assert 'data-tracks=' in response.text
    assert 'data-location=' in response.text
    assert 'data-format=' in response.text
    assert 'data-prize=' in response.text
    assert 'data-start=' in response.text


def test_registrations_sidebar_collapsible_items_and_placement(client: TestClient, auth_cookies):
    cookies = auth_cookies["participant"]

    # 1. On /participant/registrations (global account-level page):
    response = client.get("/participant/registrations", cookies=cookies)
    assert response.status_code == 200

    # Ensure Current Hackathon sidebar buttons and section are NOT visible on registrations page
    assert "CURRENT HACKATHON" not in response.text
    assert '<div style="font-weight: 500;">Sample Hack 2026</div>' not in response.text

    # Global participant items are visible
    for label in ["Home", "Explore Hackathons", "My Registrations", "Profile"]:
        assert f"<span>{label}</span>" in response.text

    # Ensure collapse toggle button exists inside sidebar
    assert 'id="sidebarCollapseBtn"' in response.text
    assert "toggleSidebar()" in response.text

    # 2. When entering a specific hackathon workspace (/participant/evt_01/dashboard):
    ws_res = client.get("/participant/evt_01/dashboard", cookies=cookies)
    assert ws_res.status_code == 200

    # Topbar displays the active event name
    assert '<div style="font-weight: 500;">Sample Hack 2026</div>' in ws_res.text

    # Sidebar displays the Current Hackathon items
    assert "CURRENT HACKATHON" in ws_res.text
    for label in ["Overview", "Team", "Find a Team", "Submission", "Certificate", "API &amp; Docs"]:
        assert f"<span>{label}</span>" in ws_res.text
    for tooltip in ["Overview", "Team", "Find a Team", "Submission", "Certificate", "API &amp; Docs"]:
        assert f'data-tooltip="{tooltip}"' in ws_res.text


def test_cannot_register_for_completed_hackathon(client: TestClient, auth_cookies):
    cookies = auth_cookies["participant"]
    
    # 1. Event landing page for completed hackathon (evt_03)
    res_landing = client.get("/events/evt_03", cookies=cookies)
    assert res_landing.status_code == 200
    assert "Completed" in res_landing.text
    assert "Hackathon Completed" in res_landing.text
    assert "Join Hackathon" not in res_landing.text
    assert 'id="register-modal"' not in res_landing.text

    # 2. GET registration wizard for completed hackathon redirects
    res_wizard = client.get("/events/evt_03/register", cookies=cookies, follow_redirects=False)
    assert res_wizard.status_code == 303
    assert "/events/evt_03?error=completed" in res_wizard.headers.get("location", "")

    # 3. POST registration wizard for completed hackathon returns 400
    res_submit = client.post(
        "/events/evt_03/register",
        data={
            "skills_offered": "Python, AI",
            "looking_for_team": True,
            "team_action": "solo",
        },
        cookies=cookies,
    )
    assert res_submit.status_code == 400
    assert "already completed" in res_submit.text

    # 4. POST join for completed hackathon returns 400
    res_join = client.post("/events/evt_03/join", cookies=cookies)
    assert res_join.status_code == 400
    assert "already completed" in res_join.text

    # 5. Open hackathon (evt_10) displays interactive skill tags container and allows registration
    res_open = client.get("/events/evt_10", cookies=cookies)
    assert res_open.status_code == 200
    assert "skills-tag-box" in res_open.text
    assert "skills-pill-input" in res_open.text


