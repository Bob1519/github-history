import os
from openai import OpenAI
from pathlib import Path

PROMPT_FILE = Path("src/llm_api/test_prompt.md")
TEMPERATURE = 0.2

class LLMClient():
    def __init__(self, api_key: str, generation_model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.client = OpenAI(api_key=self.api_key)
        self.generation_model = generation_model
        
        if PROMPT_FILE.exists():
            with open(PROMPT_FILE, "r", encoding="utf-8") as f:
                self.prompt = f.read()
        else:
            self.prompt = ""
        
    
    def generate_content(self, prompt: str):
        messages = [
            {"role": "system", "content": self.prompt},
            {"role": "user", "content": prompt}
        ]
        
        res = self.client.chat.completions.create(
            model = self.generation_model,
            messages=messages,
            temperature=TEMPERATURE
        )
        
        return res