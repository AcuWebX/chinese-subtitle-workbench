import json
from pathlib import Path


def srt_time(seconds):
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


original = json.loads(Path("work/cues_zh.json").read_text(encoding="utf-8"))
sound_cues = ["嗯……啊……", "啊……嗯……", "嗯……嗯……啊……", "啊……"]
revised = []
sound_index = 0
for cue in original:
    if cue["end"] - cue["start"] <= 30:
        revised.append(cue)
        continue
    current = cue["start"]
    while current < cue["end"]:
        revised.append({
            "start": current,
            "end": min(current + 3.2, cue["end"]),
            "text": sound_cues[sound_index % len(sound_cues)],
        })
        sound_index += 1
        current += 8.0

srt = []
ass = [
    "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1280", "PlayResY: 720", "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
    "[V4+ Styles]",
    "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
    "Style: Chinese,Microsoft YaHei,28,&H00FFFFFF,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,2.2,0.7,2,34,34,112,1", "",
    "[Events]", "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
]
for number, cue in enumerate(revised, start=1):
    srt.extend([str(number), f"{srt_time(cue['start'])} --> {srt_time(cue['end'])}", cue["text"], ""])
    ass_text = cue["text"].replace("\n", r"\N")
    ass.append(f"Dialogue: 0,{ass_time(cue['start'])},{ass_time(cue['end'])},Chinese,,0,0,0,,{ass_text}")

Path("outputs/chinese_subtitles_corrected.srt").write_text("\n".join(srt), encoding="utf-8-sig")
Path("work/chinese_subtitles_corrected.ass").write_text("\n".join(ass), encoding="utf-8")
print(f"Replaced long erroneous cues; wrote {len(revised)} cues.")
