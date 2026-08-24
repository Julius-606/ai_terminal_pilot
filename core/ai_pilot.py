from google import genai
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class AIPilot:
    def __init__(self, model_name=None):
        model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
        self.model_name = model_name
        # Get keys from GEMINI_API_KEY
        raw_keys = os.getenv("GEMINI_API_KEY")
        if not raw_keys:
            try:
                import streamlit as st
                raw_keys = st.secrets.get("GEMINI_API_KEY")
            except Exception:
                raw_keys = None
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
            logger.info("Generating AI suggestion for goal: %s", user_goal)
            self._rotate_client()

            prompt = (
                f"You are an expert system administrator and PowerShell master. "
                f"Your task is to convert the following user goal into a PowerShell command line and a brief explanation.\n\n"
                f"Terminal Context:\n{context}\n\n"
                f"User Goal: {user_goal}\n\n"
                f"Format your response as a JSON object with two keys: 'command' (the raw PowerShell string) and 'explanation' (a brief one-sentence description)."
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )

            import json
            data = json.loads(response.text)
            if not isinstance(data, dict) or not data.get("command") or not data.get("explanation"):
                raise ValueError("Gemini response must contain non-empty 'command' and 'explanation' keys")
            return data # Returns {'command': '...', 'explanation': '...'}
        except Exception as e:
            logger.exception("AI suggestion failed")
            return {"command": "# Error", "explanation": f"Failed to generate suggestion: {e}"}
