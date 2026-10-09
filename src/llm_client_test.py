from llm_api.llm_client import LLMClient
from dotenv import load_dotenv
import os
import json

load_dotenv()

LLM_API_KEY = os.getenv("OPENAI_API_KEY")

openai_client = LLMClient(LLM_API_KEY)

res = openai_client.generate_content("What did the dog say to the man, WOOF")
with open("test.json", "w", encoding="utf-8") as f:
    f.write(res.model_dump_json(indent=2))

print(res.choices[0].message.content)