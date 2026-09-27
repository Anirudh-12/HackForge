def test_judge_sees_own_scores(client, auth_cookies):
    response = client.get("/api/judge/scores", cookies=auth_cookies["judge_a"])
    assert response.status_code == 200


def test_judge_cannot_see_peer_scores(client, auth_cookies):
    # Attempting to fetch judge_a's scores as judge_b must return 401 or 403
    response = client.get(
        "/api/judge/scores?judge=jdg_01",
        cookies=auth_cookies["judge_b"],
    )
    assert response.status_code in (401, 403)


def test_participant_blocked_from_judge_scores(client, auth_cookies):
    response = client.get("/api/judge/scores", cookies=auth_cookies["participant"])
    assert response.status_code in (401, 403)


def test_visitor_blocked_from_judge_scores(client):
    response = client.get("/api/judge/scores")
    assert response.status_code in (401, 403)
