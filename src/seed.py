from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from src.auth import make_session_token
from src.models import (
    AuditLog,
    Event,
    EventMember,
    JudgeTrack,
    Project,
    RubricCriteria,
    Score,
    Team,
    TeamMember,
    Track,
    User,
)
from src.seed_assets import ensure_all_assets
from src.timeutil import parse_iso_utc, utcnow

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_PATH = ROOT / "fixtures.json"
TOML_PATH = ROOT / ".dogfood.toml"


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _user(db: Session, user_id: str, email: str, name: str) -> User:
    existing = (
        db.get(User, user_id) or db.query(User).filter(User.email == email).first()
    )
    if existing:
        return existing
    user = User(id=user_id, email=email, name=name, password_hash=None)
    db.add(user)
    db.flush()
    return user


def _member(db: Session, event_id: str, user_id: str, role: str) -> None:
    exists = (
        db.query(EventMember)
        .filter(EventMember.event_id == event_id, EventMember.user_id == user_id)
        .first()
    )
    if exists:
        return
    db.add(EventMember(event_id=event_id, user_id=user_id, role=role))


def _audit(db: Session, event_id: str, message: str) -> None:
    db.add(
        AuditLog(
            event_id=event_id, actor_id="seed", message=message, created_at=utcnow()
        )
    )


OTHER_EVENTS_DATA = [
    # 4 FINISHED HACKATHONS (Timelines strictly non-overlapping, in past)
    {
        "id": "evt_02",
        "name": "GreenBuild Hackathon",
        "tagline": "Climate Tech, Carbon Accounting & Clean Energy Grid",
        "type": "finished",
        "start_iso": "2025-08-01T00:00:00Z",
        "close_iso": "2025-08-15T18:00:00Z",
        "judge_close_iso": "2025-08-22T18:00:00Z",
        "results_published": True,
        "tracks": [
            ("Clean Energy Grid", "$5,000 for best decentralized microgrid solution"),
            ("Carbon Accounting", "$3,500 for most accurate carbon ledger tool"),
            ("Circular Economy", "$3,000 for lifecycle recycling tracker"),
            ("Green AI & Efficiency", "$2,500 for lowest compute inference pipeline"),
        ],
        "judge_prefix": "shared",
        "rubric": [
            ("Climate Impact", 35),
            ("Technical Feasibility", 35),
            ("Code Architecture", 30),
        ],
        "projects": [
            (
                "VoltMesh",
                "Decentralized microgrid balancing using smart contracts",
                "Solidity, React, Node.js",
            ),
            (
                "CarbonLens",
                "Automated carbon footprint auditor for cloud providers",
                "Python, FastAPI, AWS SDK",
            ),
            (
                "BioRecycle",
                "Computer vision for rapid plastic sorting at recycling plants",
                "PyTorch, OpenCV, Flask",
            ),
            (
                "EcoTransit",
                "Dynamic carpool route optimizer to reduce single-occupancy commutes",
                "Go, Flutter, OpenStreetMap",
            ),
            (
                "WattWatch",
                "Smart meter telemetry aggregator with anomaly detection",
                "Rust, TimescaleDB, Grafana",
            ),
            (
                "CircularCloth",
                "Apparel lifecycle tracking and second-hand material passport",
                "Next.js, Supabase, Tailwind",
            ),
            (
                "AgriSense",
                "Precision irrigation optimization driven by soil moisture sensors",
                "Python, IoT, MQTT, InfluxDB",
            ),
            (
                "SolarSync",
                "Predictive solar panel yield and distributed battery management",
                "Python, TensorFlow, React",
            ),
            (
                "PaperLessOrg",
                "Complete zero-paper workflow orchestrator for government offices",
                "Django, HTMX, SQLite",
            ),
            (
                "OceanCleanBot",
                "Autonomous drone path planner for surface plastic collection",
                "ROS2, Python, C++",
            ),
        ],
    },
    {
        "id": "evt_03",
        "name": "AI for Health Hackathon",
        "tagline": "Diagnostics, Medical Imaging AI & Patient Wellbeing",
        "type": "finished",
        "start_iso": "2025-09-01T00:00:00Z",
        "close_iso": "2025-09-15T18:00:00Z",
        "judge_close_iso": "2025-09-22T18:00:00Z",
        "results_published": True,
        "tracks": [
            ("Clinical Decision Support", "$6,000 Grand Prize"),
            ("Medical Imaging AI", "$4,000 Imaging Innovation Award"),
            ("Patient Telehealth", "$3,000 Accessibility Prize"),
            ("Mental Wellbeing", "$2,000 Community Award"),
        ],
        "judge_prefix": "shared",
        "rubric": [
            ("Clinical Safety", 40),
            ("Diagnostic Accuracy", 30),
            ("Usability & UX", 30),
        ],
        "projects": [
            (
                "DermaScan AI",
                "Mobile melanoma detection using on-device neural network",
                "Swift, CoreML, FastAPI",
            ),
            (
                "PulseGuard",
                "Arrhythmia detection from continuous photoplethysmography data",
                "Python, PyTorch, React Native",
            ),
            (
                "ClinicFlow",
                "Triage prioritization and intake transcription assistant",
                "Whisper, Next.js, PostgreSQL",
            ),
            (
                "MindPath",
                "Cognitive behavioral therapy companion with mood journaling",
                "React, Node.js, MongoDB",
            ),
            (
                "PathoVision",
                "Histopathology slide tile classifier for automated cancer grading",
                "PyTorch, CUDA, FastAPI",
            ),
            (
                "PharmaCheck",
                "Adverse drug-drug interaction checker with clinical citations",
                "Python, LangChain, SQLite",
            ),
            (
                "NeuroRehab",
                "Gamified stroke recovery exercise tracking via webcam pose",
                "TensorFlow.js, HTML5 Canvas",
            ),
            (
                "ElderCare",
                "Non-intrusive fall detection and daily vitals telemetry system",
                "Raspberry Pi, Python, WebSockets",
            ),
            (
                "VoiceBiomarker",
                "Early Parkinson's speech acoustic feature analyzer",
                "Librosa, Scikit-Learn, Streamlit",
            ),
            (
                "GeneMatch",
                "Pediatric rare disease variant filtering and clinical summary",
                "Python, Biopython, FastAPI",
            ),
        ],
    },
    {
        "id": "evt_04",
        "name": "SecureIndia Cyber Sprint",
        "tagline": "Zero-Trust Architecture, AppSec & Threat Defense",
        "type": "finished",
        "start_iso": "2025-10-01T00:00:00Z",
        "close_iso": "2025-10-15T18:00:00Z",
        "judge_close_iso": "2025-10-22T18:00:00Z",
        "results_published": True,
        "tracks": [
            ("Zero-Trust Architecture", "$5,000 Infrastructure Prize"),
            ("AppSec & Vulnerability Scanning", "$4,000 SecOps Award"),
            ("Cryptographic Privacy", "$3,500 Privacy Champion"),
            ("Threat Intelligence", "$2,500 Threat Hunter Award"),
        ],
        "judge_prefix": "shared",
        "rubric": [
            ("Security Rigor", 40),
            ("Architectural Resilience", 35),
            ("Execution & PoC", 25),
        ],
        "projects": [
            (
                "ShieldVault",
                "Self-hosted zero-knowledge secrets manager for dev teams",
                "Rust, WebAssembly, React",
            ),
            (
                "TraceAudit",
                "eBPF-powered container runtime anomaly detector",
                "C, Go, eBPF, Prometheus",
            ),
            (
                "KeySentinel",
                "Automated TLS certificate rotation and HSM audit agent",
                "Python, Cryptography, Docker",
            ),
            (
                "PhishBuster",
                "Email header heuristic and spoofed domain detection gateway",
                "Python, Postfix, Redis",
            ),
            (
                "PrivaQuery",
                "Differential privacy database query wrapper with budget controls",
                "Python, DuckDB, FastAPI",
            ),
            (
                "BOMVerify",
                "Software bill of materials (SBOM) attestation and CVE scanner",
                "Go, Syft, Grype, React",
            ),
            (
                "ZeroGate",
                "WireGuard-based identity-aware access proxy for internal tools",
                "Go, WireGuard, OAuth2",
            ),
            (
                "HoneyNet AI",
                "Deceptive decoys and automated attacker fingerprinting suite",
                "Python, FastAPI, ElasticSearch",
            ),
            (
                "PassKeyBridge",
                "FIDO2 WebAuthn authentication drop-in for legacy web apps",
                "TypeScript, Node.js, Express",
            ),
            (
                "FirmwareGuard",
                "Static firmware analysis and embedded secret extractor",
                "Python, Radare2, Capstone",
            ),
        ],
    },
    {
        "id": "evt_05",
        "name": "EduForge Global Challenge",
        "tagline": "Adaptive Learning, Interactive STEM & Education Tech",
        "type": "finished",
        "start_iso": "2025-11-01T00:00:00Z",
        "close_iso": "2025-11-15T18:00:00Z",
        "judge_close_iso": "2025-11-22T18:00:00Z",
        "results_published": True,
        "tracks": [
            ("Personalized Tutoring", "$4,500 Education Award"),
            ("Accessible Learning Tech", "$4,000 Universal Access Prize"),
            ("Gamified STEM", "$3,500 Interactive Learning Award"),
            ("Teacher Tooling", "$2,500 Classroom Helper"),
        ],
        "judge_prefix": "shared",
        "rubric": [
            ("Pedagogical Value", 40),
            ("Accessibility", 30),
            ("Engagement", 30),
        ],
        "projects": [
            (
                "MathMorph",
                "Interactive geometry proof visualizer with real-time feedback",
                "TypeScript, React, MathJax",
            ),
            (
                "ReadAdapt",
                "Dyslexia-friendly reading tutor with phoneme highlighting",
                "React Native, Web Speech API",
            ),
            (
                "CodeCraft Kids",
                "Block-based visual programming environment for microcontrollers",
                "Blockly, JavaScript, WebUSB",
            ),
            (
                "LabVerse",
                "Virtual chemistry laboratory simulator with hazard safety checks",
                "Three.js, WebGL, Next.js",
            ),
            (
                "ClassEcho",
                "Automated formative quiz generator from lecture audio recordings",
                "Python, Whisper, Flask",
            ),
            (
                "BrailleLearn",
                "Audio-haptic tactile alphabet tutor for visually impaired students",
                "Arduino, Python, PyGame",
            ),
            (
                "StorySparks",
                "Creative writing prompt generator with collaborative world-building",
                "Vue.js, Firebase, Tailwind",
            ),
            (
                "BioCell VR",
                "Interactive 3D cell biology exploration experience",
                "A-Frame, WebXR, JavaScript",
            ),
            (
                "GradeFlow",
                "Handwritten math assignment grading assistant for educators",
                "Python, OCR, PyTorch, React",
            ),
            (
                "GlobeQuest",
                "Interactive geography and historical event timeline map",
                "Leaflet, Mapbox, React, Node.js",
            ),
        ],
    },
    # 2 ONGOING HACKATHONS (Submissions currently open!)
    {
        "id": "evt_06",
        "name": "CloudScale Builders 2026",
        "tagline": "Distributed Systems, Microservices & Edge Automation",
        "type": "ongoing",
        "days_ago_open": 7,
        "days_ahead_close": 5,
        "days_ahead_judge_close": 12,
        "results_published": False,
        "tracks": [
            ("Serverless & Edge", "$5,000 Edge Innovation"),
            ("Microservices & Mesh", "$4,000 Systems Architecture"),
            ("DevOps & Observability", "$3,500 Reliability Award"),
            ("Resilient Storage", "$3,000 High-Availability Prize"),
        ],
        "judge_prefix": "evt06",
        "rubric": [
            ("Scalability", 40),
            ("Code Architecture", 30),
            ("DevOps Polish", 30),
        ],
        "projects": [
            (
                "EdgeSync KV",
                "Globally distributed eventual-consistent key-value cache",
                "Rust, WebAssembly, Tokio",
            ),
            (
                "MeshPilot",
                "Autonomous service mesh traffic shaping and canary deployer",
                "Go, Kubernetes, Envoy",
            ),
            (
                "LogPrism",
                "Sub-second distributed log stream search and indexing engine",
                "Go, ClickHouse, React",
            ),
            (
                "ClusterHeal",
                "Self-healing Kubernetes node failure predictor using metrics",
                "Python, PyTorch, Prometheus",
            ),
            (
                "LambdaCost",
                "Fine-grained serverless cost profiler and memory auto-tuner",
                "Node.js, AWS CloudWatch, Chart.js",
            ),
            (
                "RaftDb",
                "Lightweight consensus-backed embedded transactional database",
                "Rust, Raft, RocksDB",
            ),
            (
                "TraceFlow",
                "Distributed OpenTelemetry visual trace topology debugger",
                "TypeScript, React, D3.js",
            ),
            (
                "ColdStartZero",
                "Predictive container pre-warming for zero-latency serverless",
                "Go, Docker API, Python",
            ),
            (
                "S3Mirror",
                "Multi-cloud active-active object storage synchronization gateway",
                "Go, MinIO, Redis",
            ),
            (
                "ChaosSim",
                "Continuous chaos engineering runner with automated rollback",
                "Python, FastAPI, Docker",
            ),
        ],
    },
    {
        "id": "evt_07",
        "name": "DevCraft Web3 & AI Jam",
        "tagline": "Autonomous Agents, Verifiable Workflows & Protocols",
        "type": "ongoing",
        "days_ago_open": 10,
        "days_ahead_close": 4,
        "days_ahead_judge_close": 10,
        "results_published": False,
        "tracks": [
            ("Autonomous Agents", "$6,000 Autonomous Tech Prize"),
            ("Decentralized Identity", "$4,000 DID Innovation Award"),
            ("Verifiable AI Workflows", "$3,500 Cryptographic AI"),
            ("Smart Contracts & L2", "$3,000 Protocol Scalability"),
        ],
        "judge_prefix": "evt07",
        "rubric": [
            ("Protocol Innovation", 35),
            ("Agent Autonomy", 35),
            ("UX & Security", 30),
        ],
        "projects": [
            (
                "AgentSwarm",
                "Collaborative multi-agent market research and report synthesizer",
                "Python, LangGraph, React",
            ),
            (
                "ZeroID",
                "Zero-knowledge credential verification for decentralized identity",
                "Circom, SnarkJS, Next.js",
            ),
            (
                "ProofChain",
                "Cryptographic verifiable execution proofs for LLM outputs",
                "Python, EZKL, Solidity",
            ),
            (
                "L2ArbitrageBot",
                "Decentralized liquidity pool arbitrage agent with flash loans",
                "Rust, Web3.py, Foundry",
            ),
            (
                "DAOVoice",
                "Liquid democracy on-chain voting portal with privacy ballots",
                "Solidity, IPFS, React",
            ),
            (
                "OracleGuard",
                "Decentralized oracle feed dispute and tamper resolution layer",
                "Go, Chainlink, Solidity",
            ),
            (
                "AgentWallet",
                "Non-custodial smart contract wallet controlled by constrained AI keys",
                "Solidity, ERC-4337, Next.js",
            ),
            (
                "NFTAttest",
                "Dynamic skills attestation token for hackathon verified achievements",
                "Solidity, Polygon, Vite",
            ),
            (
                "DataBounty",
                "Encrypted peer-to-peer data labeling marketplace",
                "Node.js, Web3Storage, Express",
            ),
            (
                "ZkAudit",
                "Privacy-preserving regulatory compliance verification for Web3 protocols",
                "Rust, Noir, React",
            ),
        ],
    },
    # 3 UPCOMING HACKATHONS (Registrations open! Rubrics completely editable!)
    {
        "id": "evt_08",
        "name": "NextGen Mobility Hack 2026",
        "tagline": "Autonomous Transit, EV Infrastructure & Micromobility",
        "type": "upcoming",
        "days_ago_reg_open": 5,
        "days_ahead_reg_close": 12,
        "days_ahead_sub_open": 10,
        "days_ahead_sub_close": 20,
        "days_ahead_judge_close": 28,
        "results_published": False,
        "tracks": [
            ("EV Fleet Intelligence", "$5,000 Fleet Prize"),
            ("Autonomous Safety", "$4,000 Safety Innovation"),
            ("Smart Logistics", "$3,500 Routing Excellence"),
            ("Micromobility", "$2,500 Urban Transit Award"),
        ],
        "judge_prefix": "evt08",
        "rubric": [
            ("Safety & Feasibility", 40),
            ("Technical Innovation", 35),
            ("Community Impact", 25),
        ],
        "projects": [
            (
                "ChargeGrid",
                "Peer-to-peer residential EV charger sharing network",
                "React, Node.js, Stripe",
            ),
            (
                "VisionDrive",
                "Open-source ADAS computer vision safety copilot for older vehicles",
                "Python, OpenCV, Jetson Nano",
            ),
            (
                "FleetEco",
                "Heavy truck aerodynamic formation drafting and routing scheduler",
                "Go, Python, OpenStreetMap",
            ),
            (
                "ScooterSafe",
                "Sidewalk riding detector and geofenced speed controller for e-scooters",
                "C++, TensorFlow Lite, ESP32",
            ),
            (
                "BatteryHealth",
                "Predictive EV lithium degradation estimator from OBD-II data",
                "Python, XGBoost, Streamlit",
            ),
            (
                "UrbanTransit",
                "Real-time municipal bus occupancy and multimodal connection predictor",
                "FastAPI, React, Redis",
            ),
            (
                "DeliveryDrone",
                "Urban last-mile parcel drop path optimizer avoiding flight obstacles",
                "Python, ROS2, Gazebo",
            ),
            (
                "PedestrianGuard",
                "Crosswalk illumination and collision early warning sensor array",
                "Python, YOLOv8, MQTT",
            ),
            (
                "ParkEasy",
                "Crowdsourced curb parking availability tracker using dashcam feeds",
                "React Native, FastAPI, PostgreSQL",
            ),
            (
                "TransitToken",
                "Universal single-ticket multimodal transit payment protocol",
                "Next.js, Tailwind, SQLite",
            ),
        ],
    },
    {
        "id": "evt_09",
        "name": "FinTech Fusion 2026",
        "tagline": "Open Banking, Real-Time Fraud Defense & Wealth AI",
        "type": "upcoming",
        "days_ago_reg_open": 4,
        "days_ahead_reg_close": 15,
        "days_ahead_sub_open": 14,
        "days_ahead_sub_close": 25,
        "days_ahead_judge_close": 32,
        "results_published": False,
        "tracks": [
            ("Real-Time Fraud Detection", "$6,000 Security Award"),
            ("Open Banking & Embedded Finance", "$4,500 Banking Innovation"),
            ("DeFi Compliance", "$3,500 RegTech Prize"),
            ("Personal Wealth AI", "$2,500 Consumer Financial Wellness"),
        ],
        "judge_prefix": "evt09",
        "rubric": [
            ("Security & Compliance", 40),
            ("Algorithm Robustness", 30),
            ("Market Fit", 30),
        ],
        "projects": [
            (
                "FraudShield",
                "Millisecond transaction anomaly scoring using graph embeddings",
                "Python, Neo4j, FastAPI",
            ),
            (
                "SplitPay",
                "Fair split payment API for group travel and subscriptions",
                "Next.js, Node.js, PostgreSQL",
            ),
            (
                "TaxPilot",
                "Freelancer real-time quarterly tax calculation and deduction assistant",
                "Python, Django, SQLite",
            ),
            (
                "KYCFlow",
                "Automated biometric ID document verification with anti-spoofing",
                "PyTorch, FastAPI, React",
            ),
            (
                "MicroLend",
                "Alternative credit scoring engine for unbanked small businesses",
                "Python, Scikit-Learn, Flask",
            ),
            (
                "WealthSync",
                "Tax-loss harvesting and portfolio rebalancing autonomous agent",
                "Python, NumPy, Pandas, React",
            ),
            (
                "ReceiptAudit",
                "Smart OCR expense categorizer for small business bookkeeping",
                "Tesseract, FastAPI, Tailwind",
            ),
            (
                "InvoiceFactoring",
                "Decentralized accounts receivable financing marketplace",
                "Solidity, React, Node.js",
            ),
            (
                "KidFin",
                "Gamified financial literacy and chore allowance platform for teenagers",
                "React Native, Firebase",
            ),
            (
                "ForexHedge",
                "Currency fluctuation risk mitigation planner for cross-border exporters",
                "Python, FastAPI, Chart.js",
            ),
        ],
    },
    {
        "id": "evt_10",
        "name": "BioTech Horizon Summit",
        "tagline": "Genomics Pipelines, Drug Discovery & Lab Automation",
        "type": "upcoming",
        "days_ago_reg_open": 3,
        "days_ahead_reg_close": 18,
        "days_ahead_sub_open": 16,
        "days_ahead_sub_close": 30,
        "days_ahead_judge_close": 38,
        "results_published": False,
        "tracks": [
            ("Genomic Sequencing Tools", "$6,000 Genomics Prize"),
            ("Molecular Docking AI", "$5,000 Drug Discovery Award"),
            ("Lab Automation APIs", "$3,500 Hardware Integration"),
            ("Bioinformatics Cloud", "$3,000 Cloud Scale Biology"),
        ],
        "judge_prefix": "evt10",
        "rubric": [
            ("Scientific Rigor", 40),
            ("Computational Efficiency", 30),
            ("Novelty", 30),
        ],
        "projects": [
            (
                "FoldFast",
                "GPU-accelerated protein conformational docking simulator",
                "Python, PyTorch, CUDA, React",
            ),
            (
                "SeqPipeline",
                "High-throughput variant calling pipeline with interactive IGV view",
                "Nextflow, Docker, Python",
            ),
            (
                "CrisprTarget",
                "Off-target guide RNA cleavage risk predictor and score visualizer",
                "Python, Biopython, Streamlit",
            ),
            (
                "PipetteBot",
                "Standardized Python protocol driver for automated liquid handlers",
                "Python, PySerial, Raspberry Pi",
            ),
            (
                "MoleculeGen",
                "Small molecule generative diffusion model for target inhibition",
                "PyTorch, RDKit, FastAPI",
            ),
            (
                "CellSegment",
                "Fluorescence microscopy single-cell segmentation and count tool",
                "PyTorch, Cellpose, OpenCV",
            ),
            (
                "BioGraph",
                "Biomedical literature knowledge graph knowledge extraction agent",
                "Python, LangChain, Neo4j",
            ),
            (
                "LabInventory",
                "Smart barcode and cold-storage biological specimen tracker",
                "React, Node.js, SQLite",
            ),
            (
                "PhyloTree",
                "Real-time viral strain phylogenetic tree evolution visualizer",
                "JavaScript, D3.js, Python",
            ),
            (
                "MicrobiomeAI",
                "Gut microbiome taxonomic profiling and dietary recommendation assistant",
                "Python, Scikit-Learn, Flask",
            ),
        ],
    },
]


def seed(db: Session) -> None:
    if db.get(Event, "evt_01") and db.get(Event, "evt_10"):
        _write_toml(db)
        _print_logins(db)
        return

    now = utcnow()
    all_projects_meta = []

    # ---------------------------------------------------------
    # 1. CORE ORGANIZER AND ADMIN USERS
    # ---------------------------------------------------------
    organizer = _user(db, "org_1", "organizer@hackforge.local", "Organizer")
    admin = _user(db, "adm_1", "admin@hackforge.local", "Admin")

    # ---------------------------------------------------------
    # 2. SEED evt_01 FROM fixtures.json (Sample Hack 2026 - Finished)
    # ---------------------------------------------------------
    data = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    event_data = data["event"]

    evt_01 = Event(
        id=event_data["id"],
        name=event_data["name"],
        tagline="Official DOGFOOD 2026 Systems & Developer Tooling Hackathon",
        banner_image_path="/static/banners/evt_01.jpg",
        description_markdown="Welcome to **Sample Hack 2026**, the premier hackathon for developer tools, systems engineering, and distributed architecture.",
        rules_markdown="All submissions must be open source. Teams of 1–3 members. Standard code of conduct applies.",
        event_starts=parse_iso_utc("2026-02-05T00:00:00Z"),
        event_ends=parse_iso_utc("2026-03-08T18:00:00Z"),
        registrations_open=parse_iso_utc("2026-01-15T00:00:00Z"),
        registrations_close=parse_iso_utc("2026-02-05T00:00:00Z"),
        submissions_open=parse_iso_utc("2026-02-05T00:00:00Z"),
        submissions_close=parse_iso_utc(event_data.get("submissions_close")),
        judging_open=parse_iso_utc("2026-03-01T18:00:00Z"),
        judging_close=parse_iso_utc("2026-03-08T18:00:00Z"),
        results_date=parse_iso_utc("2026-03-10T12:00:00Z"),
        results_published=False,  # Finished hackathon (judging closed), allows voting tests
        community_voting_enabled=True,
    )
    db.add(evt_01)
    db.flush()

    _member(db, evt_01.id, organizer.id, "organizer")
    _member(db, evt_01.id, admin.id, "admin")

    track_map_01 = {}
    for track in data.get("tracks") or []:
        trk = Track(
            id=track["id"],
            event_id=evt_01.id,
            name=track["name"],
            prize=track.get("prize") or "Track Winner Prize ($3,000)",
        )
        db.add(trk)
        track_map_01[trk.id] = trk.name

    for judge in data.get("judges") or []:
        user = _user(db, judge["id"], judge["email"], judge["name"])
        _member(db, evt_01.id, user.id, "judge")
        for track_id in judge.get("tracks") or []:
            db.add(JudgeTrack(event_id=evt_01.id, judge_id=user.id, track_id=track_id))

    first_participant_id = None
    for team in data.get("teams") or []:
        team_obj = Team(
            id=team["id"], event_id=evt_01.id, name=team["name"], invite_token=None
        )
        db.add(team_obj)
        db.flush()
        # Enforce team members from 1-3
        team_members_list = (team.get("members") or [])[:3]
        for index, email in enumerate(team_members_list):
            local = email.split("@")[0]
            if first_participant_id is None:
                user_id = "prt_1"
                first_participant_id = user_id
            else:
                user_id = f"usr_{local}"
            user = _user(db, user_id, email, local)
            _member(db, evt_01.id, user.id, "participant")
            db.add(TeamMember(team_id=team["id"], user_id=user.id))
            if index == 0:
                team_obj.leader_id = user.id

    for project in data.get("projects") or []:
        prj_id = project["id"]
        cover_path = f"/static/projects/{prj_id}.jpg"
        db.add(
            Project(
                id=prj_id,
                event_id=evt_01.id,
                team_id=project["team"],
                track_id=project.get("track"),
                title=project.get("title") or "",
                summary=project.get("summary")
                or "High performance developer tool built for modern engineering workflows.",
                repo_url=project.get("repo_url")
                or "https://github.com/hackforge/sample-project",
                demo_url=project.get("demo_url") or "https://demo.hackforge.dev",
                cover_image_path=cover_path,
                tech_stack="Python, FastAPI, TypeScript, Docker",
                is_draft=False,
                submitted_at=parse_iso_utc(project.get("submitted_at")),
                is_disqualified=False,
            )
        )
        all_projects_meta.append(
            {
                "id": prj_id,
                "title": project.get("title") or "Project",
                "tech_stack": "Python, FastAPI, TypeScript, Docker",
                "track_name": track_map_01.get(project.get("track"), "Developer Tools"),
            }
        )

    weights = {"functionality": 40, "quality": 30, "innovation": 30}
    for name, weight in weights.items():
        db.add(
            RubricCriteria(
                id=f"{evt_01.id}:{name}",
                event_id=evt_01.id,
                name=name.title(),
                weight=weight,
            )
        )
    db.flush()

    for score in data.get("scores") or []:
        judge_id = score.get("judge")
        project_id = score.get("project")
        comment = score.get("comment")
        for criterion, value in (score.get("criteria") or {}).items():
            db.add(
                Score(
                    event_id=evt_01.id,
                    judge_id=judge_id,
                    project_id=project_id,
                    criteria_id=f"{evt_01.id}:{criterion}",
                    value=int(value),
                    comment=comment,
                )
            )

    _audit(db, evt_01.id, "Seeded Sample Hack 2026 from fixtures.json")

    # ---------------------------------------------------------
    # 3. PREPARE 5 SHARED JUDGES FOR FINISHED EVENTS (evt_01 .. evt_05)
    # ---------------------------------------------------------
    # Closed hackathons have distinct non-overlapping timelines and share these 5 judges
    shared_judges = [
        _user(db, "jdg_01", "tomas.varga@example.org", "Tomas Varga"),
        _user(db, "jdg_02", "wei.lindqvist@example.org", "Wei Lindqvist"),
        _user(db, "jdg_03", "elena.rostova@example.org", "Elena Rostova"),
        _user(db, "jdg_04", "marcus.adebayo@example.org", "Marcus Adebayo"),
        _user(db, "jdg_05", "priya.nair@example.org", "Priya Nair"),
    ]

    # ---------------------------------------------------------
    # 4. SEED THE OTHER 9 EVENTS (evt_02 .. evt_10)
    # ---------------------------------------------------------
    for edata in OTHER_EVENTS_DATA:
        eid = edata["id"]
        etype = edata["type"]

        # Calculate Dates
        if etype == "finished":
            s_start = parse_iso_utc(edata["start_iso"])
            s_close = parse_iso_utc(edata["close_iso"])
            j_open = s_close
            j_close = parse_iso_utc(edata["judge_close_iso"])
            res_date = j_close + timedelta(days=2)
            reg_open = s_start - timedelta(days=15)
            reg_close = s_start
        elif etype == "ongoing":
            s_start = now - timedelta(days=edata["days_ago_open"])
            s_close = now + timedelta(days=edata["days_ahead_close"])
            j_open = s_close
            j_close = now + timedelta(days=edata["days_ahead_judge_close"])
            res_date = j_close + timedelta(days=2)
            reg_open = s_start - timedelta(days=7)
            reg_close = s_close
        else:  # upcoming
            reg_open = now - timedelta(days=edata["days_ago_reg_open"])
            reg_close = now + timedelta(days=edata["days_ahead_reg_close"])
            s_start = now + timedelta(days=edata["days_ahead_sub_open"])
            s_close = now + timedelta(days=edata["days_ahead_sub_close"])
            j_open = s_close
            j_close = now + timedelta(days=edata["days_ahead_judge_close"])
            res_date = j_close + timedelta(days=3)

        event = Event(
            id=eid,
            name=edata["name"],
            tagline=edata["tagline"],
            banner_image_path=f"/static/banners/{eid}.jpg",
            description_markdown=f"Welcome to **{edata['name']}**! Join industry mentors, developers, and builders worldwide in crafting transformative solutions for {edata['tagline']}.",
            rules_markdown="All submissions must be original code created during the hackathon. Teams must consist of 1–3 members. Code must be hosted on GitHub or GitLab.",
            event_starts=s_start,
            event_ends=j_close,
            registrations_open=reg_open,
            registrations_close=reg_close,
            submissions_open=s_start,
            submissions_close=s_close,
            judging_open=j_open,
            judging_close=j_close,
            results_date=res_date,
            results_published=edata["results_published"],
        )
        db.add(event)
        db.flush()

        _member(db, eid, organizer.id, "organizer")
        _member(db, eid, admin.id, "admin")

        # Tracks
        track_objs = []
        for t_idx, (t_name, t_prize) in enumerate(edata["tracks"], start=1):
            trk = Track(
                id=f"trk_{eid}_{t_idx:02d}",
                event_id=eid,
                name=t_name,
                prize=t_prize,
            )
            db.add(trk)
            track_objs.append(trk)
        db.flush()

        # 5 Judges per Hackathon
        if edata["judge_prefix"] == "shared":
            event_judges = shared_judges
        else:
            j_pfx = edata["judge_prefix"]
            event_judges = [
                _user(
                    db,
                    f"jdg_{j_pfx}_1",
                    f"judge1.{j_pfx}@hackforge.dev",
                    f"Judge Alpha ({j_pfx})",
                ),
                _user(
                    db,
                    f"jdg_{j_pfx}_2",
                    f"judge2.{j_pfx}@hackforge.dev",
                    f"Judge Beta ({j_pfx})",
                ),
                _user(
                    db,
                    f"jdg_{j_pfx}_3",
                    f"judge3.{j_pfx}@hackforge.dev",
                    f"Judge Gamma ({j_pfx})",
                ),
                _user(
                    db,
                    f"jdg_{j_pfx}_4",
                    f"judge4.{j_pfx}@hackforge.dev",
                    f"Judge Delta ({j_pfx})",
                ),
                _user(
                    db,
                    f"jdg_{j_pfx}_5",
                    f"judge5.{j_pfx}@hackforge.dev",
                    f"Judge Epsilon ({j_pfx})",
                ),
            ]

        for j in event_judges:
            _member(db, eid, j.id, "judge")
            # Assign judges across all event tracks
            for trk in track_objs:
                db.add(JudgeTrack(event_id=eid, judge_id=j.id, track_id=trk.id))
        db.flush()

        # Rubrics
        rubric_objs = []
        for r_name, r_weight in edata["rubric"]:
            rub = RubricCriteria(
                id=f"rub_{eid}_{r_name.lower().replace(' ', '_')[:12]}",
                event_id=eid,
                name=r_name,
                weight=r_weight,
            )
            db.add(rub)
            rubric_objs.append(rub)
        db.flush()

        # 10 Teams & 10 Projects per Hackathon (Members 1-3)
        created_projects = []
        for p_idx, (p_title, p_summary, p_tech) in enumerate(
            edata["projects"], start=1
        ):
            team_id = f"tem_{eid}_{p_idx:02d}"
            team = Team(
                id=team_id,
                event_id=eid,
                name=f"{p_title} Collective",
                invite_token=uuid.uuid4().hex[:12],
            )
            db.add(team)
            db.flush()

            # Teams of 1 to 3 members
            # Varied sizes: 2, 3, 1, 2, 3, 1, 2, 3, 2, 1
            member_counts = [2, 3, 1, 2, 3, 1, 2, 3, 2, 1]
            num_members = member_counts[(p_idx - 1) % len(member_counts)]

            for m_idx in range(1, num_members + 1):
                # Ensure prt_1 is in some teams for testing
                if (
                    eid == "evt_06"
                    and p_idx == 1
                    and m_idx == 1
                    or eid == "evt_08"
                    and p_idx == 1
                    and m_idx == 1
                ):
                    u = db.get(User, "prt_1")
                else:
                    u_email = f"builder_{eid}_{p_idx}_{m_idx}@hackforge.dev"
                    u = _user(
                        db,
                        f"usr_{eid}_{p_idx}_{m_idx}",
                        u_email,
                        f"Builder {p_title} {m_idx}",
                    )

                _member(db, eid, u.id, "participant")
                db.add(TeamMember(team_id=team.id, user_id=u.id))
                if m_idx == 1:
                    team.leader_id = u.id

            # Associate with a Track
            assigned_track = track_objs[(p_idx - 1) % len(track_objs)]
            prj_id = f"prj_{eid}_{p_idx:02d}"
            cover_path = f"/static/projects/{prj_id}.jpg"

            proj = Project(
                id=prj_id,
                event_id=eid,
                team_id=team.id,
                track_id=assigned_track.id,
                title=p_title,
                summary=p_summary,
                repo_url=f"https://github.com/hackforge/{p_title.lower().replace(' ', '-')}",
                demo_url=f"https://{p_title.lower().replace(' ', '-')}.hackforge.dev",
                cover_image_path=cover_path,
                tech_stack=p_tech,
                is_draft=False,
                submitted_at=s_start + timedelta(days=2),
                is_disqualified=False,
            )
            db.add(proj)
            created_projects.append(proj)

            all_projects_meta.append(
                {
                    "id": prj_id,
                    "title": p_title,
                    "tech_stack": p_tech,
                    "track_name": assigned_track.name,
                }
            )
        db.flush()

        # For finished hackathons, seed scores from the 5 judges
        # Upcoming hackathons have NO scores so rubric can be edited!
        if etype == "finished":
            for proj in created_projects:
                for j_idx, judge in enumerate(event_judges):
                    # Deterministic realistic score
                    base_val = 75 + (int(hashlib_seed(f"{proj.id}_{judge.id}")) % 22)
                    for rub in rubric_objs:
                        variance = (int(hashlib_seed(f"{rub.id}_{judge.id}")) % 7) - 3
                        val = max(50, min(100, base_val + variance))
                        db.add(
                            Score(
                                event_id=eid,
                                judge_id=judge.id,
                                project_id=proj.id,
                                criteria_id=rub.id,
                                value=val,
                                comment="Great demonstration of engineering depth, execution clarity, and architecture.",
                            )
                        )

        _audit(db, eid, f"Seeded {edata['name']} ({edata['type']})")

    db.commit()

    # ---------------------------------------------------------
    # 5. GENERATE & ENSURE ALL 10 EVENT BANNERS + 130 PROJECT COVERS
    # ---------------------------------------------------------
    ensure_all_assets(all_projects_meta)

    _write_toml(db)
    _print_logins(db)


def hashlib_seed(val: str) -> int:
    import hashlib

    return int(hashlib.md5(val.encode("utf-8")).hexdigest()[:6], 16)


def _print_logins(db: Session) -> None:
    rows = [
        ("organizer", "org_1"),
        ("judge_a", "jdg_01"),
        ("judge_b", "jdg_02"),
        ("participant", "prt_1"),
        ("admin", "adm_1"),
    ]
    port = os.environ.get("PORT", "8080")
    base_url = os.environ.get("BASE_URL", f"http://localhost:{port}")
    print("\n================ HACKFORGE SEEDED ================")
    print(f"  Portal URL:  {base_url}")
    print(f"  API Docs:    {base_url}/docs\n")
    print("Test Logins (any password accepted for fixture/seed accounts):")
    for label, user_id in rows:
        user = db.get(User, user_id)
        if user is None:
            continue
        token = make_session_token(user.id)
        print(f"  {label:12} Email: {user.email:30} Cookie: session={token[:25]}...")
    print("==================================================\n")


def _write_toml(db: Session) -> None:
    def cookie(user_id: str) -> str:
        return f"Cookie: session={make_session_token(user_id)}"

    body = f"""[portal]
base_url = "http://localhost:8080"

[tiers]
claimed = ["T1", "T2", "T3", "T4"]
pitch = "Run your hackathon without the spreadsheet chaos."

[auth]
organizer   = "{cookie("org_1")}"
judge_a     = "{cookie("jdg_01")}"
judge_b     = "{cookie("jdg_02")}"
participant = "{cookie("prt_1")}"

[routes]
gallery      = "/projects"
submit       = "/projects/new"
judge_scores = "/api/judge/scores"
peer_scores  = "/api/judge/scores?judge=jdg_01"
csv_export   = "/api/export.csv"
"""
    TOML_PATH.write_text(body, encoding="utf-8")


if __name__ == "__main__":
    from src.db import SessionLocal, init_db

    init_db()
    session = SessionLocal()
    try:
        seed(session)
    finally:
        session.close()
