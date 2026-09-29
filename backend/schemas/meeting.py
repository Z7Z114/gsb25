from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime


class MeetingBase(BaseModel):
    title: str
    date: Optional[datetime] = None
    location: Optional[str] = None
    duration: Optional[float] = None
    attendees: Optional[List[str]] = None


class MeetingCreate(MeetingBase):
    pass


class Meeting(MeetingBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InsectDataBase(BaseModel):
    chinese_name: str
    latin_name: Optional[str] = None
    protein_content: Optional[float] = None
    fat_content: Optional[float] = None
    amino_acid_profile: Optional[Dict] = None
    key_nutrients: Optional[List[str]] = None
    other_components: Optional[Dict] = None
    data_source: Optional[str] = None


class InsectDataCreate(InsectDataBase):
    meeting_id: int


class InsectData(InsectDataBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class EnvironmentDataBase(BaseModel):
    insect_name: Optional[str] = None
    optimal_temperature_min: Optional[float] = None
    optimal_temperature_max: Optional[float] = None
    optimal_humidity_min: Optional[float] = None
    optimal_humidity_max: Optional[float] = None
    farming_density: Optional[float] = None
    density_unit: Optional[str] = None
    growth_cycle_days: Optional[int] = None
    feed_conversion_rate: Optional[float] = None
    survival_rate: Optional[float] = None
    other_parameters: Optional[Dict] = None


class EnvironmentDataCreate(EnvironmentDataBase):
    meeting_id: int


class EnvironmentData(EnvironmentDataBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    speaker: Optional[str] = None
    insect_terms: Optional[List[Dict]] = None


class TranscriptBase(BaseModel):
    meeting_id: int
    audio_file_id: Optional[int] = None
    full_text: Optional[str] = None
    language: Optional[str] = None
    detected_insects: Optional[List[Dict]] = None
    segments: Optional[List[TranscriptSegment]] = None
    speaker_roles: Optional[Dict] = None
    formatted_dialogue: Optional[str] = None


class TranscriptCreate(TranscriptBase):
    pass


class Transcript(TranscriptBase):
    id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingSummaryBase(BaseModel):
    meeting_id: int
    summary_data: Optional[Dict] = None
    markdown_content: Optional[str] = None
    emails_sent: Optional[List[Dict]] = None


class MeetingSummaryCreate(MeetingSummaryBase):
    pass


class MeetingSummary(MeetingSummaryBase):
    id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AudioFileBase(BaseModel):
    meeting_id: int
    filename: str
    original_path: str
    duration: Optional[float] = None
    sample_rate: Optional[int] = None


class AudioFileCreate(AudioFileBase):
    pass


class AudioFile(AudioFileBase):
    id: int
    cleaned_path: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class EmailSendRequest(BaseModel):
    meeting_id: int
    recipients: List[str]
    recipient_type: str = "investors"
    subject: Optional[str] = None


class ProcessAudioRequest(BaseModel):
    meeting_id: int
    audio_file_id: int
    enable_noise_reduction: bool = True
    model_size: str = "medium"
    num_speakers: Optional[int] = None


class GenerateSummaryRequest(BaseModel):
    meeting_id: int
    transcript_id: int


class MeetingFullResponse(BaseModel):
    meeting: Meeting
    audio_files: List[AudioFile] = []
    transcripts: List[Transcript] = []
    summaries: List[MeetingSummary] = []
    insect_data: List[InsectData] = []
    environment_data: List[EnvironmentData] = []


class DashboardStats(BaseModel):
    total_meetings: int
    total_insect_species: int
    avg_protein_content: float
    total_processing_minutes: float
    recent_meetings: List[Meeting]


class InsectSpeciesNutrition(BaseModel):
    chinese_name: str
    latin_name: str
    protein_content: float
    fat_content: float
    amino_acid_score: Optional[float] = None
    comparison_data: Optional[Dict] = None
