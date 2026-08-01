# Gen AI Beginner Basics

A small AI Assistant API, built step by step to learn Python + LangChain.

## Stack

- Python 3.12
- uv (project + package manager)
- FastAPI (web framework)
- uvicorn (the server that runs FastAPI)

## Setup

Put your Groq API key in `.env` (get a free one at https://console.groq.com/keys):

```
GROQ_API_KEY=gsk_your_real_key
```

`.env` is gitignored — never commit it.

## Run the server

```bash
uv run uvicorn app:app --reload
```

Then open http://127.0.0.1:8000/docs

## Lesson progress

- [x] Lesson 1 — Python, uv, virtual environments, pyproject.toml, running the server
- [x] Lesson 2 — FastAPI, endpoints, HTTP methods, JSON
- [x] Lesson 3 — Groq, API keys, environment variables, POST /chat
- [ ] Lesson 4 — ChatPromptTemplate, system prompt, human prompt
- [ ] Lesson 5 — StrOutputParser
# Gen-AI-Basics
