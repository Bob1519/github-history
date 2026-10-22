import os
from openai import OpenAI
from pathlib import Path

TEMPERATURE = 0.2

class LLMClient():
    def __init__(self, api_key: str, generation_model: str = "gpt-4o-mini", prompt_file: Path = Path("src/llm_api/analyzer_prompt.md")):
        self.api_key = api_key
        self.client = OpenAI(api_key=self.api_key)
        self.generation_model = generation_model
        
        if prompt_file.exists():
            with open(prompt_file, "r", encoding="utf-8") as f:
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
        
        return res.choices[0].message.content