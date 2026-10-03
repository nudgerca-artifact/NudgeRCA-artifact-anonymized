"""Reads the answer of a FoundRoot response (the JSON between <answer> and </answer>) with the same tolerance as FoundRoot's
evaluation: unquoted or unescaped strings are repaired before the JSON is loaded, and an unreadable answer gives None."""
import json, re

def _repair(s, keys):
    out = list(s)
    for i in (m.start() for m in re.finditer(r'"', s)):   # escape quotes that neither open a known key nor follow ": "
        if not any(s[i + 1:].startswith(k) for k in keys) and not s[:i].endswith(": "): out[i] = r'\"'
    s = "".join(out).replace("True", "true").replace("False", "false")
    return re.sub(r'"\s*\n\s*"', '",\n"', s)

def _escape_newlines(s):
    return re.sub(r'(?<!\\)"([^"\\]*(?:\\.[^"\\]*)*)"', lambda m: m.group(0).replace("\n", "\\n"), s, flags=re.DOTALL)

def parse_answer(text, keys=("metric", "component", "conclusion", ",", ":", "\n", "}", "{")):
    if "<answer>" in text and "</answer>" in text: text = text.split("<answer>")[1].split("</answer>")[0]
    text = text.strip().replace("```json", "").replace("```", "")
    if "{" in text and "}" in text: text = text[text.find("{"):text.rfind("}") + 1]
    try:
        try: return json.loads(text)
        except Exception: return json.loads(_escape_newlines(_repair(text, keys)))
    except Exception:
        return None
