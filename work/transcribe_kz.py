import json
from pathlib import Path

from faster_whisper import WhisperModel


model = WhisperModel("deepdml/faster-whisper-large-v3-turbo-ct2", device="cpu", compute_type="int8")
segments, info = model.transcribe(
    "work/audio_kz.wav",
    beam_size=5,
    vad_filter=True,
    vad_parameters={"min_silence_duration_ms": 500},
    condition_on_previous_text=False,
    word_timestamps=True,
)

rows = []
for segment in segments:
    text = segment.text.strip()
    if text:
        words = [
            {"start": word.start, "end": word.end, "text": word.word.strip()}
            for word in (segment.words or [])
            if word.word.strip()
        ]
        rows.append({"start": segment.start, "end": segment.end, "text": text, "words": words})
        print(f"{segment.start:8.2f} --> {segment.end:8.2f}  {text}", flush=True)

Path("work/transcript_kz.json").write_text(
    json.dumps({"language": info.language, "segments": rows}, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"Detected {info.language}; wrote {len(rows)} segments.")
