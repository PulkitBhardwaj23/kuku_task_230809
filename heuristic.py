import re

KW = re.compile(r"\b(slap|gasp|scream|dead|kill|poison|secret|truth|lie|divorce|wedding|blood|shock|betray|who|why|never|arsenic|ring|whip)\b", re.I)
END = re.compile(r"black|cliffhanger|freez|gasp|shock|terrified", re.I)


def find(ep, top=40):
    ev, D = ep["events"], ep["duration"]
    starts = sorted({e["start"] for e in ev})
    ends = sorted({e["end"] for e in ev})
    first = {s: " ".join(e["text"] for e in ev
                         if e["kind"] != "CAMERA" and e["start"] < s + 3 and e["end"] > s)
             for s in starts}
    lastline, endtext = {}, {}
    for t in ends:
        d = [e for e in ev if e["kind"] == "DIALOGUE" and e["end"] <= t]
        lastline[t] = d[-1]["text"] if d else ""
        endtext[t] = " ".join(e["text"] for e in ev if abs(e["end"] - t) < 0.05)
    out = []
    for s in starts:
        f = first[s]
        hook = min(10, (4 if f else 0) + 2 * len(KW.findall(f)) + (2 if re.search(r"[?!]", f) else 0))
        for t in ends:
            if not 20 <= t - s <= 60:
                continue
            ll = lastline[t]
            cliff = min(10, (4 if D - t <= 6 else 0)
                        + (3 if ll.rstrip('"').endswith(("?", "...", "…")) else 0)
                        + (3 if END.search(endtext[t]) else 0))
            out.append(dict(segments=[dict(episode=ep["ep"], start=s, end=t)],
                            hook=f[:120], cliffhanger=ll[:120],
                            why="rule-based: keyword hook, ending near episode end",
                            hook_score=hook, cliff_score=cliff, standalone_score=5))
    out.sort(key=lambda c: -(c["hook_score"] + c["cliff_score"]))
    return out[:top]
