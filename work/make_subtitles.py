import json
import re
import time
from pathlib import Path

from deep_translator import GoogleTranslator


MAX_DURATION = 5.5
BREAK_AFTER = 3.0
MAX_CHARS_PER_LINE = 18


def subtitle_time(seconds):
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def ass_time(seconds):
    centiseconds = round(seconds * 100)
    hours, centiseconds = divmod(centiseconds, 360_000)
    minutes, centiseconds = divmod(centiseconds, 6_000)
    seconds, centiseconds = divmod(centiseconds, 100)
    return f"{hours}:{minutes:02}:{seconds:02}.{centiseconds:02}"


def make_cues(segments):
    cues, current = [], []
    for segment in segments:
        for word in segment["words"]:
            current.append(word)
            elapsed = word["end"] - current[0]["start"]
            punctuation = bool(re.search(r"[.!?…]$", word["text"]))
            if elapsed >= MAX_DURATION or (punctuation and elapsed >= BREAK_AFTER):
                cues.append(current)
                current = []
        if current and current[-1]["end"] - current[0]["start"] >= MAX_DURATION:
            cues.append(current)
            current = []
    if current:
        cues.append(current)
    return cues


def wrap_chinese(text):
    text = re.sub(r"\s+", "", text)
    if len(text) <= MAX_CHARS_PER_LINE:
        return text
    breakpoint = min(MAX_CHARS_PER_LINE, len(text) - 1)
    for offset in range(0, 7):
        for index in (breakpoint - offset, breakpoint + offset):
            if 0 < index < len(text) and text[index - 1] in "，。！？；：、":
                return text[:index] + "\n" + text[index:]
    return text[:breakpoint] + "\n" + text[breakpoint:]


data = json.loads(Path("work/transcript_ru.json").read_text(encoding="utf-8"))
translator = GoogleTranslator(source="ru", target="zh-CN")
cues = []
for index, words in enumerate(make_cues(data["segments"]), start=1):
    source = " ".join(word["text"] for word in words)
    try:
        translated = translator.translate(source)
    except Exception as error:
        print(f"Translation failed for cue {index}: {error}")
        translated = source
    cues.append({"start": words[0]["start"], "end": words[-1]["end"], "text": wrap_chinese(translated)})
    print(f"{index}/{len(cues)}", flush=True)
    time.sleep(0.12)

srt = []
ass = [
    "[Script Info]",
    "ScriptType: v4.00+",
    "PlayResX: 1280",
    "PlayResY: 720",
    "WrapStyle: 0",
    "ScaledBorderAndShadow: yes",
    "",
    "[V4+ Styles]",
    "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
    "Style: Chinese,Microsoft YaHei,28,&H00FFFFFF,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,2.2,0.7,2,34,34,34,1",
    "",
    "[Events]",
    "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
]
for index, cue in enumerate(cues, start=1):
    srt.extend([str(index), f"{subtitle_time(cue['start'])} --> {subtitle_time(cue['end'])}", cue["text"], ""])
    ass_text = cue["text"].replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")
    ass.append(f"Dialogue: 0,{ass_time(cue['start'])},{ass_time(cue['end'])},Chinese,,0,0,0,,{ass_text}")

Path("outputs/chinese_subtitles.srt").write_text("\n".join(srt), encoding="utf-8-sig")
Path("work/chinese_subtitles.ass").write_text("\n".join(ass), encoding="utf-8")
Path("work/cues_zh.json").write_text(json.dumps(cues, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(cues)} cues")
