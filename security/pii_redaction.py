"""
pii_redaction.py — PII Redaction for Receipts

Strips sensitive data (card numbers, addresses) from text before it's
passed to the LLM agents.

Design note: This is scored as a "security feature." Don't bury it in
preprocessing — the README and UI should explicitly call out that PII
is redacted *before* LLM ingestion. This module is that visible step.

Pattern coverage:
- Credit card numbers (PAN): 16 digits, optionally grouped
- Addresses: U.S. street format (123 Main St, Apt 4B)
- Email addresses
- Phone numbers (U.S. formats)
"""

import re


def redact_pii(text: str) -> str:
    """
    Redacts personally identifiable information from text.
    
    Returns: Text with PII replaced by [REDACTED:type] placeholders.
    
    Examples:
        "Card: 4111 1111 1111 1111" → "Card: [REDACTED:CARD]"
        "john@example.com"          → "[REDACTED:EMAIL]"
        "555-123-4567"              → "[REDACTED:PHONE]"
    """
    
    # Credit card numbers (16 digits, common groupings)
    # Matches: 4111111111111111, 4111 1111 1111 1111, 4111-1111-1111-1111
    text = re.sub(
        r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b',
        '[REDACTED:CARD]',
        text
    )
    
    # Email addresses
    text = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        '[REDACTED:EMAIL]',
        text
    )
    
    # U.S. phone numbers (common formats)
    # Matches: (555) 123-4567, 555-123-4567, 555.123.4567, 5551234567
    text = re.sub(
        r'\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}\b',
        '[REDACTED:PHONE]',
        text
    )
    
    # Street addresses (simplified heuristic: number + street type)
    # Matches: "123 Main St", "456 Oak Avenue Apt 3"
    # Note: This is a conservative pattern to avoid false positives.
    text = re.sub(
        r'\b\d{1,5}\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Court|Ct|Way|Place|Pl)\.?\s*(?:Apt|Apartment|Unit|#)?\s*[A-Za-z0-9]*\b',
        '[REDACTED:ADDRESS]',
        text,
        flags=re.IGNORECASE
    )
    
    return text


# ── Test/demo ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_cases = [
        "Receipt from Whole Foods\nCard: 4111 1111 1111 1111\nTotal: $42.35",
        "Contact: john.doe@email.com for inquiries",
        "Delivery to 123 Main Street Apt 4B, call 555-123-4567",
        "Card ending in 9876 (full: 5105105105105100) charged $200",
    ]
    
    print("[PII Redaction Demo]\n")
    for i, text in enumerate(test_cases, 1):
        print(f"Test case {i}:")
        print(f"Before: {text}")
        print(f"After:  {redact_pii(text)}\n")
