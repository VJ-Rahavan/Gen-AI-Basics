# python-dotenv reads the .env file and loads each line into "environment variables"
from dotenv import load_dotenv

# ChatGroq is LangChain's wrapper around Groq's chat models
from langchain_groq import ChatGroq


# Runs once, when this file is first imported.
# It finds .env and loads GROQ_API_KEY into the environment,
# where ChatGroq will pick it up automatically -- we never type the key in code.
load_dotenv()


# Create the model object ONCE and reuse it for every request.
# This is a module-level variable, so it is created at startup, not per request.
llm = ChatGroq(
    # Which model to use. Groq hosts open models and runs them very fast.
    model="llama-3.3-70b-versatile",
    # 0.0 = focused and repetitive, 1.0 = creative and varied.
    temperature=0.7,
)
