from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

class AIPilot:
    def __init__(self, model_name="gemini-1.5-flash"):
        self.model_name = model_name
        # Get keys from GEMINI_API_KEY
        raw_keys = os.getenv("GEMINI_API_KEY")
        self.api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()] if raw_keys else []
        self.key_index = 0
        self.client = None

    def _rotate_client(self):
        """Cycles through the available Gemini API keys and creates a new client."""
        if not self.api_keys:
            raise ValueError("No GEMINI_API_KEY found in .env file.")

        current_key = self.api_keys[self.key_index]
        self.client = genai.Client(api_key=current_key)

        # Increment index for next call
        self.key_index = (self.key_index + 1) % len(self.api_keys)

    def suggest_command(self, user_goal, context=""):
        try:
            self._rotate_client()

            prompt = (
                f"You are an expert system administrator and PowerShell master. "
                f"Your task is to convert the following user goal into a single, efficient PowerShell command line. "
                f"Use the provided terminal context if helpful to understand the current state or previous errors.\n\n"
                f"Terminal Context:\n{context}\n\n"
                f"User Goal: {user_goal}\n\n"
                f"Return only the raw command text, no explanations, no markdown."
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )

            # Clean up potential markdown formatting
            command = response.text.strip().replace('```powershell', '').replace('```', '').strip()
            return command
        except Exception as e:
            return f"# Error: {str(e)}"
