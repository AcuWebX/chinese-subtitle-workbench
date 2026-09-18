import json
import re
import time
from pathlib import Path

from deep_translator import GoogleTranslator


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


data = json.loads(Path("work/transcript_kz.json").read_text(encoding="utf-8"))
groups, current = [], []
for segment in data["segments"]:
    for word in segment.get("words", []):
        current.append(word)
        duration = word["end"] - current[0]["start"]
        if duration >= 5.5 or (duration >= 3 and re.search(r"[.!?…]$", word["text"])):
            groups.append(current)
            current = []
if current:
    groups.append(current)

translator = GoogleTranslator(source=data["language"], target="zh-CN")
cues = []
for number, words in enumerate(groups, start=1):
    source = " ".join(word["text"] for word in words)
    text = None
    for attempt in range(3):
        try:
            candidate = translator.translate(source)
            if candidate and "error" not in candidate.lower() and "server" not in candidate.lower():
                text = wrap(candidate)
                break
        except Exception:
            pass
        time.sleep(1.0 + attempt)
    if text is None:
        text = "（对白声）"
    cues.append({"start": words[0]["start"], "end": words[-1]["end"], "text": text})
    print(f"Translated {number}/{len(groups)}", flush=True)
    time.sleep(0.35)

# Whisper may stretch a hallucinated phrase over minutes in non-dialogue scenes.
sound_text = ["嗯……啊……", "啊……嗯……", "嗯……嗯……啊……", "啊……"]
revised, sound_index = [], 0
for cue in cues:
    if cue["end"] - cue["start"] <= 30:
        revised.append(cue)
        continue
    position = cue["start"]
    while position < cue["end"]:
        revised.append({"start": position, "end": min(position + 3.2, cue["end"]), "text": sound_text[sound_index % len(sound_text)]})
        sound_index += 1
        position += 8.0

srt, ass = [], [
    "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080", "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
    "[V4+ Styles]",
    "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
    "Style: Chinese,Microsoft YaHei,42,&H00FFFFFF,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,3,0.8,2,52,52,168,1", "",
    "[Events]", "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
]
for number, cue in enumerate(revised, start=1):
    srt.extend([str(number), f"{srt_time(cue['start'])} --> {srt_time(cue['end'])}", cue["text"], ""])
    ass_text = cue["text"].replace("\n", r"\N")
    ass.append(f"Dialogue: 0,{ass_time(cue['start'])},{ass_time(cue['end'])},Chinese,,0,0,0,,{ass_text}")

Path("outputs/chinese_subtitles_maid.srt").write_text("\n".join(srt), encoding="utf-8-sig")
Path("work/chinese_subtitles_maid.ass").write_text("\n".join(ass), encoding="utf-8")
print(f"Wrote {len(revised)} subtitle cues.")
