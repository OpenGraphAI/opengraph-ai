"""Pydantic models for audio transcripts.

These models are provider-neutral: transcription backends (OpenRouter, Azure,
...) map their own response formats onto them. Metadata a backend does not
supply (timestamps, speaker labels, confidence) stays None.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import AwareDatetime, BaseModel, Field, model_validator


def _validate_time_range(start: float | None, end: float | None) -> None:
    """Require end >= start when both timestamps are present."""

    if start is not None and end is not None and end < start:
        raise ValueError(f"end ({end}) must be >= start ({start})")


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------


class AudioSource(BaseModel):
    """The audio file a transcript was produced from."""

    path: str = Field(..., description="Filesystem path to the audio file")
    filename: str = Field(..., description="Base name of the audio file")
    format: str = Field(..., description="Audio format, e.g. 'mp3', 'wav', 'm4a'")
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    sha256: str = Field(..., description="Hex SHA-256 digest of the file contents")


# ---------------------------------------------------------------------------
# Transcript pieces
# ---------------------------------------------------------------------------


class TranscriptSegment(BaseModel):
    """A contiguous span of transcribed speech, e.g. a sentence or utterance."""

    id: str = Field(..., description="Segment identifier, unique within the transcript")
    text: str = Field(..., description="Transcribed text of the segment")
    start: float | None = Field(None, ge=0.0, description="Start time in seconds")
    end: float | None = Field(None, ge=0.0, description="End time in seconds")
    speaker: str | None = Field(None, description="Speaker label, if diarization is available")

    @model_validator(mode="after")
    def end_not_before_start(self) -> "TranscriptSegment":
        _validate_time_range(self.start, self.end)
        return self


class TranscriptWord(BaseModel):
    """A single transcribed word with optional timing and confidence."""

    text: str = Field(..., description="The transcribed word")
    start: float | None = Field(None, ge=0.0, description="Start time in seconds")
    end: float | None = Field(None, ge=0.0, description="End time in seconds")
    speaker: str | None = Field(None, description="Speaker label, if diarization is available")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Recognition confidence")

    @model_validator(mode="after")
    def end_not_before_start(self) -> "TranscriptWord":
        _validate_time_range(self.start, self.end)
        return self


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


class Transcript(BaseModel):
    """The full transcription of a single audio file."""

    source: AudioSource
    text: str = Field(..., description="Full transcript text")
    language: str | None = Field(None, description="Detected or requested language code, e.g. 'en'")
    duration_seconds: float | None = Field(None, ge=0.0, description="Audio duration in seconds")
    segments: list[TranscriptSegment] = Field(default_factory=list)
    words: list[TranscriptWord] = Field(default_factory=list)
    model: str = Field(..., description="Transcription model identifier")
    transcribed_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the transcription was produced (timezone-aware)",
    )
    usage: dict[str, Any] | None = Field(None, description="Provider-reported usage/billing data")
