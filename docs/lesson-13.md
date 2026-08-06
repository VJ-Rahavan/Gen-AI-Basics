# Lesson 13 — Your First Tool

## 1. Problem

Everything built so far, the model does **alone**. It reads text, it writes text. That works beautifully for explaining tuples or summarizing a complaint.

Now watch it fail. The plain model — no tool — was asked to compute `98765 × 43210`, three times:

```
correct answer      : 4267635650

=== plain model, NO tool, 3 tries ===
  try 1 -> 4264431950
  try 2 -> 4267792650
  try 3 -> 4264432650
```

**Three attempts, three different answers, all wrong.** Not one is close enough to be useful. And notice it never said *"I'm not sure"* — it answered confidently every time.

This isn't a flaw you can prompt away. A language model predicts *likely text*. `4264431950` looks exactly like a plausible product of two five-digit numbers, and the model has no calculator inside it to check. It's pattern-matching the shape of an answer, not computing one.

The same limitation covers a whole family of things:

| The model cannot | Because |
|---|---|
| do reliable arithmetic | it predicts text, it doesn't compute |
| know today's date | its knowledge was frozen at training time |
| read your database | it has no connection to it |
| check a live price | it can't make network requests |
| run your code | it produces text, nothing more |

Meanwhile, a calculator that multiplies two numbers correctly is **three lines of Python.** You've been able to write that since Lesson 2.

So the problem isn't capability — it's *connection*. You have a model that understands the question but can't compute. You have Python that can compute but doesn't understand the question. **Tools are the bridge.**

---

## 2. New Concepts

### What is a Tool?

A **Tool** is a normal Python function that you've made **available to the model**.

That's genuinely all it is. The function doesn't change. What changes is that the model is now told *"this function exists, here's what it does, here's what it needs"* — and the model can **ask** for it to be run.

### The single most important thing to understand

**The model cannot run your tool. It can only ask you to run it.**

Beginners almost always get this backwards, imagining the model reaching into their program and executing code. It can't. It has no ability to run anything. All it can do is produce a message that means *"please call `calculator` with these arguments."*

Your code reads that request, runs the function, and gets the result. **You** are the one executing. The model just asks.

The exact request it sends:

```
'What is 45 times 18?'
   tool_calls -> [{'name': 'calculator',
                   'args': {'first_number': 45, 'operation': 'multiply', 'second_number': 18},
                   'id': 'agf61hpfm', 'type': 'tool_call'}]
   content    -> ''
```

Read that carefully — it's the whole mechanism:

- **`content` is empty.** The model wrote no prose at all. It has nothing to say yet.
- **`tool_calls` holds a request**: the tool's `name`, and `args` — the arguments it worked out from your English sentence.
- **No result anywhere.** The multiplication hasn't happened. It can't have.

The model did the part it's good at (understanding *"45 times 18"* means multiply 45 and 18) and stopped at the part it's bad at.

### Analogy: a chef and a waiter

The **model is a waiter**. Excellent with customers — understands what people want, even vaguely phrased, translates it into a precise order.

Your **tool is the kitchen**. It can actually cook, but it doesn't talk to customers.

The waiter takes your muddled *"something light, no dairy"* and writes a precise ticket: *`salad, no cheese`*. Then hands it through the window. **The waiter does not cook.** The kitchen cooks; the waiter carries.

`tool_calls` is the ticket. Your code is the window it goes through.

### Tool vs a normal Python function

Here's the thing: **it's the same function.** The difference is in what surrounds it.

| | Normal function | Tool |
|---|---|---|
| Who decides to call it | **you**, in your code | **the model**, based on the question |
| Who supplies the arguments | you, explicitly | the model, extracted from English |
| Does the model know it exists | no | yes — name + description are sent to it |
| Can you still call it directly | — | **yes**, always |

That last row matters. `calculator` remains an ordinary function you can call yourself:

```
=== the tool on its own (no model involved) ===
810.0
Cannot divide by zero.
```

No model, no network, no API key. Which means you can test your tool logic in isolation — the same benefit you got from keeping `clean_input` plain in Lesson 7.

### What does `@tool` do?

You've used decorators since Lesson 2 — `@app.get("/")` registers a function with FastAPI. `@tool` is the same idea, registering with LangChain:

```python
@tool
def calculator(operation: str, first_number: float, second_number: float) -> str:
    """Do arithmetic on two numbers. ..."""
```

It reads your function and builds a description for the model. What it produced:

```
type        -> StructuredTool
name        -> calculator
description -> Do arithmetic on two numbers.
args        -> {'operation':      {'title': 'Operation',      'type': 'string'},
                'first_number':   {'title': 'First Number',   'type': 'number'},
                'second_number':  {'title': 'Second Number',  'type': 'number'}}
```

Three things it extracted, without you writing any of them out:

1. **`name`** — from the function name.
2. **`description`** — from the **docstring**.
3. **`args`** — from the **type hints**. Note `float` became `"number"`, `str` became `"string"`. Those are JSON Schema types — the same JSON Schema seen in Lesson 12 when `with_structured_output` sent `ChatResponse` to Groq. Same machinery, other direction.

### The docstring is not a comment

This is new, and it's load-bearing:

```python
def calculator(...) -> str:
    """Do arithmetic on two numbers.

    Use this whenever the user asks for a calculation.
    operation must be one of: add, subtract, multiply, divide.
    """
```

A **docstring** is a string as the very first thing in a function body. Normally it documents code for humans. Here, **LangChain sends it to the model** — it's how the model knows when this tool applies.

So the docstring is prompt engineering. *"Use this whenever the user asks for a calculation"* is an instruction to the model, not a note to yourself.

And it's mandatory:

```
no docstring -> ValueError : Function must have a docstring if description not provided.
```

`@tool` refuses to build a tool it can't describe. Sensible — a nameless, undescribed tool is useless to the model.

### `bind_tools` — telling the model what exists

```python
llm_with_tools = llm.bind_tools([calculator])
```

This returns a **new** model object that knows about your tools. It doesn't run anything, and it doesn't force anything — the model stays free to answer normally. `[calculator]` is a list because you'll add more (Lesson 14).

This is the same `bind` pattern as `with_structured_output` from Lesson 12 — attaching extra information to the request. Last lesson it was a schema with `tool_choice` forcing its use. Here there's **no** `tool_choice`, so the model chooses.

### The Python bit: `elif`

```python
if operation == "add":
    result = first_number + second_number
elif operation == "subtract":
    result = first_number - second_number
elif operation == "multiply":
    ...
else:
    return "Unknown operation..."
```

`elif` is short for *"else if"*. Each one is tested only if all the ones above were `False`, and once one matches the rest are skipped.

```javascript
if (op === "add") { ... }
else if (op === "subtract") { ... }   // JS spells it out
else { ... }
```
```python
if op == "add":
    ...
elif op == "subtract":                # Python contracts it to elif
    ...
else:
    ...
```

**Python has no `switch` statement**, so a chain of `elif` is the normal way to handle several cases. (There's a `match` statement in modern Python, but `elif` is clearer for four cases and universally understood.)

---

## 3. Project Changes

Both files, purely additive.

| File | Change | Why |
|---|---|---|
| `llm.py` | added `from langchain_core.tools import tool`; the `calculator` tool; `llm_with_tools`; the `answer_with_calculator` function | tools and the model belong together |
| `app.py` | imported `answer_with_calculator`; added `CalculateRequest` and `POST /calculate` | new capability, new endpoint |

Nothing existing was touched — all eight earlier endpoints are unaffected.

**Why `answer_with_calculator` lives in `llm.py`:** it's the two-step dance of asking the model and then running what it requested. That's AI plumbing, not HTTP. The endpoint stays three lines.

It's a plain function, not a chain, and that's deliberate: an `if` deciding whether to run a tool doesn't compose into a `|` pipeline neatly, and writing it out longhand means you can *see* both steps. Making this automatic is what agents do — which is precisely why we're doing it by hand first.

**No Tool Schema yet.** `@tool` inferred one from the type hints, which is enough for three parameters. Lesson 15 makes it explicit with Pydantic and shows why that becomes necessary.

---

## 4. Complete Code

**`llm.py`** — the new import:

```python
# The @tool decorator turns an ordinary function into something the model can call.
from langchain_core.tools import tool
```

New code at the bottom:

```python
# ----- Lesson 13: give the model a tool it can choose to use -----


# @tool turns this ordinary function into a Tool the model is allowed to call.
# The DOCSTRING below is not a comment -- LangChain sends it to the model as the
# tool's description, and the model reads it to decide when this tool applies.
# A tool without a docstring is an error.
@tool
def calculator(operation: str, first_number: float, second_number: float) -> str:
    """Do arithmetic on two numbers.

    Use this whenever the user asks for a calculation.
    operation must be one of: add, subtract, multiply, divide.
    """
    # "elif" means "else if" -- it checks the next condition only if the
    # previous ones were False. Python has no "switch" statement.
    if operation == "add":
        result = first_number + second_number
    elif operation == "subtract":
        result = first_number - second_number
    elif operation == "multiply":
        result = first_number * second_number
    elif operation == "divide":
        # Dividing by zero would crash Python, so we stop before that happens.
        if second_number == 0:
            return "Cannot divide by zero."
        result = first_number / second_number
    else:
        # The model sent an operation we do not support.
        return "Unknown operation. Use add, subtract, multiply or divide."

    # We return TEXT rather than a number, so that answers and error messages
    # can both travel back the same way.
    return str(result)


# Give the model a list of tools it is allowed to use.
# This does NOT run anything -- it only tells Groq which tools exist.
# The model stays free to answer normally instead.
llm_with_tools = llm.bind_tools([calculator])


# A plain function that does the two steps by hand, so we can watch them.
def answer_with_calculator(message):
    """Ask the model, then run the calculator only if the model asked us to."""
    # STEP 1: the model reads the question and DECIDES.
    reply = llm_with_tools.invoke(message)

    # reply.tool_calls is a LIST. It is empty when the model chose to answer
    # by itself, and holds one entry per tool the model wants called.
    if len(reply.tool_calls) == 0:
        return {
            "answer": reply.content,
            "tool_used": None,
            "tool_args": None,
        }

    # STEP 2: the model asked for a tool. [0] is the first (and here, only) one.
    first_call = reply.tool_calls[0]

    # WE run the tool -- the model cannot run code, it can only ask.
    # first_call["args"] is the dictionary of arguments the model filled in.
    tool_result = calculator.invoke(first_call["args"])

    return {
        "answer": tool_result,
        "tool_used": first_call["name"],
        "tool_args": first_call["args"],
    }
```

**`app.py`** — the new endpoint:

```python
class CalculateRequest(BaseModel):
    message: str


@app.post("/calculate")
def calculate(request: CalculateRequest):
    # All the work happens in llm.py. The result is a dictionary telling us
    # both the answer AND whether the model chose to use the tool.
    result = answer_with_calculator(request.message)

    # We report tool_used and tool_args so the model's DECISION is visible
    # in the response, instead of something we have to guess at.
    return {
        "answer": result["answer"],
        "tool_used": result["tool_used"],
        "tool_args": result["tool_args"],
        "model": llm.model_name,
    }
```

Returning `tool_used` and `tool_args` is the same trick as Lesson 9's `"route"` field: **make the model's decision visible in the response.** Without it you'd be guessing whether the tool ran.

---

## 5. Execution Flow

```
User
 │   POST /calculate   {"message": "What is 45 times 18?"}
 ↓
FastAPI
 ↓
answer_with_calculator(message)
 │
 │  ┌───────────────────────────────────────────────────────────────────────┐
 │  │  STEP 1 -- ask the model, and let it decide                            │
 │  │                                                                        │
 │  │  llm_with_tools.invoke("What is 45 times 18?")                          │
 │  │     the request carries:  messages + the calculator's name,             │
 │  │                           description and argument types                │
 │  │            ↓                                                            │
 │  │  AIMessage(content='',                       ← NO prose                 │
 │  │            tool_calls=[{name: 'calculator',                             │
 │  │                         args: {operation: 'multiply',                   │
 │  │                                first_number: 45,                        │
 │  │                                second_number: 18}}])                    │
 │  │            │                                                            │
 │  │            ↓  are there any tool_calls?                                 │
 │  │      ┌─────┴─────┐                                                      │
 │  │  no  │           │ yes                                                  │
 │  │      ↓           ↓                                                      │
 │  │  return      STEP 2 -- WE run it                                        │
 │  │  reply           │                                                      │
 │  │  .content        ↓  calculator.invoke({...})   ← plain Python, no model  │
 │  │                  │                                                      │
 │  │                  ↓  '810.0'                                             │
 │  └───────────────────────────────────────────────────────────────────────┘
 ↓
{"answer": "810.0", "tool_used": "calculator", "tool_args": {...}}
 ↓
Response
```

Note the two boxes never overlap. **The model decides; Python computes.** Neither does the other's job.

Compare with `RunnableBranch` from Lesson 9: there, *your keyword function* chose the path. Here **the model** chooses, from the question's meaning. That's a real step up in capability — and the reason it works is that the model only has to *recognize* arithmetic, not *perform* it.

---

## 6. Run the Project

```bash
cd "/Users/purpleslate14mbp/Desktop/Mission G/gen-ai-beginner-basics"

uv run uvicorn app:app --reload
```

**Nine** endpoints now. http://127.0.0.1:8000/docs → `POST /calculate`.

### Test the tool alone, with no model

Do this first — it proves the tool is an ordinary function:

```bash
uv run python -c "
from llm import calculator

print(calculator.invoke({'operation': 'multiply', 'first_number': 45, 'second_number': 18}))
print(calculator.invoke({'operation': 'divide', 'first_number': 10, 'second_number': 0}))
"
```

### Watch the model decide

**This is the most important command in the lesson.** It shows the raw decision, before any tool runs:

```bash
uv run python -c "
from llm import llm_with_tools

for q in ['What is 45 times 18?', 'Who wrote Hamlet?']:
    reply = llm_with_tools.invoke(q)
    print(repr(q))
    print('   tool_calls ->', reply.tool_calls)
    print('   content    ->', repr(reply.content[:60]))
    print()
"
```

### See what `@tool` built

```bash
uv run python -c "
from llm import calculator
print('name        ->', calculator.name)
print('description ->', calculator.description)
print('args        ->', calculator.args)
"
```

### And prove why you needed it

```bash
uv run python -c "
from llm import llm
print('correct: 4267635650')
for i in range(3):
    r = llm.invoke('What is 98765 multiplied by 43210? Reply with only the number.')
    print(' plain model ->', r.content.strip()[:40])
"
```

---

## 7. Example Requests

```bash
# A -- multiplication
curl -X POST http://127.0.0.1:8000/calculate -H "Content-Type: application/json" \
  -d '{"message":"What is 45 times 18?"}'

# B -- no calculation needed
curl -X POST http://127.0.0.1:8000/calculate -H "Content-Type: application/json" \
  -d '{"message":"Who wrote Hamlet?"}'

# C -- division by zero
curl -X POST http://127.0.0.1:8000/calculate -H "Content-Type: application/json" \
  -d '{"message":"What is 7 divided by 0?"}'

# D -- awkward word order
curl -X POST http://127.0.0.1:8000/calculate -H "Content-Type: application/json" \
  -d '{"message":"subtract 19 from 100 please"}'

# E -- numbers too big for the model to guess
curl -X POST http://127.0.0.1:8000/calculate -H "Content-Type: application/json" \
  -d '{"message":"What is 98765 multiplied by 43210?"}'
```

---

## 8. Expected Output

**A — multiplication:**
```json
{"answer":"810.0","tool_used":"calculator",
 "tool_args":{"first_number":45,"operation":"multiply","second_number":18},
 "model":"llama-3.3-70b-versatile"}
```

**B — no tool.** `tool_used` is `null`; the model answered by itself:
```json
{"answer":"William Shakespeare wrote Hamlet.","tool_used":null,"tool_args":null,
 "model":"llama-3.3-70b-versatile"}
```

**One model, two behaviors, same endpoint.** Nothing in your code chose between them.

**C — division by zero.** The model *did* call the tool, and your guard produced the message:
```json
{"answer":"Cannot divide by zero.","tool_used":"calculator",
 "tool_args":{"first_number":7,"operation":"divide","second_number":0}}
```

Worth noticing: the model happily asked to divide by zero. **It doesn't validate arguments — your tool must.** That's your job, always.

**D — the one to study.** *"subtract 19 from 100 please"* mentions 19 **before** 100, but:
```json
{"answer":"81.0","tool_args":{"first_number":100,"operation":"subtract","second_number":19}}
```

It assigned `first_number: 100` and `second_number: 19` — the correct order for subtraction, not the order the words appeared. `100 - 19 = 81` ✓. That's the model *understanding* the sentence, which no `elif` chain could do.

**E — the payoff:**
```json
{"answer":"4267635650.0","tool_args":{"first_number":98765,"operation":"multiply","second_number":43210}}
```

`4267635650` — **exactly right.** Against the plain model's three attempts:

| | Answer | |
|---|---|---|
| correct | `4267635650` | |
| plain model, try 1 | `4264431950` | ✗ |
| plain model, try 2 | `4267792650` | ✗ |
| plain model, try 3 | `4264432650` | ✗ |
| **with the tool** | **`4267635650`** | **✓** |

Not "more accurate" — **exact, every time.** Because Python multiplied it. The model only worked out *which two numbers and which operation*.

### One rough edge, on purpose

Look at A's answer again: `"810.0"`. Not *"45 times 18 is 810."* Just the bare number, with a trailing `.0` because we used `float`.

That's because we **stop after running the tool.** The tool result never goes back to the model, so the model never gets to phrase it. `answer_with_calculator` does:

```
ask the model → run the tool → return the raw result
```

To get a sentence you'd need a third step — send the result back and let the model write it up. And if the model then asked for *another* tool, you'd need a fourth. That loop — *ask, run, feed back, repeat until done* — is exactly what an **agent** is.

Which is why the roadmap does Tools and Memory before Agents. An agent isn't magic; it's this loop, automated. Feeling the missing step by hand is worth more than being handed the loop.

### All endpoints
```
/chat  /simple-chat  /ask  /analyze  /report  /report-v2  /report-v3  /calculate
```

---

## 9. Mini Exercise

**Change only the docstring, and watch the model's behavior change.**

The docstring is an instruction to the model, so editing it is prompt engineering. Prove it:

**Part 1.** Narrow the docstring to:

```python
    """Multiply two numbers together."""
```

Restart the server (`--reload` won't reliably re-read a decorator) and try all five requests again. Does `"What is 45 times 18?"` still call the tool? Does `"subtract 19 from 100"`? Watch `tool_used` — you should see the model refuse the tool for subtraction, because you told it the tool only multiplies.

**Part 2.** Now go the other way — describe it as something it isn't:

```python
    """Look up the weather in a city."""
```

Ask `"What is 45 times 18?"`. Does it call the tool now? What does this tell you about who's really in charge of tool selection?

**Part 3.** Restore the original docstring, then answer:

1. Which parts of the tool did the model read to decide — the name, the docstring, the type hints, or the function body?
2. Could the model *ever* see your function body? (Think about what actually gets sent.)

---

## 10. Challenge

**Add a fifth operation, and find the tool's real weak spot.**

**Part 1 — extend it.** Add `"power"` (raise the first number to the power of the second). Python's operator is `**`, so `2 ** 10` is `1024`. Add one `elif`, and mention `power` in the docstring.

Test with `"What is 2 to the power of 10?"` and `"square 7 for me"` — that second one has no explicit operation word. Does it manage?

**Part 2 — break it deliberately.** Try these and record what happens:

1. `"What is 45 times 18 plus 3?"` — **two** operations, one tool call. What does `tool_args` show? Is the answer right?
2. `"What is the square root of 144?"` — your tool has no such operation. Does the model invent one, pick the closest, or answer by itself?
3. `"Add apple and banana"` — the arguments should be numbers. What does the model send, and where does the failure happen: at the model, at `@tool`'s type checking, or inside your `if`/`elif`?

**Part 3 — the questions that matter.**

4. In case 1, the honest fix is **two** calls: multiply, then add the result to 3. Your `answer_with_calculator` runs `tool_calls[0]` — the first one only. Look at your code and say exactly what it would ignore if the model requested two tools at once.
5. Case 3 is worth pinning down precisely. `@tool` declared `first_number` as a `"number"`. Did that stop bad input, and if so **where**? Try calling the tool directly with `calculator.invoke({"operation": "add", "first_number": "apple", "second_number": "banana"})` and compare against what happens through the model. Two different layers, possibly two different behaviors.
6. Right now the answer is `"810.0"` rather than a sentence. Without writing it, describe the third step you'd add — what would you send to the model, and what would you expect back?

Question 5 sets up Lesson 15 directly. Question 6 sets up agents, later.
