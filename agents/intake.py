"""
intake.py — Intake Agent

Responsibility: Parse raw expense submissions into structured JSON.

Input:  Raw submission (receipt text/image + employee-entered fields)
Output: StructuredExpense object with fully extracted fields

Two execution modes (auto-selected):
  - LLM mode:   GOOGLE_API_KEY is set → Gemini 2.0 Flash extracts vendor/amount/date
                from receipt text or images (OCR/vision). This is the demo mode.
  - Fallback:   No API key → uses employee-entered fields directly. Lets tests
                and offline demos run without a live key.

Design note: The typed output contract (StructuredExpense) is what matters
architecturally. The LLM is the extraction engine, not the decision-maker —
decisions belong to the Policy and Risk agents downstream.
"""

import os
import json
import base64
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional

try:
    from google import genai
    from google.genai import types as genai_types
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False


# ── Data contracts ────────────────────────────────────────────────────────────

class ExpenseSubmission(BaseModel):
    """Raw input from the employee submission form or CLI."""
    employee_id: str
    description: str
    amount: Optional[float] = None        # Employee-entered; may be overridden by receipt
    category: str
    date: str                              # ISO 8601 YYYY-MM-DD
    receipt_image_path: Optional[str] = None  # Path to image file (jpg/png/pdf)
    receipt_text: Optional[str] = None    # Pre-extracted OCR text (PII already redacted)


class StructuredExpense(BaseModel):
    """
    Structured output — the typed contract passed to the Policy Agent.

    Every field has a clear source:
    - vendor/amount/date: LLM-extracted from receipt, or employee-entered fallback
    - receipt_data: populated when a receipt was provided (image or text)
    """
    employee_id: str
    vendor: str
    amount: float
    currency: str = "USD"
    category: str
    date: str                              # ISO 8601 YYYY-MM-DD
    description: str
    receipt_data: Optional[dict] = Field(
        default=None,
        description="Extracted receipt fields. Presence confirms receipt was provided."
    )
    extraction_method: str = Field(
        default="employee_entered",
        description="'gemini_text', 'gemini_vision', or 'employee_entered'"
    )


# ── Prompt template ───────────────────────────────────────────────────────────

_SYSTEM_INSTRUCTION = """You are the Intake Agent for ExpenseGuard, an expense validation system.

Your sole job is extraction — not evaluation. Pull structured fields from what you're given.

Rules:
1. Extract: vendor name, total amount (USD), transaction date (YYYY-MM-DD), and category.
2. If a receipt is provided, prefer its data over employee-entered values.
3. Vendor: use the merchant/company name, not the card network or bank.
4. Amount: the final charged total (after tax, tips). Numbers only, no currency symbols.
5. Date: always output YYYY-MM-DD. If ambiguous (e.g. "June 25"), use the year from context.
6. If a field is genuinely unclear or missing, use the employee-entered value.
7. Do NOT evaluate policy compliance. That is the next agent's job.

Output exactly this JSON schema — no extra keys, no markdown:
{
  "employee_id": "string",
  "vendor": "string",
  "amount": float,
  "currency": "USD",
  "category": "string",
  "date": "YYYY-MM-DD",
  "description": "string",
  "receipt_data": {
    "vendor": "string",
    "amount": float,
    "date": "YYYY-MM-DD",
    "line_items": ["item1 $X.XX", "item2 $X.XX"]
  } | null
}
"""


# ── LLM extraction ────────────────────────────────────────────────────────────

def _extract_via_gemini_text(
    submission: ExpenseSubmission,
    client: "genai.Client",
) -> StructuredExpense:
    """
    Calls Gemini with receipt text (already PII-redacted) to extract fields.
    Used when receipt_text is provided.
    """
    prompt = f"""Expense submission to parse:

Employee ID:          {submission.employee_id}
Employee description: {submission.description}
Employee category:    {submission.category}
Employee date:        {submission.date}
Employee amount:      {f'${submission.amount}' if submission.amount else 'not provided'}

Receipt text (PII has been redacted — [REDACTED:X] are safe placeholders):
---
{submission.receipt_text}
---

Extract the structured fields and output JSON."""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            temperature=0.0,          # Deterministic extraction
            response_mime_type="application/json",
        ),
    )

    result = json.loads(response.text)
    return StructuredExpense(**result, extraction_method="gemini_text")


def _extract_via_gemini_vision(
    submission: ExpenseSubmission,
    client: "genai.Client",
) -> StructuredExpense:
    """
    Calls Gemini with a receipt image for OCR + field extraction.
    Used when receipt_image_path is provided.

    Design note: Gemini's multimodal capability handles receipt images
    without a separate OCR step — the LLM extracts directly from the image.
    """
    image_path = Path(submission.receipt_image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Receipt image not found: {image_path}")

    # Read image and encode as base64 for the Gemini API
    image_bytes = image_path.read_bytes()
    
    # Detect MIME type from extension
    ext = image_path.suffix.lower()
    mime_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                  ".pdf": "application/pdf", ".webp": "image/webp"}
    mime_type = mime_types.get(ext, "image/jpeg")

    prompt_text = f"""Expense submission — parse the receipt image:

Employee ID:          {submission.employee_id}
Employee description: {submission.description}
Employee category:    {submission.category}
Employee date:        {submission.date}
Employee amount:      {f'${submission.amount}' if submission.amount else 'not provided'}

Extract all fields from the receipt image. Output JSON."""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt_text,
        ],
        config=genai_types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            temperature=0.0,
            response_mime_type="application/json",
        ),
    )

    result = json.loads(response.text)
    return StructuredExpense(**result, extraction_method="gemini_vision")


# ── Fallback extraction (no API key) ─────────────────────────────────────────

def _extract_fallback(submission: ExpenseSubmission) -> StructuredExpense:
    """
    Deterministic extraction from employee-entered fields.
    Used when no GOOGLE_API_KEY is set, or as a fallback on LLM error.

    Design note: This keeps the pipeline fully functional for testing
    and demos without requiring a live API key. The downstream agents
    (Policy, Risk) work identically regardless of extraction method.
    """
    # Infer vendor from description if possible
    # Heuristics (in priority order):
    # 1. "Category — VendorName"  (CLI default format)
    # 2. "VendorName - description" (common user pattern)
    # 3. First word of description
    description = submission.description or ""
    if " — " in description:
        # CLI default: "meals — Chipotle"  → vendor = "Chipotle"
        vendor = description.split(" — ", 1)[-1].strip()
    elif " - " in description:
        vendor = description.split(" - ", 1)[0].strip()
    else:
        vendor = description.strip() or "Unknown Vendor"

    receipt_data = None
    if submission.receipt_text:
        # Minimal parsing: grab first line as vendor, look for "Total:" or "$"
        lines = [l.strip() for l in submission.receipt_text.splitlines() if l.strip()]
        receipt_vendor = lines[0] if lines else vendor
        receipt_data = {
            "vendor": receipt_vendor,
            "amount": submission.amount,
            "date": submission.date,
            "line_items": [],
        }
        vendor = receipt_vendor  # prefer receipt vendor

    return StructuredExpense(
        employee_id=submission.employee_id,
        vendor=vendor,
        amount=submission.amount or 0.0,
        currency="USD",
        category=submission.category,
        date=submission.date,
        description=description,
        receipt_data=receipt_data,
        extraction_method="employee_entered",
    )


# ── Public entry point ────────────────────────────────────────────────────────

def run_intake_agent(submission: ExpenseSubmission) -> StructuredExpense:
    """
    Executes the Intake Agent.

    Selection logic:
    1. If GOOGLE_API_KEY is set:
       a. Image provided → Gemini vision (OCR)
       b. Receipt text provided → Gemini text extraction
       c. Neither → Gemini with employee fields only
    2. No API key → deterministic fallback

    Returns StructuredExpense ready for Policy Agent.
    The extraction_method field records which path was taken (visible in audit log).
    """
    api_key = os.getenv("GOOGLE_API_KEY")

    if api_key and _GENAI_AVAILABLE:
        client = genai.Client(api_key=api_key)
        try:
            if submission.receipt_image_path:
                return _extract_via_gemini_vision(submission, client)
            elif submission.receipt_text:
                return _extract_via_gemini_text(submission, client)
            else:
                # No receipt — still pass through Gemini to normalise vendor name
                # (e.g. "delta airlines chicago" → "Delta Airlines")
                synthetic_text = (
                    f"Vendor/merchant: {submission.description}\n"
                    f"Amount: {submission.amount}\n"
                    f"Date: {submission.date}"
                )
                temp = submission.model_copy(update={"receipt_text": synthetic_text})
                return _extract_via_gemini_text(temp, client)
        except Exception as e:
            # LLM call failed — fall back gracefully, don't crash the pipeline
            print(f"[Intake Agent] Gemini call failed ({e}). Using fallback extraction.")
            return _extract_fallback(submission)
    else:
        return _extract_fallback(submission)


# ── Standalone test harness ───────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    test_cases = [
        ExpenseSubmission(
            employee_id="E1001",
            description="Flight to client meeting in Chicago",
            amount=345.00,
            category="travel",
            date="2026-06-25",
            receipt_text=(
                "Delta Airlines\n"
                "Flight DL1234 — SFO → ORD\n"
                "Passenger: [REDACTED:NAME]\n"
                "Date: June 25, 2026\n"
                "Fare: $315.00\n"
                "Taxes & Fees: $30.00\n"
                "Total Charged: $345.00\n"
                "Card: [REDACTED:CARD]"
            ),
        ),
        ExpenseSubmission(
            employee_id="E1003",
            description="Adobe Creative Cloud annual renewal",
            amount=54.99,
            category="software",
            date="2026-06-01",
        ),
    ]

    for i, submission in enumerate(test_cases, 1):
        print(f"\n[Intake Agent] Test {i}: {submission.description}")
        result = run_intake_agent(submission)
        print(result.model_dump_json(indent=2))
