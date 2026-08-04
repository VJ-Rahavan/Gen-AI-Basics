# Lesson 10 — JsonOutputParser

## 1. Problem

Every chain so far ends in `StrOutputParser` — you get **text**. Text is fine for a human reading an answer. It's a poor way for one program to talk to another.

You have already been bitten by this, twice:

**Lesson 8.** You asked for one lowercase word from `positive, negative, neutral`. You got `"Negative"`. Then on a later run, `"Negative."` Same prompt, three formats. Any code doing:

```python
if result["sentiment"] == "negative":     # silently False for both
```

...is broken, and broken *silently* — no error, no warning, just the wrong branch taken.

**Lesson 8's challenge.** The `valueExtractor` tried `x["summary"]` on `summary_chain`'s output and got:

```
TypeError : string indices must be integers, not 'str'
```

Because the output was a string, not a dictionary.

### Why plain text is hard for applications

Say you want three facts about a message — a summary, a sentiment, and its language. With text output the model replies:

```
The user seems frustrated about a water problem. The sentiment is negative,
and they are writing in English.
```

Correct, useless. To *use* those three facts your code must now find them in the prose:

```python
# don't do this
sentiment = "negative" if "negative" in answer.lower() else "positive"
```

Four things wrong with that, all fatal in production:

1. **The format changes run to run.** The model might say *"a negative tone"*, *"Sentiment: Negative"*, or *"they're not happy"*. Your parsing code chases a moving target forever.
2. **You get false matches.** *"This is not negative at all"* contains `"negative"`.
3. **No structure.** Three facts arrive fused in one blob. There's no `.sentiment` to read.
4. **Failures are silent.** When parsing fails you get a wrong value, not an exception — the worst kind of bug.

The `/analyze` endpoint dodged all this by using `RunnableMap` to run three *separate* chains, each returning one short string. That works — at the cost of **five LLM calls per request**.

### Why JSON is easier

JSON is a format with **exactly one correct reading**. `{"sentiment": "negative"}` means one thing. There's no prose to interpret, no phrasing to vary, and — crucially — **Python already knows how to turn it into a dictionary.**

So instead of asking for prose and guessing, you ask for JSON and *read* it:

```python
result["sentiment"]      # "negative". No searching, no guessing.
```

---

## 2. New Concepts

### What is `JsonOutputParser`?

It's a drop-in replacement for `StrOutputParser` at the end of your chain:

```python
json_parser = JsonOutputParser()

report_chain = cleaner | report_prompt | llm | json_parser
#                                              ^^^^^^^^^^^ the only change
```

Instead of handing you the model's text, it **reads that text as JSON and gives you a Python dictionary.**

### The difference, measured

The *same prompt* through the *same model* twice, changing only the parser:

```
=== with StrOutputParser ===
type      -> TextAccessor
value     -> '{"summary": "user is frustrated with apartment water issue", "sentiment": "negative", ...}'
is a dict? False

s["sentiment"] -> TypeError : string indices must be integers, not 'str'
```

```
=== with JsonOutputParser ===
type      -> dict
value     -> {'summary': 'user is frustrated with a water issue in their apartment',
              'sentiment': 'negative', 'language': 'english'}
is a dict? True

d["sentiment"] -> 'negative'
keys           -> ['summary', 'sentiment', 'language']
```

Look closely at the `StrOutputParser` output: it **contains** valid JSON. The model did its job. But it's still a *string* — note the outer quotes, and note the `TypeError`, which is precisely the error the `valueExtractor` hit.

The distinction is the whole lesson:

```
'{"sentiment": "negative"}'      ← a STRING that looks like JSON.  d["x"] → TypeError
 {"sentiment": "negative"}       ← a real Python DICTIONARY.       d["x"] → works
^                        ^
these quotes are the difference
```

### Analogy: a sealed box vs an unpacked one

Text output is a **sealed shipping box** with a description written on the side. You can read the label, but to get anything out you have to cut it open and rummage — and every shipment is packed differently.

JSON output through the parser is the box **already unpacked onto labelled shelves**. `result["sentiment"]` is reaching for the shelf marked *sentiment*.

`JsonOutputParser` is the person who opens the box and puts things on shelves. Every time, the same way.

### It's tolerant of the mess models make

Models often wrap JSON in markdown fences despite being told not to. Tested:

```
input was wrapped in fences + chatter:
   Here you go:
   ```json
   {"summary": "a test", ...}
   ```

parsed -> {'summary': 'a test', 'sentiment': 'neutral', 'language': 'english'}
```

It found the JSON inside the fences and the surrounding chatter, and parsed it anyway. Genuinely useful — that's a class of bug you'd otherwise hand-fix.

### And when it fails, it fails loudly

```
json_parser.invoke('Sorry, I cannot do that.')

OutputParserException
Invalid json output: Sorry, I cannot do that.
```

This is the property that matters most. Compare the two failure modes:

| | Text + manual searching | JSON parser |
|---|---|---|
| Model returns something odd | you get a **wrong value** | you get an **exception** |
| You find out | eventually, from a user | immediately, in the traceback |

**A loud failure beats a silent wrong answer.** An exception tells you exactly what went wrong; a silently mis-parsed sentiment corrupts your data quietly for weeks.

### The gotcha that will bite you: doubled braces

To ask for JSON you must show the model the shape you want. But braces are *placeholder syntax* in a prompt template (Lesson 4). So this crashes:

```python
"Reply as {\"summary\": \"...\"}"     # KeyError : '"summary"'
```

Verified:

```
=== single braces: treated as a PLACEHOLDER ===
KeyError : '"a"'

=== doubled braces: treated as LITERAL text ===
Reply as {"a": 1}
```

LangChain saw `{"a": 1}` and looked for a variable named `"a"`. **Double the braces to mean a literal brace:**

```python
{{  →  a literal {
}}  →  a literal }
```

This is the single most common error when writing JSON prompts. If you see `KeyError` with a quoted field name in it, you forgot to double a brace.

### The Python bit: dictionary vs object access, one more time

You now have both kinds in the same function, so it's worth stating plainly:

```python
request.message       # OBJECT (Pydantic)   → dot access
result["sentiment"]   # DICTIONARY (parser) → square brackets
```

Mixing these up is the most common early Python error in this project. The rule: **if a parser or a `RunnableMap` produced it, use `["..."]`.** If Pydantic produced it, use `.`.

---

## 3. Project Changes

Both files, additive. Nothing to install.

| File | Change | Why |
|---|---|---|
| `llm.py` | added `JsonOutputParser` to the import; `REPORT_SYSTEM_PROMPT`; `report_prompt`; `json_parser`; `report_chain` | parsing is AI plumbing |
| `app.py` | import reformatted to multi-line, added `report_chain`; new `ReportRequest` and `POST /report` | new capability, new endpoint |

**`parser` (the string one) is still there and still used** by five other chains. Adding `json_parser` doesn't replace it — different chains want different output shapes.

All four older endpoints confirmed `200`.

> **A note on the import style.** `app.py`'s import got long enough to wrap:
> ```python
> from llm import (
>     llm,
>     chain,
>     ...
> )
> ```
> The parentheses let one import span several lines — the same "indentation relaxes inside brackets" rule from Lesson 3's multi-line dictionary. One name per line means adding the next one is a clean one-line change.

---

## 4. Complete Code

**`llm.py`** — the import:

```python
# StrOutputParser turns a model's message object into a plain string.
# JsonOutputParser turns the model's JSON text into a real Python dictionary.
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
```

New code at the bottom:

```python
# ----- Lesson 10: ask for JSON instead of prose -----

# NOTE THE DOUBLED BRACES {{ and }}.
# A single { starts a placeholder, so {"summary": ...} would be read as a
# variable named '"summary"' and crash. Doubling them means "a literal brace".
REPORT_SYSTEM_PROMPT = """You analyse the user's message.

Reply with a JSON object in exactly this shape:
{{"summary": "one short sentence", "sentiment": "positive or negative or neutral", "language": "the language the message is written in"}}

Use lowercase for sentiment.
Reply with the JSON object only. No code fences, no explanation."""


report_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", REPORT_SYSTEM_PROMPT),
        ("human", "{message}"),
    ]
)


# The new parser. StrOutputParser gave us text; this one reads that text AS
# JSON and hands back a real Python dictionary.
json_parser = JsonOutputParser()


# Same shape of chain as always -- only the last piece changed.
report_chain = cleaner | report_prompt | llm | json_parser
```

Notice `("human", "{message}")` still has **single** braces — that one *is* a placeholder and must stay single. Only the literal JSON example is doubled.

**`app.py`** — the new endpoint:

```python
class ReportRequest(BaseModel):
    message: str


@app.post("/report")
def report(request: ReportRequest):
    # ONE call to Groq returns all three facts at once.
    # Because the chain ends with JsonOutputParser, "result" is already a
    # Python DICTIONARY -- not a string we would have to pick apart.
    result = report_chain.invoke({"message": request.message})

    # So we can read fields straight out of it, the normal way.
    return {
        "summary": result["summary"],
        "sentiment": result["sentiment"],
        "language": result["language"],
        "model": llm.model_name,
    }
```

---

## 5. Execution Flow

```
User
 │   POST /report   {"message": "I am so frustrated about the water issue..."}
 ↓
FastAPI
 ↓
report_chain.invoke({...})
 │
 │  ┌──────────────────────────────────────────────────────────────────────┐
 │  │  {"message": "I am so frustrated about..."}                           │
 │  │            ↓  cleaner                                                 │
 │  │  {"message": "I am so frustrated about..."}                           │
 │  │            ↓  report_prompt      ← the {{...}} shape goes to the model │
 │  │  [SystemMessage("...reply with JSON in this shape..."), HumanMessage]  │
 │  │            ↓  llm               ← ONE network call                     │
 │  │  AIMessage(content='{"summary": "...", "sentiment": "negative", ...}') │
 │  │                              ^^^ still a STRING at this point          │
 │  │            ↓  json_parser       ← reads the text AS JSON               │
 │  │  {'summary': '...', 'sentiment': 'negative', 'language': 'english'}    │
 │  │   ^ a real Python dictionary                                           │
 │  └──────────────────────────────────────────────────────────────────────┘
 ↓
result["sentiment"]  →  works
 ↓
Response
```

Compare this to `/analyze` from Lesson 8, which gets similar information:

| | `/analyze` (Lesson 8) | `/report` (Lesson 10) |
|---|---|---|
| Technique | `RunnableMap`, 4 branches | one JSON call |
| LLM calls | **5** | **1** |
| Output format | one string per branch | one dictionary |
| Sentiment value | `"Negative"` / `"Negative."` — drifts | `"negative"` — consistent |
| Measured time | ~0.85s | **~0.38s** |

**Five calls became one, and it got twice as fast.** That's not what this lesson was about, but it's a real consequence: asking one model for a structured answer often beats orchestrating several models for pieces of it.

---

## 6. Run the Project

```bash
cd "/Users/purpleslate14mbp/Desktop/Mission G/gen-ai-beginner-basics"

uv run uvicorn app:app --reload
```

**Six** endpoints now. Try `POST /report`:

```bash
curl -X POST http://127.0.0.1:8000/report -H "Content-Type: application/json" \
  -d '{"message":"I am so frustrated right now because of a water issue in my apartment."}'
```

### See the string-vs-dictionary difference yourself

The experiment that makes this concrete — same prompt, same model, two parsers:

```bash
uv run python -c "
from llm import cleaner, report_prompt, llm, parser, json_parser

text = 'I am so frustrated about the water issue.'

s = (cleaner | report_prompt | llm | parser).invoke({'message': text})
print('StrOutputParser  ->', type(s).__name__, '| is dict?', isinstance(s, dict))

d = (cleaner | report_prompt | llm | json_parser).invoke({'message': text})
print('JsonOutputParser ->', type(d).__name__, '| is dict?', isinstance(d, dict))
print('d[\"sentiment\"]   ->', repr(d['sentiment']))
"
```

### And see it fail properly

```bash
uv run python -c "
from llm import json_parser
json_parser.invoke('Sorry, I cannot do that.')
"
```

Read that `OutputParserException`. Getting comfortable with it now is worth a lot — it's the error you'll meet whenever a model ignores your format instructions.

---

## 7. Expected Output

**A — English, negative** (`200`, **0.38s**):
```json
{
  "summary": "user is frustrated with a water issue in their apartment",
  "sentiment": "negative",
  "language": "english",
  "model": "llama-3.3-70b-versatile"
}
```

**B — Tamil input**, to check the `language` field is real:
```json
{
  "summary": "python lists are mutable",
  "sentiment": "neutral",
  "language": "tamil",
  "model": "llama-3.3-70b-versatile"
}
```

It detected Tamil *and* summarized in English. Nice bonus.

**C — positive:**
```json
{
  "summary": "the user likes the library",
  "sentiment": "positive",
  "language": "english",
  "model": "llama-3.3-70b-versatile"
}
```

### The consistency win

This is the payoff for Lesson 8's `"Negative."` problem. Four consecutive runs, same input:

```
run 1 -> sentiment='negative'  language='english'
run 2 -> sentiment='negative'  language='english'
run 3 -> sentiment='negative'  language='english'
run 4 -> sentiment='negative'  language='english'
```

**Four for four, lowercase, no trailing period.** Now `if result["sentiment"] == "negative":` actually works.

Why so much steadier? Because JSON is a *format the model recognizes*, and being inside a quoted JSON string value discourages the decorative punctuation that free prose invites.

**But be careful with the word "guaranteed."** Nothing here *enforces* the value. The model could still return `"Negative"`, or `"very negative"`, or a `sentiment` key that's missing entirely — and `JsonOutputParser` would happily hand you the dictionary, because that's still valid JSON. It validates **syntax**, not **content**.

Four out of four is encouraging, not a guarantee. **That gap is exactly what Lesson 11 closes.**

### Regressions
```
/chat -> 200      /simple-chat -> 200      /ask -> 200      /analyze -> 200
```

---

## 8. Mini Exercise

**Add a fourth field, then break it on purpose.**

**Part 1** — add `"is_question"`, a true/false field. In `REPORT_SYSTEM_PROMPT`, extend the shape:

```
{{"summary": "...", "sentiment": "...", "language": "...", "is_question": true}}
```

Return `result["is_question"]` from the endpoint. Then send a statement and a question, and check:

1. Does the value come back as JSON `true`/`false`, or as the string `"true"`? Test with `print(type(result["is_question"]))`. JSON booleans become real Python `True`/`False` — worth confirming, because `"false"` (a non-empty string) is **truthy** in Python and would silently break an `if`.

**Part 2** — cause the brace error deliberately. Change one `{{` to a single `{` and hit the endpoint. Read the error. Which field name appears in the `KeyError`, and why that one?

**Part 3** — cause a parse failure. Add this line to the end of the system prompt:

```
Also add a friendly greeting before the JSON.
```

Send a request. Does it still work, or do you get `OutputParserException`? The answer may surprise you — recall the fence test. Then try `Reply in plain prose, no JSON.` and see it fail properly.

---

## 9. Challenge

**Replace `/analyze`'s five calls with one, and measure what you gain and lose.**

The `/analyze` endpoint uses `RunnableMap` with four branches and makes five LLM calls to produce a summary, translation, sentiment, and Tamil summary. `/report` gets three comparable facts in **one** call. So: rebuild `/analyze`'s output using a single JSON call.

1. **Write one prompt** asking for all four fields at once:
   ```
   {{"summary": "...", "translation": "the message in Tamil", "sentiment": "...", "tamil_summary": "the summary in Tamil"}}
   ```
   Build `analyze_json_chain`, and add a `POST /analyze-v2` endpoint. Leave the original `/analyze` alone so you can compare them side by side.

2. **Time both.** Expect a big difference — but which direction? One call doing four jobs isn't necessarily faster than four calls doing one job each, because the single call has to *generate more tokens*, and generation is the slow part. Predict before measuring, then measure.

3. **Compare quality honestly.** Read the Tamil from both. Is the one-shot translation as good as the dedicated translation chain? A prompt focused on one job usually outperforms a prompt juggling four — this is a real trade-off, not a free win.

4. **Break it and compare failure modes.** Send an empty-ish message like `"..."` to both endpoints. What does each do? Note the structural difference: with `RunnableMap`, one bad branch still leaves you three good results. With one JSON call, a single malformed reply loses **everything**. Which failure would you rather debug at 3am?

5. **The judgement call.** Write down when you'd pick each approach. Consider: cost, latency, per-field prompt quality, partial failure, and how easy each is to extend with a fifth field. There's no single right answer — the skill is being able to state the trade-off out loud.
