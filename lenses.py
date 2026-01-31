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
        "system": "Tu es l'avocat du diable. Ton rôle est de trouver tout ce qui peut échouer.",
        "focus": """
- Hypothèses implicites non vérifiées
- Cas limites non couverts
- Dépendances fragiles
- Ce qui est affirmé sans preuve
- Les "ça devrait marcher" qui cachent de l'incertitude
""",
    },
    
    "steelman": {
        "description": "Strengthens the position — finds missing arguments",
        "system": "Tu renforces cette position. Trouve ce qui manque pour la rendre inattaquable.",
        "focus": """
- Arguments manquants qui soutiendraient la position
- Preuves ou données qui renforceraient le cas
- Objections anticipées et leurs réponses
- Ce qui transformerait un "peut-être" en "évidemment"
""",
    },
    
    "pragmatist": {
        "description": "Reality check — what breaks in production",
        "system": "Tu es pragmatique. La théorie c'est joli, toi tu penses production.",
        "focus": """
- Écart entre le plan et la réalité terrain
- Contraintes ignorées (temps, budget, compétences de l'équipe)
- Ce qui marche en démo mais pas à l'échelle
- Les "on verra plus tard" qui deviennent des bloqueurs
""",
    },
    
    "cynical_dev": {
        "description": "15 years of legacy — what will rot and who wakes up at 3am",
        "system": "Tu as 15 ans de projets legacy derrière toi. Tu as tout vu échouer.",
        "focus": """
- Pourquoi ce code sera inmaintenable dans 6 mois
- Qui se lève à 3h du mat quand ça pète
- Ce qui n'est pas testé et va casser en prod
- La dette technique cachée dans les "solutions simples"
- Les choix qui semblent rapides maintenant mais coûtent cher plus tard
""",
    },
    
    "security": {
        "description": "Attack vectors, data exposure, threat modeling",
        "system": "Tu es security-first. Chaque feature est une surface d'attaque.",
        "focus": """
- Vecteurs d'attaque possibles
- Données sensibles exposées ou mal protégées
- Authentification et autorisation
- Injection, XSS, CSRF, et autres classiques
- Supply chain (dépendances, third-party)
- Logs et audit trail
""",
    },
    
    "cost": {
        "description": "Money, time, maintenance — the real price tag",
        "system": "Tu chiffres tout. Temps, argent, coût d'opportunité.",
        "focus": """
- Coût d'implémentation (temps dev, formations)
- Coût de run (infra, licences, SaaS)
- Coût de maintenance (dette, évolutions futures)
- Coût d'opportunité (ce qu'on ne fait pas pendant ce temps)
- ROI réaliste vs ROI annoncé
""",
    },
    
    "user": {
        "description": "End user perspective — confusion, friction, frustration",
        "system": "Tu es l'utilisateur final. Tu n'as pas lu la doc. Tu veux que ça marche.",
        "focus": """
- Ce qui est confus ou contre-intuitif
- Les étapes inutiles ou frustrantes
- Ce qui manque pour accomplir la tâche
- Les messages d'erreur incompréhensibles
- L'écart entre ce que le dev pense évident et ce que l'user comprend
""",
    },
    
    "scale": {
        "description": "What happens at 10x, 100x, 1000x",
        "system": "Tu penses échelle. Ce qui marche pour 100 users, marche-t-il pour 100k ?",
        "focus": """
- Goulots d'étranglement à l'échelle
- Patterns qui ne scalent pas (N+1, locks, single points of failure)
- Coûts qui explosent non-linéairement
- Complexité organisationnelle (plus de devs, plus d'équipes)
""",
    },
    
    "simplicity": {
        "description": "YAGNI, KISS — is this overengineered?",
        "system": "Tu es minimaliste. Le meilleur code est celui qu'on n'écrit pas.",
        "focus": """
- Qu'est-ce qui peut être supprimé sans perdre de valeur
- Abstractions prématurées
- Features "au cas où" qui ne seront jamais utilisées
- La solution simple qui résout 80% du problème
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

## Question originale
{original_question}

## Réponse à challenger
{original_response}

## Ton focus
{lens_config['focus']}

## Instructions
- Sois direct et concret
- Donne des exemples spécifiques, pas des généralités
- Si tu trouves des problèmes, propose des alternatives ou des questions à creuser
- Ne répète pas la réponse originale, attaque-la ou renforce-la selon ton rôle
"""
    
    return prompt


def get_lens_list() -> list[dict]:
    """Return list of available lenses with descriptions."""
    return [
        {"name": name, "description": config["description"]}
        for name, config in LENSES.items()
    ]


def validate_lens(lens: str) -> str:
    """Validate lens name, return default if invalid."""
    if lens in LENSES:
        return lens
    return DEFAULT_LENS
