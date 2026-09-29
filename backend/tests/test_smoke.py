"""冒烟测试：只覆盖顺利路径。

这些用例在初始快照上全绿；它们不覆盖 README「行为规格」里的边界语义，
因此通过它们并不代表规格已被满足。
"""
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    import backend.main as app_module

    with TestClient(app_module.app) as test_client:
        yield test_client


def create_meeting(client, title="昆虫蛋白产业化例行会议", location="上海"):
    resp = client.post("/api/meetings", json={"title": title, "location": location})
    assert resp.status_code == 200, resp.text
    return resp.json()


def upload_audio(client, meeting_id, filename="session.wav", content=b"RIFF....WAVEfmt "):
    resp = client.post(
        f"/api/meetings/{meeting_id}/audio",
        files={"file": (filename, content, "audio/wav")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_root_and_service_info(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "running"
    assert body["version"] == "1.0.0"


def test_meeting_flow(client):
    meeting = create_meeting(client, title="顺利路径会议")
    assert meeting["id"] and meeting["status"]
    assert meeting["created_at"]

    listed = client.get("/api/meetings")
    assert listed.status_code == 200
    assert [m["id"] for m in listed.json()] == [meeting["id"]]

    detail = client.get(f"/api/meetings/{meeting['id']}")
    assert detail.status_code == 200
    assert detail.json()["meeting"]["title"] == "顺利路径会议"

    assert client.get("/api/meetings/987654").status_code == 404


def test_audio_upload(client):
    meeting = create_meeting(client, title="带录音的会议")
    uploaded = upload_audio(client, meeting["id"])

    from backend.database.models import AudioFile, SessionLocal

    db = SessionLocal()
    try:
        row = db.query(AudioFile).filter(AudioFile.id == uploaded["audio_id"]).first()
        stored = row.original_path
        assert row.status == "uploaded"
    finally:
        db.close()

    assert os.path.exists(stored), stored

    detail = client.get(f"/api/meetings/{meeting['id']}").json()
    assert len(detail["audio_files"]) == 1
    assert detail["audio_files"][0]["filename"] == "session.wav"


def test_process_audio_is_accepted(client):
    meeting = create_meeting(client, title="待处理会议")
    uploaded = upload_audio(client, meeting["id"])

    resp = client.post(
        "/api/process-audio",
        json={
            "meeting_id": meeting["id"],
            "audio_file_id": uploaded["audio_id"],
            "enable_noise_reduction": False,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "processing"


def test_nutrition_and_environment_lists(client):
    assert client.get("/api/insects/nutrition").json() == []
    assert client.get("/api/environment/data").json() == []


def test_transcript_and_summary_missing(client):
    assert client.get("/api/transcripts/987654").status_code == 404
    assert client.get("/api/summaries/987654").status_code == 404


def test_send_email_requires_summary(client):
    meeting = create_meeting(client, title="没有纪要的会议")
    resp = client.post(
        "/api/send-email",
        json={
            "meeting_id": meeting["id"],
            "recipients": ["partner@example.com"],
            "recipient_type": "partners",
        },
    )
    assert resp.status_code == 404, resp.text
