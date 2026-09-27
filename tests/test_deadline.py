def test_closed_event_refuses_submissions(client, auth_cookies):
    # Submissions to closed events must be rejected with HTTP 4xx
    response = client.post(
        "/projects/new",
        json={"title": "dogfood-late-submission-probe", "summary": "probe"},
        cookies=auth_cookies["participant"],
    )
    assert 400 <= response.status_code < 500
