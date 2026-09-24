import streamlit as st
import os
import bcrypt
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import (create_engine, Column, Integer, String, Date, DateTime,
                        Float, Text, ForeignKey)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.pool import NullPool
from pathlib import Path

# --- Database path (works locally and on Streamlit Cloud) ---
BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "database"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "mathshub.db"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

# --- Engine: NullPool for Supabase pooler; check_same_thread for SQLite ---
_engine_kwargs = {"poolclass": NullPool}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False)
    full_name = Column(String(128))
    created_at = Column(DateTime, default=datetime.utcnow)


class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    admission_no = Column(String(32), unique=True)
    roll_no = Column(String(16))
    class_name = Column(String(16))
    section = Column(String(8))
    curriculum = Column(String(32))
    user = relationship("User")


class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    date = Column(Date, index=True)
    status = Column(String(16))
    marked_by = Column(Integer, ForeignKey("users.id"))


class Curriculum(Base):
    __tablename__ = "curricula"
    id = Column(Integer, primary_key=True)
    name = Column(String(64))
    description = Column(Text)


class Topic(Base):
    __tablename__ = "topics"
    id = Column(Integer, primary_key=True)
    curriculum_id = Column(Integer, ForeignKey("curricula.id"))
    name = Column(String(128))
    class_level = Column(String(16))
    parent_id = Column(Integer, ForeignKey("topics.id"), nullable=True)
    status = Column(String(24), default="not_started")
    progress = Column(Float, default=0.0)


Base.metadata.create_all(bind=engine)


def seed():
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add_all([
                User(username="teacher", password_hash=hash_password("teacher123"),
                     role="teacher", full_name="Ms. Math Teacher"),
                User(username="student1", password_hash=hash_password("student123"),
                     role="student", full_name="Aarav Sharma"),
                User(username="parent1", password_hash=hash_password("parent123"),
                     role="parent", full_name="Mr. Sharma"),
            ])
            db.commit()
            s_user = db.query(User).filter_by(username="student1").first()
            db.add(Student(user_id=s_user.id, admission_no="ADM001", roll_no="1",
                           class_name="XII", section="A", curriculum="CBSE"))
            db.commit()
            c = Curriculum(name="CBSE", description="Central Board of Secondary Education")
            db.add(c); db.commit()
            calculus = Topic(curriculum_id=c.id, name="Calculus",
                             class_level="XII", status="in_progress", progress=0.3)
            db.add(calculus); db.commit()
            db.add_all([
                Topic(curriculum_id=c.id, parent_id=calculus.id, name="Continuity",
                      class_level="XII", status="completed", progress=1.0),
                Topic(curriculum_id=c.id, parent_id=calculus.id, name="Differentiability",
                      class_level="XII", status="in_progress", progress=0.5),
                Topic(curriculum_id=c.id, parent_id=calculus.id,
                      name="Applications of Derivatives",
                      class_level="XII", status="not_started", progress=0.0),
            ])
            db.commit()
    finally:
        db.close()


seed()


def authenticate(username, password):
    db = SessionLocal()
    try:
        u = db.query(User).filter_by(username=username).first()
        if u and verify_password(password, u.password_hash):
            return {"id": u.id, "username": u.username,
                    "role": u.role, "full_name": u.full_name}
        return None
    finally:
        db.close()


def login_page():
    st.title("MathsHub")
    st.caption("AI Mathematics Teaching & Learning Platform")
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in"):
            user = authenticate(u, p)
            if user:
                st.session_state["user"] = user
                st.rerun()
            else:
                st.error("Invalid username or password.")


def dashboard_page():
    st.header("Teacher Dashboard")
    st.caption(date.today().strftime("%A, %d %B %Y"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Today's Classes", 3)
    c2.metric("Pending Assignments", 14)
    c3.metric("Answer Sheets to Review", 8)
    c4.metric("Lesson Plans Pending", 2)
    st.subheader("Alerts")
    st.warning("3 students showing declining performance")
    st.warning("5 students have missed two consecutive classes")
    st.subheader("Today's Timetable")
    st.table([
        {"Time": "8:00 AM",  "Class": "XII Mathematics"},
        {"Time": "10:00 AM", "Class": "XI Mathematics"},
        {"Time": "12:00 PM", "Class": "IX Mathematics"},
    ])


def students_page():
    st.header("Students")
    db = SessionLocal()
    try:
        rows = db.query(Student).all()
        if not rows:
            st.info("No students yet.")
            return
        data = []
        for s in rows:
            name = s.user.full_name if s.user else "-"
            data.append({"Admission No": s.admission_no, "Name": name,
                         "Class": s.class_name, "Section": s.section,
                         "Curriculum": s.curriculum})
        st.dataframe(data)
    finally:
        db.close()


def attendance_page():
    st.header("Attendance")
    st.caption(date.today().strftime("%A, %d %B %Y"))
    db = SessionLocal()
    try:
        students = db.query(Student).all()
        if not students:
            st.info("No students yet.")
            return
        with st.form("attendance_form"):
            statuses = {}
            for s in students:
                name = s.user.full_name if s.user else f"Student #{s.id}"
                statuses[s.id] = st.radio(
                    f"{name} ({s.admission_no})",
                    ["present", "absent", "late", "excused"],
                    horizontal=True, key=f"att_{s.id}")
            if st.form_submit_button("Save Attendance"):
                for sid, status in statuses.items():
                    existing = db.query(Attendance).filter_by(
                        student_id=sid, date=date.today()).first()
                    if existing:
                        existing.status = status
                    else:
                        db.add(Attendance(student_id=sid, date=date.today(),
                                          status=status,
                                          marked_by=st.session_state["user"]["id"]))
                db.commit()
                st.success("Attendance saved.")
    finally:
        db.close()


def curriculum_page():
    st.header("Curriculum")
    db = SessionLocal()
    try:
        curricula = db.query(Curriculum).all()
        for c in curricula:
            st.subheader(c.name)
            topics = db.query(Topic).filter_by(
                curriculum_id=c.id, parent_id=None).all()
            for t in topics:
                st.markdown(
                    f"### {t.name} ({t.class_level}) - {t.status} - "
                    f"{int(t.progress * 100)}%")
                children = db.query(Topic).filter_by(parent_id=t.id).all()
                for ch in children:
                    st.markdown(
                        f"- {ch.name} - {ch.status} - "
                        f"{int(ch.progress * 100)}%")
    finally:
        db.close()


def ai_assistant_page():
    st.header("AI Teaching Assistant")
    st.info("AI features require an OpenAI API key. "
            "Add it to the .env file and restart the app.")
    topic = st.text_input("Topic", "Applications of Derivatives")
    cls = st.selectbox("Class",
                       ["VI", "VII", "VIII", "IX", "X", "XI", "XII"], index=6)
    if st.button("Generate Lesson"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            st.error("Please add your OPENAI_API_KEY to the .env file "
                     "and restart the app.")
            return
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        with st.spinner("Generating lesson plan..."):
            resp = client.chat.completions.create(
                model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o"),
                temperature=0.4,
                messages=[
                    {"role": "system",
                     "content": ("You are an expert mathematics teacher. "
                                 "Produce a complete 45-minute lesson plan "
                                 "with objectives, starter, explanation, "
                                 "examples, activity, exit ticket and "
                                 "homework. Use LaTeX for math.")},
                    {"role": "user", "content": f"Topic: {topic}, Class: {cls}"},
                ],
            )
            st.markdown(resp.choices[0].message.content)


st.set_page_config(page_title="MathsHub", page_icon="M", layout="wide")

if "user" not in st.session_state:
    login_page()
else:
    user = st.session_state["user"]
    st.sidebar.markdown(f"### {user['full_name'] or user['username']}")
    st.sidebar.caption(f"Role: {user['role']}")
    page = st.sidebar.radio(
        "Navigate",
        ["Dashboard", "Students", "Attendance", "Curriculum", "AI Assistant"])
    if st.sidebar.button("Log out"):
        st.session_state.clear()
        st.rerun()
    if page == "Dashboard":
        dashboard_page()
    elif page == "Students":
        students_page()
    elif page == "Attendance":
        attendance_page()
    elif page == "Curriculum":
        curriculum_page()
    elif page == "AI Assistant":
        ai_assistant_page()

