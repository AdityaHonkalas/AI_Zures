"""Same agent test as test_agent.py, using the official openai SDK."""
import json, os
from datetime import datetime
from openai import OpenAI
 
for line in open(".env"):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v)
 
client = OpenAI(base_url=os.environ["GATEWAY_URL"].rstrip("/") + "/v1",
                api_key=os.environ["GATEWAY_KEY"])
 
TOOLS = [{"type": "function", "function": {
    "name": "get_time", "description": "Get the current local time",
    "parameters": {"type": "object", "properties": {}}}}]
 
def run_agent(model):
    msgs = [{"role": "user", "content": "What time is it? Use the tool, then answer in one sentence."}]
    for _ in range(3):
        msg = client.chat.completions.create(model=model, messages=msgs, tools=TOOLS).choices[0].message
        msgs.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            return f"OK: {msg.content}"
        for tc in msg.tool_calls:
            msgs.append({"role": "tool", "tool_call_id": tc.id,
                         "content": datetime.now().strftime("%H:%M:%S")})
    return "FAIL: agent loop did not finish"
 
def test_embedding(model):
    emb = client.embeddings.create(model=model, input="hello world")
    return f"OK: embedding length {len(emb.data[0].embedding)}"
 
if __name__ == "__main__":
    for m, fn in [("gpt-5-gig", run_agent), ("claude-sonnet-5-gig", run_agent),
                  ("text-embedding-3-large-gig", test_embedding)]:
        try:
            print(f"{m}: {fn(m)}")
        except Exception as e:
            print(f"{m}: FAIL ({type(e).__name__}): {str(e)[:300]}")