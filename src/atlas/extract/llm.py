"""A small local model (through Ollama) that confirms or rejects what the rules propose and finds what they miss.

Free and offline: nothing leaves the laptop. Answers are forced into a JSON schema, the model sees one sentence at a time,
and it is told to use only that sentence. Every answer is cached by (model, prompt version, input), so a re-run costs
nothing. The prompt version is part of the cache key and of every fact it produces: change the prompt, bump the version.
"""

from __future__ import annotations

import hashlib
import json
import threading

import requests
import yaml

from ..core import ROOT

OLLAMA = "http://127.0.0.1:11434"
MODEL = "qwen2.5:3b"
PROMPT_VERSION = "v2"
CACHE = ROOT / "data" / "cache" / "llm_facts.jsonl"
VALUES = ["yes", "limited", "no"]
_lock = threading.Lock()
_cache: dict[str, dict] | None = None

SYSTEM = (
    "You read single sentences from websites and report facts about physical accessibility (wheelchair access, "
    "restrooms, parking, entrances, hearing, vision, sensory needs, trails). Use ONLY the sentence you are given. "
    "A headline, event title, program name, law or general statement is NOT a fact about a place or service. "
    "Answer with JSON only."
)


def attributes() -> dict[str, str]:
    return yaml.safe_load((ROOT / "config" / "attributes.yaml").read_text())


def _key(kind: str, *parts: str) -> str:
    return hashlib.sha256("\x1f".join([MODEL, PROMPT_VERSION, kind, *parts]).encode()).hexdigest()


def _load() -> dict:
    global _cache
    if _cache is None:
        _cache = {}
        if CACHE.exists():
            for line in CACHE.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    _cache[r["key"]] = r["answer"]
    return _cache


def _store(key: str, answer: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with _lock, CACHE.open("a") as f:
        f.write(json.dumps({"key": key, "answer": answer}) + "\n")
    _load()[key] = answer


def available(model: str = MODEL) -> bool:
    try:
        tags = requests.get(f"{OLLAMA}/api/tags", timeout=3).json()
        return any(
            m["name"].split(":")[0] == model.split(":")[0] and m["name"] == model
            for m in tags.get("models", [])
        )
    except (requests.RequestException, ValueError):
        return False


def _chat(prompt: str, schema: dict, num_predict: int = 200) -> dict:
    r = requests.post(
        f"{OLLAMA}/api/chat",
        json={
            "model": MODEL,
            "stream": False,
            "format": schema,
            "keep_alive": "30m",
            "options": {"temperature": 0, "num_ctx": 2048, "num_predict": num_predict},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
        },
        timeout=300,
    )
    r.raise_for_status()
    return json.loads(r.json()["message"]["content"])


VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "states_fact": {"type": "boolean"},
        "value": {"type": "string", "enum": VALUES},
        "detail": {"type": "string"},
    },
    "required": ["states_fact", "value", "detail"],
}


def verify(sentence: str, attribute: str, proposed: str) -> dict:
    """{states_fact, value, detail} for one rule-proposed (sentence, attribute)."""
    key = _key("verify", attribute, sentence)
    cache = _load()
    if key in cache:
        return cache[key]
    meaning = attributes().get(attribute, attribute)
    prompt = (
        "Decide whether the sentence is a statement about what a place, venue or service offers or lacks for the attribute below.\n"
        'Say states_fact=false ONLY for a headline, a title, an event or program name, a law, or text that says nothing about the attribute.\n'
        'value: "yes" = available / accessible (also when there is a fee or it is on request), "limited" = only partly or only some areas, '
        '"no" = not available. detail: the key words from the sentence, at most 10 words.\n\n'
        "Examples:\n"
        'Attribute restroom_accessible. Sentence: "Accessible restrooms are located throughout Union Terminal." '
        '-> {"states_fact": true, "value": "yes", "detail": "throughout Union Terminal"}\n'
        'Attribute elevator. Sentence: "There is no elevator to the second floor." '
        '-> {"states_fact": true, "value": "no", "detail": "no elevator to second floor"}\n'
        'Attribute wheelchair_loan. Sentence: "Wheelchairs are available for rental at the box office." '
        '-> {"states_fact": true, "value": "yes", "detail": "rental at the box office"}\n'
        'Attribute entrance_step_free. Sentence: "Some galleries can only be reached by stairs." '
        '-> {"states_fact": true, "value": "limited", "detail": "some galleries only by stairs"}\n'
        'Attribute sensory_friendly. Sentence: "Sensory-Friendly Santa" -> {"states_fact": false, "value": "no", "detail": ""}\n'
        'Attribute asl_interpretation. Sentence: "Cincinnati State\u2019s Interpreter Training Program" '
        '-> {"states_fact": false, "value": "no", "detail": ""}\n\n'
        f'Now this one. Attribute {attribute} ({meaning}). Sentence: "{sentence}"\n'
        f"(A pattern matcher guessed the value is {proposed!r}; correct it if the sentence says otherwise.)"
    )
    try:
        ans = _chat(prompt, VERIFY_SCHEMA)
    except (requests.RequestException, ValueError, KeyError):
        return {
            "states_fact": None,
            "value": proposed,
            "detail": "",
            "error": True,
        }  # not cached: try again next run
    _store(key, ans)
    return ans


def discover_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "attribute": {"type": "string", "enum": list(attributes())},
                        "value": {"type": "string", "enum": VALUES},
                        "detail": {"type": "string"},
                    },
                    "required": ["attribute", "value", "detail"],
                },
            }
        },
        "required": ["facts"],
    }


def discover(sentence: str) -> list[dict]:
    """Facts stated in a sentence that no rule matched: [{attribute, value, detail}] (often empty)."""
    key = _key("discover", sentence)
    cache = _load()
    if key in cache:
        return cache[key]["facts"]
    menu = "\n".join(f"- {a}: {d}" for a, d in attributes().items())
    prompt = (
        f'Sentence: "{sentence}"\n\nWhich of these attributes does the sentence state a fact about, for a specific place, '
        f"venue, service or programme? Return an empty list if none.\n{menu}"
    )
    try:
        ans = _chat(prompt, discover_schema(), num_predict=300)
    except (requests.RequestException, ValueError, KeyError):
        return []
    _store(key, ans)
    return ans["facts"]
