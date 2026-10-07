import requests
import json
from ..config import GOOGLE_API_KEY, GEMINI_MODEL_ID

def call_gemini_json(prompt: str, temperature: float = 0.3, max_tokens: int = 900) -> dict:
    """
    Call Gemini API expecting JSON response.
    
    Args:
        prompt: Full prompt text
        temperature: Lower = more deterministic (default 0.3 for planner)
        max_tokens: Max output tokens (default 900)
    
    Returns:
        Parsed JSON dict, or empty dict if failed
    """
    if not GOOGLE_API_KEY:
        return {}
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_ID}:generateContent?key={GOOGLE_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            response_text = resp.json()['candidates'][0]['content']['parts'][0]['text']
            # Try to extract JSON from response
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "{" in response_text:
                # Try to find JSON object
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = response_text[start:end]
                else:
                    return {}
            else:
                return {}
            
            return json.loads(json_str)
        else:
            return {}
    except Exception as e:
        return {}
