import sys
import uuid
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

# Adjust the path to import from src
sys.path.append(".")

from src.db import SessionLocal, init_db
from src.models import (
    Event,
    Track,
    Team,
    TeamMember,
    Project,
    User,
    EventMember
)

def get_random_past_date():
    return datetime.now(timezone.utc) - timedelta(days=random.randint(30, 365))

def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"

hackathons_data = [
    {"name": "DOGFOOD 2026", "tracks": ["Open Innovation", "Internal Tools"]},
    {"name": "GreenBuild 2026", "tracks": ["Climate Tech", "Sustainability", "Clean Energy"]},
    {"name": "AI for India", "tracks": ["Healthcare", "Education", "Rural Development"]},
    {"name": "SafeRoute Hackathon", "tracks": ["Mobility", "IoT", "Data Analytics"]},
    {"name": "BuildEd 2026", "tracks": ["EdTech", "Web", "Mobile"]},
    {"name": "SecureIndia", "tracks": ["Cybersecurity", "Blockchain", "Privacy"]},
]

tech_stacks = [
    "React, Node.js, MongoDB",
    "Python, FastAPI, PostgreSQL",
    "Next.js, Tailwind, Supabase",
    "Vue.js, Express, MySQL",
    "Flutter, Firebase",
    "Django, SQLite",
    "Spring Boot, React",
    "Svelte, GraphQL",
    "Go, Docker, Kubernetes"
]

adjectives = ["Smart", "Intelligent", "Auto", "Quantum", "Eco", "Cyber", "Cloud", "Data", "Health", "Edu"]
nouns = ["Flow", "Sense", "OS", "Platform", "Hub", "Network", "Bot", "AI", "App", "System"]

def generate_project_name():
    return random.choice(adjectives) + random.choice(nouns)

def generate_summary():
    summaries = [
        "A revolutionary platform to connect people and resources.",
        "An AI-driven solution for optimizing daily workflows.",
        "A tool designed to make education more accessible.",
        "Tracking and managing sustainability metrics for modern businesses.",
        "A mobile application focused on mental health and well-being.",
        "Automating tedious tasks to save time and reduce errors.",
        "A community-driven platform for sharing knowledge and resources.",
        "Leveraging blockchain for secure and transparent transactions.",
        "An innovative approach to solving complex logistics problems.",
        "Empowering local businesses with data-driven insights."
    ]
    return random.choice(summaries)


def seed():
    init_db()
    db: Session = SessionLocal()

    try:
        # Create some random users
        users = []
        for i in range(100):
            user_id = new_id("usr")
            user = User(
                id=user_id,
                email=f"user_{uuid.uuid4().hex[:6]}@example.com",
                name=f"User {i}",
                password_hash=None
            )
            db.add(user)
            users.append(user)
        db.flush()

        for hackathon_data in hackathons_data:
            event_id = new_id("evt")
            past_date = get_random_past_date()
            event = Event(
                id=event_id,
                name=hackathon_data["name"],
                submissions_open=past_date - timedelta(days=30),
                submissions_close=past_date - timedelta(days=20),
                judging_open=past_date - timedelta(days=19),
                judging_close=past_date - timedelta(days=10),
                results_published=True
            )
            db.add(event)
            db.flush()

            # Add tracks
            track_models = []
            for track_name in hackathon_data["tracks"]:
                track = Track(
                    id=new_id("trk"),
                    event_id=event.id,
                    name=track_name,
                    prize="Awesome Prize"
                )
                db.add(track)
                track_models.append(track)
            db.flush()

            # Add 10 projects
            for i in range(10):
                # Create team
                team = Team(
                    id=new_id("team"),
                    event_id=event.id,
                    name=f"{generate_project_name()} Team",
                    invite_token=uuid.uuid4().hex
                )
                db.add(team)
                db.flush()

                # Add 1-4 members
                num_members = random.randint(1, 4)
                team_users = random.sample(users, num_members)
                for user in team_users:
                    # check if event member exists
                    existing = db.query(EventMember).filter_by(event_id=event.id, user_id=user.id).first()
                    if not existing:
                        db.add(EventMember(event_id=event.id, user_id=user.id, role="participant"))
                    
                    # check if team member exists
                    existing_tm = db.query(TeamMember).filter_by(team_id=team.id, user_id=user.id).first()
                    if not existing_tm:
                        db.add(TeamMember(team_id=team.id, user_id=user.id))
                db.flush()
                
                # Add project
                track = random.choice(track_models) if track_models else None
                project = Project(
                    id=new_id("prj"),
                    event_id=event.id,
                    team_id=team.id,
                    track_id=track.id if track else None,
                    title=generate_project_name(),
                    summary=generate_summary(),
                    repo_url="https://github.com/example/project",
                    demo_url="https://demo.example.com",
                    cover_image_path=None,  # Or add a random image from placeholder
                    screenshots=None,
                    tech_stack=random.choice(tech_stacks),
                    is_draft=False,
                    submitted_at=event.submissions_close - timedelta(days=random.randint(1, 9)),
                    is_disqualified=False
                )
                db.add(project)
        db.commit()
        print("Successfully seeded hackathons and projects!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding: {e}")
    finally:
        db.close()

if __name__ == '__main__':
    seed()
