# "import" brings code from another package into this file.
# In JavaScript you would write: import { FastAPI } from "fastapi"
# In Python the same idea is written as: from <package> import <thing>
from fastapi import FastAPI

# BaseModel lets us describe the SHAPE of incoming JSON so FastAPI can validate it
from pydantic import BaseModel

# Import our own file, llm.py, and take the variable named "llm" out of it.
# No "./" and no ".py" -- Python finds llm.py because it sits next to this file.
from llm import llm


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


# POST, not GET, because the client needs to SEND data in the request body.
@app.post("/chat")
def chat(request: ChatRequest):
    # "request: ChatRequest" is a parameter with a TYPE HINT after the colon.
    # Because the type is a BaseModel, FastAPI reads the JSON body, validates it,
    # and hands us a ready-made ChatRequest object.
    # Dot access here (not ["..."]) -- it is an object, not a dictionary.

    # .invoke() sends the text to Groq and waits for the reply.
    # It returns a MESSAGE OBJECT, not a plain string.
    result = llm.invoke(request.message)

    # A dictionary can hold as many key/value pairs as we like, separated by commas.
    # .content pulls the actual text out of that message object.
    # llm.model_name asks the llm object which model it is -- so the name is stored
    # in ONE place (llm.py). Typing "llama-3.3-70b-versatile" again here would mean
    # two copies to keep in sync, and one of them would eventually be wrong.
    return {
        "answer": result.content,
        "model": llm.model_name,
    }