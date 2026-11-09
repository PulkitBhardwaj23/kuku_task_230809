import os, hashlib, pathlib, time

CACHE = pathlib.Path("cache")
CACHE.mkdir(exist_ok=True)
PROVIDER = os.getenv("LLM_PROVIDER", "openai")
MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
BASE_URL = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
API_KEY = os.getenv("LLM_API_KEY", "")


def _call(system, user):
    if PROVIDER == "anthropic":
        from anthropic import Anthropic
        r = Anthropic(api_key=API_KEY or None).messages.create(
            model=MODEL, max_tokens=4000, system=system,
            messages=[{"role": "user", "content": user}])
        return r.content[0].text
    from openai import OpenAI
    r = OpenAI(base_url=BASE_URL, api_key=API_KEY).chat.completions.create(
        model=MODEL, temperature=0.2,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}])
    return r.choices[0].message.content


def ask(system, user):
    key = hashlib.sha256(f"{PROVIDER}|{MODEL}|{system}|{user}".encode()).hexdigest()
    f = CACHE / f"{key}.txt"
    if f.exists():
        return f.read_text(encoding="utf-8")
    for n in range(4):
        try:
            out = _call(system, user)
            f.write_text(out, encoding="utf-8")
            return out
        except Exception as e:
            if n == 3:
                raise
            time.sleep(15 * (n + 1))
