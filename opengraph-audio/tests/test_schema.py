from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from opengraph_audio.schema import (
    AudioSource,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
)


def _source() -> AudioSource:
    return AudioSource(
        path="recordings/standup.mp3",
        filename="standup.mp3",
        format="mp3",
        size_bytes=48_213,
        sha256="9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    )


def _full_transcript() -> Transcript:
    return Transcript(
        source=_source(),
        text="Good morning. Morning, Sam.",
        language="en",
        duration_seconds=3.2,
        segments=[
            TranscriptSegment(id="seg_0", text="Good morning.", start=0.0, end=1.1, speaker="A"),
            TranscriptSegment(id="seg_1", text="Morning, Sam.", start=1.4, end=3.2, speaker="B"),
        ],
        words=[
            TranscriptWord(text="Good", start=0.0, end=0.4, speaker="A", confidence=0.98),
            TranscriptWord(text="morning.", start=0.4, end=1.1, speaker="A", confidence=0.95),
            TranscriptWord(text="Morning,", start=1.4, end=2.0, speaker="B", confidence=0.91),
            TranscriptWord(text="Sam.", start=2.1, end=3.2, speaker="B"),
        ],
        model="microsoft/mai-transcribe-2",
        transcribed_at=datetime(2026, 10, 27, 9, 30, tzinfo=timezone.utc),
        usage={"seconds": 3.2, "cost": 0.0004},
    )


# ---------------------------------------------------------------------------
# Valid transcripts
# ---------------------------------------------------------------------------


def test_minimal_transcript_leaves_optional_metadata_none():
    transcript = Transcript(source=_source(), text="Hello there.", model="test-model")

    assert transcript.language is None
    assert transcript.duration_seconds is None
    assert transcript.segments == []
    assert transcript.words == []
    assert transcript.usage is None
    assert transcript.transcribed_at.tzinfo is not None
    assert transcript.transcribed_at.utcoffset() == timedelta(0)


def test_segment_and_word_without_timing_or_speaker():
    segment = TranscriptSegment(id="seg_0", text="Hello.")
    word = TranscriptWord(text="Hello.")

    assert (segment.start, segment.end, segment.speaker) == (None, None, None)
    assert (word.start, word.end, word.speaker, word.confidence) == (None, None, None, None)


def test_transcript_with_segments_speakers_and_word_timestamps():
    transcript = _full_transcript()

    assert [s.speaker for s in transcript.segments] == ["A", "B"]
    assert transcript.segments[1].start == 1.4
    assert transcript.words[0].end == 0.4
    assert transcript.words[3].confidence is None


def test_zero_length_range_is_allowed():
    word = TranscriptWord(text="uh", start=2.0, end=2.0)

    assert word.start == word.end


def test_only_one_timestamp_is_allowed():
    assert TranscriptSegment(id="s", text="x", start=5.0).end is None
    assert TranscriptSegment(id="s", text="x", end=5.0).start is None


# ---------------------------------------------------------------------------
# Invalid values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model_cls, kwargs", [
    (TranscriptSegment, {"id": "s", "text": "x", "start": -0.1}),
    (TranscriptSegment, {"id": "s", "text": "x", "end": -1.0}),
    (TranscriptWord, {"text": "x", "start": -0.5}),
    (TranscriptWord, {"text": "x", "end": -0.5}),
])
def test_negative_times_rejected(model_cls, kwargs):
    with pytest.raises(ValidationError):
        model_cls(**kwargs)


def test_negative_duration_rejected():
    with pytest.raises(ValidationError):
        Transcript(source=_source(), text="x", model="m", duration_seconds=-1.0)


def test_negative_size_bytes_rejected():
    with pytest.raises(ValidationError):
        AudioSource(path="a.wav", filename="a.wav", format="wav", size_bytes=-1, sha256="00")


@pytest.mark.parametrize("model_cls, kwargs", [
    (TranscriptSegment, {"id": "s", "text": "x", "start": 2.0, "end": 1.0}),
    (TranscriptWord, {"text": "x", "start": 2.0, "end": 1.999}),
])
def test_reversed_time_range_rejected(model_cls, kwargs):
    with pytest.raises(ValidationError, match="must be >= start"):
        model_cls(**kwargs)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_out_of_range_confidence_rejected(confidence):
    with pytest.raises(ValidationError):
        TranscriptWord(text="x", confidence=confidence)


@pytest.mark.parametrize("confidence", [0.0, 1.0])
def test_boundary_confidence_accepted(confidence):
    assert TranscriptWord(text="x", confidence=confidence).confidence == confidence


def test_naive_transcribed_at_rejected():
    with pytest.raises(ValidationError):
        Transcript(source=_source(), text="x", model="m", transcribed_at=datetime(2026, 10, 27, 9, 30))


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_json_round_trip_preserves_data():
    original = _full_transcript()

    restored = Transcript.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.transcribed_at == datetime(2026, 10, 27, 9, 30, tzinfo=timezone.utc)
    assert restored.words[3].confidence is None


def test_json_round_trip_of_minimal_transcript():
    original = Transcript(source=_source(), text="Hello there.", model="test-model")

    restored = Transcript.model_validate_json(original.model_dump_json())

    assert restored == original
