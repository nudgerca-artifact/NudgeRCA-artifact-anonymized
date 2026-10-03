"""Model-family adapter for the mixed-family size ladder. The pipeline scripts were written for Qwen3 (system+user messages,
chat template enable_thinking=True, reasoning between <think> and </think>, temperature 0.6 / top-p 0.95 / top-k 20). Prompt format per
family follows its model card; sampling is the same for every family (see SAMPLING):
  qwen3    : as before
  r1       : DeepSeek-R1 distills. No system prompt (instructions go to the user turn); <think> ... </think>
  nemotron : Llama-3.1-Nemotron-Nano. System "detailed thinking on", instructions in the user turn; <think> ... </think>
  gemma4   : Gemma 4. System prompt kept, thinking on through the chat template; reasoning between <|channel>thought and <channel|>
The family is read from the environment variable FAMILY (default qwen3).
gen_prompt(tok, system, user) returns the generation prompt that already ends with the reasoning opener, so a sample, a continuation
(gen_prompt + prefix) and a training context are built the same way."""
import os
FAMILY = os.environ.get("FAMILY", "qwen3")
OPEN, END = ("<|channel>thought\n", "<channel|>") if FAMILY == "gemma4" else ("<think>\n", "</think>")
# Every family samples with the Qwen3 setting used in the paper (temperature 0.6, top-p 0.95, top-k 20), so the only
# difference across the ladder is the model. 
SAMPLING = dict(temperature=0.6, top_p=0.95, top_k=20)

def messages(system, user):
    if FAMILY == "r1": return [{"role": "user", "content": system + "\n\n" + user}]
    if FAMILY == "nemotron": return [{"role": "system", "content": "detailed thinking on"}, {"role": "user", "content": system + "\n\n" + user}]
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]

def gen_prompt(tok, system, user):
    kw = {"enable_thinking": True} if FAMILY in ("qwen3", "gemma4") else {}
    p = tok.apply_chat_template(messages(system, user), tokenize=False, add_generation_prompt=True, **kw)
    return p if p.rstrip().endswith(OPEN.strip()) else p + OPEN

def split(text):
    """(reasoning, answer) of a generated text, or (None, None) when the reasoning never closes."""
    if END not in text: return None, None
    think, ans = text.split(END, 1)
    return think.replace(OPEN.strip(), "", 1).strip(), ans

def closed(text): return END in text
