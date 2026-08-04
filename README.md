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

- [x] [Lesson 1](docs/lesson-1.md) — Python, uv, virtual environments, pyproject.toml, running the server
- [x] [Lesson 2](docs/lesson-2.md) — FastAPI, endpoints, HTTP methods, JSON
- [x] [Lesson 3](docs/lesson-3.md) — Groq, API keys, environment variables, POST /chat
- [x] [Lesson 4](docs/lesson-4.md) — ChatPromptTemplate, system prompt, human prompt
- [x] [Lesson 5](docs/lesson-5.md) — StrOutputParser
- [x] [Lesson 6](docs/lesson-6.md) — LCEL, the `|` operator, `prompt | llm | parser`
- [x] [Lesson 7](docs/lesson-7.md) — RunnableLambda
- [x] [Lesson 8](docs/lesson-8.md) — RunnableMap
- [x] [Lesson 9](docs/lesson-9.md) — RunnableBranch
- [x] [Lesson 10](docs/lesson-10.md) — JsonOutputParser
- [x] [Lesson 11](docs/lesson-11.md) — PydanticOutputParser
- [ ] Lesson 12 — Structured Output
# Gen-AI-Basics
