import os
import json
from dotenv import load_dotenv

# Load env variables
load_dotenv()

class AIEngine:
    """Wrapper to route tasks to Groq or Gemini based on availability and task type."""
    
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        
        # Init Gemini
        self.gemini_model = None
        if self.gemini_key:
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_key)
            self.gemini_model = genai.GenerativeModel("gemini-2.5-flash")
            
        # Init Groq
        self.groq_client = None
        if self.groq_key:
            from groq import Groq
            self.groq_client = Groq(api_key=self.groq_key)

    def has_groq(self) -> bool:
        return self.groq_client is not None

    def has_gemini(self) -> bool:
        return self.gemini_model is not None

    def generate_json(self, prompt: str, prefer_groq: bool = True) -> dict:
        """Generate JSON output using the preferred AI provider."""
        if prefer_groq and self.has_groq():
            try:
                response = self.groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                return json.loads(response.choices[0].message.content)
            except Exception as e:
                print(f"[AIEngine] Groq JSON error: {type(e).__name__} - {e}. Falling back to Gemini.")
                
        if self.has_gemini():
            try:
                # Gemini expects JSON wrapper usually
                resp = self.gemini_model.generate_content(prompt)
                text = resp.text.strip()
                if text.startswith("```json"):
                    text = text[7:-3].strip()
                return json.loads(text)
            except Exception as e:
                print(f"[AIEngine] Gemini error: {e}")
                
        return {}

    def generate_text(self, prompt: str, prefer_groq: bool = True) -> str:
        """Generate plain text output using the preferred AI provider."""
        if prefer_groq and self.has_groq():
            try:
                response = self.groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"[AIEngine] Groq Text error: {type(e).__name__} - {e}. Falling back to Gemini.")
                
        if self.has_gemini():
            try:
                resp = self.gemini_model.generate_content(prompt)
                return resp.text.strip()
            except Exception as e:
                print(f"[AIEngine] Gemini error: {e}")
                
        return f"Error: No AI provider available or both failed."
