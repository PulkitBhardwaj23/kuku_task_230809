import re, glob, os

TS = r"\((\d+):(\d+(?:\.\d+)?)\)"
HEAD = re.compile(r"^\*\*(.+?):\*\*\s*$")
TIME = re.compile(rf"^Start:\s*{TS}\s*\|\s*End:\s*{TS}")
SCENE = re.compile(r"^Scene (start|end):\s*(\d+):(\d+(?:\.\d+)?)")


def sec(m, s):
    return int(m) * 60 + float(s)


def fmt(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def parse_episode(path):
    lines = [l.strip() for l in open(path, encoding="utf-8-sig")]
    m = re.search(r"episode-(\d+)", os.path.basename(path), re.I)
    num = int(m.group(1)) if m else 0
    logline = notes = ""
    events, offset, last_end = [], 0.0, 0.0
    i = 0
    while i < len(lines):
        l = lines[i]
        if l.startswith("EPISODE NUMBER:"):
            n = re.search(r"(\d+)", l)
            num = int(n.group(1)) if n else num
        elif l.startswith("EPISODE LOGLINE:"):
            logline = l.split(":", 1)[1].strip()
        elif l.startswith("CONTINUITY NOTES:"):
            notes = l.split(":", 1)[1].strip()
        sc = SCENE.match(l)
        if sc and sc.group(1) == "start":
            s = sec(sc.group(2), sc.group(3))
            offset = last_end if (events and s < last_end - 1) else 0.0
        h = HEAD.match(l)
        if h and i + 1 < len(lines) and TIME.match(lines[i + 1]):
            t = TIME.match(lines[i + 1])
            start = sec(t.group(1), t.group(2)) + offset
            end = sec(t.group(3), t.group(4)) + offset
            j, text = i + 2, []
            while j < len(lines) and lines[j] and not HEAD.match(lines[j]):
                text.append(lines[j])
                j += 1
            name = h.group(1)
            up = name.upper()
            if up.startswith("CAMERA"):
                kind, speaker, tone = "CAMERA", "", ""
            elif up.startswith("ACTION"):
                kind, speaker, tone = "ACTION", "", ""
            elif up.startswith("SOUND"):
                kind, speaker, tone = "SOUND", "", ""
            else:
                kind = "DIALOGUE"
                speaker = name.split("(")[0].strip()
                tone = name[len(speaker):].strip()
            events.append(dict(kind=kind, speaker=speaker, tone=tone,
                               start=start, end=end, text=" ".join(text)))
            last_end = max(last_end, end)
            i = j
            continue
        i += 1
    events.sort(key=lambda e: (e["start"], e["end"]))
    return dict(ep=num, logline=logline, notes=notes, events=events,
                duration=max((e["end"] for e in events), default=0.0))


def load_all(folder):
    files = glob.glob(os.path.join(folder, "*.txt"))
    eps = [parse_episode(f) for f in files]
    eps = [e for e in eps if e["events"]]
    return sorted(eps, key=lambda e: e["ep"])


def transcript(ep):
    out = [f"=== EPISODE {ep['ep']} (length {ep['duration']:.1f}s) ===",
           f"Logline: {ep['logline']}", f"Continuity: {ep['notes']}"]
    for e in ep["events"]:
        who = e["kind"] if not e["speaker"] else f"{e['speaker']} {e['tone']}".strip()
        out.append(f"[{e['start']:.1f}-{e['end']:.1f}] {who}: {e['text']}")
    return "\n".join(out)
