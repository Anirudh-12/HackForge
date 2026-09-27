def test_list_comments_public(client):
    res = client.get("/api/projects/prj_01/comments")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_post_and_delete_comment(client, auth_cookies):
    # Post comment as participant
    post_res = client.post(
        "/api/projects/prj_01/comments",
        json={"content": "Great work on this project!"},
        cookies=auth_cookies["participant"],
    )
    assert post_res.status_code == 200
    data = post_res.json()
    assert data["content"] == "Great work on this project!"
    comment_id = data["id"]

    # Delete comment as author
    del_res = client.delete(
        f"/api/projects/prj_01/comments/{comment_id}",
        cookies=auth_cookies["participant"],
    )
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True


def test_empty_comment_rejected(client, auth_cookies):
    res = client.post(
        "/api/projects/prj_01/comments",
        json={"content": "   "},
        cookies=auth_cookies["participant"],
    )
    assert res.status_code == 400


def test_visitor_cannot_post_comment(client):
    res = client.post(
        "/api/projects/prj_01/comments",
        json={"content": "Should fail without login"},
    )
    assert res.status_code in (401, 403)
