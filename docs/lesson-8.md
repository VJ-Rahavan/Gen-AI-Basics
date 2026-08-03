# Lesson 8 — RunnableMap

## 1. Problem

Every chain you've built is a **straight line**: one input, one path, one answer.

```
input → cleaner → prompt → llm → parser → output
```

But real assistants often need **several things about the same input**. Say you want both a summary *and* a Tamil translation of the user's message. With what you know, you'd write:

```python
summary     = summary_chain.invoke({"message": text})      # wait ~0.4s
translation = translate_chain.invoke({"message": text})    # wait ~0.6s again
```

Two problems, and one is worse than it looks:

**1. It's slow, and needlessly so.** You wait for the summary to finish before the translation even starts. Total time is the **sum**. But these two jobs don't depend on each other at all — the translation doesn't need the summary. There is no reason to wait.

Measured on your actual chains, three times:

| | Sequential | Parallel |
|---|---|---|
| trial 1 | 1.05s | 0.72s |
| trial 2 | 0.92s | 0.59s |
| trial 3 | 0.82s | 0.63s |

Roughly a third of the time, gone. And that gap **grows with every branch you add** — five sequential jobs take five times as long; five parallel ones still take about as long as the slowest one.

**2. It's back in `app.py`.** Two `.invoke()` calls with hand-written coordination is precisely the shape Lesson 6 pulled out of your endpoint. You'd be undoing that.

What you need is a way to say *"run these two chains on the same input, together, and give me both results."* That's `RunnableMap`.

---

## 2. New Concepts

### What is `RunnableMap`?

`RunnableMap` takes a **dictionary of runnables** and turns it into a single runnable.

```python
analysis_map = RunnableMap(
    {
        "summary": summary_chain,
        "translation": translate_chain,
    }
)
```

When you invoke it:

1. It sends **the same input** to every entry.
2. It runs them **at the same time**.
3. It returns **one dictionary**, with your keys and each branch's result.

```python
analysis_map.invoke({"message": "Python lists are mutable..."})

# {"summary":     "Python lists are mutable.",
#  "translation": "பைத்தான் பட்டியல்கள் மாற்றம் செய்யக்கூடியவை..."}
```

**The keys are yours to choose.** `"summary"` and `"translation"` are names you invented; nothing in LangChain requires them. Whatever keys go in, the same keys come out. That's why it's called a *map* — it maps names to branches.

### Analogy: one order, several kitchen stations

A restaurant order arrives: *"soup and salad."*

**Sequential** is one cook doing everything: make the soup, plate it, *then* start the salad. The customer waits for the sum of both.

**Parallel** is handing a copy of the ticket to the soup station and the salad station simultaneously. Both start immediately. The order is ready when the **slower** one finishes.

`RunnableMap` is the ticket printer that copies one order to several stations, and the pass that collects the finished plates into one tray.

### Sequential vs parallel — the shape of it

Sequential — what `|` does. Each step's output feeds the next:

```
input → [A] → [B] → [C] → output
        each waits for the one before it
        TOTAL = A + B + C
```

Parallel — what `RunnableMap` does. Every branch gets the same input:

```
                 ┌→ [A] →┐
input → (copy) ──┼→ [B] →┼── → {"a":…, "b":…, "c":…}
                 └→ [C] →┘
        all three start at once
        TOTAL ≈ the SLOWEST one
```

The two combine, which is the real power. Our chain is sequential *and* parallel:

```
input → cleaner → ┌→ summary_chain   →┐ → {"summary":…, "translation":…}
                  └→ translate_chain →┘
```

The cleaner runs **once**, then its single output fans out to both branches.

### Why is parallel execution useful?

**1. Latency is dominated by waiting, not computing.** Your program spends nearly the whole request sitting idle, waiting for Groq to answer over the network. Two waits can overlap at almost no cost — you're not doing twice the work, you're doing the same waiting *once*.

**2. It scales in the right direction.** Sequential cost grows with the number of branches. Parallel cost stays near the slowest branch. Ten independent LLM calls: ~10× vs ~1×.

**3. You get it for free.** No threads, no `async`, no `await` in your code. LangChain manages it inside the map. This is a genuinely large amount of complexity you're not writing.

### The one requirement: the branches must be independent

Parallel only works when the branches **don't need each other's results**. Summary and translation both need the original message, and neither needs the other — so they can run together.

If you wanted to *translate the summary*, that's a dependency, and it must be sequential:

```python
summary_chain | translate_chain      # sequential: translate needs the summary
```

**Rule: `|` when B needs A's output. `RunnableMap` when A and B only need the same input.**

### `RunnableMap` and `RunnableParallel` are the same thing

You'll see both names in documentation. Verified:

```
RunnableMap      -> <class 'langchain_core.runnables.base.RunnableParallel'>
RunnableParallel -> <class 'langchain_core.runnables.base.RunnableParallel'>
same object?     -> True
```

Literally one class with two names. `RunnableMap` describes the *shape* (a dict of names to runnables); `RunnableParallel` describes the *behavior*. Use either — this lesson uses `RunnableMap` because the dictionary is what you actually type.

### The Python bit: reading values out of the result

The map returns a dictionary, so you read it with square brackets — the same syntax from Lesson 2:

```python
result = analyze_chain.invoke({"message": text})

result["summary"]        # the summary branch's output
result["translation"]    # the translation branch's output
```

Dot access (`result.summary`) will **not** work here. That's for objects like your Pydantic `request`. This is a plain dictionary. Keeping those two straight is a common early stumble — remember Lesson 3's comment: *"Dot access here — it is an object, not a dictionary."* This is the other case.

---

## 3. Project Changes

Both files. Nothing to install.

| File | Change | Why |
|---|---|---|
| `llm.py` | added `RunnableMap` to the imports, two new system prompts, two new prompt templates, two new chains, the `analysis_map`, and `analyze_chain` | All AI plumbing, so it lives here |
| `app.py` | imported `analyze_chain`; added `AnalyzeRequest` and the `POST /analyze` endpoint | A new capability needs a new endpoint |

**Nothing existing was modified.** `chain`, `simple_chain`, `cleaner`, `prompt` and both old endpoints are untouched — `/chat` and `/simple-chat` were confirmed still returning `200`. This is additive work, which is the safest kind.

Note that `summary_chain` and `translate_chain` reuse the **same `llm` and the same `parser`** — for the reason worked out in Lesson 6's challenge: they hold configuration, not state.

> **A linter warning you may see:** SonarLint may flag `"{message}"` as *"duplicated literal, define a constant."* It's technically right that the string repeats four times, and wrong that it would help — `("human", "{message}")` is clearer read inline than as `("human", HUMAN_TEMPLATE)`. Ignore this one.

---

## 4. Complete Code

**`llm.py`** — the updated import:

```python
# RunnableLambda turns any ordinary Python function into a chain component.
# RunnableMap runs several runnables AT THE SAME TIME on the same input.
from langchain_core.runnables import RunnableLambda, RunnableMap
```

Everything below is **new**, appended after `simple_chain`:

```python
# ----- Lesson 8: two small jobs we want done at the same time -----

# Job 1: shorten the message.
SUMMARY_SYSTEM_PROMPT = """Summarize the user's message in ONE short sentence.

Reply with the summary only. Do not add any explanation."""

# Job 2: translate the message.
TRANSLATE_SYSTEM_PROMPT = """Translate the user's message into Tamil.

Reply with the translation only. Do not add any explanation."""


summary_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SUMMARY_SYSTEM_PROMPT),
        ("human", "{message}"),
    ]
)

translate_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", TRANSLATE_SYSTEM_PROMPT),
        ("human", "{message}"),
    ]
)


# Two ordinary chains, built exactly the way you already know.
# Note both reuse the same llm and the same parser.
summary_chain = summary_prompt | llm | parser
translate_chain = translate_prompt | llm | parser


# THE MAP. RunnableMap takes a DICTIONARY of runnables.
# It sends the SAME input to every one of them, runs them AT THE SAME TIME,
# and gives back a dictionary with the same keys -- each holding that
# branch's result.
analysis_map = RunnableMap(
    {
        "summary": summary_chain,
        "translation": translate_chain,
    }
)


# The cleaner runs first (once), then the map fans out to both branches.
analyze_chain = cleaner | analysis_map
```

Both system prompts say **"Reply with the summary only"** / **"the translation only."** Without that, the model adds *"Here's a summary of your message:"* and you'd have to strip it off. Constraining the output in the system prompt is cheaper than cleaning it up afterward.

**`app.py`** — the updated import:

```python
from llm import llm, chain, simple_chain, analyze_chain
```

And the new endpoint, appended at the bottom:

```python
class AnalyzeRequest(BaseModel):
    message: str


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    # ONE invoke, but TWO trips to Groq happen inside -- at the same time.
    # The result is a DICTIONARY, because analysis_map was built from one.
    # Its keys are the keys we chose: "summary" and "translation".
    result = analyze_chain.invoke({"message": request.message})

    # Read the two branch results out of the dictionary with ["..."].
    return {
        "summary": result["summary"],
        "translation": result["translation"],
        "model": llm.model_name,
    }
```

**One `.invoke()`, two network round-trips.** That's the whole point — the parallelism is invisible from here.

---

## 5. Execution Flow

```
User
 │   POST /analyze   {"message": "   Python lists are mutable, ...   "}
 ↓
FastAPI                          validates → request.message
 ↓
analyze_chain.invoke({...})
 │
 │  ┌─────────────────────────────────────────────────────────────────────┐
 │  │  {"message": "   Python lists are mutable, ...   "}                  │
 │  │            │                                                        │
 │  │            ↓  cleaner            ← runs ONCE, before the split       │
 │  │  {"message": "Python lists are mutable, ..."}                        │
 │  │            │                                                        │
 │  │            ├──────────────── copy ────────────────┐                  │
 │  │            │                                      │                  │
 │  │   ┌────────↓────────┐               ┌─────────────↓────────┐         │
 │  │   │ summary_prompt  │               │  translate_prompt    │         │
 │  │   │       ↓         │               │         ↓            │         │
 │  │   │      llm  ─────────► GROQ ◄───────────── llm           │  BOTH   │
 │  │   │       ↓         │   (two calls  │         ↓            │  AT THE │
 │  │   │     parser      │  in flight)   │       parser         │  SAME   │
 │  │   └────────┬────────┘               └─────────────┬────────┘  TIME   │
 │  │            │                                      │                  │
 │  │            └───────────── collect ────────────────┘                  │
 │  │                            │                                        │
 │  │  {"summary": "Python lists are mutable.",                            │
 │  │   "translation": "பைத்தான் பட்டியல்கள்..."}                              │
 │  └─────────────────────────────────────────────────────────────────────┘
 ↓
{"summary": ..., "translation": ..., "model": ...}
 ↓
Response
```

Two details worth pointing at:

- **The cleaner runs once, not twice.** It sits before the fan-out, so both branches receive the already-cleaned dictionary. Putting it inside each branch would do the same work twice.
- **The branches never talk to each other.** No arrows between them. That's what makes running them together safe.

---

## 6. Run the Project

```bash
cd "/Users/purpleslate14mbp/Desktop/Mission G/gen-ai-beginner-basics"

uv run uvicorn app:app --reload
```

Open http://127.0.0.1:8000/docs — you now have **four** endpoints. Try `POST /analyze`:

```json
{ "message": "Python lists are mutable, which means you can add or remove items after creating them." }
```

Or from the terminal:

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"message":"Python lists are mutable, which means you can add or remove items after creating them."}'
```

### Measure the parallelism yourself

This is the experiment that makes the lesson real — run it, don't take it on trust:

```bash
uv run python -c "
import time
from llm import summary_chain, translate_chain, analyze_chain

data = {'message': 'Python lists are mutable, which means you can add or remove items after creating them.'}

print('trial   sequential   parallel')
for i in range(1, 4):
    t0 = time.perf_counter()
    summary_chain.invoke(dict(data))
    translate_chain.invoke(dict(data))
    seq = time.perf_counter() - t0

    t0 = time.perf_counter()
    analyze_chain.invoke(dict(data))
    par = time.perf_counter() - t0

    print('  %d      %.2fs       %.2fs' % (i, seq, par))
"
```

Two small Python things in there: `time.perf_counter()` returns a precise timestamp (subtract two to get elapsed seconds), and `dict(data)` makes a **fresh copy** of the dictionary each time — necessary because `clean_input` modifies the dictionary it's given.

---

## 7. Expected Output

### The endpoint

Request:
```json
{ "message": "   Python lists are mutable, which means you can add or remove items after creating them.   " }
```

Real response — `200`, total `0.77s`:
```json
{
  "summary": "Python lists are mutable.",
  "translation": "பைத்தான் பட்டியல்கள் மாற்றம் செய்யக்கூடியவை, அதாவது நீங்கள் அவற்றை உருவாக்கிய பின்னர் பொருட்களைச் சேர்க்கவும் அல்லது நீக்கவும் முடியும்.",
  "model": "llama-3.3-70b-versatile"
}
```

Note the padding deliberately added to the request is gone from both results — **one cleaner, two branches.** Lesson 7 still paying off.

### The timing proof

```
trial   sequential   parallel
  1      1.05s       0.72s
  2      0.92s       0.59s
  3      0.82s       0.63s
```

Parallel wins every trial. And check the arithmetic from the individual measurements: summary took `0.35s`, translate took `0.62s`.

- **Sequential ≈ 0.35 + 0.62 = 0.97s** — the sum ✓
- **Parallel ≈ max(0.35, 0.62) = 0.62s** — the slower one ✓ (measured 0.68s; the extra ~0.06s is coordination overhead)

That's the formula: **sequential adds, parallel takes the maximum.**

### Regression check

```
/chat        -> 200
/simple-chat -> 200
```

Both older endpoints unaffected.

**An honest caveat about the numbers:** Groq is unusually fast, so a ~0.3s saving is modest in absolute terms. On a slower provider where each call takes 3 seconds, the same code turns 6s into 3s — very noticeable. Also, these timings vary with network conditions; run the trials a few times and expect scatter. The *pattern* (parallel < sequential) is reliable; the exact numbers are not.

---

## 8. Mini Exercise

**Add a third branch and watch the shape of the cost.**

Add a sentiment prompt in `llm.py`:

```python
SENTIMENT_SYSTEM_PROMPT = """Reply with ONE word describing the tone of the user's message.

Choose from: positive, negative, neutral.
Reply with the single word only."""
```

Then a `sentiment_prompt`, a `sentiment_chain`, and a third entry in the map:

```python
analysis_map = RunnableMap(
    {
        "summary": summary_chain,
        "translation": translate_chain,
        "sentiment": sentiment_chain,
    }
)
```

And return `result["sentiment"]` from the endpoint.

Three things to check:

1. Did the endpoint get noticeably slower? Time it. **It shouldn't** — you added a third wait that overlaps the other two.
2. Compare: three sequential calls would cost roughly the sum of three. Measure that too, using the timing script as a template.
3. Change the key from `"sentiment"` to `"mood"` in the map. What breaks in `app.py`, and what does the error tell you about where the keys come from?

---

## 9. Challenge

**Make one branch depend on another — which means it can't be in the map.**

Goal: `POST /analyze` also returns a `"tamil_summary"` — the **summary**, translated into Tamil. Not the original message translated; the *summary* translated.

This is deliberately the case parallelism can't handle, and the exercise is figuring out why and where it goes.

Work through it in this order:

1. **Why can't `"tamil_summary"` just be a fourth entry in `analysis_map`?** Say precisely what it would receive if you tried, and what it would produce. (Hint: what input does every branch of a map get?)

2. **Build it as a sequential chain instead.** You need `summary_chain`'s output to become `translate_chain`'s input — but there's a shape mismatch: `summary_chain` outputs a **string**, and `translate_prompt` needs a **dictionary** with a `"message"` key. Bridge it with a `RunnableLambda`, the tool from Lesson 7:

   ```python
   tamil_summary_chain = summary_chain | <something> | translate_chain
   ```

   Write a named function for the middle piece. What does it take, and what does it return?

3. **Now combine both patterns.** Add `tamil_summary_chain` to the map as a fourth branch. It works — a sequential chain can absolutely be one branch of a parallel map. Draw the resulting shape as an ASCII diagram.

4. **The measurement that matters.** Time the four-branch version against the three-branch one. It should be *slower* — but not by much. Why is `tamil_summary` slower than the other branches, and why doesn't it slow the others down? (Count the network hops in each branch.)

5. **Efficiency question, no code needed.** Your four-branch map now calls the summary model **twice** — once for `"summary"`, once inside `"tamil_summary"`. Same input, same prompt, same answer, paid for twice. Can you restructure to avoid that, using only `|`, `RunnableMap` and `RunnableLambda`? Sketch it. This is a genuinely tricky one, and noticing the waste is most of the skill.
