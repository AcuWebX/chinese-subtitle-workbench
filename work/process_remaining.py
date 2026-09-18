import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from deep_translator import GoogleTranslator
from faster_whisper import WhisperModel


WORK = Path("work/batch")
OUTPUTS = Path("outputs")


def desktop_path():
    for name in ("Desktop", "桌面"):
        candidate = Path.home() / name
        if candidate.is_dir():
            return candidate
    candidate = Path.home() / "Desktop"
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


DESKTOP = desktop_path()


def find_tool(name):
    found = shutil.which(name)
    if found:
        return found
    # WinGet may install FFmpeg after the current shell's PATH was created.
    # Search its package directory so a fresh deployment works immediately.
    roots = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages",
        Path(os.environ.get("ProgramFiles", "")) / "WinGet" / "Packages",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "WinGet" / "Packages",
        Path("C:/ffmpeg"),
    ]
    for root in roots:
        if not root.is_dir():
            continue
        try:
            matches = root.rglob(f"{name}.exe")
        except OSError:
            continue
        for candidate in matches:
            if candidate.is_file() and "ffmpeg" in str(candidate).lower():
                return str(candidate)
    return name


FFMPEG = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")
SOURCES = [
]
STATUS = WORK / "status.log"


def note(message):
    stamped = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(stamped, flush=True)
    with STATUS.open("a", encoding="utf-8") as stream:
        stream.write(stamped + "\n")


def command(args, cwd=None):
    with (WORK / "ffmpeg.log").open("a", encoding="utf-8") as log:
        try:
            subprocess.run(args, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, check=True)
        except FileNotFoundError as error:
            raise RuntimeError("找不到 FFmpeg。请重新运行 DEPLOY.cmd，或安装 FFmpeg 后重启电脑。") from error
        except subprocess.CalledProcessError as error:
            try:
                tail = (WORK / "ffmpeg.log").read_text(encoding="utf-8", errors="replace")[-800:].strip()
            except OSError:
                tail = ""
            detail = f"\nFFmpeg: {tail}" if tail else ""
            raise RuntimeError(f"FFmpeg 处理失败（退出码 {error.returncode}）。{detail}") from error


def srt_time(value):
    milliseconds = round(value * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def ass_time(value):
    centiseconds = round(value * 100)
    hours, centiseconds = divmod(centiseconds, 360_000)
    minutes, centiseconds = divmod(centiseconds, 6_000)
    seconds, centiseconds = divmod(centiseconds, 100)
    return f"{hours}:{minutes:02}:{seconds:02}.{centiseconds:02}"


def wrap(text):
    text = re.sub(r"\s+", "", text)
    if len(text) <= 18:
        return text
    return text[:18] + "\n" + text[18:]


def dimensions(source):
    raw = subprocess.check_output(
        [FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", source],
        text=True,
        encoding="utf-8",
    )
    stream = json.loads(raw)["streams"][0]
    return stream["width"], stream["height"]


def translate_groups(groups, language):
    cues = []
    for number, words in enumerate(groups, start=1):
        source = " ".join(word["text"] for word in words)
        translated = None
        # Recreate the translator for each retry so a transient Google endpoint
        # failure does not poison the rest of the queue.
        for source_language in (language or "auto", "auto"):
            try:
                translator = GoogleTranslator(source=source_language, target="zh-CN")
            except Exception as error:
                note(f"Translation setup retry {number}: {type(error).__name__}")
                continue
            for attempt in range(3):
                try:
                    candidate = (translator.translate(source) or "").strip()
                    if candidate and "error" not in candidate.lower() and "server" not in candidate.lower():
                        translated = wrap(candidate)
                        break
                except Exception as error:
                    note(f"Translation retry {number}: {type(error).__name__}")
                time.sleep(1 + attempt)
            if translated:
                break
        # Never replace recognized speech with a fake sound label. Keeping the
        # recognized source text is more useful than hiding a translation error.
        text = translated or wrap(source)
        cues.append({"start": words[0]["start"], "end": words[-1]["end"], "text": text})
        note(f"Translated {number}/{len(groups)}" if translated else f"Kept original {number}/{len(groups)}")
    return cues


def make_groups(segments):
    groups, current = [], []
    for segment in segments:
        for word in segment.get("words", []):
            if current and word["start"] - current[-1]["end"] > 0.9:
                groups.append(current)
                current = []
            current.append(word)
            duration = word["end"] - current[0]["start"]
            if duration >= 5.5 or (duration >= 3 and re.search(r"[.!?…]$", word["text"])):
                groups.append(current)
                current = []
    if current:
        groups.append(current)
    return groups


def replace_long_cues(cues):
    # Long cues are still recognized speech. Do not fabricate moaning labels or
    # overwrite dialogue just because a segment has unusual timing.
    return cues


def write_subtitles(cues, output_srt, output_ass, width, height):
    font_size = round(height * 0.039)
    margin_v = round(height * 0.155)
    outline = round(height * 0.0028, 1)
    srt, ass = [], [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: Chinese,Microsoft YaHei,{font_size},&H00FFFFFF,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,{outline},0.8,2,52,52,{margin_v},1", "",
        "[Events]", "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    for number, cue in enumerate(cues, start=1):
        srt.extend([str(number), f"{srt_time(cue['start'])} --> {srt_time(cue['end'])}", cue["text"], ""])
        ass_text = cue["text"].replace("\n", r"\N")
        ass.append(f"Dialogue: 0,{ass_time(cue['start'])},{ass_time(cue['end'])},Chinese,,0,0,0,,{ass_text}")
    output_srt.write_text("\n".join(srt), encoding="utf-8-sig")
    output_ass.write_text("\n".join(ass), encoding="utf-8")


WORK.mkdir(parents=True, exist_ok=True)
OUTPUTS.mkdir(exist_ok=True)
model = WhisperModel("deepdml/faster-whisper-large-v3-turbo-ct2", device="cpu", compute_type="int8")
for position, source in enumerate(SOURCES, start=1):
    job = WORK / f"{position:02d}"
    job.mkdir(exist_ok=True)
    note(f"Starting {position}: {source.name}")
    audio = job / "audio.wav"
    command([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", source, "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", audio])
    segments, info = model.transcribe(
        str(audio),
        beam_size=5,
        best_of=5,
        temperature=0,
        vad_filter=True,
        vad_parameters={
            "min_silence_duration_ms": 180,
            "min_speech_duration_ms": 80,
            "speech_pad_ms": 500,
        },
        no_speech_threshold=0.2,
        log_prob_threshold=-1.5,
        compression_ratio_threshold=2.6,
        condition_on_previous_text=True,
        word_timestamps=True,
    )
    transcript = []
    for segment in segments:
        words = [{"start": word.start, "end": word.end, "text": word.word.strip()} for word in (segment.words or []) if word.word.strip()]
        # Word timestamps can be absent for quiet/short speech. Keep the
        # segment instead of silently dropping a perfectly valid recognition.
        if not words and segment.text.strip():
            words = [{"start": segment.start, "end": max(segment.end, segment.start + 0.8), "text": segment.text.strip()}]
        if words:
            transcript.append({"words": words})
    # Very quiet speech can be rejected by VAD on some computers. Retry once
    # without VAD only when the first pass found nothing, avoiding false cues
    # during normal processing while recovering low-volume dialogue.
    if not transcript:
        note("No speech found with VAD; retrying quiet-audio recognition")
        retry_segments, retry_info = model.transcribe(
            str(audio),
            beam_size=5,
            best_of=5,
            temperature=0,
            vad_filter=False,
            no_speech_threshold=0.15,
            log_prob_threshold=-1.8,
            compression_ratio_threshold=2.6,
            condition_on_previous_text=False,
            word_timestamps=True,
        )
        for segment in retry_segments:
            words = [{"start": word.start, "end": word.end, "text": word.word.strip()} for word in (segment.words or []) if word.word.strip()]
            if not words and segment.text.strip():
                words = [{"start": segment.start, "end": max(segment.end, segment.start + 0.8), "text": segment.text.strip()}]
            if words:
                transcript.append({"words": words})
        info = retry_info
    note(f"Recognized {len(transcript)} segments in {info.language} ({info.language_probability:.0%} confidence)")
    groups = make_groups(transcript)
    cues = replace_long_cues(translate_groups(groups, info.language))
    srt = OUTPUTS / f"{source.stem}.srt"
    ass = job / "subtitles.ass"
    width, height = dimensions(source)
    write_subtitles(cues, srt, ass, width, height)
    destination = DESKTOP / source.name
    command([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", source, "-vf", "ass=subtitles.ass", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "copy", destination], cwd=job)
    subprocess.run([FFPROBE, "-v", "fatal", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1", destination], check=True)
    note(f"Completed {position}: {destination}")

note("All videos completed and verified.")
