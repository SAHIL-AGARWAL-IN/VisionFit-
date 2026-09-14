import os
import re
from services.config.workout_config import PROMPT


class LLMCoach:
    def __init__(self, groq_client):
        self.client = groq_client
        self.history = []
        self.system_prompt = PROMPT
        self.model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

    def give_feedback(self, event, issue):
        prompt = f"Event: {event}"

        if issue:
            prompt += f" Form Issue: {issue}"

        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history[-10:],
            {"role": "user", "content": prompt}
        ]

        candidate_models = [self.model, "openai/gpt-oss-20b", "groq/compound-mini", "openai/gpt-oss-120b", "llama-3.3-70b-versatile"]
        unique_models = list(dict.fromkeys(candidate_models))

        text = ""
        last_error = None

        for model_name in unique_models:
            try:
                kwargs = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": 0.4,
                }
                # For models supporting hidden reasoning
                if "gpt-oss" in model_name:
                    kwargs["reasoning_format"] = "hidden"

                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content or ""
                # Strip think tags if any exist
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                if content:
                    text = content
                    self.model = model_name
                    break
            except Exception as e:
                last_error = e
                continue

        if not text:
            if last_error:
                print(f"[LLMCoach] Warning: Could not generate LLM feedback: {last_error}")
            text = "Stay focused on your form and keep pushing!"

        self.history.append({"role": "assistant", "content": text})
        return text

    