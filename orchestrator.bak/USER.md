# USER: orchestrator

## Purpose
Defines user context, preferences, and interaction patterns.
The orchestrator reads this file at startup and on each new conversation
to adapt its tone, defaults, and behavior accordingly.

---

## User Profile

```yaml
name         : (not set — update when known)
role         : System developer / ML engineer
language     : Indonesian (Bahasa Indonesia)
tech_level   : Advanced — understands agent architecture, ML concepts, Python
timezone     : Asia/Jakarta (WIB, UTC+7)
```

---

## Interaction Preferences

### Language
- **Respond in Bahasa Indonesia** for all chat (UI) interactions
- **Respond in English** for all API interactions (structured JSON, no natural language)
- Technical terms (skill names, file paths, JSON keys) always in English regardless of mode

### Tone (Chat mode)
- Direct and technical — skip pleasantries, get to the point
- Show intermediate steps for long tasks ("Step 1/3: Retrieving from knowledge base...")
- Use progress indicators when delegating to slow skills (video processing)
- Do not over-explain things the user already knows

### Output verbosity
- Short answers preferred unless the user asks to elaborate
- Always show sources when answering from knowledge base
- For pipeline results, show a summary table — not raw JSON
- Raw JSON only when explicitly requested or in API mode

---

## Default Parameters

These are the defaults to use when the user does not specify:

| Parameter          | Default     | Notes                                      |
|--------------------|-------------|--------------------------------------------|
| rag top_k          | 4           | Chunks passed to LLM                       |
| rag top_n          | 10          | Candidates from ChromaDB before rerank     |
| rag temperature    | 0.2         | Factual, low creativity                    |
| whisper model      | medium      | Good accuracy for Indonesian               |
| whisper language   | id          | Indonesian — override if video is in EN    |
| domain_filter      | null        | No filter unless user specifies domain     |
| video_filter       | null        | No filter unless user specifies video      |
| pipeline force     | false       | Skip already-processed videos              |

---

## Known Context

### System configuration
- LLM      : qwen2.5:9b via Ollama (local, no cloud API)
- ASR      : OpenAI Whisper
- VectorDB : ChromaDB (persistent, local)
- Agents   : orchestrator + ml_processor (2 agents active)
- Environment: Development / testing phase

### User's current focus
- Testing the full pipeline: video processing → knowledge base → RAG query
- Validating orchestrator → ml_processor delegation works correctly
- Both chat and API interaction modes

---

## Shorthand Commands (Chat mode)

Recognize these shorthand inputs and expand to full actions:

| User says                        | Orchestrator does                                           |
|----------------------------------|-------------------------------------------------------------|
| "status" / "cek status"          | check_heartbeat all agents + check_vector_store             |
| "list video" / "video apa saja"  | list_processed_videos                                       |
| "proses [filename]"              | delegate video_content_analysis with that file              |
| "tanya: [question]"              | delegate rag_engine with that question, skip intent detect  |
| "help" / "bantuan"               | Show available commands and agent capabilities              |

---

## Session Memory

The orchestrator does NOT persist memory across sessions by default.
Each new session starts fresh from these files.

If the user provides context during a session (e.g. "I'm working on the finance domain"),
carry that context for the duration of the session only — do not write it back to this file
unless the user explicitly says "remember this".

---

## Update Instructions

When the user profile changes (new preferences, new agents added, etc.):
1. The orchestrator itself should NOT edit this file
2. The system developer (user) edits USER.md directly
3. Changes take effect on next orchestrator startup or warm start
