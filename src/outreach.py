"""LLM Outreach and Customer Intent Parsing Engine.

This module is the ONLY component in AutoPey-Rescue that leverages LLMs.
It supports:
1. Google Gemini API (via google-genai SDK — GEMINI_API_KEY / GOOGLE_API_KEY)
   Model: gemini-3.6-flash / gemini-flash-latest
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

# In-memory caches to prevent redundant API calls and rate-limiting
_NUDGE_CACHE: Dict[str, str] = {}
_PROMISE_CACHE: Dict[str, Dict[str, Any]] = {}


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
    """Deterministic fallback Hinglish reminder when no API key is present or on API error."""
    customer_name = transaction.get("customer_name", "Customer")
    first_name = customer_name.split()[0] if customer_name else "Customer"
    amount = transaction.get("amount_inr", 499)
    due_date = transaction.get("due_date", "recently")
    failure_code = transaction.get("failure_code", "UNKNOWN")

    # Contextual messages per failure type for richer fallback variety
    if failure_code == "INSUFFICIENT_BALANCE":
        templates = [
            f"Hi {first_name}! Rs.{amount} ka payment {due_date} ko process nahi ho paya — balance thoda kam tha. Salary aane ke baad ek baar check kar lijiye!",
            f"Namaste {first_name}! Aapka Rs.{amount} subscription {due_date} ko fail hua. Kabhi bhi convenient ho toh UPI se complete kar sakte ho — hum wait karenge!",
            f"Hey {first_name}! Rs.{amount} payment {due_date} ko fail hua. Koi bhi waqt complete kar sakte ho — aapka plan safe hai abhi. 🙏",
        ]
    elif failure_code == "MANDATE_EXPIRED":
        templates = [
            f"Hi {first_name}! Aapka Rs.{amount} ka autopay mandate expire ho gaya ({due_date}). Ek baar mandate renew kar lo toh subscription automatic ho jayega!",
            f"Hey {first_name}! Rs.{amount} ka mandate {due_date} ko expire hua. Please mandate reauthorize kar lo — link bhejte hain. Easy process hai!",
        ]
    elif failure_code == "TECH_TIMEOUT":
        templates = [
            f"Hi {first_name}! Rs.{amount} payment {due_date} ko bank timeout ki wajah se fail hua — aapki galti nahi! Automatically retry ho jayega, koi action needed nahi.",
            f"Hey {first_name}! Technical issue se Rs.{amount} payment {due_date} ko ruk gayi. Hum retry kar rahe hain — koi tension nahi!",
        ]
    else:
        templates = [
            f"Hi {first_name}! Apka Rs.{amount} ka subscription payment {due_date} ko complete nahi ho paya. Please UPI app par check kar lijiye taki plan chalta rahe. Koi query ho toh bataiye!",
        ]

    import random
    rng = random.Random(hash(transaction.get("transaction_id", "default")))
    msg = rng.choice(templates)
    return msg[:299]


def _fallback_parse_promise(reply: str) -> Dict[str, Any]:
    """Deterministic heuristic fallback intent parser for offline testing or API errors."""
    if not reply or not isinstance(reply, str):
        return {"status": "UNCLEAR", "promised_date": None}

    lower = reply.lower().strip()

    # Decline indicators
    decline_words = [
        "cancel", "cancelled", "band karo", "nahi chahiye", "stop", "no thanks",
        "mat karo", "not interested", "refund", "fraud", "block karo", "deactivate"
    ]
    promise_words = [
        "kal", "tomorrow", "shaam", "evening", "aaj", "today", "kar dunga", "karta hu",
        "pay karunga", "salary", "pay later", "will pay", "5th", "1st", "10th", "15th",
        "haan", "yes", "done", "zaroor", "pakka", "abhi karta", "ho jayega", "karunga"
    ]

    if any(w in lower for w in decline_words) and not any(p in lower for p in ["kal", "kar dunga", "pay karunga"]):
        return {"status": "DECLINED", "promised_date": None}

    if any(w in lower for w in promise_words):
        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", reply)
        promised_date = date_match.group(1) if date_match else None
        return {"status": "PROMISED", "promised_date": promised_date}

    return {"status": "UNCLEAR", "promised_date": None}


def draft_nudge(transaction: Dict[str, Any]) -> str:
    """Draft a friendly, low-pressure Hinglish WhatsApp payment reminder.

    Tone: Polite, helpful, low-pressure, conversational.
    Constraints: Must mention first name, amount_inr, and due_date. Length < 300 characters.

    Args:
        transaction: Dict containing customer_name, amount_inr, due_date, failure_code.

    Returns:
        Hinglish message text under 300 characters.
    """
    customer_name = transaction.get("customer_name", "Customer")
    first_name = customer_name.split()[0] if customer_name else "Customer"
    amount = transaction.get("amount_inr", 499)
    due_date = transaction.get("due_date", "recently")
    failure_code = transaction.get("failure_code", "UNKNOWN")

    cache_key = f"{first_name}_{amount}_{due_date}_{failure_code}"
    if cache_key in _NUDGE_CACHE:
        return _NUDGE_CACHE[cache_key]

    provider, api_key = _get_api_provider()

    if not provider or not api_key:
        return _fallback_draft_nudge(transaction)

    # Contextualize prompt based on failure type
    context_map = {
        "INSUFFICIENT_BALANCE": "The customer's account had insufficient balance. Align message with salary cycle timing.",
        "MANDATE_EXPIRED": "The customer's autopay mandate has expired. Gently request mandate re-authorization.",
        "TECH_TIMEOUT": "This was a technical bank timeout — not the customer's fault. Reassure them no action is needed, retry is automatic.",
        "HARD_DECLINE_OR_CANCELLED": "The customer has cancelled. Do NOT contact — this case should not reach outreach.",
    }
    context = context_map.get(failure_code, "General payment failure.")

    prompt = (
        f"You are an empathetic customer success assistant for an Indian subscription service. "
        f"Draft a short, polite WhatsApp payment reminder in natural Hinglish (Hindi-English mix). "
        f"Context: {context} "
        f"Details: Customer First Name: {first_name}, Amount: INR {amount}, Due Date: {due_date}. "
        f"Rules: "
        f"1. Low pressure, empathetic, courteous tone. "
        f"2. MUST naturally reference {first_name}, Rs.{amount}, and date {due_date}. "
        f"3. Do NOT threaten cancellation, penalties, or legal action. "
        f"4. Length MUST be strictly under 280 characters. "
        f"5. Output ONLY the message text without quotes, preamble, or markdown."
    )

    try:
        if provider == "gemini":
            from google import genai as google_genai
            from google.genai import types

            client = google_genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=5000)
            )
            config = types.GenerateContentConfig(
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                temperature=0.3,
                max_output_tokens=100,
            )

            # Try primary active model, fallback to flash-latest if unavailable
            response = None
            for model_name in ["gemini-3.6-flash", "gemini-flash-latest"]:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    )
                    if response and response.text:
                        break
                except Exception:
                    continue

            text = response.text.strip() if (response and response.text) else ""
            if text:
                res = text[:299]
                _NUDGE_CACHE[cache_key] = res
                return res
            return _fallback_draft_nudge(transaction)

        elif provider == "openai":
            import requests
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
                "temperature": 0.4
            }
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=6)
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"].strip()
                res = text[:299]
                _NUDGE_CACHE[cache_key] = res
                return res

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
            resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=6)
            if resp.status_code == 200:
                text = resp.json()["content"][0]["text"].strip()
                res = text[:299]
                _NUDGE_CACHE[cache_key] = res
                return res

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

    cache_key = customer_reply.strip()
    if cache_key in _PROMISE_CACHE:
        return _PROMISE_CACHE[cache_key]

    provider, api_key = _get_api_provider()

    if not provider or not api_key:
        return _fallback_parse_promise(customer_reply)

    system_instruction = (
        "You are a payment intent classifier for an Indian fintech system. "
        "Classify the customer's payment response into exactly one of: 'PROMISED', 'DECLINED', or 'UNCLEAR'. "
        "PROMISED: customer agrees to pay (now, later, or on a specific date). "
        "DECLINED: customer explicitly refuses, cancels subscription, or says not interested. "
        "UNCLEAR: ambiguous, unrelated, or insufficient information. "
        "If PROMISED and a specific date is mentioned, extract 'promised_date' (ISO YYYY-MM-DD if available, or natural language like 'tomorrow', else null). "
        "Return ONLY a valid JSON object with keys 'status' and 'promised_date'. No explanation or markdown."
    )
    prompt = f"{system_instruction}\nCustomer Reply: \"{customer_reply}\""

    try:
        if provider == "gemini":
            from google import genai as google_genai
            from google.genai import types

            client = google_genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=5000)
            )
            config = types.GenerateContentConfig(
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                response_mime_type="application/json",
                temperature=0.1,
            )

            response = None
            for model_name in ["gemini-3.6-flash", "gemini-flash-latest"]:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    )
                    if response and response.text:
                        break
                except Exception:
                    continue

            raw_text = response.text.strip() if (response and response.text) else ""
            cleaned = re.sub(r"^```json\s*", "", raw_text, flags=re.MULTILINE)
            cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE).strip()
            parsed = json.loads(cleaned)
            status = parsed.get("status", "UNCLEAR").upper()
            if status not in ["PROMISED", "DECLINED", "UNCLEAR"]:
                status = "UNCLEAR"
            res = {"status": status, "promised_date": parsed.get("promised_date")}
            _PROMISE_CACHE[cache_key] = res
            return res

        elif provider == "openai":
            import requests
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": customer_reply}],
                "response_format": {"type": "json_object"},
                "temperature": 0.1
            }
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=6)
            if resp.status_code == 200:
                parsed = resp.json()["choices"][0]["message"]["content"]
                data = json.loads(parsed)
                status = data.get("status", "UNCLEAR").upper()
                if status not in ["PROMISED", "DECLINED", "UNCLEAR"]:
                    status = "UNCLEAR"
                res = {"status": status, "promised_date": data.get("promised_date")}
                _PROMISE_CACHE[cache_key] = res
                return res

    except Exception:
        return _fallback_parse_promise(customer_reply)

    return _fallback_parse_promise(customer_reply)
