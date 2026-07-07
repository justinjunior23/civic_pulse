import os
import json
import logging
from groq import Groq

logger = logging.getLogger(__name__)


def _fallback_confidence(severity: str) -> int:
    """Return a sensible fallback confidence when the model returns 0 or None."""
    return {"Critical": 95, "High": 90, "Medium": 80, "Low": 75}.get(severity, 85)


def _fallback_priority(severity: str) -> int:
    """Return a sensible fallback priority when the model returns 0 or None."""
    return {"Critical": 95, "High": 80, "Medium": 55, "Low": 20}.get(severity, 50)


def classify_report(text: str, existing_reports: list = None) -> dict:
    """
    Send a civic report to Groq (Llama) and get back rich structured
    classification for CivicPulse AI.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set.")

    client = Groq(api_key=api_key)

    similar_context = ""
    if existing_reports:
        recent = []
        for r in existing_reports[:10]:
            t = getattr(r, "text", None) or str(r)
            recent.append(f"- {t}")
        similar_context = "\n".join(recent)

    prompt = f"""
You are CivicPulse AI, an advanced Government Decision Intelligence System
designed to assist local authorities in Rwanda.

You must analyze each citizen report like an emergency operations center.

Citizen Report:
\"\"\"{text}\"\"\"

Existing reports for duplicate detection:
{similar_context if similar_context else "None"}

Return ONLY valid JSON. No markdown. No explanation. No extra text.

JSON Schema:

{{
    "title": "short descriptive title",
    "category": "Infrastructure | Utilities | Safety | Health | Environment | Transport | Education | Security | Other",
    "severity": "Critical | High | Medium | Low",
    "priority_score": 0,
    "confidence": 0,
    "status": "Open",
    "location": null,
    "district": null,
    "sector": null,
    "cell": null,
    "village": null,
    "summary": "",
    "reasoning": ["", "", ""],
    "recommended_action": "",
    "department": "",
    "estimated_resolution": "",
    "estimated_people_affected": null,
    "public_safety_risk": "Low | Medium | High",
    "economic_impact": "Low | Medium | High",
    "environmental_impact": "Low | Medium | High",
    "urgency": "Immediate | Within 24 Hours | Within 3 Days | Routine",
    "duplicate_detected": false,
    "similarity_score": 0,
    "similar_report_text": null,
    "ai_insights": ["", "", ""],
    "keywords": []
}}

═══════════════════════════════════
SEVERITY RULES
═══════════════════════════════════

Critical (Priority 90–100, Confidence 90–99%)
- Immediate danger to life
- Hospital emergency
- Bridge collapse
- Major flooding
- Fire
- Major power grid failure
- Epidemic or disease outbreak

High (Priority 70–89, Confidence 85–95%)
- Water outage
- Electricity outage
- Dangerous roads
- Major sanitation issue
- Sewage overflow

Medium (Priority 40–69, Confidence 75–90%)
- Street lights out
- Waste collection delay
- Road damage (non-dangerous)
- Pest or rodent infestation
- Noise pollution
- Blocked drainage

Low (Priority 10–39, Confidence 70–85%)
- Cosmetic issues
- Minor complaints
- Requests for information

═══════════════════════════════════
HEALTH SEVERITY RULES (override general)
═══════════════════════════════════

These health issues must be classified as MINIMUM Medium severity:
- Rodent or pest infestation → Medium (disease risk, sanitation concern)
- Waste contamination → Medium
- Food contamination → High
- Disease outbreak → Critical
- Sewage near homes → High

Never classify rodent/pest infestation as Low — it poses real health risk.

═══════════════════════════════════
PRIORITY SCORE RULES
═══════════════════════════════════

You MUST return a non-zero priority score.
Calculate based on:
- Severity band (Critical=90-100, High=70-89, Medium=40-69, Low=10-39)
- Duration of problem
- Number of people affected
- Public safety risk
- Infrastructure importance
- Confidence level

Return integer between 0 and 100. NEVER return 0.

═══════════════════════════════════
CONFIDENCE RULES
═══════════════════════════════════

You MUST return a non-zero confidence score.
Confidence reflects how certain the AI is about its classification.
- High evidence in report → 90–99%
- Moderate evidence → 75–89%
- Low evidence or vague report → 60–74%

Return integer between 0 and 100. NEVER return 0.

═══════════════════════════════════
ESTIMATED PEOPLE AFFECTED RULES
═══════════════════════════════════

Only estimate if report mentions a scope:
- "my home" / "my house" / single household → 5
- Named village or cell → 120
- Named sector → 600
- Named district → 3000+
- No location or scope mentioned → return null (do NOT guess)

═══════════════════════════════════
REASONING
═══════════════════════════════════

Explain clearly WHY the issue has that severity and priority.
Always return exactly 3 items.

Example:
[
  "Water unavailable for more than 72 hours.",
  "Essential utility directly affecting multiple households.",
  "High probability of public health consequences if unresolved."
]

═══════════════════════════════════
AI INSIGHTS
═══════════════════════════════════

Three concise forward-looking observations or recommendations.
Always return exactly 3 items.

Example:
[
  "Service disruption likely spreading to nearby villages.",
  "Issue should be treated as urgent within 24 hours.",
  "Similar utility complaints have been increasing in this area."
]

═══════════════════════════════════
RECOMMENDED ACTION
═══════════════════════════════════

Must be specific and operational.
Good: "Dispatch pest control services to the affected home immediately."
Bad: "Authorities should investigate the matter."

═══════════════════════════════════
DEPARTMENT MAPPING (by category)
═══════════════════════════════════

Map department strictly by category:

Health → "Health Ministry"
Infrastructure → "Roads Authority"
Utilities (water) → "Water Utility"
Utilities (electricity) → "Energy Authority"
Transport → "Transport Authority"
Security → "Rwanda National Police"
Safety → "Rwanda National Police"
Environment → "Environment Agency"
Education → "Ministry of Education"
Other → "Local Government Office"

Pest / Rodent / Infestation → category = "Health", department = "Health Ministry"

═══════════════════════════════════
LOCATION EXTRACTION
═══════════════════════════════════

Extract District, Sector, Cell, Village from report text.
If any field is not explicitly mentioned, return null for that field.
Do NOT invent location names.

═══════════════════════════════════
DUPLICATE DETECTION
═══════════════════════════════════

Compare report against existing reports.
If similarity > 80%:
  duplicate_detected = true
  similarity_score = integer percentage (e.g. 85)
  similar_report_text = the most similar existing report text
Otherwise:
  duplicate_detected = false
  similarity_score = 0
  similar_report_text = null

Return ONLY JSON. No markdown. No explanation.
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=1200,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are CivicPulse AI. Always return valid JSON only. "
                        "Never use markdown or code blocks. "
                        "Never return 0 for priority_score or confidence."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        raw = response.choices[0].message.content.strip()
        clean = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)

        # ── Post-processing safety net ──────────────────────────────────────

        severity = result.get("severity", "Medium")

        # Priority score: never 0
        ps = result.get("priority_score")
        if not ps or int(ps) == 0:
            result["priority_score"] = _fallback_priority(severity)
        else:
            result["priority_score"] = max(1, min(100, int(ps)))

        # Confidence: never 0
        conf = result.get("confidence")
        if not conf or int(conf) == 0:
            result["confidence"] = _fallback_confidence(severity)
        else:
            result["confidence"] = max(1, min(100, int(conf)))

        # Health + pest/rodent → minimum Medium severity
        category = result.get("category", "")
        title_lower = (result.get("title") or "").lower()
        summary_lower = (result.get("summary") or "").lower()
        pest_keywords = ("rodent", "mouse", "mice", "rat", "pest", "infestation",
                         "cockroach", "termite", "bedbug", "mosquito")
        is_pest = any(k in title_lower or k in summary_lower for k in pest_keywords)
        if is_pest or category == "Health":
            if result.get("severity") == "Low":
                result["severity"] = "Medium"
                # Re-adjust priority if it was in the Low band
                if result["priority_score"] < 40:
                    result["priority_score"] = 45
            result["category"] = "Health"
            result["department"] = "Health Ministry"

        # Ensure required string fields are never empty/None
        for field in ("title", "summary", "recommended_action", "department",
                      "estimated_resolution", "severity", "category",
                      "urgency", "public_safety_risk", "economic_impact",
                      "environmental_impact", "status"):
            if not result.get(field):
                result[field] = "Unknown"

        # Ensure list fields are always proper lists with content
        for field in ("reasoning", "ai_insights"):
            val = result.get(field)
            if not isinstance(val, list) or len(val) == 0:
                result[field] = ["No data available.", "", ""]
            # Filter out empty strings
            result[field] = [item for item in result[field] if item.strip()]

        if not isinstance(result.get("keywords"), list):
            result["keywords"] = []

        # similarity_score
        result["similarity_score"] = max(0, min(100, int(result.get("similarity_score") or 0)))

        # estimated_people_affected must be int or null — never 0 as a guess
        epa = result.get("estimated_people_affected")
        if epa is not None:
            try:
                result["estimated_people_affected"] = int(epa)
            except (ValueError, TypeError):
                result["estimated_people_affected"] = None

        # duplicate_detected must be bool
        result["duplicate_detected"] = bool(result.get("duplicate_detected", False))

        return result

    except json.JSONDecodeError as e:
        logger.error("CivicPulse AI: Failed to parse JSON response: %s", e)
        raise ValueError(f"AI returned invalid JSON: {e}") from e
    except Exception as e:
        logger.error("CivicPulse AI: Classification failed: %s", e)
        raise