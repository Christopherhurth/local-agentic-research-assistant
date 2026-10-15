"""Final project for Agentic AI course 230/ish"""
import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

MODEL = os.getenv("AGENT_MODEL", "qwen2.5")
MAX_TURNS = int(os.getenv("MAX_ITERATIONS", "5"))
SERVER_SCRIPT = "rag_mcp_server.py"
BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")

DECLINE = "I don't have enough information in the document collection to answer that."

SYSTEM = (
    "You answer questions using ONLY a document collection reachable through "
    "the semantic_search tool.\n"
    "1. Always call semantic_search first. Never answer from background knowledge.\n"
    "2. Read the results. Lower distance means a better match. Decide in plain "
    "words whether they actually answer the question.\n"
    "3. If not, search again with different wording (at most a few times).\n"
    "4. Answer only with facts found in the results and cite them as "
    "(filename, p.N), using the real filename and page from the result, for example: (falconry_study utah.pdf, p.3).\n"
    f"5. If the documents do not contain the answer, reply exactly: {DECLINE}"
)

client = AsyncOpenAI(base_url=f"{BASE}/v1", api_key="ollama")


async def call_search(session, args):
    """Run semantic_search through MCP and return text for the model."""
    query = str(args.get("query", "")).strip()
    if not query:
        return "Error: query is empty."
    
    params = {"query": query}
    
    try:
        params["k"] = int(args.get("k", 5))
    except (TypeError, ValueError):
        params["k"] = 5
    
    result = await session.call_tool("semantic_search", params)
    
    blocks = [c.text for c in result.content if getattr(c, "type", "") =="text"]
    # text = "\n".join(c.text for c in result.content if getattr(c, "type", "") == "text")
    if getattr(result, "isError", False) or getattr(result, "is_error", False):
        return "Error from search tool: " + "\n".join(blocks)
    
    text = format_hits(blocks)
    print(f"\n[retrieved for '{query}']\n{text[:1500]}\n") # may need to try higher limit
    
    return text or "No results."


async def run_agentic_loop(session, tools_schema, user_prompt, max_turns=MAX_TURNS):
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_prompt},
    ]
    seen = set()

    for turn in range(max_turns):
        print(f"--- turn {turn + 1} ---")
        response = await client.chat.completions.create(
            model=MODEL, messages=messages, tools=tools_schema, temperature=0.1
        )
        response_message = response.choices[0].message
        messages.append(response_message.model_dump(exclude_none=True))

        if not response_message.tool_calls:
            if not searched and turn < max_turns - 1:
                messages.append({
                    "role": "user",
                    "content": "Call semantic_search tool first, then answer from the results."})
                continue
            return response_message.content

        for tool_call in response_message.tool_calls:
            name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if name != "semantic_search":
                result = f"Error: unknown tool {name}."
            else:
                key = str(args.get("query", "")).strip().lower()
                if key in seen:
                    result = "You already searched that. Rephrase it or give your answer."
                else:
                    seen.add(key)
                    searched = True
                    result = await call_search(session, args)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": name,
                "content": result,
            })

    # hit the cap: force a final answer with no tools
    print("Reached max turns, forcing a final answer.")
    messages.append({
        "role": "user",
        "content": "Search limit reached. Answer now using only what you "
                   f"retrieved, or reply exactly: {DECLINE}",
    })
    response = await client.chat.completions.create(
        model=MODEL, messages=messages, temperature=0.1
    )
    return response.choices[0].message.content

def format_hits(blocks):
    hits = []
    for b in blocks:
        try:
            data = json.loads(b)
        except ValueError:
            continue
        hits.extend(data if isinstance(data, list) else [data])
    lines = []
    for i, h in enumerate(hits, 1):
        if isinstance(h, dict) and "content" in h:
            lines.append(f"[{i}] {h.get('source', '')}, p.{h.get('page', '')} "
                         f"(distance {h.get('distance', '')}\ncontent: {h.get('content', '')}")
        elif isinstance(h, dict) and "message" in h:
            lines.append(f"[{i}] {h['message']}")
        else:
            lines.append(str(h))
    return '\n\n'.join(lines)


async def main():
    params = StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            tools_schema = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": t.input_schema,
                    },
                }
                for t in listed.tools
            ]
            print(f"Model: {MODEL} | tools: {[t.name for t in listed.tools]}")
            while True:
                try:
                    q = input("\nQuestion (blank to quit): ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not q:
                    break
                try:
                    answer = await run_agentic_loop(session, tools_schema, q)
                    print("\n=== Answer ===\n" + (answer or DECLINE))
                except Exception as e:
                    print(f"Something went wrong: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
