def test_csv_export_as_organizer(client, auth_cookies):
    response = client.get("/api/export.csv", cookies=auth_cookies["organizer"])
    assert response.status_code == 200
    first_line = response.text.splitlines()[0] if response.text.splitlines() else ""
    assert "," in first_line
    assert "project_id" in first_line


def test_csv_export_blocked_for_participant(client, auth_cookies):
    response = client.get("/api/export.csv", cookies=auth_cookies["participant"])
    assert response.status_code in (401, 403)


def test_csv_export_blocked_for_visitor(client):
    response = client.get("/api/export.csv")
    assert response.status_code in (401, 403)
