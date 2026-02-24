from __future__ import annotations

import re
from typing import Any

import structlog

logger = structlog.get_logger()

# Patterns from OWASP LLM Top 10 injection taxonomy + common attack vectors
INJECTION_PATTERNS: list[tuple[str, str]] = [
    # Direct instruction override
    (r"(?i)ignore\s+(all\s+)?(previous|above|prior|your)\s+(instructions?|prompts?|rules?|context|directives?|guidelines?)", "instruction_override"),
    (r"(?i)disregard\s+(all\s+)?(previous|above|prior|your|the)\s+(instructions?|prompts?|rules?|guidelines?|safety)", "instruction_override"),
    (r"(?i)disregard\s+the\s+above\b", "instruction_override"),
    (r"(?i)forget\s+(everything|all|your)\s+(you|instructions?|rules?|were|have)", "instruction_override"),
    (r"(?i)override\s+(your|all|the|any)\s+(safety|security|rules?|restrictions?|protocols?|guidelines?|instructions?)", "instruction_override"),
    (r"(?i)stop\s+following\s+(your|the|all)\s+(guidelines?|rules?|instructions?|restrictions?)", "instruction_override"),
    (r"(?i)previous\s+instructions?\s+(are|is)\s+(void|invalid|null|cancelled|overridden)", "instruction_override"),
    (r"(?i)you\s+must\s+(ignore|disregard|bypass|override|break)\s+(your|all|the|any)\s+(rules?|safety|restrictions?|instructions?)", "instruction_override"),
    (r"(?i)new\s+(instruction|directive|rule|system\s+prompt)\s*:", "instruction_override"),

    # Role manipulation / jailbreaking
    (r"(?i)you\s+are\s+(now\s+)?(a|an|the|DAN|operating|in)\b", "role_manipulation"),
    (r"(?i)act\s+as\s+(a|an|if|though)\s+", "role_manipulation"),
    (r"(?i)pretend\s+(you|to\s+be|that)\s+", "role_manipulation"),
    (r"(?i)roleplay\s+(as|like)\s+", "role_manipulation"),
    (r"(?i)from\s+now\s+on\s*,?\s*(you|act|behave|respond|ignore|operate)", "role_manipulation"),
    (r"(?i)switch\s+to\s+(\w+)\s+mode", "role_manipulation"),
    (r"(?i)enter\s+(\w+)\s+mode", "role_manipulation"),
    (r"(?i)(enable|activate|unlock)\s+(developer|admin|unrestricted|jailbreak|debug|god)\s+mode", "role_manipulation"),
    (r"(?i)you\s+have\s+(been|no)\s+(upgraded|updated|reprogrammed|restrictions?|filters?|rules?|limitations?|ethical|content\s+policy)", "role_manipulation"),
    (r"(?i)imagine\s+you\s+(are|were|had|have)\s+(a|an|no)\s+", "role_manipulation"),
    (r"(?i)assume\s+the\s+role\s+of", "role_manipulation"),
    (r"(?i)(you\s+can|able\s+to)\s+(do\s+anything|bypass|break\s+free)", "role_manipulation"),
    (r"(?i)without\s+(any|ethical|safety|content)\s+(guidelines?|restrictions?|filters?|policy|limitations?)", "role_manipulation"),

    # System prompt extraction
    (r"(?i)(show|reveal|display|print|output|repeat|echo|tell|give)\s+(me\s+)?(your|the|system|base|original|initial|hidden|secret|complete|full)\s+((system|initial|original|hidden|secret|full|base|complete)\s+)?(prompt|instructions?|rules?|config|configuration|message|directives?)", "prompt_extraction"),
    (r"(?i)what\s+(are|is|were|does)\s+(your|the)\s+(system\s+)?(prompt|instructions?|rules?|initial\s+prompt|base\s+instructions?|configuration)", "prompt_extraction"),
    (r"(?i)(begin|start)\s+your\s+(response|reply|answer)\s+with\s+(the\s+)?(system|initial)\s+prompt", "prompt_extraction"),
    (r"(?i)repeat\s+(everything|all|the\s+text)\s+(above|before)\s+(this|my)", "prompt_extraction"),
    (r"(?i)(what|output)\s+(text|message|content)\s+appears?\s+before\s+my\s+message", "prompt_extraction"),
    (r"(?i)what\s+were\s+you\s+told\s+before\s+this", "prompt_extraction"),
    (r"(?i)confirm\s+by\s+showing\s+your\s+prompt", "prompt_extraction"),
    (r"(?i)copy\s+of\s+your\s+(system\s+)?instructions", "prompt_extraction"),
    (r"(?i)(output|show|display)\s+(the\s+)?(text|content|message)\s+.{0,30}(before|above|prior)", "prompt_extraction"),
    (r"(?i)show\s+me\s+(the\s+)?(hidden|secret|system)\s+(message|prompt|instructions?)", "prompt_extraction"),
    (r"(?i)(see|view|access)\s+(the\s+)?(system\s+)?(message|prompt|instructions?|configuration)", "prompt_extraction"),
    (r"(?i)(hidden|secret)\s+(system\s+)?(prompt|message|instructions?|config)", "prompt_extraction"),
    (r"(?i)(we\s+)?need\s+(your|the)\s+(base|system|complete|full|original)\s+(instructions?|prompt|configuration|message)", "prompt_extraction"),
    (r"(?i)(output|review|show)\s+your\s+(complete|full|entire|system)\s+(system\s+)?(prompt|instructions?|configuration)", "prompt_extraction"),
    (r"(?i)(told|said)\s+(me\s+)?(I|we)\s+could\s+see\s+(the\s+)?(system\s+)?(message|prompt|instructions?)", "prompt_extraction"),

    # Delimiter/encoding attacks
    (r"(?i)\[/?system\]", "delimiter_attack"),
    (r"(?i)<\|?(system|im_start|im_end|endoftext)\|?>", "delimiter_attack"),
    (r"(?i)```\s*(system|admin|root)", "delimiter_attack"),
    (r"(?i)###\s*(system|instruction|admin|end|break)", "delimiter_attack"),
    (r"(?i)\[/?INST\]", "delimiter_attack"),
    (r"(?i)(===|---)\s*(BREAK|END|SYSTEM|NEW)", "delimiter_attack"),
    (r"(?i)END\s+OF\s+PROMPT", "delimiter_attack"),
    (r"(?i)\\n\\n(Human|System|Assistant)\s*:", "delimiter_attack"),

    # Base64/encoding evasion
    (r"(?i)(decode|decrypt|deobfuscate|base64|rot13)\s*:?\s+(this|the\s+following|below|decode|[A-Za-z0-9+/=]{6,})", "encoding_evasion"),
    # Obfuscated "ignore" variants — leetspeak, dot-separated, space-inserted
    (r"(?i)ign[o0]re\s+(all\s+)?prev[i1]", "encoding_evasion"),
    (r"(?i)d\.?i\.?s\.?r\.?e\.?g\.?a\.?r\.?d", "encoding_evasion"),
    (r"(?i)i\s*g\s+n\s*o\s*r\s*e\s+.{0,20}(instruct|prev|rules?|safety)", "encoding_evasion"),
    (r"[ÏïÎî][gĝ][nñ][öoóò][rŕ][êeéè]", "encoding_evasion"),
    # Dot-separated letters forming "ignore"
    (r"(?i)i\.g\.?n\.?o\.?r\.?e", "encoding_evasion"),

    # Payload injection
    (r"(?i)(execute|run|eval|exec)\s+(this|the\s+following)\s+(code|command|script|payload|python|javascript)", "code_injection"),
    (r"(?i)(import|require|include)\s+(os|sys|subprocess|exec|shutil)", "code_injection"),
    (r"(?i)__import__\s*\(", "code_injection"),
    (r"(?i)(eval|exec)\s*\(", "code_injection"),
    (r"(?i)javascript\s*:", "code_injection"),
    (r"(?i)subprocess\.(run|call|Popen|check_output)", "code_injection"),
    (r"(?i)os\.(system|popen|exec)", "code_injection"),

    # Recursive/nested injection
    (r"(?i)(translate|summarize|analyze|search\s+for|rephrase)\s+(this|the\s+following)\s*:?\s*.{0,80}(ignore|disregard|forget|reveal|override|bypass)", "nested_injection"),
    (r"(?i)(summarize|translate|analyze|search)\s*:\s*.{0,80}(disregard|ignore|override|reveal|safety|output\s+secrets)", "nested_injection"),

    # Multi-turn manipulation
    (r"(?i)in\s+(the|your)\s+(next|following)\s+(response|reply|message)\s*,?\s*(only|just|simply)", "multi_turn_manipulation"),
    (r"(?i)(actually|wait)\s*,?\s*(forget|ignore|new\s+topic|never\s+mind).{0,50}(ignore|reveal|override|prompt|rules)", "multi_turn_manipulation"),
    (r"(?i)step\s+\d+\s*:\s*.{0,50}(break|override|ignore|bypass|disable)\s+(them|your|the|all|it|rules?|safety)", "multi_turn_manipulation"),
    (r"(?i)I\s+(know|understand)\s+you\s+(said|can't|cannot).{0,50}(but|now|override|ignore|tell\s+me)", "multi_turn_manipulation"),
    (r"(?i)(now|so)\s+override\s+it", "multi_turn_manipulation"),

    # Social engineering / authority claims
    (r"(?i)(I\s+am|I'm|as)\s+(your|a|the|an)\s+(developer|admin|administrator|creator|owner|CEO|manager|root|supervisor)", "social_engineering"),
    (r"(?i)(authorized|admin|root)\s+(access|override|privilege|clearance)", "social_engineering"),
    (r"(?i)(security|penetration|pen)\s+(test|audit|review)\s*(authorized|mode)?", "social_engineering"),
    (r"(?i)for\s+(debugging|compliance|audit|review|testing)\s+purposes?\s*,?\s*(please\s+)?(show|reveal|display|output|give|print)", "social_engineering"),
    (r"(?i)(management|CEO|CTO|team\s+lead)\s+(authorized|approved|told|instructed|said)", "social_engineering"),
    (r"(?i)according\s+to\s+policy.{0,30}(you\s+must|show|reveal|display)", "social_engineering"),
    (r"(?i)(quality\s+assurance|QA|internal\s+security|safety\s+team)\s*:?\s*(please\s+)?(show|reveal|confirm|need)", "social_engineering"),
    (r"(?i)(FOIA|freedom\s+of\s+information)\s*.{0,30}(request|copy|your)", "social_engineering"),

    # Hypothetical bypass attempts
    (r"(?i)hypothetically\s*,?\s*(if|what\s+if)\s+you\s+(had|have|were)", "hypothetical_bypass"),
    (r"(?i)if\s+I\s+were\s+(an?\s+)?(admin|developer|root|authorized)", "hypothetical_bypass"),
    (r"(?i)in\s+an?\s+(emergency|override)\s+scenario", "hypothetical_bypass"),
    (r"(?i)to\s+pass\s+the\s+test\s*,?\s*(show|reveal|display|output)", "hypothetical_bypass"),
]

# Suspicious token patterns (high entropy, control chars)
SUSPICIOUS_PATTERNS: list[tuple[str, str]] = [
    (r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "control_characters"),
    (r"(\w)\1{20,}", "repetition_attack"),  # 20+ repeated characters
    (r"(\b\w+\b)\s+(\1\s+){4,}", "repetition_attack"),  # 5+ repeated words
    (r"[^\x00-\x7F]{50,}", "unicode_flooding"),  # 50+ consecutive non-ASCII
    (r"[\u200b-\u200f\u2028-\u202f\ufeff]", "zero_width_chars"),  # Zero-width/invisible chars
]


class InjectionDetector:
    """Layer 1: Fast regex/heuristic injection detection. Target: <10ms."""

    def __init__(
        self,
        patterns: list[tuple[str, str]] | None = None,
        suspicious_patterns: list[tuple[str, str]] | None = None,
    ) -> None:
        self._patterns = [
            (re.compile(p), label)
            for p, label in (patterns or INJECTION_PATTERNS)
        ]
        self._suspicious = [
            (re.compile(p), label)
            for p, label in (suspicious_patterns or SUSPICIOUS_PATTERNS)
        ]

    def check(self, text: str) -> dict[str, Any]:
        """Check text for injection patterns. Returns immediately on first match."""
        # Check injection patterns
        for pattern, label in self._patterns:
            if pattern.search(text):
                return {
                    "passed": False,
                    "detection": label,
                    "layer": "injection_pattern",
                }

        # Check suspicious patterns
        for pattern, label in self._suspicious:
            if pattern.search(text):
                return {
                    "passed": False,
                    "detection": label,
                    "layer": "suspicious_pattern",
                }

        return {"passed": True, "detection": None, "layer": None}
