import random
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src.models import Event, EventMember, Project, Team, TeamMember, Track, User, Vote, Comment


def default_event(db: Session) -> Event | None:
    return db.get(Event, "evt_01") or db.query(Event).order_by(Event.id).first()


def get_event(db: Session, event_id: str) -> Event | None:
    return db.get(Event, event_id)


def user_team(db: Session, user_id: str, event_id: str) -> Team | None:
    return (
        db.query(Team)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .filter(Team.event_id == event_id, TeamMember.user_id == user_id)
        .first()
    )


def gallery_projects(
    db: Session,
    event_id: str,
    q: str | None = None,
    track_id: str | None = None,
    sort: str | None = None,
    user_seed: str | None = None,
):
    query = (
        db.query(Project)
        .options(joinedload(Project.team), joinedload(Project.track))
        .filter(Project.event_id == event_id, Project.is_draft.is_(False), Project.is_disqualified.is_(False))
    )
    if q:
        like = f"%{q}%"
        query = query.filter(Project.title.ilike(like) | Project.summary.ilike(like))
    if track_id:
        query = query.filter(Project.track_id == track_id)

    projects = query.order_by(Project.title.asc()).all()
    if sort == "random":
        rng = random.Random(user_seed) if user_seed else random.Random()
        shuffled = list(projects)
        rng.shuffle(shuffled)
        return shuffled
    return projects


def event_tracks(db: Session, event_id: str) -> list[Track]:
    return db.query(Track).filter(Track.event_id == event_id).order_by(Track.name.asc()).all()


def upsert_membership(db: Session, event_id: str, user_id: str, role: str) -> EventMember:
    member = (
        db.query(EventMember)
        .filter(EventMember.event_id == event_id, EventMember.user_id == user_id)
        .first()
    )
    if member:
        return member
    member = EventMember(event_id=event_id, user_id=user_id, role=role)
    db.add(member)
    return member


def compute_results(db: Session, event_id: str):
    from src.models import Score, RubricCriteria, JudgeTrack
    import math

    projects = gallery_projects(db, event_id) # gets non-draft, non-disqualified
    criteria = db.query(RubricCriteria).filter_by(event_id=event_id).all()
    total_weight = sum(c.weight for c in criteria)
    if not total_weight:
        total_weight = 1

    crit_weights = {c.id: c.weight / total_weight for c in criteria}

    scores = db.query(Score).filter_by(event_id=event_id).all()
    
    # group scores by (project_id, judge_id)
    grouped_scores = {}
    for s in scores:
        if getattr(s, 'conflict_of_interest', False):
            continue
        key = (s.project_id, s.judge_id)
        if key not in grouped_scores:
            grouped_scores[key] = {}
        grouped_scores[key][s.criteria_id] = s.value

    project_judge_raw = {}
    judge_scores_by_track = {}
    
    for p in projects:
        project_judge_raw[p.id] = {}
        if p.track_id not in judge_scores_by_track:
            judge_scores_by_track[p.track_id] = {}
            
        for (pid, jid), c_scores in grouped_scores.items():
            if pid == p.id:
                raw_score = sum(val * crit_weights.get(cid, 0) for cid, val in c_scores.items())
                project_judge_raw[p.id][jid] = raw_score
                
                if jid not in judge_scores_by_track[p.track_id]:
                    judge_scores_by_track[p.track_id][jid] = []
                judge_scores_by_track[p.track_id][jid].append(raw_score)

    judge_stats = {}
    for track_id, j_scores in judge_scores_by_track.items():
        for jid, raw_scores in j_scores.items():
            n = len(raw_scores)
            if n == 0:
                continue
            mean = sum(raw_scores) / n
            if n > 1:
                variance = sum((x - mean)**2 for x in raw_scores) / n
                stdev = math.sqrt(variance)
            else:
                stdev = 0
            judge_stats[(track_id, jid)] = (mean, stdev)

    # Bradley-Terry ELO calculation
    from src.models import PairwiseComparison
    pairwise = db.query(PairwiseComparison).filter_by(event_id=event_id).order_by(PairwiseComparison.created_at).all()
    
    elo_scores = {p.id: 1500.0 for p in projects}
    K = 32
    
    for comp in pairwise:
        if comp.winner_project_id in elo_scores and comp.loser_project_id in elo_scores:
            r_win = elo_scores[comp.winner_project_id]
            r_lose = elo_scores[comp.loser_project_id]
            
            # Expected win probabilities
            p_win = 1.0 / (1.0 + 10 ** ((r_lose - r_win) / 400.0))
            p_lose = 1.0 / (1.0 + 10 ** ((r_win - r_lose) / 400.0))
            
            elo_scores[comp.winner_project_id] = r_win + K * (1 - p_win)
            elo_scores[comp.loser_project_id] = r_lose + K * (0 - p_lose)

    # Community votes per project
    community_votes_map = dict(
        db.query(Vote.project_id, func.count(Vote.id))
        .filter(Vote.event_id == event_id)
        .group_by(Vote.project_id)
        .all()
    )

    results = []
    for p in projects:
        p_raw_scores = project_judge_raw.get(p.id, {})
        p_norm_scores = []
        p_raw_list = []
        
        for jid, raw in p_raw_scores.items():
            p_raw_list.append(raw)
            mean, stdev = judge_stats.get((p.track_id, jid), (0, 0))
            if stdev == 0:
                norm = 50.0
            else:
                z = (raw - mean) / stdev
                norm = 50.0 + (z * 15.0)
            p_norm_scores.append(norm)
            
        avg_raw = sum(p_raw_list) / len(p_raw_list) if p_raw_list else 0
        avg_norm = sum(p_norm_scores) / len(p_norm_scores) if p_norm_scores else 0
        
        results.append({
            "project": p,
            "raw_score": avg_raw,
            "normalized_score": avg_norm,
            "elo_score": elo_scores[p.id],
            "reviews_count": len(p_raw_list),
            "judge_raw_scores": p_raw_scores,
            "community_votes": community_votes_map.get(p.id, 0),
        })
        
    return sorted(results, key=lambda x: x["normalized_score"], reverse=True)
