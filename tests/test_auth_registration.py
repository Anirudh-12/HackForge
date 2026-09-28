from src.main import app
from starlette.testclient import TestClient

client = TestClient(app)


def test_register_page_has_already_a_user_signin_button():
    response = client.get("/register")
    assert response.status_code == 200
    html = response.text
    # Verify the registration form has 'Already a user? Sign in' button
    assert "Already a user? Sign in" in html
    assert 'href="/login"' in html or 'href="/login' in html
    # Verify the button has the expected styling/id
    assert 'id="already-user-btn"' in html


def test_register_page_preserves_next_param():
    response = client.get("/register?next=/organizer/events")
    assert response.status_code == 200
    html = response.text
    assert 'name="next" value="/organizer/events"' in html
    assert 'href="/login?next=/organizer/events"' in html
