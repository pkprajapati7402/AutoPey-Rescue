"""LLM Outreach and Customer Intent Parsing Engine.

This module is the ONLY component in AutoPey-Rescue that leverages LLMs.
It supports:
1. Google Gemini API (Free tier / production via GEMINI_API_KEY / GOOGLE_API_KEY)
2. Optional OpenAI API (OPENAI_API_KEY)
3. Optional Anthropic API (ANTHROPIC_API_KEY)
4. Offline / No-API-Key fallback mode for resilient automated tests and offline simulation.

Capabilities:
- draft_nudge: Generates conversational, low-pressure Hinglish WhatsApp reminders (<300 chars).
- parse_promise_to_pay: Classifies simulated customer responses into PROMISED, DECLINED, or UNCLEAR.
"""

import json
import os
import re
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def _get_api_provider() -> tuple[Optional[str], Optional[str]]:
    """Detect available LLM provider and API key from environment."""
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key and gemini_key.strip() and not gemini_key.startswith("your_"):
        return "gemini", gemini_key.strip()

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and openai_key.strip() and not openai_key.startswith("your_"):
        return "openai", openai_key.strip()

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key and anthropic_key.strip() and not anthropic_key.startswith("your_"):
        return "anthropic", anthropic_key.strip()

    return None, None


def _fallback_draft_nudge(transaction: Dict[str, Any]) -> str:
    """Deterministic fallback Hinglish reminder when no API key is present."""
    customer_name = transaction.get("customer_name", "Customer")
    first_name = customer_name.split()[0] if customer_name else "Customer"
    amount = transaction.get("amount_inr", 499)
    due_date = transaction.get("due_date", "recent date")

    message = (
        f"Hi {first_name}! Apka Rs.{amount} ka subscription payment {due_date} ko "
        f"complete nahi ho paya. Please UPI app par check kar lijiye taki plan chalta rahe. "
        f"Koi query ho toh bataiye!"
    )
    return message[:299]


def _fallback_parse_promise(reply: str) -> Dict[str, Any]:
    """Deterministic heuristic fallback intent parser for offline testing."""
    if not reply or not isinstance(reply, str):
        return {"status": "UNCLEAR", "promised_date": None}

    lower = reply.lower().strip()

    # Decline indicators
    decline_words = ["cancel", "cancelled", "band karo", "nahi chahiye", "stop", "no", "mat karo", "not interested"]
    if any(w in lower for w in decline_words) and not any(p in lower for p in ["kal", "kar dunga", "pay karunga"]):
        return {"status": "DECLINED", "promised_date": None}

    # Promise / commitment indicators
    promise_words = [
        "kal", "tomorrow", "shaam", "evening", "aaj", "today", "kar dunga", "karta hu",
        "pay karunga", "salary", "pay later", "will pay", "5th", "1st", "10th", "haan", "yes", "done"
    ]
    if any(w in lower for w in promise_words):
        # Check for explicit date mentions like 2026-09-05 or 5th or tomorrow
        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", reply)
        promised_date = date_match.group(1) if date_match else None
        return {"status": "PROMISED", "promised_date": promised_date}

    return {"status": "UNCLEAR", "promised_date": None}


def draft_nudge(transaction: Dict[str, Any]) -> str:
    """Draft a friendly, low-pressure Hinglish WhatsApp payment reminder.

    Tone: Polite, helpful, low-pressure, conversational.
    Constraints: Must mention first name, amount_inr, and due_date. Length < 300 characters.

    Args:
        transaction: Dict containing customer_name, amount_inr, due_date.

    Returns:
        Hinglish message text under 300 characters.
    """
    provider, api_key = _get_api_provider()

    if not provider or not api_key:
        return _fallback_draft_nudge(transaction)

    customer_name = transaction.get("customer_name", "Customer")
    first_name = customer_name.split()[0] if customer_name else "Customer"
    amount = transaction.get("amount_inr", 499)
    due_date = transaction.get("due_date", "recently")

    prompt = (
        f"You are an empathetic customer success assistant for an Indian subscription service. "
        f"Draft a short, polite WhatsApp payment reminder in natural Hinglish (Hindi-English mix). "
        f"Details: Customer First Name: {first_name}, Amount: INR {amount}, Due Date: {due_date}. "
        f"Rules: "
        f"1. Low pressure, empathetic, courteous. "
        f"2. MUST reference {first_name}, INR {amount} (or Rs.{amount}), and date {due_date}. "
        f"3. Do NOT threaten cancellation or penalty. "
        f"4. Length MUST be strictly under 280 characters. "
        f"5. Output ONLY the message text without quotes or preamble."
    )

    try:
        if provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            text = response.text.strip()
            return text[:299] if text else _fallback_draft_nudge(transaction)

        elif provider == "openai":
            import requests
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
                "temperature": 0.4
            }
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"].strip()
                return text[:299]

        elif provider == "anthropic":
            import requests
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            payload = {
                "model": "claude-3-haiku-20240307",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": prompt}]
            }
            resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                text = resp.json()["content"][0]["text"].strip()
                return text[:299]

    except Exception:
        # Graceful fallback on any network or API error
        return _fallback_draft_nudge(transaction)

    return _fallback_draft_nudge(transaction)


def parse_promise_to_pay(customer_reply: str) -> Dict[str, Any]:
    """Classify a customer's simulated response to an outreach nudge.

    Args:
        customer_reply: The text message reply received from the customer.

    Returns:
        Dict with keys:
        - 'status': 'PROMISED' | 'DECLINED' | 'UNCLEAR'
        - 'promised_date': str (YYYY-MM-DD or descriptive) or None
    """
    if not customer_reply or not isinstance(customer_reply, str):
        return {"status": "UNCLEAR", "promised_date": None}

    provider, api_key = _get_api_provider()

    if not provider or not api_key:
        return _fallback_parse_promise(customer_reply)

    system_instruction = (
        "Classify the customer's payment response into exactly one of: 'PROMISED', 'DECLINED', or 'UNCLEAR'. "
        "If the customer promised to pay on a specific date, extract 'promised_date' (ISO YYYY-MM-DD if available, or string, else null). "
        "Return ONLY a JSON object with keys 'status' and 'promised_date'. No explanation or markdown."
    )
    prompt = f"{system_instruction}\nCustomer Reply: \"{customer_reply}\""

    try:
        if provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            raw_text = response.text.strip()
            # Clean markdown codeblocks if present
            cleaned = re.sub(r"^```json\s*", "", raw_text, flags=re.MULTILINE)
            cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE).strip()
            parsed = json.loads(cleaned)
            status = parsed.get("status", "UNCLEAR").upper()
            if status not in ["PROMISED", "DECLINED", "UNCLEAR"]:
                status = "UNCLEAR"
            return {"status": status, "promised_date": parsed.get("promised_date")}

        elif provider == "openai":
            import requests
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": customer_reply}],
                "response_format": {"type": "json_object"},
                "temperature": 0.1
            }
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                parsed = resp.json()["choices"][0]["message"]["content"]
                data = json.loads(parsed)
                status = data.get("status", "UNCLEAR").upper()
                if status not in ["PROMISED", "DECLINED", "UNCLEAR"]:
                    status = "UNCLEAR"
                return {"status": status, "promised_date": data.get("promised_date")}

    except Exception:
        return _fallback_parse_promise(customer_reply)

    return _fallback_parse_promise(customer_reply)
