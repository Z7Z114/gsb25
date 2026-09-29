from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./insect_protein.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    location = Column(String(255))
    duration = Column(Float)
    attendees = Column(JSON)
    status = Column(String(50), default="processing")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    audio_files = relationship("AudioFile", back_populates="meeting", cascade="all, delete-orphan")
    transcripts = relationship("Transcript", back_populates="meeting", cascade="all, delete-orphan")
    summaries = relationship("MeetingSummary", back_populates="meeting", cascade="all, delete-orphan")
    insect_data = relationship("InsectData", back_populates="meeting", cascade="all, delete-orphan")
    environment_data = relationship("EnvironmentData", back_populates="meeting", cascade="all, delete-orphan")


class AudioFile(Base):
    __tablename__ = "audio_files"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    filename = Column(String(255), nullable=False)
    original_path = Column(String(500), nullable=False)
    cleaned_path = Column(String(500))
    duration = Column(Float)
    sample_rate = Column(Integer)
    status = Column(String(50), default="uploaded")
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="audio_files")


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    audio_file_id = Column(Integer, ForeignKey("audio_files.id"))
    full_text = Column(Text)
    language = Column(String(20))
    detected_insects = Column(JSON)
    segments = Column(JSON)
    speaker_roles = Column(JSON)
    formatted_dialogue = Column(Text)
    status = Column(String(50), default="processing")
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="transcripts")


class MeetingSummary(Base):
    __tablename__ = "meeting_summaries"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    summary_data = Column(JSON)
    markdown_content = Column(Text)
    emails_sent = Column(JSON)
    status = Column(String(50), default="processing")
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="summaries")


class InsectData(Base):
    __tablename__ = "insect_data"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    chinese_name = Column(String(100), nullable=False)
    latin_name = Column(String(150))
    protein_content = Column(Float)
    fat_content = Column(Float)
    amino_acid_profile = Column(JSON)
    key_nutrients = Column(JSON)
    other_components = Column(JSON)
    data_source = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="insect_data")


class EnvironmentData(Base):
    __tablename__ = "environment_data"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    insect_name = Column(String(100))
    optimal_temperature_min = Column(Float)
    optimal_temperature_max = Column(Float)
    optimal_humidity_min = Column(Float)
    optimal_humidity_max = Column(Float)
    farming_density = Column(Float)
    density_unit = Column(String(50))
    growth_cycle_days = Column(Integer)
    feed_conversion_rate = Column(Float)
    survival_rate = Column(Float)
    other_parameters = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="environment_data")


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer)
    recipient_type = Column(String(50))
    recipients = Column(JSON)
    subject = Column(String(255))
    status = Column(String(50))
    error_message = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
