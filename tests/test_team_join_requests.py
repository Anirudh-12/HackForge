import pytest  # noqa: F401
from src.auth import make_session_token
from src.db import SessionLocal
from src.models import (
    Event,
    EventMember,
    Notification,
    Team,
    TeamJoinRequest,
    TeamMember,
    User,
)


def test_request_to_join_sends_to_leader_and_provides_visual_feedback(client):
    db = SessionLocal()
    try:
        # Create an event
        event = db.get(Event, "evt_01")
        assert event is not None

        # User 1: Team Leader
        leader = db.get(User, "usr_alice")
        if not leader:
            leader = User(id="usr_alice", name="Alice Leader", email="alice@test.com")
            db.add(leader)
            db.commit()

        # User 2: Applicant
        applicant = db.get(User, "usr_bob")
        if not applicant:
            applicant = User(id="usr_bob", name="Bob Applicant", email="bob@test.com")
            db.add(applicant)
            db.commit()

        # Register both for the event
        for u in [leader, applicant]:
            m = db.query(EventMember).filter_by(event_id=event.id, user_id=u.id).first()
            if not m:
                db.add(EventMember(event_id=event.id, user_id=u.id, role="participant"))
        db.commit()

        # Create a team where Alice is the leader
        team = (
            db.query(Team)
            .filter_by(event_id=event.id, name="Alice's Wonder Team")
            .first()
        )
        if not team:
            team = Team(
                id="tm_alice_1",
                event_id=event.id,
                name="Alice's Wonder Team",
                leader_id=leader.id,
            )
            db.add(team)
            db.flush()
            db.add(TeamMember(team_id=team.id, user_id=leader.id))
            db.commit()
        else:
            team.leader_id = leader.id
            db.commit()

        # Ensure Bob is not in any team
        db.query(TeamMember).filter_by(user_id=applicant.id).delete()
        # Clean up any previous join requests between them
        db.query(TeamJoinRequest).filter_by(
            team_id=team.id, user_id=applicant.id
        ).delete()
        # Clean up notifications for both
        db.query(Notification).filter(
            Notification.user_id.in_([leader.id, applicant.id])
        ).delete()
        db.commit()

        # Step 1: Bob clicks "Request to Join" via AJAX (XMLHttpRequest)
        bob_cookie = {"session": make_session_token(applicant.id)}
        res_ajax = client.post(
            f"/participant/{event.id}/request_join",
            data={"target_team_id": team.id},
            cookies=bob_cookie,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
        )
        assert res_ajax.status_code == 200
        data = res_ajax.json()
        assert data["ok"] is True
        assert "Join request sent to Alice Leader!" in data["message"]
        assert data["status"] == "pending"
        assert data["team_id"] == team.id

        # Step 2: Verify database state
        join_req = (
            db.query(TeamJoinRequest)
            .filter_by(team_id=team.id, user_id=applicant.id)
            .first()
        )
        assert join_req is not None
        assert join_req.status == "pending"

        # Step 3: Verify notification was sent to the team leader (Alice)
        leader_notif = (
            db.query(Notification)
            .filter_by(user_id=leader.id)
            .order_by(Notification.created_at.desc())
            .first()
        )
        assert leader_notif is not None
        assert "Bob Applicant" in leader_notif.message
        assert f"requested to join your team '{team.name}'" in leader_notif.message

        # Step 4: Verify confirmation notification was sent to applicant (Bob)
        applicant_notif = (
            db.query(Notification)
            .filter_by(user_id=applicant.id)
            .order_by(Notification.created_at.desc())
            .first()
        )
        assert applicant_notif is not None
        assert "You requested to join" in applicant_notif.message
        assert "Alice Leader" in applicant_notif.message

        # Step 5: Test standard form post (non-AJAX) redirect visual feedback
        # Cancel first so we can re-request via standard post
        join_req.status = "cancelled"
        db.commit()

        res_post = client.post(
            f"/participant/{event.id}/request_join",
            data={"target_team_id": team.id},
            cookies=bob_cookie,
            follow_redirects=False,
        )
        assert res_post.status_code == 303
        assert "msg=" in res_post.headers["location"]
        assert "msg_type=success" in res_post.headers["location"]

        # Step 6: Verify matchmaking page renders visual feedback for applicant:
        # - Team card displays "Request Sent" (disabled button)
        # - Sidebar displays "My Join Requests" with "Pending Leader Review"
        page_res = client.get(
            f"/participant/{event.id}/matchmaking", cookies=bob_cookie
        )
        assert page_res.status_code == 200
        assert "Request Sent" in page_res.text
        assert "My Join Requests" in page_res.text
        assert "Pending Leader Review" in page_res.text
        assert "👑" in page_res.text
        assert "Alice Leader" in page_res.text

        # Step 7: Verify matchmaking page and team page for the Team Leader (Alice):
        # - Shows "Incoming Requests" with Bob Applicant
        # - Shows "Accept" and "Decline" buttons
        leader_cookie = {"session": make_session_token(leader.id)}
        leader_mm_res = client.get(
            f"/participant/{event.id}/matchmaking", cookies=leader_cookie
        )
        assert leader_mm_res.status_code == 200
        assert "Incoming Requests" in leader_mm_res.text
        assert "Bob Applicant" in leader_mm_res.text

        leader_team_res = client.get(
            f"/participant/{event_id}/team"
            if False
            else f"/participant/{event.id}/team",
            cookies=leader_cookie,
        )
        assert leader_team_res.status_code == 200
        assert "Incoming Join Requests" in leader_team_res.text
        assert "Bob Applicant" in leader_team_res.text
        assert "👑 Team Leader" in leader_team_res.text

        # Step 8: Leader accepts the request
        join_req = (
            db.query(TeamJoinRequest)
            .filter_by(team_id=team.id, user_id=applicant.id)
            .first()
        )
        accept_res = client.post(
            f"/participant/{event.id}/requests/{join_req.id}/accept",
            cookies=leader_cookie,
            follow_redirects=False,
        )
        assert accept_res.status_code == 303

        # Verify Bob is now a member of the team
        db.expire_all()
        is_member = (
            db.query(TeamMember)
            .filter_by(team_id=team.id, user_id=applicant.id)
            .first()
        )
        assert is_member is not None

        # Verify Bob received acceptance notification
        bob_accept_notif = (
            db.query(Notification)
            .filter(
                Notification.user_id == applicant.id,
                Notification.message.like("%accepted%"),
            )
            .first()
        )
        assert bob_accept_notif is not None

    finally:
        db.close()
