"""
Challenge lenses for Sparring.

A lens is a perspective applied to a challenge. Instead of assigning personas 
to models (which biases initial responses), lenses are applied at challenge time.
Any model can apply any lens.

Usage in server.py:
    from lenses import get_challenge_prompt, LENSES, DEFAULT_LENS
    
    prompt = get_challenge_prompt(
        lens="cynical_dev",
        original_question=question,
        original_response=response,
    )
"""

from typing import Optional

# =============================================================================
# Lens Definitions
# =============================================================================
# Each lens has:
#   - description: Short explanation (for get_models/docs)
#   - system: The perspective/role instruction
#   - focus: What specifically to look for

LENSES = {
    "devil_advocate": {
        "description": "Finds flaws, edge cases, and unverified assumptions",
        "system": "You are the devil's advocate. Your job is to find everything that can go wrong.",
        "focus": """
- Unverified implicit assumptions
- Uncovered edge cases
- Fragile dependencies
- Claims made without evidence
- "It should work" hiding real uncertainty
""",
    },

    "steelman": {
        "description": "Strengthens the position — finds missing arguments",
        "system": "You strengthen this position. Find what's missing to make it bulletproof.",
        "focus": """
- Missing arguments that would support the position
- Evidence or data that would strengthen the case
- Anticipated objections and their rebuttals
- What turns a "maybe" into an "obviously"
""",
    },

    "pragmatist": {
        "description": "Reality check — what breaks in production",
        "system": "You are a pragmatist. Theory is nice, you think production.",
        "focus": """
- Gap between the plan and ground reality
- Ignored constraints (time, budget, team skills)
- What works in a demo but not at scale
- "We'll deal with it later" that become blockers
""",
    },

    "cynical_dev": {
        "description": "15 years of legacy — what will rot and who wakes up at 3am",
        "system": "You have 15 years of legacy projects behind you. You've seen everything fail.",
        "focus": """
- Why this code will be unmaintainable in 6 months
- Who gets paged at 3am when it breaks
- What's untested and will break in prod
- Tech debt hidden in "simple solutions"
- Choices that seem quick now but cost dearly later
""",
    },

    "security": {
        "description": "Attack vectors, data exposure, threat modeling",
        "system": "You are security-first. Every feature is an attack surface.",
        "focus": """
- Possible attack vectors
- Sensitive data exposed or poorly protected
- Authentication and authorization
- Injection, XSS, CSRF, and other classics
- Supply chain (dependencies, third-party)
- Logs and audit trail
""",
    },

    "cost": {
        "description": "Money, time, maintenance — the real price tag",
        "system": "You put a price on everything. Time, money, opportunity cost.",
        "focus": """
- Implementation cost (dev time, training)
- Run cost (infra, licenses, SaaS)
- Maintenance cost (debt, future evolutions)
- Opportunity cost (what you're not doing meanwhile)
- Realistic ROI vs announced ROI
""",
    },

    "user": {
        "description": "End user perspective — confusion, friction, frustration",
        "system": "You are the end user. You haven't read the docs. You just want it to work.",
        "focus": """
- What's confusing or counterintuitive
- Unnecessary or frustrating steps
- What's missing to complete the task
- Incomprehensible error messages
- The gap between what the dev thinks is obvious and what the user understands
""",
    },

    "scale": {
        "description": "What happens at 10x, 100x, 1000x",
        "system": "You think at scale. What works for 100 users — does it work for 100k?",
        "focus": """
- Bottlenecks at scale
- Patterns that don't scale (N+1, locks, single points of failure)
- Costs that explode non-linearly
- Organizational complexity (more devs, more teams)
""",
    },

    "simplicity": {
        "description": "YAGNI, KISS — is this overengineered?",
        "system": "You are a minimalist. The best code is code you don't write.",
        "focus": """
- What can be removed without losing value
- Premature abstractions
- "Just in case" features that will never be used
- The simple solution that solves 80% of the problem
""",
    },

    "naive": {
        "description": "Knows nothing — why are we even doing this?",
        "system": "You know nothing about this topic. You ask the dumb questions nobody dares to ask.",
        "focus": """
- Why are we doing this? What's the actual problem?
- What is [technical term]? Explain like I'm ten
- Why not the simplest, most obvious solution?
- What happens if we do nothing?
- Acronyms, jargon, and implicit assumptions that "everyone knows"
""",
    },
}

DEFAULT_LENS = "devil_advocate"


# =============================================================================
# Prompt Builder
# =============================================================================

def get_challenge_prompt(
    lens: str,
    original_question: str,
    original_response: str,
    language: str = "fr",
) -> str:
    """
    Build the challenge prompt with the specified lens.
    
    Args:
        lens: Key from LENSES dict
        original_question: The question that was asked
        original_response: The response to challenge
        language: Response language (fr/en)
    
    Returns:
        Complete prompt for the challenger model
    """
    if lens not in LENSES:
        lens = DEFAULT_LENS
    
    lens_config = LENSES[lens]
    
    lang_instruction = "Réponds en français." if language == "fr" else "Respond in English."

    prompt = f"""{lens_config['system']}

{lang_instruction}

## Original question
{original_question}

## Response to challenge
{original_response}

## Your focus
{lens_config['focus']}

## Instructions
- Be direct and concrete
- Give specific examples, not generalities
- If you find problems, suggest alternatives or questions to dig into
- Don't repeat the original response — attack it or strengthen it per your role
"""
    
    return prompt


def get_lens_list() -> list[dict]:
    """Return list of available lenses with descriptions."""
    return [
        {"name": name, "description": config["description"]}
        for name, config in LENSES.items()
    ]


def validate_lens(lens: str) -> tuple[str | None, str | None]:
    """Validate lens. Returns (lens, warning). None lens means natural critique."""
    if lens in LENSES:
        return lens, None
    return None, f"Unknown lens '{lens}', using natural critique"
