from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
from pathlib import Path
from datetime import datetime
import logging

from .database.models import get_db, init_db, Meeting, AudioFile, Transcript, MeetingSummary, InsectData, EnvironmentData, EmailLog
from .schemas import meeting as schemas
from .audio.processor import AudioProcessor
from .audio.transcriber import WhisperTranscriber
from .audio.diarizer import SpeakerDiarizer
from .ai.summary_generator import SummaryGenerator
from .email.sender import EmailSender

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="昆虫蛋白产业化会议纪要系统",
    description="可持续食品会议纪要全栈应用",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
CLEANED_DIR = Path(os.getenv("CLEANED_DIR", "cleaned"))
UPLOAD_DIR.mkdir(exist_ok=True)
CLEANED_DIR.mkdir(exist_ok=True)

init_db()

audio_processor = AudioProcessor()
whisper_transcriber = None
speaker_diarizer = None
summary_generator = None
email_sender = EmailSender()


def get_transcriber():
    global whisper_transcriber
    if whisper_transcriber is None:
        whisper_transcriber = WhisperTranscriber()
    return whisper_transcriber


def get_diarizer():
    global speaker_diarizer
    if speaker_diarizer is None:
        auth_token = os.getenv("PYANNOTE_AUTH_TOKEN")
        if auth_token:
            speaker_diarizer = SpeakerDiarizer(auth_token=auth_token)
    return speaker_diarizer


def get_summary_gen():
    global summary_generator
    if summary_generator is None:
        summary_generator = SummaryGenerator()
    return summary_generator


@app.get("/")
async def root():
    return {
        "name": "昆虫蛋白产业化会议纪要系统",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.post("/api/meetings", response_model=schemas.Meeting)
def create_meeting(meeting: schemas.MeetingCreate, db: Session = Depends(get_db)):
    db_meeting = Meeting(**meeting.model_dump())
    db.add(db_meeting)
    db.commit()
    db.refresh(db_meeting)
    return db_meeting


@app.get("/api/meetings", response_model=List[schemas.Meeting])
def list_meetings(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).offset(skip).limit(limit).all()
    return meetings


@app.get("/api/meetings/{meeting_id}", response_model=schemas.MeetingFullResponse)
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return {
        "meeting": meeting,
        "audio_files": meeting.audio_files,
        "transcripts": meeting.transcripts,
        "summaries": meeting.summaries,
        "insect_data": meeting.insect_data,
        "environment_data": meeting.environment_data
    }


@app.post("/api/meetings/{meeting_id}/audio")
async def upload_audio(
    meeting_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    file_ext = Path(file.filename).suffix
    unique_name = f"{uuid.uuid4()}{file_ext}"
    file_path = UPLOAD_DIR / unique_name
    
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    db_audio = AudioFile(
        meeting_id=meeting_id,
        filename=file.filename,
        original_path=str(file_path),
        status="uploaded"
    )
    db.add(db_audio)
    db.commit()
    db.refresh(db_audio)

    return {"message": "Audio uploaded successfully", "audio_id": db_audio.id}

@app.post("/api/process-audio")
def process_audio_endpoint(
    request: schemas.ProcessAudioRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)):
    audio_file = db.query(AudioFile).filter(AudioFile.id == request.audio_file_id).first()
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    background_tasks.add_task(
        process_audio_task,
        request.meeting_id,
        request.audio_file_id,
        request.enable_noise_reduction,
        request.model_size,
        request.num_speakers,
        db
    )

    return {"message": "Audio processing started", "status": "processing"}


def process_audio_task(
    meeting_id: int,
    audio_file_id: int,
    enable_noise_reduction: bool,
    model_size: str,
    num_speakers: Optional[int],
    db: Session
):
    try:
        audio_file = db.query(AudioFile).filter(AudioFile.id == audio_file_id).first()
        if not audio_file:
            return

        audio_file.status = "processing"
        db.commit()

        input_path = audio_file.original_path
        cleaned_path = str(CLEANED_DIR / f"cleaned_{Path(input_path).name}")

        if enable_noise_reduction:
            cleaned_path = audio_processor.process_audio(input_path, cleaned_path)
            audio_file.cleaned_path = cleaned_path
            db.commit()

        transcriber = get_transcriber()
        transcription = transcriber.transcribe(cleaned_path if enable_noise_reduction else input_path)

        diarizer = get_diarizer()
        if diarizer:
            diarization = diarizer.diarize(cleaned_path, num_speakers=num_speakers)
            merged_segments = diarizer.merge_with_transcript(diarization, transcription["segments"])
            speaker_roles = diarizer.identify_roles(merged_segments)
            formatted_dialogue = diarizer.format_dialogue(merged_segments, speaker_roles)

            db_transcript = Transcript(
                meeting_id=meeting_id,
                audio_file_id=audio_file_id,
                full_text=transcription["text"],
                language=transcription["language"],
                detected_insects=transcription["detected_insects"],
                segments=merged_segments,
                speaker_roles=speaker_roles,
                formatted_dialogue=formatted_dialogue,
                status="completed"
            )
        else:
            db_transcript = Transcript(
                meeting_id=meeting_id,
                audio_file_id=audio_file_id,
                full_text=transcription["text"],
                language=transcription["language"],
                detected_insects=transcription["detected_insects"],
                segments=transcription["segments"],
                status="completed"
            )

        db.add(db_transcript)
        audio_file.status = "completed"
        db.commit()

        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting:
            meeting.status = "transcribed"
            db.commit()

    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        audio_file.status = "failed"
        db.commit()


@app.post("/api/generate-summary")
def generate_summary_endpoint(
    request: schemas.GenerateSummaryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)):
    transcript = db.query(Transcript).filter(Transcript.id == request.transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    background_tasks.add_task(
        generate_summary_task,
        request.meeting_id,
        request.transcript_id,
        db
    )

    return {"message": "Summary generation started", "status": "processing"}


def generate_summary_task(meeting_id: int, transcript_id: int, db: Session):
    try:
        transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
        if not transcript:
            return

        summary_gen = get_summary_gen()

        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        meeting_context = {
            "date": meeting.date.isoformat() if meeting.date else None,
            "location": meeting.location,
            "attendees": meeting.attendees or []
        }

        summary = summary_gen.generate_summary(
            transcript.formatted_dialogue or transcript.full_text,
            transcript.detected_insects or [],
            meeting_context
        )

        markdown_report = summary_gen.generate_markdown_report(summary)

        db_summary = MeetingSummary(
            meeting_id=meeting_id,
            summary_data=summary,
            markdown_content=markdown_report,
            status="completed"
        )
        db.add(db_summary)

        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting:
            meeting.status = "summarized"
            db.commit()

        _extract_and_store_insect_data(summary, meeting_id, db)

    except Exception as e:
        logger.error(f"Error generating summary: {e}")


def _extract_and_store_insect_data(summary: dict, meeting_id: int, db: Session):
    insect_analysis = summary.get("insect_production_analysis", {})
    main_species = insect_analysis.get("main_species", [])

    for species in main_species:
        db_insect = InsectData(
            meeting_id=meeting_id,
            chinese_name=species.get("chinese_name", ""),
            latin_name=species.get("latin_name"),
            protein_content=float(species.get("nutritional_value", {}).get("protein_content", 0)),
            fat_content=float(species.get("nutritional_value", {}).get("fat_content", 0)),
            amino_acid_profile=species.get("nutritional_value", {}).get("amino_acid_profile"),
            key_nutrients=species.get("nutritional_value", {}).get("key_nutrients"),
            data_source="Meeting Transcript Analysis"
        )
        db.add(db_insect)

        env = species.get("farming_environment", {})
        db_env = EnvironmentData(
            meeting_id=meeting_id,
            insect_name=species.get("chinese_name"),
            optimal_temperature_min=float(env.get("optimal_temperature_min", 0)),
            optimal_temperature_max=float(env.get("optimal_temperature_max", 0)),
            optimal_humidity_min=float(env.get("optimal_humidity_min", 0)),
            optimal_humidity_max=float(env.get("optimal_humidity_max", 0)),
            farming_density=float(env.get("farming_density", 0)),
            growth_cycle_days=int(env.get("growth_cycle_days", 0)),
            feed_conversion_rate=float(env.get("feed_conversion_rate", 0)),
            other_parameters=env
        )
        db.add(db_env)

    db.commit()


@app.post("/api/send-email")
def send_email(
    request: schemas.EmailSendRequest,
    db: Session = Depends(get_db)):
    summary = db.query(MeetingSummary).filter(MeetingSummary.meeting_id == request.meeting_id).order_by(MeetingSummary.created_at.desc()).first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")

    success = False
    error_msg = ""

    try:
        if request.recipient_type == "investors":
            success = email_sender.send_to_investors(
                request.recipients,
                summary.markdown_content
            )
        elif request.recipient_type == "partners":
            success = email_sender.send_to_partners(
                request.recipients,
                summary.markdown_content
            )
        else:
            success = email_sender.send_meeting_summary(
                request.recipients,
                request.subject or "会议纪要",
                summary.markdown_content
            )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error sending email: {e}")

    email_log = EmailLog(
        meeting_id=request.meeting_id,
        recipient_type=request.recipient_type,
        recipients=request.recipients,
        subject=request.subject,
        status="sent" if success else "failed",
        error_message=error_msg
    )
    db.add(email_log)
    db.commit()

    return {"success": success, "message": "Email sent" if success else f"Failed: {error_msg}"}


@app.get("/api/dashboard/stats", response_model=schemas.DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_meetings = db.query(Meeting).count()
    total_insect_species = db.query(InsectData).distinct(InsectData.chinese_name).count()
    avg_protein = db.query(db.func.avg(InsectData.protein_content)).scalar() or 0

    recent_meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).limit(5).all()

    return {
        "total_meetings": total_meetings,
        "total_insect_species": total_insect_species,
        "avg_protein_content": avg_protein,
        "total_processing_minutes": 0,
        "recent_meetings": recent_meetings
    }


@app.get("/api/insects/nutrition", response_model=List[schemas.InsectData])
def get_insect_nutrition(db: Session = Depends(get_db)):
    return db.query(InsectData).all()


@app.get("/api/environment/data", response_model=List[schemas.EnvironmentData])
def get_environment_data(db: Session = Depends(get_db)):
    return db.query(EnvironmentData).all()


@app.get("/api/transcripts/{transcript_id}")
def get_transcript(transcript_id: int, db: Session = Depends(get_db)):
    transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return transcript


@app.get("/api/summaries/{summary_id}")
def get_summary(summary_id: int, db: Session = Depends(get_db)):
    summary = db.query(MeetingSummary).filter(MeetingSummary.id == summary_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return summary


@app.get("/api/summaries/{summary_id}/markdown")
def get_summary_markdown(summary_id: int, db: Session = Depends(get_db)):
    summary = db.query(MeetingSummary).filter(MeetingSummary.id == summary_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return {"markdown": summary.markdown_content}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
