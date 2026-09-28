"""Append /vote route to public.py"""
with open(r'src/routers/public.py', 'r', encoding='utf-8') as f:
    content = f.read()

route_code = '''

@router.get("/vote")
def community_voting_page(
    request: Request,
    event_id: str | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if event_id:
        event = db.get(Event, event_id)
    else:
        from sqlalchemy import true
        event = db.query(Event).filter(Event.community_voting_enabled == true()).first()
        if not event:
            event = default_event(db)
    if not event:
        raise HTTPException(status_code=404, detail="No event found")
    projects_q = (
        db.query(Project)
        .options(joinedload(Project.team), joinedload(Project.track))
        .filter(Project.event_id == event.id, Project.is_draft.is_(False), Project.is_disqualified.is_(False))
    )
    import random as _random
    projects = list(projects_q.all())
    rng = _random.Random(user.id if user else "anon")
    rng.shuffle(projects)
    tracks = event_tracks(db, event.id)
    current_role = role_for(membership_for(db, user, event.id) if user else None)
    user_voted_project_id = None
    if user:
        ev = db.query(Vote).filter(Vote.user_id == user.id, Vote.event_id == event.id).first()
        if ev:
            user_voted_project_id = ev.project_id
    user_team_project_ids = set()
    if user:
        user_teams = db.query(TeamMember.team_id).filter(TeamMember.user_id == user.id).subquery()
        user_team_project_ids = set(p[0] for p in db.query(Project.id).filter(Project.team_id.in_(user_teams)).all())
    vote_counts = {}
    if event.results_published or current_role in ("organizer", "admin"):
        vote_counts = dict(db.query(Vote.project_id, func.count(Vote.id)).filter(Vote.event_id == event.id).group_by(Vote.project_id).all())
    from sqlalchemy import true as _true
    all_voting_events = db.query(Event).filter(Event.community_voting_enabled == _true()).all()
    return templates.TemplateResponse(
        request=request,
        name="community_voting.html",
        context=base_context(
            request=request, event=event, user=user, role=current_role,
            projects=projects, tracks=tracks,
            user_voted_project_id=user_voted_project_id,
            user_team_project_ids=user_team_project_ids,
            vote_counts=vote_counts, all_voting_events=all_voting_events,
        ),
    )
'''

if '/vote' not in content:
    with open(r'src/routers/public.py', 'w', encoding='utf-8') as f:
        f.write(content.rstrip() + route_code)
    print('Added /vote route')
else:
    print('/vote route already present')
