from llm_api.llm_client import LLMClient
from pathlib import Path


class Evaluator():
    def __init__(self, llm_key: str, save_location: Path, ground_truth: Path):
        self.llm = LLMClient(llm_key, prompt_file = Path("src/llm_api/evaluator_prompt.md"))
        self.save_location = save_location
        
        with open(ground_truth, "r", encoding="utf-8") as f:
            self.ground_truth = f.read()
    
    def evaluate(self, response: str):
        context = f"Ground Truth: {self.ground_truth} \n\nGenerated Summary: {response}"
        
        evaluation = self.llm.generate_content(context)
        with open(self.save_location, "w", encoding="utf-8") as f:
            f.write(evaluation)