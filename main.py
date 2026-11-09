import argparse, csv, json, os, re
from collections import Counter
from parse import load_all, fmt, transcript
import llm, heuristic

MAX_PER_EP = 3

SYSTEM = """You are an editor who cuts promo clips for vertical microdrama apps (ReelShort, DramaBox style).
A promo is a 20-60 second clip taken from the screenplay, posted to pull in new viewers.
Rules:
- HOOK: in the first 3 seconds something makes a scroller stop (slap, reveal, shocking line, confrontation).
- CLIFFHANGER: the clip ends at an unresolved moment. Never include the answer or resolution.
- STANDALONE: someone who never saw the show must understand who is fighting about what.
- One continuous stretch is best. You may join 2-3 segments (also across the given episodes) only if it helps; keep them in story order.
- Total length of all segments: 20-60 seconds. Start at the beginning of a line/shot and end at the end of one.
- Use the times (in seconds) shown in the transcript.
- Return 0-3 promos. Only return strong ones. Do not pad.
Return ONLY a JSON list. Each item:
{"segments":[{"episode":int,"start":float,"end":float}],"hook":"what happens in first 3s","cliffhanger":"the unresolved moment at the end","why":"one line","hook_score":1-10,"cliff_score":1-10,"standalone_score":1-10}
Score strictly; most moments deserve 4-6."""


def llm_find(group):
    user = "\n\n".join(transcript(e) for e in group)
    raw = llm.ask(SYSTEM, user)
    m = re.search(r"\[.*\]", raw, re.S)
    return json.loads(m.group(0)) if m else []


def snap(ep, s, e):
    ev = ep["events"]
    s2 = min((x["start"] for x in ev), key=lambda v: abs(v - s))
    e2 = min((x["end"] for x in ev), key=lambda v: abs(v - e))
    return s2, e2


def build(raw, epmap):
    segs = []
    for g in raw.get("segments", []):
        ep = epmap.get(int(g["episode"]))
        if not ep:
            return None, "unknown episode"
        s, e = snap(ep, float(g["start"]), float(g["end"]))
        if e <= s:
            return None, "empty segment"
        segs.append(dict(episode=ep["ep"], start=s, end=e))
    if not segs:
        return None, "no segments"
    if [(g["episode"], g["start"]) for g in segs] != sorted((g["episode"], g["start"]) for g in segs):
        return None, "out of order"
    dur = sum(g["end"] - g["start"] for g in segs)
    if not 20 <= dur <= 60:
        return None, "bad duration"
    f = segs[0]
    ev = epmap[f["episode"]]["events"]
    weak = not any(x["kind"] != "CAMERA" and x["start"] < f["start"] + 3 and x["end"] > f["start"] for x in ev)
    h, c, s = (float(raw.get(k, 5)) for k in ("hook_score", "cliff_score", "standalone_score"))
    score = round(0.4 * h + 0.4 * c + 0.2 * s - (1 if weak else 0), 2)
    return dict(segments=segs, duration=round(dur, 1), hook=raw.get("hook", ""),
                cliffhanger=raw.get("cliffhanger", ""), why=raw.get("why", ""),
                hook_score=h, cliff_score=c, standalone_score=s,
                weak_open=weak, score=score), None


def overlap(a, b):
    return sum(max(0, min(x["end"], y["end"]) - max(x["start"], y["start"]))
               for x in a["segments"] for y in b["segments"] if x["episode"] == y["episode"])


def pick(cands):
    kept, per = [], Counter()
    for c in sorted(cands, key=lambda c: -c["score"]):
        if any(overlap(c, k) > 0.5 * min(c["duration"], k["duration"]) for k in kept):
            continue
        ep = c["segments"][0]["episode"]
        if per[ep] >= MAX_PER_EP:
            continue
        per[ep] += 1
        kept.append(c)
    return kept


def where(c):
    return " + ".join(f"E{g['episode']} {fmt(g['start'])}-{fmt(g['end'])}" for g in c["segments"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="episodes")
    ap.add_argument("--out", default="outputs")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--window", type=int, default=2)
    a = ap.parse_args()

    eps = load_all(a.input)
    epmap = {e["ep"]: e for e in eps}
    print(f"loaded {len(eps)} episodes")
    raws = []
    for i, e in enumerate(eps):
        if a.no_llm:
            raws += heuristic.find(e)
        else:
            try:
                raws += llm_find(eps[i:i + a.window])
            except Exception as ex:
                print(f"episode {e['ep']}: failed ({ex})")
    cands, rejected = [], Counter()
    for r in raws:
        try:
            c, why = build(r, epmap)
        except Exception:
            c, why = None, "bad json item"
        if c:
            cands.append(c)
        else:
            rejected[why] += 1
    final = pick(cands)
    for n, c in enumerate(final, 1):
        c["rank"] = n

    os.makedirs(a.out, exist_ok=True)
    json.dump(final, open(f"{a.out}/promos.json", "w"), indent=2)
    with open(f"{a.out}/promos.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "segments", "duration_s", "hook", "cliffhanger", "why", "score", "weak_open"])
        for c in final:
            w.writerow([c["rank"], where(c), c["duration"], c["hook"], c["cliffhanger"], c["why"], c["score"], c["weak_open"]])
    with open(f"{a.out}/report.md", "w", encoding="utf-8") as f:
        f.write(f"# Promos ({len(final)} found in {len(eps)} episodes)\n\n")
        for c in final:
            f.write(f"## #{c['rank']}  {where(c)}  ({c['duration']}s, score {c['score']})\n"
                    f"- Hook: {c['hook']}\n- Cliffhanger: {c['cliffhanger']}\n- Why: {c['why']}\n"
                    f"- Scores: hook {c['hook_score']}, cliff {c['cliff_score']}, standalone {c['standalone_score']}"
                    f"{' | WEAK OPEN' if c['weak_open'] else ''}\n\n")
        f.write(f"## Rejected by code checks\n{dict(rejected)}\n")
    print(f"{len(final)} promos -> {a.out}/ (rejected: {dict(rejected)})")


if __name__ == "__main__":
    main()
