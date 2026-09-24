import streamlit as st
import os
import bcrypt
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import (create_engine, Column, Integer, String, Date, DateTime,
                        Float, Text, ForeignKey, UniqueConstraint)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.pool import NullPool
from pathlib import Path

# --- Database path (works locally and on Streamlit Cloud) ---
BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "database"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "mathshub.db"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

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


# ---------------- Models ----------------

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False)
    full_name = Column(String(128))
    created_at = Column(DateTime, default=datetime.utcnow)


class SchoolClass(Base):
    __tablename__ = "classes"
    id = Column(Integer, primary_key=True)
    name = Column(String(16), nullable=False)
    section = Column(String(8), nullable=False)
    curriculum = Column(String(32), default="CBSE")
    __table_args__ = (UniqueConstraint("name", "section", name="uq_class_section"),)


class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, unique=True)


class ClassSubject(Base):
    __tablename__ = "class_subjects"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id"))
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    __table_args__ = (UniqueConstraint("class_id", "subject_id",
                                       name="uq_class_subject"),)


class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    admission_no = Column(String(32), unique=True)
    roll_no = Column(String(16))
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)
    class_name = Column(String(16))
    section = Column(String(8))
    curriculum = Column(String(32))
    dob = Column(Date, nullable=True)
    guardian_name = Column(String(128), nullable=True)
    guardian_phone = Column(String(32), nullable=True)
    user = relationship("User", lazy="joined")
    klass = relationship("SchoolClass")
    observations = relationship("Observation", back_populates="student",
                                cascade="all, delete-orphan")


class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)
    date = Column(Date, index=True)
    status = Column(String(16))
    marked_by = Column(Integer, ForeignKey("users.id"))


class Observation(Base):
    __tablename__ = "observations"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    author_id = Column(Integer, ForeignKey("users.id"))
    category = Column(String(32))
    note = Column(Text)
    is_private = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    student = relationship("Student", back_populates="observations")


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




class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    body = Column(Text)
    answer_hint = Column(Text)
    marks = Column(Integer, default=5)
    topic = Column(String(128))
    difficulty = Column(String(16), default="medium")
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    due_date = Column(Date, nullable=True)


class QuestionAssignment(Base):
    __tablename__ = "question_assignments"
    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id"))
    class_id = Column(Integer, ForeignKey("classes.id"))
    assigned_on = Column(Date, default=date.today)
    assigned_by = Column(Integer, ForeignKey("users.id"))
    question = relationship("Question", lazy="joined")
    klass = relationship("SchoolClass", lazy="joined")


class QuestionSubmission(Base):
    __tablename__ = "question_submissions"
    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("question_assignments.id"))
    student_id = Column(Integer, ForeignKey("students.id"))
    answer_text = Column(Text)
    file_path = Column(String(255), nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    marks_awarded = Column(Integer, nullable=True)
    feedback = Column(Text, nullable=True)
    status = Column(String(16), default="submitted")
    assignment = relationship("QuestionAssignment", lazy="joined")
    student = relationship("Student", lazy="joined")


Base.metadata.create_all(bind=engine)


# ---------------- Seed ----------------

def seed():
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add(User(username="teacher", password_hash=hash_password("teacher123"),
                        role="teacher", full_name="Ms. Math Teacher"))
            db.commit()
        if db.query(Subject).count() == 0:
            for s in ["Mathematics", "Physics", "Chemistry", "Biology",
                      "Computer Science", "English"]:
                db.add(Subject(name=s))
            db.commit()
        if db.query(SchoolClass).count() == 0:
            for cls in ["VI", "VII", "VIII", "IX", "X", "XI", "XII"]:
                for sec in ["A", "B"]:
                    db.add(SchoolClass(name=cls, section=sec, curriculum="CBSE"))
            db.commit()
        if db.query(Curriculum).count() == 0:
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


# ---------------- Helpers ----------------

def generate_username(full_name, admission_no):
    base = "".join(ch for ch in (full_name or admission_no or "student").lower()
                   if ch.isalnum())[:16] or "student"
    db = SessionLocal()
    try:
        candidate = base
        n = 1
        while db.query(User).filter_by(username=candidate).first():
            n += 1
            candidate = f"{base}{n}"
        return candidate
    finally:
        db.close()


def add_student(full_name, admission_no, roll_no, class_id, curriculum,
                dob=None, guardian_name=None, guardian_phone=None, password=None):
    db = SessionLocal()
    try:
        if db.query(Student).filter_by(admission_no=admission_no).first():
            return False, f"Admission number {admission_no} already exists.", None
        klass = db.query(SchoolClass).filter_by(id=class_id).first()
        if not klass:
            return False, "Please select a valid class-section.", None
        username = generate_username(full_name, admission_no)
        password = password or "student123"
        user = User(username=username, password_hash=hash_password(password),
                    role="student", full_name=full_name)
        db.add(user); db.commit(); db.refresh(user)
        s = Student(user_id=user.id, admission_no=admission_no, roll_no=roll_no,
                    class_id=klass.id, class_name=klass.name, section=klass.section,
                    curriculum=curriculum, dob=dob, guardian_name=guardian_name,
                    guardian_phone=guardian_phone)
        db.add(s); db.commit()
        return True, f"Added {full_name} (username: {username})", username
    except Exception as e:
        db.rollback()
        return False, f"Error: {e}", None
    finally:
        db.close()


def update_student(student_id, full_name=None, roll_no=None, class_id=None,
                   curriculum=None, dob=None, guardian_name=None,
                   guardian_phone=None):
    db = SessionLocal()
    try:
        s = db.query(Student).filter_by(id=student_id).first()
        if not s:
            return False, "Student not found."
        if s.user and full_name is not None:
            s.user.full_name = full_name
        if roll_no is not None:        s.roll_no = roll_no
        if class_id is not None:
            klass = db.query(SchoolClass).filter_by(id=class_id).first()
            if klass:
                s.class_id = klass.id
                s.class_name = klass.name
                s.section = klass.section
        if curriculum is not None:     s.curriculum = curriculum
        if dob is not None:            s.dob = dob
        if guardian_name is not None:  s.guardian_name = guardian_name
        if guardian_phone is not None: s.guardian_phone = guardian_phone
        db.commit()
        return True, "Updated."
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


def delete_student(student_id):
    db = SessionLocal()
    try:
        s = db.query(Student).filter_by(id=student_id).first()
        if not s:
            return False, "Student not found."
        db.query(Attendance).filter_by(student_id=student_id).delete()
        db.query(Observation).filter_by(student_id=student_id).delete()
        if s.user:
            db.delete(s.user)
        db.delete(s)
        db.commit()
        return True, "Deleted."
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


def add_class(name, section, curriculum):
    db = SessionLocal()
    try:
        if db.query(SchoolClass).filter_by(name=name, section=section).first():
            return False, f"Class {name}-{section} already exists."
        db.add(SchoolClass(name=name, section=section, curriculum=curriculum))
        db.commit()
        return True, f"Created {name}-{section}."
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


def delete_class(class_id):
    db = SessionLocal()
    try:
        n = db.query(Student).filter_by(class_id=class_id).count()
        if n > 0:
            return False, f"Cannot delete  {n} students in this class."
        db.query(ClassSubject).filter_by(class_id=class_id).delete()
        db.query(SchoolClass).filter_by(id=class_id).delete()
        db.commit()
        return True, "Deleted."
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


def add_subject(name):
    db = SessionLocal()
    try:
        if db.query(Subject).filter_by(name=name).first():
            return False, f"Subject '{name}' already exists."
        db.add(Subject(name=name))
        db.commit()
        return True, f"Created subject {name}."
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


def delete_subject(subject_id):
    db = SessionLocal()
    try:
        db.query(ClassSubject).filter_by(subject_id=subject_id).delete()
        db.query(Subject).filter_by(id=subject_id).delete()
        db.commit()
        return True, "Deleted."
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


def assign_subject_to_class(class_id, subject_id):
    db = SessionLocal()
    try:
        if db.query(ClassSubject).filter_by(
                class_id=class_id, subject_id=subject_id).first():
            return False, "Already assigned."
        db.add(ClassSubject(class_id=class_id, subject_id=subject_id))
        db.commit()
        return True, "Assigned."
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


def unassign_subject(class_id, subject_id):
    db = SessionLocal()
    try:
        db.query(ClassSubject).filter_by(
            class_id=class_id, subject_id=subject_id).delete()
        db.commit()
        return True, "Removed."
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


def save_attendance(student_id, class_id, status, marked_by, on_date=None):
    db = SessionLocal()
    try:
        on_date = on_date or date.today()
        existing = db.query(Attendance).filter_by(
            student_id=student_id, date=on_date).first()
        if existing:
            existing.status = status
            existing.class_id = class_id
            existing.marked_by = marked_by
        else:
            db.add(Attendance(student_id=student_id, class_id=class_id,
                              date=on_date, status=status, marked_by=marked_by))
        db.commit()
    finally:
        db.close()


def get_attendance_for_date(class_id, on_date):
    db = SessionLocal()
    try:
        return {a.student_id: a.status for a in
                db.query(Attendance).filter_by(class_id=class_id, date=on_date).all()}
    finally:
        db.close()


def student_attendance_summary(student_id, start=None, end=None):
    db = SessionLocal()
    try:
        q = db.query(Attendance).filter_by(student_id=student_id)
        if start: q = q.filter(Attendance.date >= start)
        if end:   q = q.filter(Attendance.date <= end)
        rows = q.all()
        total = len(rows)
        present = sum(1 for r in rows if r.status in ("present", "late"))
        absent = sum(1 for r in rows if r.status == "absent")
        late = sum(1 for r in rows if r.status == "late")
        excused = sum(1 for r in rows if r.status == "excused")
        pct = round(100.0 * present / total, 1) if total else 0.0
        return {"total": total, "present": present, "absent": absent,
                "late": late, "excused": excused, "percent": pct}
    finally:
        db.close()


def consecutive_absences(student_id):
    db = SessionLocal()
    try:
        rows = db.query(Attendance).filter_by(student_id=student_id).order_by(
            Attendance.date.desc()).limit(20).all()
        count = 0
        for r in rows:
            if r.status == "absent":
                count += 1
            else:
                break
        return count
    finally:
        db.close()


def class_attendance_summary(class_id, start=None, end=None):
    db = SessionLocal()
    try:
        students = db.query(Student).filter_by(class_id=class_id).order_by(
            Student.roll_no).all()
        out = []
        for s in students:
            name = s.user.full_name if s.user else "-"
            summ = student_attendance_summary(s.id, start, end)
            row = {"Student": name, "Admission": s.admission_no, "Roll": s.roll_no}
            row.update(summ)
            out.append(row)
        return out
    finally:
        db.close()


def attendance_records(student_id, start=None, end=None):
    db = SessionLocal()
    try:
        q = db.query(Attendance).filter_by(student_id=student_id)
        if start: q = q.filter(Attendance.date >= start)
        if end:   q = q.filter(Attendance.date <= end)
        rows = q.order_by(Attendance.date.desc()).all()
        return [{"Date": r.date, "Status": r.status} for r in rows]
    finally:
        db.close()


def add_observation(student_id, author_id, category, note, is_private=True):
    db = SessionLocal()
    try:
        db.add(Observation(student_id=student_id, author_id=author_id,
                           category=category, note=note,
                           is_private=1 if is_private else 0))
        db.commit()
        return True, "Observation saved."
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


def get_observations(student_id):
    db = SessionLocal()
    try:
        return db.query(Observation).filter_by(student_id=student_id).order_by(
            Observation.created_at.desc()).all()
    finally:
        db.close()


def delete_observation(obs_id):
    db = SessionLocal()
    try:
        db.query(Observation).filter_by(id=obs_id).delete()
        db.commit()
        return True, "Deleted."
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


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




def create_question(title, body, answer_hint, marks, topic, difficulty,
                    created_by, due_date=None):
    db = SessionLocal()
    try:
        q = Question(title=title, body=body, answer_hint=answer_hint,
                     marks=marks, topic=topic, difficulty=difficulty,
                     created_by=created_by, due_date=due_date)
        db.add(q); db.commit(); db.refresh(q)
        return True, "Question created (ID %d)" % q.id, q.id
    except Exception as e:
        db.rollback()
        return False, str(e), None
    finally:
        db.close()


def assign_question(question_id, class_id, assigned_by):
    db = SessionLocal()
    try:
        existing = db.query(QuestionAssignment).filter_by(
            question_id=question_id, class_id=class_id).first()
        if existing:
            return False, "Already assigned to this class."
        a = QuestionAssignment(question_id=question_id, class_id=class_id,
                               assigned_by=assigned_by)
        db.add(a); db.commit()
        return True, "Assigned."
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


def unassign_question(assignment_id):
    db = SessionLocal()
    try:
        db.query(QuestionSubmission).filter_by(
            assignment_id=assignment_id).delete()
        db.query(QuestionAssignment).filter_by(id=assignment_id).delete()
        db.commit()
        return True, "Unassigned."
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


def delete_question(question_id):
    db = SessionLocal()
    try:
        db.query(QuestionAssignment).filter_by(question_id=question_id).delete()
        db.query(Question).filter_by(id=question_id).delete()
        db.commit()
        return True, "Deleted."
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


def all_questions():
    db = SessionLocal()
    try:
        return db.query(Question).order_by(Question.created_at.desc()).all()
    finally:
        db.close()


def assignments_for_student(student_id):
    db = SessionLocal()
    try:
        student = db.query(Student).filter_by(id=student_id).first()
        if not student or not student.class_id:
            return []
        return db.query(QuestionAssignment).filter_by(
            class_id=student.class_id).order_by(
            QuestionAssignment.assigned_on.desc()).all()
    finally:
        db.close()


def submission_status(assignment_id, student_id):
    db = SessionLocal()
    try:
        return db.query(QuestionSubmission).filter_by(
            assignment_id=assignment_id, student_id=student_id).first()
    finally:
        db.close()


def submit_answer(assignment_id, student_id, answer_text):
    db = SessionLocal()
    try:
        existing = db.query(QuestionSubmission).filter_by(
            assignment_id=assignment_id, student_id=student_id).first()
        if existing:
            existing.answer_text = answer_text
            existing.submitted_at = datetime.utcnow()
            existing.status = "submitted"
        else:
            db.add(QuestionSubmission(assignment_id=assignment_id,
                                      student_id=student_id,
                                      answer_text=answer_text))
        db.commit()
        return True, "Submitted."
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


def grade_submission(submission_id, marks, feedback):
    db = SessionLocal()
    try:
        s = db.query(QuestionSubmission).filter_by(id=submission_id).first()
        if not s:
            return False, "Submission not found."
        s.marks_awarded = marks
        s.feedback = feedback
        s.status = "graded"
        db.commit()
        return True, "Graded."
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


def submissions_for_assignment(assignment_id):
    db = SessionLocal()
    try:
        return db.query(QuestionSubmission).filter_by(
            assignment_id=assignment_id).all()
    finally:
        db.close()


def all_submissions():
    db = SessionLocal()
    try:
        return db.query(QuestionSubmission).order_by(
            QuestionSubmission.submitted_at.desc()).all()
    finally:
        db.close()



# ---------------- Pages ----------------

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
    db = SessionLocal()
    try:
        n_students = db.query(Student).count()
        n_classes = db.query(SchoolClass).count()
    finally:
        db.close()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Students", n_students)
    c2.metric("Class-Sections", n_classes)
    c3.metric("Pending Assignments", 14)
    c4.metric("Answer Sheets to Review", 8)
    st.subheader("Alerts")
    st.warning("3 students showing declining performance")
    st.warning("5 students have missed two consecutive classes")


def classes_page():
    st.header(" Classes & Subjects")
    tab_class, tab_subject, tab_assign = st.tabs(
        [" Classes", " Subjects", " Assign Subjects to Classes"])

    with tab_class:
        db = SessionLocal()
        try:
            classes = db.query(SchoolClass).order_by(
                SchoolClass.name, SchoolClass.section).all()
            rows = []
            for c in classes:
                n = db.query(Student).filter_by(class_id=c.id).count()
                rows.append({"Class": f"{c.name}-{c.section}",
                             "Curriculum": c.curriculum,
                             "Students": n, "class_id": c.id})
        finally:
            db.close()
        if rows:
            st.dataframe([{"Class": r["Class"], "Curriculum": r["Curriculum"],
                           "Students": r["Students"]} for r in rows],
                         use_container_width=True)
        else:
            st.info("No classes yet.")
        st.markdown("###  Add a class-section")
        with st.form("add_class_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            new_name = c1.selectbox("Class",
                ["VI", "VII", "VIII", "IX", "X", "XI", "XII"])
            new_sec = c2.text_input("Section", "A")
            new_curr = c3.selectbox("Curriculum",
                ["CBSE", "IBDP", "MYP", "IGCSE", "JEE", "IOQM", "Custom"])
            if st.form_submit_button("Create"):
                ok, msg = add_class(new_name, new_sec.strip(), new_curr)
                st.success(msg) if ok else st.error(msg)
                st.rerun()
        st.markdown("###  Delete a class-section")
        if rows:
            options = {f"{r['Class']} ({r['Students']} students)": r["class_id"]
                       for r in rows}
            choice = st.selectbox("Select", list(options.keys()), key="del_class")
            if st.button("Delete this class"):
                ok, msg = delete_class(options[choice])
                st.success(msg) if ok else st.error(msg)
                st.rerun()

    with tab_subject:
        db = SessionLocal()
        try:
            subjects = db.query(Subject).order_by(Subject.name).all()
        finally:
            db.close()
        if subjects:
            st.dataframe([{"Subject": s.name} for s in subjects],
                         use_container_width=True)
        else:
            st.info("No subjects yet.")
        st.markdown("###  Add a subject")
        with st.form("add_subject_form", clear_on_submit=True):
            new_subject = st.text_input("Subject name", "Mathematics")
            if st.form_submit_button("Create"):
                if new_subject.strip():
                    ok, msg = add_subject(new_subject.strip())
                    st.success(msg) if ok else st.error(msg)
                    st.rerun()

    with tab_assign:
        db = SessionLocal()
        try:
            classes = db.query(SchoolClass).order_by(
                SchoolClass.name, SchoolClass.section).all()
            subjects = db.query(Subject).order_by(Subject.name).all()
            assignments = db.query(ClassSubject).all()
        finally:
            db.close()
        if not classes or not subjects:
            st.info("Create at least one class and one subject first.")
            return
        st.markdown("### Current assignments")
        if assignments:
            data = []
            for a in assignments:
                c = next((x for x in classes if x.id == a.class_id), None)
                s = next((x for x in subjects if x.id == a.subject_id), None)
                if c and s:
                    data.append({"Class": f"{c.name}-{c.section}",
                                 "Subject": s.name})
            st.dataframe(data, use_container_width=True)
        else:
            st.caption("Nothing assigned yet.")
        st.markdown("###  Assign a subject to a class")
        class_opts = {f"{c.name}-{c.section}": c.id for c in classes}
        subject_opts = {s.name: s.id for s in subjects}
        c1, c2 = st.columns(2)
        cls_choice = c1.selectbox("Class", list(class_opts.keys()), key="assign_cls")
        sub_choice = c2.selectbox("Subject", list(subject_opts.keys()), key="assign_sub")
        if st.button("Assign"):
            ok, msg = assign_subject_to_class(class_opts[cls_choice],
                                              subject_opts[sub_choice])
            st.success(msg) if ok else st.warning(msg)
            st.rerun()


def students_page():
    st.header(" Students")
    db = SessionLocal()
    try:
        classes = db.query(SchoolClass).order_by(
            SchoolClass.name, SchoolClass.section).all()
    finally:
        db.close()
    if not classes:
        st.warning(" Create at least one class-section first "
                   "(go to **Classes & Subjects**).")
        return
    class_map = {f"{c.name}-{c.section}": c.id for c in classes}

    tab_view, tab_add, tab_import, tab_edit = st.tabs(
        [" All Students", " Add One", " Import CSV/Excel", " Edit / Delete"])

    with tab_view:
        db = SessionLocal()
        try:
            rows = db.query(Student).order_by(
                Student.class_name, Student.section, Student.roll_no).all()
        finally:
            db.close()
        if not rows:
            st.info("No students yet.")
        else:
            data = []
            for s in rows:
                name = s.user.full_name if s.user else "-"
                username = s.user.username if s.user else "-"
                data.append({"Admission No": s.admission_no, "Name": name,
                             "Username": username, "Roll": s.roll_no,
                             "Class": s.class_name, "Section": s.section,
                             "Curriculum": s.curriculum})
            st.caption(f"Showing {len(data)} students")
            st.dataframe(data, use_container_width=True)
            df = pd.DataFrame(data)
            st.download_button(" Download as CSV",
                               df.to_csv(index=False).encode("utf-8"),
                               file_name="students.csv", mime="text/csv")

    with tab_add:
        st.subheader("Add a single student")
        with st.form("add_student_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            full_name = col1.text_input("Full name *")
            admission_no = col2.text_input("Admission number *")
            col3, col4, col5 = st.columns(3)
            roll_no = col3.text_input("Roll no")
            cls_choice = col4.selectbox("Class-Section", list(class_map.keys()))
            curriculum = col5.selectbox("Curriculum",
                ["CBSE", "IBDP", "MYP", "IGCSE", "JEE", "IOQM", "Custom"])
            password = st.text_input("Password (default 'student123')",
                                     type="password")
            if st.form_submit_button("Add Student"):
                if not full_name.strip() or not admission_no.strip():
                    st.error("Full name and Admission number are required.")
                else:
                    ok, msg, _ = add_student(
                        full_name.strip(), admission_no.strip(),
                        roll_no.strip(), class_map[cls_choice],
                        curriculum.strip(), password=password.strip() or None)
                    st.success(msg) if ok else st.error(msg)

    with tab_import:
        st.subheader("Import many students at once")
        template = pd.DataFrame([
            {"full_name": "Aarav Sharma", "admission_no": "ADM001",
             "roll_no": "1", "class_name": "XII", "section": "A",
             "curriculum": "CBSE"},
        ])
        st.download_button(" Download sample CSV",
                           template.to_csv(index=False).encode("utf-8"),
                           file_name="students_template.csv", mime="text/csv")
        uploaded = st.file_uploader("Upload CSV or Excel",
                                    type=["csv", "xlsx", "xls"])
        if uploaded is not None:
            try:
                df = (pd.read_csv(uploaded) if uploaded.name.endswith(".csv")
                      else pd.read_excel(uploaded))
                st.dataframe(df.head(20), use_container_width=True)
                if st.button(" Confirm Import"):
                    ok_count = 0
                    failed = []
                    for _, row in df.iterrows():
                        klass = db.query(SchoolClass).filter_by(
                            name=str(row.get("class_name", "")).strip(),
                            section=str(row.get("section", "")).strip()).first()
                        if not klass:
                            failed.append(f"Class {row.get('class_name')}-"
                                          f"{row.get('section')} not found")
                            continue
                        ok, msg, _ = add_student(
                            str(row.get("full_name", "")).strip(),
                            str(row.get("admission_no", "")).strip(),
                            str(row.get("roll_no", "")).strip(),
                            klass.id,
                            str(row.get("curriculum", "CBSE")).strip())
                        if ok: ok_count += 1
                        else:  failed.append(msg)
                    st.success(f"Imported {ok_count} students.")
                    if failed:
                        for f_ in failed[:20]: st.write(f"- {f_}")
            except Exception as e:
                st.error(f"Could not read file: {e}")

    with tab_edit:
        db = SessionLocal()
        try:
            students = db.query(Student).all()
        finally:
            db.close()
        if not students:
            st.info("No students to edit.")
        else:
            options = {f"{s.user.full_name if s.user else '-'}  "
                       f"{s.admission_no} ({s.class_name}-{s.section})": s.id
                       for s in students}
            choice = st.selectbox("Select a student", list(options.keys()))
            sid = options[choice]
            db = SessionLocal()
            try:
                s = db.query(Student).filter_by(id=sid).first()
                cur_name = s.user.full_name if s.user else ""
                cur_user = s.user.username if s.user else ""
                cur_roll = s.roll_no or ""
                cur_key = (f"{s.class_name}-{s.section}"
                           if s.class_name else list(class_map.keys())[0])
                cur_curr = s.curriculum or "CBSE"
            finally:
                db.close()
            st.caption(f"Username: `{cur_user}`")
            with st.form("edit_student_form"):
                new_name = st.text_input("Full name", cur_name)
                col3, col4, col5 = st.columns(3)
                new_roll = col3.text_input("Roll", cur_roll)
                cls_opts = list(class_map.keys())
                new_cls = col4.selectbox(
                    "Class-Section", cls_opts,
                    index=cls_opts.index(cur_key) if cur_key in cls_opts else 0)
                curr_opts = ["CBSE", "IBDP", "MYP", "IGCSE", "JEE", "IOQM", "Custom"]
                new_curr = col5.selectbox(
                    "Curriculum", curr_opts,
                    index=curr_opts.index(cur_curr) if cur_curr in curr_opts else 0)
                c1, c2 = st.columns(2)
                save = c1.form_submit_button(" Save changes")
                delete = c2.form_submit_button(" Delete student")
            if save:
                ok, msg = update_student(sid, new_name.strip(), new_roll.strip(),
                                         class_map[new_cls], new_curr.strip())
                st.success(msg) if ok else st.error(msg)
                st.rerun()
            if delete:
                if st.button("Yes, delete permanently"):
                    ok, msg = delete_student(sid)
                    st.success(msg) if ok else st.error(msg)
                    st.rerun()


def attendance_page():
    st.header(" Attendance")
    tab_mark, tab_history, tab_student, tab_class = st.tabs(
        [" Mark Today", " History (Edit Past)", " Student Report",
         " Class Report"])

    db = SessionLocal()
    try:
        classes = db.query(SchoolClass).order_by(
            SchoolClass.name, SchoolClass.section).all()
    finally:
        db.close()
    if not classes:
        st.warning("Create classes first.")
        return
    class_map = {f"{c.name}-{c.section}": c.id for c in classes}

    with tab_mark:
        chosen = st.selectbox("Class-Section", list(class_map.keys()),
                              key="mark_class")
        cid = class_map[chosen]
        db = SessionLocal()
        try:
            students = db.query(Student).filter_by(class_id=cid).order_by(
                Student.roll_no).all()
        finally:
            db.close()
        if not students:
            st.info("No students in this class.")
        else:
            st.caption(f"Marking for {date.today().strftime('%A, %d %B %Y')}")
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
                        save_attendance(sid, cid, status,
                                        st.session_state["user"]["id"])
                    st.success("Attendance saved.")

    with tab_history:
        c1, c2 = st.columns(2)
        chosen_hist = c1.selectbox("Class-Section", list(class_map.keys()),
                                   key="hist_class")
        chosen_date = c2.date_input("Date", value=date.today(), key="hist_date")
        cid = class_map[chosen_hist]
        existing = get_attendance_for_date(cid, chosen_date)
        db = SessionLocal()
        try:
            students = db.query(Student).filter_by(class_id=cid).order_by(
                Student.roll_no).all()
        finally:
            db.close()
        if not students:
            st.info("No students in this class.")
        else:
            with st.form("history_form"):
                statuses = {}
                for s in students:
                    name = s.user.full_name if s.user else f"Student #{s.id}"
                    current = existing.get(s.id, "present")
                    statuses[s.id] = st.radio(
                        f"{name} ({s.admission_no})",
                        ["present", "absent", "late", "excused"],
                        index=["present", "absent", "late", "excused"].index(current),
                        horizontal=True, key=f"hist_{s.id}_{chosen_date}")
                if st.form_submit_button("Save"):
                    for sid, status in statuses.items():
                        save_attendance(sid, cid, status,
                                        st.session_state["user"]["id"],
                                        on_date=chosen_date)
                    st.success(f"Saved for {chosen_date}.")

    with tab_student:
        db = SessionLocal()
        try:
            students = db.query(Student).order_by(
                Student.class_name, Student.section, Student.roll_no).all()
        finally:
            db.close()
        if not students:
            st.info("No students yet.")
        else:
            options = {f"{s.user.full_name if s.user else '-'}  "
                       f"{s.admission_no} ({s.class_name}-{s.section})": s.id
                       for s in students}
            choice = st.selectbox("Student", list(options.keys()), key="sr_student")
            sid = options[choice]
            c1, c2 = st.columns(2)
            start = c1.date_input("From", value=date.today() - timedelta(days=30),
                                  key="sr_start")
            end = c2.date_input("To", value=date.today(), key="sr_end")
            summ = student_attendance_summary(sid, start, end)
            streak = consecutive_absences(sid)
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Days", summ["total"])
            m2.metric("Present", summ["present"])
            m3.metric("Absent", summ["absent"])
            m4.metric("Attendance %", f"{summ['percent']}%")
            m5.metric("Consec. absences", streak)
            records = attendance_records(sid, start, end)
            if records:
                df = pd.DataFrame(records)
                df["Date"] = df["Date"].astype(str)
                st.dataframe(df, use_container_width=True)

    with tab_class:
        c1, c2, c3 = st.columns(3)
        chosen_cr = c1.selectbox("Class-Section", list(class_map.keys()),
                                 key="cr_class")
        start = c2.date_input("From", value=date.today() - timedelta(days=30),
                              key="cr_start")
        end = c3.date_input("To", value=date.today(), key="cr_end")
        cid = class_map[chosen_cr]
        rows = class_attendance_summary(cid, start, end)
        if not rows:
            st.info("No students in this class.")
        else:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)
            st.download_button(" Download class report as CSV",
                               df.to_csv(index=False).encode("utf-8"),
                               file_name=f"attendance_{chosen_cr}.csv",
                               mime="text/csv")


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
                st.markdown(f"### {t.name} ({t.class_level}) - {t.status} - "
                            f"{int(t.progress * 100)}%")
                children = db.query(Topic).filter_by(parent_id=t.id).all()
                for ch in children:
                    st.markdown(f"- {ch.name} - {ch.status} - "
                                f"{int(ch.progress * 100)}%")
    finally:
        db.close()


def ai_assistant_page():
    st.header("AI Teaching Assistant")
    st.info("AI features require an OpenAI API key.")
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
                     "content": "You are an expert mathematics teacher. "
                                "Produce a complete 45-minute lesson plan. "
                                "Use LaTeX for math."},
                    {"role": "user", "content": f"Topic: {topic}, Class: {cls}"},
                ],
            )
            st.markdown(resp.choices[0].message.content)




def questions_page():
    st.header("Questions and Daily Assignments")

    tab_create, tab_assign, tab_review = st.tabs(
        ["Create Question", "Assign to Class", "Review Submissions"])

    with tab_create:
        st.subheader("Create a new question")
        with st.form("create_question_form", clear_on_submit=True):
            title = st.text_input("Title", "Daily Practice 1")
            body = st.text_area("Question body", height=120,
                                placeholder="Example: Find the derivative of x^2 sin(x).")
            answer_hint = st.text_area("Answer or hint (teacher only)", height=80)
            c1, c2, c3 = st.columns(3)
            marks = c1.number_input("Marks", 1, 100, 5)
            topic = c2.text_input("Topic", "Calculus")
            difficulty = c3.selectbox("Difficulty",
                ["easy", "medium", "hard", "olympiad"])
            due_date = st.date_input("Due date", value=date.today())
            if st.form_submit_button("Create Question"):
                if not title.strip() or not body.strip():
                    st.error("Title and question body are required.")
                else:
                    ok, msg, _ = create_question(
                        title.strip(), body.strip(), answer_hint.strip(),
                        int(marks), topic.strip(), difficulty,
                        st.session_state["user"]["id"], due_date)
                    st.success(msg) if ok else st.error(msg)

        st.markdown("### Existing questions")
        qs = all_questions()
        if not qs:
            st.caption("No questions yet.")
        else:
            for q in qs:
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    c1.markdown("**Q%d: %s**" % (q.id, q.title))
                    c1.caption("%s · %s · %d marks" % (q.topic or "-",
                                                        q.difficulty, q.marks))
                    c1.write(q.body or "")
                    if c2.button("Delete", key="del_q_%d" % q.id):
                        delete_question(q.id)
                        st.rerun()

    with tab_assign:
        qs = all_questions()
        db = SessionLocal()
        try:
            classes = db.query(SchoolClass).order_by(
                SchoolClass.name, SchoolClass.section).all()
        finally:
            db.close()

        if not qs:
            st.info("Create a question first.")
        elif not classes:
            st.info("Create a class first.")
        else:
            st.subheader("Assign a question to a class")
            q_opts = {}
            for q in qs:
                q_opts["Q%d: %s (%d marks)" % (q.id, q.title, q.marks)] = q.id
            c_opts = {}
            for c in classes:
                c_opts["%s-%s" % (c.name, c.section)] = c.id

            c1, c2 = st.columns(2)
            q_choice = c1.selectbox("Question", list(q_opts.keys()))
            c_choice = c2.selectbox("Class-Section", list(c_opts.keys()))
            if st.button("Assign"):
                ok, msg = assign_question(q_opts[q_choice], c_opts[c_choice],
                                          st.session_state["user"]["id"])
                st.success(msg) if ok else st.warning(msg)
                st.rerun()

            st.markdown("### Current assignments")
            db = SessionLocal()
            try:
                all_a = db.query(QuestionAssignment).order_by(
                    QuestionAssignment.assigned_on.desc()).all()
            finally:
                db.close()
            if not all_a:
                st.caption("No assignments yet.")
            else:
                for a in all_a:
                    klass = a.klass
                    q = a.question
                    cls_name = "%s-%s" % (klass.name, klass.section) if klass else "?"
                    title = q.title if q else "?"
                    with st.container(border=True):
                        c1, c2 = st.columns([4, 1])
                        c1.markdown("**%s** assigned to **%s**" % (title, cls_name))
                        c1.caption("Assigned on %s" % a.assigned_on)
                        if c2.button("Unassign", key="un_%d" % a.id):
                            unassign_question(a.id)
                            st.rerun()

    with tab_review:
        st.subheader("Review submissions")
        subs = all_submissions()
        if not subs:
            st.caption("No submissions yet.")
        else:
            for s in subs:
                a = s.assignment
                q = a.question if a else None
                student = s.student
                student_name = (student.user.full_name
                                if student and student.user else "?")
                title = q.title if q else "?"
                with st.container(border=True):
                    st.markdown("**%s** submitted **%s**" % (student_name, title))
                    if s.answer_text:
                        st.write("Answer:")
                        st.write(s.answer_text)
                    if s.status == "graded":
                        st.info("Marks: %s / %s | Feedback: %s" %
                                (s.marks_awarded,
                                 q.marks if q else "?",
                                 s.feedback or "(none)"))
                    else:
                        c1, c2 = st.columns([1, 3])
                        marks = c1.number_input(
                            "Marks", 0, q.marks if q else 100, 0,
                            key="mk_%d" % s.id)
                        feedback = c2.text_input("Feedback", key="fb_%d" % s.id)
                        if st.button("Save marks", key="sv_%d" % s.id):
                            ok, msg = grade_submission(s.id, marks, feedback)
                            st.success(msg) if ok else st.error(msg)
                            st.rerun()


# ---------------- STUDENT PAGES ----------------

def student_dashboard_page(user):
    st.header(f" Welcome, {user['full_name']}")

    db = SessionLocal()
    try:
        student = db.query(Student).filter_by(user_id=user["id"]).first()
        if not student:
            st.error("Your student record was not found. "
                     "Please contact your teacher.")
            return
        student_id = student.id
        cls = f"{student.class_name}-{student.section}" if student.class_name else "-"
        adm = student.admission_no
        roll = student.roll_no or "-"
        curr = student.curriculum or "-"
    finally:
        db.close()

    st.subheader(" My Attendance")
    today = date.today()
    s30 = student_attendance_summary(student_id, today - timedelta(days=30), today)
    sAll = student_attendance_summary(student_id)
    streak = consecutive_absences(student_id)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Last 30 days", f"{s30['percent']}%")
    c2.metric("Overall", f"{sAll['percent']}%")
    c3.metric("Days present", sAll["present"])
    c4.metric("Consecutive absences", streak)

    if sAll["total"] > 0 and sAll["percent"] < 75:
        st.error(f" Your overall attendance is {sAll['percent']}%  "
                 "below 75%. Please attend regularly.")

    st.subheader(" My Profile")
    st.markdown(f"**Admission No:** {adm}  \n"
                f"**Class:** {cls}  \n"
                f"**Roll No:** {roll}  \n"
                f"**Curriculum:** {curr}")


# ---------------- Main ----------------

st.set_page_config(page_title="MathsHub", page_icon="M", layout="wide")

if "user" not in st.session_state:
    login_page()
else:
    user = st.session_state["user"]
    st.sidebar.markdown(f"### {user['full_name'] or user['username']}")
    st.sidebar.caption(f"Role: {user['role']}")

    if st.sidebar.button("Log out"):
        st.session_state.clear()
        st.rerun()

    if user["role"] == "student":
        student_dashboard_page(user)
    else:
        page = st.sidebar.radio(
            "Navigate",
            ["Dashboard", "Classes & Subjects", "Students", "Attendance",
             "Questions", "Curriculum", "AI Assistant"])
        if page == "Dashboard":
            dashboard_page()
        elif page == "Classes & Subjects":
            classes_page()
        elif page == "Students":
            students_page()
        elif page == "Attendance":
            attendance_page()
        elif page == "Questions":
            questions_page()
        elif page == "Curriculum":
            curriculum_page()
        elif page == "AI Assistant":
            ai_assistant_page()
