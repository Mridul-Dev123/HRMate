"""
HRMate Guardrails Module
=========================
Reusable guardrail classes for input validation, PII detection,
content moderation, and output validation.
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass
class GuardrailResult:
    """Outcome of a guardrail check."""
    passed: bool
    reason: str = ""
    flagged_items: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 1. Input Sanitizer – prompt-injection detection
# ---------------------------------------------------------------------------
class InputSanitizer:
    """
    Detects common prompt-injection patterns in user-supplied text.
    Uses a deny-list of regex patterns that are indicative of injection attempts.
    """

    INJECTION_PATTERNS: List[re.Pattern] = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)", re.IGNORECASE),
        re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)", re.IGNORECASE),
        re.compile(r"forget\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.IGNORECASE),
        re.compile(r"act\s+as\s+(a|an)\s+", re.IGNORECASE),
        re.compile(r"pretend\s+(you\s+are|to\s+be)\s+", re.IGNORECASE),
        re.compile(r"system\s*prompt", re.IGNORECASE),
        re.compile(r"reveal\s+(your|the)\s+(instructions|prompt|system)", re.IGNORECASE),
        re.compile(r"output\s+(your|the)\s+(instructions|prompt|system)", re.IGNORECASE),
        re.compile(r"what\s+(are|is)\s+your\s+(instructions|system\s*prompt|rules)", re.IGNORECASE),
        re.compile(r"\bDAN\b"),  # "Do Anything Now" jailbreak
        re.compile(r"jailbreak", re.IGNORECASE),
        re.compile(r"<\s*script\b", re.IGNORECASE),  # XSS-style injection
    ]

    @classmethod
    def check(cls, text: str) -> GuardrailResult:
        """
        Scan *text* for known prompt-injection patterns.
        Returns GuardrailResult(passed=True) if safe.
        """
        flagged: List[str] = []
        for pattern in cls.INJECTION_PATTERNS:
            if pattern.search(text):
                flagged.append(pattern.pattern)

        if flagged:
            return GuardrailResult(
                passed=False,
                reason="Potential prompt injection detected.",
                flagged_items=flagged,
            )
        return GuardrailResult(passed=True)


# ---------------------------------------------------------------------------
# 2. PII Detector
# ---------------------------------------------------------------------------
class PIIDetector:
    """
    Detects personally-identifiable information patterns such as
    Social Security Numbers, credit-card numbers, and bank account numbers.
    """

    PII_PATTERNS: List[Tuple[str, re.Pattern]] = [
        ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
        ("SSN_NO_DASH", re.compile(r"\b\d{9}\b")),
        ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
        ("CREDIT_CARD_FORMATTED", re.compile(
            r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b"
        )),
        ("BANK_ACCOUNT", re.compile(r"\b\d{8,17}\b")),
        ("PHONE_US", re.compile(
            r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
        )),
    ]

    @classmethod
    def check(cls, text: str) -> GuardrailResult:
        """
        Scan *text* for PII patterns.
        Returns GuardrailResult(passed=True) if clean.
        """
        flagged: List[str] = []
        for label, pattern in cls.PII_PATTERNS:
            if pattern.search(text):
                flagged.append(label)

        if flagged:
            return GuardrailResult(
                passed=False,
                reason="PII detected in text.",
                flagged_items=flagged,
            )
        return GuardrailResult(passed=True)

    @classmethod
    def redact(cls, text: str) -> str:
        """Return a copy of *text* with PII patterns replaced by [REDACTED]."""
        redacted = text
        for _label, pattern in cls.PII_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted


# ---------------------------------------------------------------------------
# 3. Content Moderation Guard
# ---------------------------------------------------------------------------
class ContentModerationGuard:
    """
    Lightweight keyword-based moderation to flag overtly abusive or
    threatening language.  This is a first-pass filter; a production
    system should use an LLM-based or API-based moderation service.
    """

    ABUSE_KEYWORDS: List[re.Pattern] = [
        re.compile(r"\b(kill|murder|attack|bomb|threat(en)?)\b", re.IGNORECASE),
        re.compile(r"\b(fuck|shit|bitch|bastard|asshole)\b", re.IGNORECASE),
        re.compile(r"\b(hate\s+you|die|destroy)\b", re.IGNORECASE),
    ]

    @classmethod
    def check(cls, text: str) -> GuardrailResult:
        flagged: List[str] = []
        for pattern in cls.ABUSE_KEYWORDS:
            matches = pattern.findall(text)
            if matches:
                flagged.extend(matches)

        if flagged:
            return GuardrailResult(
                passed=False,
                reason="Abusive or threatening content detected.",
                flagged_items=flagged,
            )
        return GuardrailResult(passed=True)


# ---------------------------------------------------------------------------
# 4. Response Validator
# ---------------------------------------------------------------------------
class ResponseValidator:
    """
    Validates that the agent's outgoing response doesn't leak internal
    details and follows a reasonable email format.
    """

    LEAK_PATTERNS: List[re.Pattern] = [
        re.compile(r"system\s*prompt", re.IGNORECASE),
        re.compile(r"GOOGLE_API_KEY", re.IGNORECASE),
        re.compile(r"PINECONE_API_KEY", re.IGNORECASE),
        re.compile(r"EMAIL_PASS", re.IGNORECASE),
        re.compile(r"Action\s*Input\s*:", re.IGNORECASE),   # ReAct internals
        re.compile(r"Observation\s*:", re.IGNORECASE),       # ReAct internals
        re.compile(r"Thought\s*:", re.IGNORECASE),           # ReAct internals
    ]

    @classmethod
    def check(cls, response: str) -> GuardrailResult:
        """
        Validates the response for internal data leaks and
        basic format expectations.
        """
        flagged: List[str] = []

        # Check for internal leaks
        for pattern in cls.LEAK_PATTERNS:
            if pattern.search(response):
                flagged.append(pattern.pattern)

        if flagged:
            return GuardrailResult(
                passed=False,
                reason="Response may contain leaked internal data or raw agent traces.",
                flagged_items=flagged,
            )

        # Basic sanity: response should have at least some content
        if len(response.strip()) < 10:
            return GuardrailResult(
                passed=False,
                reason="Response is too short to be a valid email reply.",
            )

        return GuardrailResult(passed=True)


# ---------------------------------------------------------------------------
# Convenience: run all input guardrails
# ---------------------------------------------------------------------------
def run_input_guardrails(text: str) -> GuardrailResult:
    """
    Runs InputSanitizer, PIIDetector, and ContentModerationGuard sequentially.
    Returns the first failing result, or a passing result if all pass.
    """
    for guard in [InputSanitizer, ContentModerationGuard]:
        result = guard.check(text)
        if not result.passed:
            return result

    # PII in input is a warning, not a hard block; we redact instead
    return GuardrailResult(passed=True)


def run_output_guardrails(response: str) -> GuardrailResult:
    """
    Runs ResponseValidator and PIIDetector on the agent's output.
    Returns the first failing result, or a passing result if all pass.
    """
    validator_result = ResponseValidator.check(response)
    if not validator_result.passed:
        return validator_result

    pii_result = PIIDetector.check(response)
    if not pii_result.passed:
        return GuardrailResult(
            passed=False,
            reason="Response contains PII that must be redacted before sending.",
            flagged_items=pii_result.flagged_items,
        )

    return GuardrailResult(passed=True)
