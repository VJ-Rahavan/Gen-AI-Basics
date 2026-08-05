# Lesson 12 — Structured Output

## 1. Problem

`/report-v2` works. But look at how much code exists just to *ask nicely* for a shape:

```python
# 1. describe the shape in ENGLISH, for the model
REPORT_SYSTEM_PROMPT = """...
{{"summary": "one short sentence", "sentiment": "positive or negative or neutral", ...}}
Reply with the JSON object only. No code fences, no explanation."""

# 2. describe the SAME shape in PYTHON, for validation
class ChatResponse(BaseModel):
    summary: str = Field(...)
    sentiment: str = Field(...)
    language: str = Field(...)

# 3. bolt them together
pydantic_parser = PydanticOutputParser(pydantic_object=ChatResponse)
```

**The shape is described twice**, in two languages, and nothing keeps them in sync. Add a field to the class and forget the prompt: the model never returns it, validation fails, and the error points at the parser rather than at your forgotten edit.

And the whole arrangement rests on **persuasion**. You *ask* for JSON. You *ask* for no code fences. The model usually complies — but "usually" is doing a lot of work in that sentence. Every safeguard built so far (fence-stripping in Lesson 10, validation in Lesson 11) exists to catch a model that didn't quite listen.

Plus the mechanical annoyances: doubled braces (`{{`/`}}`) because your JSON example collides with placeholder syntax, and a prompt cluttered with formatting nags instead of actual instructions.

The question this lesson answers: **what if you could tell the model the shape in a way it can't misread — instead of asking in English and hoping?**

---

## 2. New Concepts

### What is structured output?

**Structured output** means the schema travels to the model **through the API**, as machine-readable data, rather than as prose inside your prompt.

One line:

```python
structured_llm = llm.with_structured_output(ChatResponse)
```

That returns a new model object that **always** replies as a `ChatResponse`. Then:

```python
report_v3_chain = cleaner | report_v3_prompt | structured_llm
#                                              ^^^^^^^^^^^^^ no parser written after it
```

### What actually happens

This is worth seeing, because it explains everything else. Inspecting what `with_structured_output` attaches to the request:

```
bound kwargs keys -> ['tools', 'ls_structured_output_format', 'tool_choice']

THE SCHEMA IS SENT AS A TOOL DEFINITION:
[
  {
    "type": "function",
    "function": {
      "name": "ChatResponse",
      "parameters": {
        "properties": {
          "summary":   {"description": "one short sentence summarising the message", "type": "string"},
          "sentiment": {"description": "positive, negative or neutral", "type": "string"},
          "language":  {"description": "the language the message is written in", "type": "string"}
        },
        "required": ["summary", "sentiment", "language"],
        "type": "object"
      }
    }
  }
]

tool_choice -> {'type': 'function', 'function': {'name': 'ChatResponse'}}
```

Your Python class became a **JSON Schema**, sent as a *tool definition* in a dedicated API field. And `tool_choice` says: *"you must use this one."* The model isn't asked to produce JSON in its prose — it's given a form to fill in, through a channel built for exactly that.

Notice your `Field(description=...)` text made it in, and `required` lists all three fields. **One Python class, no second description.**

### Analogy: a letter vs a form

**Output parser** is writing a letter: *"Please reply with your name, date of birth and address. Put them on separate lines, don't add a greeting."* The reply comes back as prose and you extract the fields — hoping the instructions were followed.

**Structured output** is sending a **form with labelled boxes**. There's a box marked *name*, a box marked *date of birth*. The form's structure carries the requirement; no cover letter needed. The reply comes back box by box.

That's the shift: from *describing* the shape to *providing* it.

### Output Parser vs Structured Output

| | Output Parser (L10–11) | Structured Output (L12) |
|---|---|---|
| Schema travels via | **the prompt**, as English | **the API**, as JSON Schema |
| Model is | *asked* for a shape | *given* a shape to fill |
| Shape written | **twice** (prompt + class) | **once** (class only) |
| Doubled braces `{{ }}` | required | not needed |
| Prompt contains format nags | yes | no |
| Where correctness is enforced | in your Python, after the fact | at the provider, during generation |
| Works with any model | **yes** | only models supporting tools/JSON mode |

The last row is the real trade-off. Output parsers work with *anything* that emits text — an old model, a local model, a plain HTTP endpoint. Structured output needs provider support. Since Groq supports it, we get the better option here.

### An honest correction: the parser is not gone

A first draft of this lesson claimed the chain would have three steps and "the parser is gone." Then it was printed:

```
report_chain    (L10) -> 4 steps: ['RunnableLambda', 'ChatPromptTemplate', 'ChatGroq', 'JsonOutputParser']
report_v2_chain (L11) -> 4 steps: ['RunnableLambda', 'ChatPromptTemplate', 'ChatGroq', 'PydanticOutputParser']
report_v3_chain (L12) -> 4 steps: ['RunnableLambda', 'ChatPromptTemplate', '_ChatModelBinding', 'PydanticToolsParser']
```

**Still four steps. Still a parser** — `PydanticToolsParser`. `with_structured_output` isn't one component; it's a small chain of two:

```
structured_llm  =  _ChatModelBinding  |  PydanticToolsParser
                   (model + schema       (reads the tool call
                    bound as a tool)      into your object)
```

LCEL flattens it into the outer chain, which is why you write three pieces and get four steps.

So what genuinely changed is **not** "no parsing." It's:

1. **Where the schema goes** — a dedicated API field instead of English prose in your prompt.
2. **Who writes the parsing** — LangChain, not you.
3. **How many times you describe the shape** — once instead of twice.

Worth stating plainly because "structured output means no parser" is a common claim, and it's wrong. The parsing moved out of your sight; it didn't disappear.

### Why do modern models support this?

Because asking for JSON in prose was never reliable, and everyone hit the same wall. Three developments made a better path possible:

1. **Tool calling.** Models were trained to emit function calls with typed arguments — for calling weather APIs, databases, and so on. That machinery is exactly "produce data matching this schema", so it was repurposed. That's why the schema shows up as `"type": "function"` above; you're using the tool-calling pathway without any actual tool.

2. **Constrained decoding.** Providers can restrict generation *token by token* so the output can only be schema-valid. The model literally cannot emit `{"summary": 123` when the schema says `string`. This is why it's stronger than asking: with real constrained decoding, invalid output isn't unlikely — it's unreachable.

3. **It's what applications actually need.** Chat needs prose. Everything else — extraction, classification, routing, form-filling — needs data. Providers standardized on it because that's what people build.

---

## 3. Project Changes

Both files, additive. Nothing to install.

| File | Change | Why |
|---|---|---|
| `llm.py` | `REPORT_V3_SYSTEM_PROMPT` (no JSON, no braces); `report_v3_prompt`; `structured_llm`; `report_v3_chain` | reuses `ChatResponse` from Lesson 11 unchanged |
| `app.py` | imported `report_v3_chain`; added `ReportV3Request` and `POST /report-v3` | third variant, so all three can be compared |

**`ChatResponse` is reused exactly as written in Lesson 11.** Not one character changed. That's the point worth noticing: the same class that *validated after the fact* now *instructs the model up front*. One definition, two very different uses.

All seven older endpoints confirmed `200`.

---

## 4. Complete Code

**`llm.py`** — new code at the bottom. No new imports:

```python
# ----- Lesson 12: let the MODEL know the shape, instead of asking in words -----

# No JSON example, no braces to double, no "reply with JSON only".
# The shape is sent separately, through the API, by with_structured_output.
REPORT_V3_SYSTEM_PROMPT = """You analyse the user's message.

Keep the summary to one short sentence.
Use lowercase for the sentiment and the language."""


report_v3_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", REPORT_V3_SYSTEM_PROMPT),
        ("human", "{message}"),
    ]
)


# Attach the ChatResponse shape to the model itself.
# Groq is told the exact schema through the API, so the model replies in that
# shape by construction instead of being asked for it in words.
# This does not remove the parsing step -- LangChain still adds one for us,
# inside structured_llm. We just no longer write it, or describe the shape twice.
structured_llm = llm.with_structured_output(ChatResponse)


# We write three pieces; LangChain expands structured_llm into two, so the
# finished chain still has four steps. Print chain.steps to see it.
report_v3_chain = cleaner | report_v3_prompt | structured_llm
```

Compare the prompts. Lesson 10's:

```python
"""You analyse the user's message.

Reply with a JSON object in exactly this shape:
{{"summary": "one short sentence", "sentiment": "positive or negative or neutral", "language": "the language the message is written in"}}

Use lowercase for sentiment.
Reply with the JSON object only. No code fences, no explanation."""
```

And Lesson 12's:

```python
"""You analyse the user's message.

Keep the summary to one short sentence.
Use lowercase for the sentiment and the language."""
```

Every line about *format* is gone. What remains is about *content* — which is what a prompt should be for. No `{{`, no field list, no pleading about code fences.

The "use lowercase" line is kept deliberately — see section 7 for why that one is still needed.

**`app.py`** — the new endpoint:

```python
class ReportV3Request(BaseModel):
    message: str


@app.post("/report-v3")
def report_v3(request: ReportV3Request):
    # The chain has no parser at the end, yet "result" is STILL a
    # ChatResponse object -- the model itself was told the shape.
    result = report_v3_chain.invoke({"message": request.message})

    # Same dot access as /report-v2. Nothing here had to change.
    return {
        "summary": result.summary,
        "sentiment": result.sentiment,
        "language": result.language,
        "model": llm.model_name,
    }
```

**Byte-for-byte the same body as `/report-v2`.** The endpoint can't tell the difference — both hand it a `ChatResponse`. That's a good sign: the change was internal to the pipeline.

---

## 5. Execution Flow

```
User
 │   POST /report-v3   {"message": "I am so frustrated about the water issue..."}
 ↓
FastAPI
 ↓
report_v3_chain.invoke({...})
 │
 │  ┌──────────────────────────────────────────────────────────────────────────┐
 │  │  {"message": "..."}                                                       │
 │  │            ↓  cleaner                                                     │
 │  │            ↓  report_v3_prompt     ← content instructions ONLY            │
 │  │  [SystemMessage("You analyse..."), HumanMessage("I am so frustrated...")]  │
 │  │            │                                                              │
 │  │            ↓  _ChatModelBinding                                           │
 │  │            │                                                              │
 │  │            │   the HTTP request to Groq carries TWO things:                │
 │  │            │     messages : the conversation above                         │
 │  │            │     tools    : {"name": "ChatResponse", "parameters": {...}}  │
 │  │            │                 ^^^^^^ your class, as JSON Schema            │
 │  │            │     tool_choice: "you MUST use ChatResponse"                  │
 │  │            ↓                                                              │
 │  │  AIMessage(tool_calls=[{name: 'ChatResponse', args: {...}}])               │
 │  │                        ^^^^^^^^^^ a tool call, not prose                   │
 │  │            │                                                              │
 │  │            ↓  PydanticToolsParser   ← LangChain added this for you         │
 │  │  ChatResponse(summary='...', sentiment='negative', language='english')     │
 │  └──────────────────────────────────────────────────────────────────────────┘
 ↓
result.sentiment
 ↓
Response
```

The key difference from Lesson 11's diagram is **what leaves your machine**. Before, the schema was buried in the system message as English. Now the request has a separate `tools` field carrying the schema as data, and the reply comes back as a **tool call** rather than prose that happens to look like JSON.

### The full arc, three lessons in one table

| | `/report` (L10) | `/report-v2` (L11) | `/report-v3` (L12) |
|---|---|---|---|
| Ends with | `JsonOutputParser` | `PydanticOutputParser` | `PydanticToolsParser` (automatic) |
| Returns | `dict` | `ChatResponse` | `ChatResponse` |
| Access | `result["x"]` | `result.x` | `result.x` |
| Missing field | **accepted** | rejected | can't happen (schema `required`) |
| Wrong type | **accepted** | rejected | can't happen (schema typed) |
| Shape written | prompt only | prompt **+** class | class only |
| Braces doubled | yes | yes | **no** |

Each lesson closed one gap. Lesson 10 gave you structure, Lesson 11 gave you verification, Lesson 12 moved the requirement to where it's enforced during generation instead of checked afterwards.

---

## 6. Run the Project

```bash
cd "/Users/purpleslate14mbp/Desktop/Mission G/gen-ai-beginner-basics"

uv run uvicorn app:app --reload
```

**Eight** endpoints now. Try `POST /report-v3`:

```bash
curl -X POST http://127.0.0.1:8000/report-v3 -H "Content-Type: application/json" \
  -d '{"message":"I am so frustrated right now because of a water issue in my apartment."}'
```

### See the schema being sent

This is the most instructive thing in the lesson. Look at what actually goes over the wire:

```bash
uv run python -c "
import json
from llm import llm, ChatResponse

st = llm.with_structured_output(ChatResponse)
kw = st.steps[0].kwargs
print('extra fields on the request ->', list(kw.keys()))
print()
print(json.dumps(kw['tools'], indent=2))
print()
print('tool_choice ->', kw['tool_choice'])
"
```

### Compare the chain shapes

```bash
uv run python -c "
from llm import report_chain, report_v2_chain, report_v3_chain
for name, c in [('L10', report_chain), ('L11', report_v2_chain), ('L12', report_v3_chain)]:
    print(name, '->', [type(s).__name__ for s in c.steps])
"
```

### Run all three side by side

```bash
for v in report report-v2 report-v3; do
  printf "%-10s -> " "$v"
  curl -s -X POST http://127.0.0.1:8000/$v -H "Content-Type: application/json" \
    -d '{"message":"This library is fantastic, it saved me hours!"}'
  echo ""
done
```

---

## 7. Expected Output

**`/report-v3`** (`200`, 0.44s):
```json
{
  "summary": "the user is frustrated with a water issue in their apartment",
  "sentiment": "negative",
  "language": "english",
  "model": "llama-3.3-70b-versatile"
}
```

### All three, same input, same moment

```
report     -> {"summary":"the user praises a library","sentiment":"positive","language":"english",...}  [200] 0.35s
report-v2  -> {"summary":"the user praises a library","sentiment":"positive","language":"english",...}  [200] 0.20s
report-v3  -> {"summary":"the user found the library to be fantastic","sentiment":"positive",...}       [200] 0.49s
```

**Identical shapes. Interchangeable results.** From the outside all three endpoints are the same API — which is exactly what you'd hope after two refactors.

On timing: 0.35 / 0.20 / 0.49s. **Don't read anything into that ordering.** Single samples over a network vary by more than the differences here; earlier in the lesson `/report-v2` measured 0.46s and now 0.20s, same code. If you care about latency, measure many runs, not one.

### Consistency

Five runs of `/report-v3`, with the prompt containing **no JSON instructions at all**:

```
run 1 -> sentiment='negative' language='english'
run 2 -> sentiment='negative' language='english'
run 3 -> sentiment='negative' language='english'
run 4 -> sentiment='negative' language='english'
run 5 -> sentiment='negative' language='english'
```

Five for five. The shape held without a single word of formatting instruction, because the shape was never a request.

### The limitation you must not miss

Calling the structured model **without** the "use lowercase" line gave:

```
summary='The user is frustrated about a water issue in their apartment.'
sentiment='negative'
language='English'          ← capital E
```

**Structured output guarantees the SHAPE, not the VALUES.** The schema says `language` must be a string. `"English"` is a string. Perfectly valid — and not what you wanted.

So the Lesson 8 bug is **still reachable**. `sentiment: str` still permits `"Negative."`. The guarantees you now have and don't have:

| Guaranteed by structured output | **Not** guaranteed |
|---|---|
| every required field present | values in the right *case* |
| every field the declared *type* | values from an allowed *set* |
| no extra fields | values being sensible or true |

That's why `Use lowercase for the sentiment and the language.` stays in the prompt. It's a *content* instruction, which is what prompts are for — and it worked, five for five.

**To constrain the value set, the schema itself must say so** — `Literal["positive", "negative", "neutral"]`. Tested separately, it holds five for five *and* puts the allowed values into the schema the model receives. That's the Challenge, and it's the last gap in this whole series.

### All endpoints
```
/chat -> 200        /simple-chat -> 200   /ask -> 200          /analyze -> 200
/report -> 200      /report-v2 -> 200     /report-v3 -> 200
```

---

## 8. Mini Exercise

**Prove the schema is what does the work.**

**Part 1 — delete the formatting help and see it survive.** Strip `REPORT_V3_SYSTEM_PROMPT` down to nothing but:

```python
REPORT_V3_SYSTEM_PROMPT = """You analyse the user's message."""
```

Hit `/report-v3`. All three fields should still come back correctly. Then do the same to `REPORT_SYSTEM_PROMPT` (used by `/report` and `/report-v2`) and hit those endpoints. What happens, and why the difference?

**Part 2 — add a field in one place.** Add to `ChatResponse`:

```python
word_count: int = Field(description="how many words the message contains")
```

Return it from `/report-v3`. Then check:

1. How many files/places did you edit to make `/report-v3` return it?
2. Did `/report-v2` break, keep working, or start returning it too? Explain — remember which prompt each chain uses.
3. Is `word_count` a real Python `int` in the response, or a string? Confirm with `print(type(result.word_count))`. The schema said `integer` — did that hold?

**Part 3 — an optional field.** Add:

```python
topic: str = "unknown"
```

Print the tool definition again (section 6's first command). Is `topic` in the `"required"` list? Compare with the fields that have no default. This is the `= default` rule from Lesson 5, now visible in the schema the model receives.

---

## 9. Challenge

**Close the last gap, then decide which of your three approaches you'd actually ship.**

**Part 1 — enforce the value set.** Change `ChatResponse`:

```python
from typing import Literal


class ChatResponse(BaseModel):
    summary: str = Field(description="one short sentence summarising the message")
    sentiment: Literal["positive", "negative", "neutral"] = Field(
        description="exactly one of: positive, negative, neutral"
    )
    language: str = Field(description="the language the message is written in, lowercase")
```

Then:

1. Print the tool definition. Does `sentiment` now carry an `"enum"`? **This is the important bit** — you're no longer *hoping* for one of three values, you're telling the API that only three exist.
2. Remove `Use lowercase for the sentiment...` from the prompt. Does the sentiment stay lowercase anyway? It should — the enum values *are* lowercase, so there's nothing else to emit. You just replaced a prompt instruction with a schema constraint.
3. Does `language` stay lowercase? Probably not — it has no enum, only a description. What does that tell you about description vs constraint?
4. All three endpoints share `ChatResponse`. Did `/report-v2` change behavior too? Why?

**Part 2 — the decision.** You have three working implementations of one feature. Write a short recommendation, in your own words, covering:

5. **Which would you ship, and why?** Consider: lines of code, number of places describing the shape, failure modes, and how much you trust each.
6. **When would you deliberately pick an output parser over structured output?** There are real answers — a model without tool support, a local model, a provider whose structured mode is buggy, or needing the raw text alongside the data. Name at least two.
7. **Which endpoints in your project would benefit from structured output that don't use it yet?** Look at `/analyze` (five calls, drifting `"Negative."` strings) and `/ask` (routing by keyword). Could `/ask`'s router be a structured call returning `{"route": Literal["coding", "general"]}` instead of a keyword list? Sketch what that would look like, and estimate the cost.
8. **The reflective one.** Across twelve lessons, the shape of the answer moved from *hoped for* → *asked for* → *validated* → *enforced by the API*. That's four positions on one axis. For your `/chat` endpoint, which returns free prose — where should it sit, and why is the answer different there?
