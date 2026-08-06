# "import" brings code from another package into this file.
# In JavaScript you would write: import { FastAPI } from "fastapi"
# In Python the same idea is written as: from <package> import <thing>
from fastapi import FastAPI

# BaseModel lets us describe the SHAPE of incoming JSON so FastAPI can validate it
from pydantic import BaseModel

# We only need TWO things now: the finished chain, and llm (for its model name).
# prompt and parser are no longer imported here -- they live inside the chain.
from llm import (
    llm,
    chain,
    simple_chain,
    analyze_chain,
    ask_chain,
    is_coding_question,
    report_chain,
    report_v2_chain,
    report_v3_chain,
    answer_with_calculator,
)


# FastAPI is a class. Calling it with () creates an object (an "instance").
# There is no "new" keyword in Python -- calling the class IS creating the object.
# JavaScript equivalent: const app = new FastAPI()
app = FastAPI(title="Gen AI Beginner Basics")


# A "decorator" is the @ line below. It attaches extra behaviour to a function.
# This one tells FastAPI: "when a GET request arrives at the URL /, run home()"
# The function itself stays a plain, normal function.
@app.get("/")
def home():
    # "def" defines a function. The colon and the indentation replace { }.
    # "return" sends a value back, exactly like JavaScript.
    # The { } below is a DICTIONARY -- Python's version of a JS object.
    # Keys must be in quotes. FastAPI converts this dictionary into JSON for us.
    return {"message": "Hello World"}

@app.get("/health")
def health():
    return {"status": "ok"}


# A "class" is a blueprint for a kind of data. This one says:
# "a chat request is any JSON object that has a 'message' field holding text."
# "str" means string. FastAPI uses this to validate the request automatically.
class ChatRequest(BaseModel):
    message: str
    tone: str = "luffy"  # Default value if the user doesn't provide one


# POST, not GET, because the client needs to SEND data in the request body.
@app.post("/chat")
def chat(request: ChatRequest):
    # "request: ChatRequest" is a parameter with a TYPE HINT after the colon.
    # Because the type is a BaseModel, FastAPI reads the JSON body, validates it,
    # and hands us a ready-made ChatRequest object.
    # Dot access here (not ["..."]) -- it is an object, not a dictionary.

    # ONE step now, instead of three. The chain already knows the order:
    # prompt -> llm -> parser.
    # The input is a DICTIONARY, not keyword arguments. Its keys must match the
    # placeholders in the prompt template: {message} and {tone}.
    answer = chain.invoke({"message": request.message, "tone": request.tone})

    # A dictionary can hold as many key/value pairs as we like, separated by commas.
    # "answer" is already a string -- the parser inside the chain did that for us.
    # llm.model_name asks the llm object which model it is -- so the name is stored
    # in ONE place (llm.py). Typing "llama-3.3-70b-versatile" again here would mean
    # two copies to keep in sync, and one of them would eventually be wrong.
    return {
        "answer": answer,
        "model": llm.model_name,
    }

class SimpleChatRequest(BaseModel):
    message: str

@app.post("/simple-chat")
def simple_chat(request: SimpleChatRequest):
    answer = simple_chain.invoke({"message": request.message})
    return {
        "answer": answer,
        "model": llm.model_name,
    }


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
        # The summary, translated -- produced by the one branch that is
        # itself a sequential chain.
        "tamil_summary": result["tamil_summary"],
        "model": llm.model_name,
        "sentiment": result["sentiment"],
    }


class AskRequest(BaseModel):
    message: str


@app.post("/ask")
def ask(request: AskRequest):
    # The branch inside ask_chain decides which prompt to use. We never
    # choose here -- we just hand over the message.
    answer = ask_chain.invoke({"message": request.message})

    # We also want to TELL the caller which route was taken.
    # is_coding_question is a plain function, so we can simply call it.
    # "if / else" picks one of two values -- note the colons and indentation.
    if is_coding_question({"message": request.message}):
        route = "coding"
    else:
        route = "general"

    return {
        "answer": answer,
        "route": route,
        "model": llm.model_name,
    }


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


class ReportV2Request(BaseModel):
    message: str


@app.post("/report-v2")
def report_v2(request: ReportV2Request):
    # This chain ends with PydanticOutputParser, so "result" is a
    # ChatResponse OBJECT -- already checked against the class.
    result = report_v2_chain.invoke({"message": request.message})

    # DOT access now, not ["..."], because it is an object and not a dictionary.
    # Your editor can even autocomplete these field names.
    return {
        "summary": result.summary,
        "sentiment": result.sentiment,
        "language": result.language,
        "model": llm.model_name,
    }


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
