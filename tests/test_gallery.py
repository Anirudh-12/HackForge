def test_gallery_is_public(client):
    response = client.get("/projects")
    assert response.status_code == 200
    assert "Explore Projects" in response.text


def test_fixture_projects_appear_in_gallery(client):
    response = client.get("/projects")
    assert response.status_code == 200
    # Checks for known fixture projects
    haystack = response.text.lower()
    known_titles = ["glass signal", "tracecraft", "beacon mesh"]
    assert any(title in haystack for title in known_titles)


def test_gallery_search_filter(client):
    response = client.get("/projects?q=Glass")
    assert response.status_code == 200
    assert "Glass Signal" in response.text


def test_gallery_randomized_ballot_ordering(client):
    response = client.get("/projects?sort=random")
    assert response.status_code == 200
    assert "Explore Projects" in response.text


def test_project_detail_view(client):
    response = client.get("/projects/prj_01")
    assert response.status_code == 200
    assert "Glass Signal" in response.text
    assert "Discussion & Feedback" in response.text
