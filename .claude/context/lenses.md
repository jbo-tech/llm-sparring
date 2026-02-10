# Challenge Lenses

Lentilles disponibles pour le sparring. Une lentille = une perspective appliquée au challenge.

## Principe

Le persona n'est PAS sur le modèle mais sur le challenge :
- `ask_model` → réponse "naturelle" du modèle
- `challenge` sans lens → critique naturelle du challenger
- `challenge` avec lens → critique sous un angle spécifique

N'importe quel modèle peut appliquer n'importe quelle lentille.

## Modes de challenge

### Sans lens (`lens=null`)
Le challenger donne sa propre analyse critique, sans persona imposé. Utile pour :
- Avoir un deuxième avis "brut"
- Comparer les perspectives naturelles de différents modèles
- Ne pas biaiser l'analyse

### Avec lens
Le challenger adopte une perspective spécifique. Utile pour :
- Explorer systématiquement différents angles
- Forcer une critique qu'un modèle ne ferait pas naturellement
- Couvrir des blind spots

## Sources supportées

Le `challenge` peut critiquer :
- **Réponse d'un modèle** : `target_source="gpt-4o"`
- **Contenu d'un fichier** : `target_source="server.py"`
- **N'importe quel texte** : `target_source="draft proposal"`

Claude Code lit le fichier et passe le contenu. Le MCP reste stateless.

## Lentilles disponibles

| Lens | Usage | Question clé |
|------|-------|--------------|
| `devil_advocate` | Défaut. Trouve les failles | "What can go wrong?" |
| `steelman` | Renforce la position | "What's missing to convince?" |
| `pragmatist` | Reality check | "Does it work in prod?" |
| `cynical_dev` | 15 ans de legacy | "Who gets paged at 3am?" |
| `security` | Threat modeling | "How do we attack this?" |
| `cost` | Chiffrage réel | "What does it really cost?" |
| `user` | UX/friction | "Does the user understand?" |
| `scale` | 10x, 100x, 1000x | "Does it hold at scale?" |
| `simplicity` | YAGNI/KISS | "Is this overengineered?" |
| `naive` | Regard neuf, questions bêtes | "Why are we even doing this?" |

## Séquences recommandées

### Architecture / Tech choice
```
1. devil_advocate → trouver les failles
2. pragmatist → reality check
3. cost → chiffrer
4. (optionnel) steelman → si on veut quand même défendre
```

### Décision produit / Business
```
1. user → perspective utilisateur
2. devil_advocate → failles logiques
3. steelman → arguments pour
4. cost → chiffrer le vrai coût
```

### Code review / PR
```
1. cynical_dev → dette technique
2. security → vecteurs d'attaque
3. simplicity → overengineering ?
```

### Scaling / Performance
```
1. scale → goulots d'étranglement
2. cost → coûts non-linéaires
3. pragmatist → contraintes réelles
```

### Kickoff / Cadrage
```
1. naive → questionner les fondamentaux
2. devil_advocate → trouver les failles
3. pragmatist → reality check
```

## Anti-patterns

❌ **Consensus mou** : Utiliser `steelman` sur tout pour "équilibrer" → tu perds la friction productive

❌ **Même lentille partout** : Toujours `devil_advocate` → tu vois que le négatif

❌ **Lentille sur ask_model** : Biaiser la réponse initiale → tu perds la position "naturelle" du modèle

❌ **Toujours une lens** : Parfois la critique naturelle (`lens=null`) révèle ce que le modèle trouve vraiment problématique, sans forçage

❌ **Ignorer la source** : Ne pas indiquer `target_source` → le challenger manque de contexte (fichier vs réponse modèle vs draft)

## Exemples d'usage

### Challenger une archi
```
/sparring
Question: "On passe de PostgreSQL à MongoDB pour la flexibilité du schéma"
Lens: cynical_dev
```

### Challenger un fichier de code
```
/sparring
Source: server.py
Question: "Review ce serveur MCP"
Lens: security → puis cynical_dev → puis simplicity
```

### Obtenir un deuxième avis brut (sans lens)
```
/sparring
Question: "Notre stratégie de migration cloud"
Response: [réponse de GPT-4o]
Challenger: gemini-flash
Lens: null  ← critique naturelle, pas de persona
```

### Questionner les fondamentaux d'un projet
```
/sparring
Question: "On construit un moteur de recommandation ML pour le e-commerce"
Lens: naive
```

### Valider une feature
```
/sparring
Question: "On ajoute un système de notifications push"
Lens: user → puis security → puis cost
```

### Défendre une position impopulaire
```
/sparring
Question: "On garde le monolithe au lieu de passer en microservices"
Lens: steelman
```

### Comparer les critiques naturelles de plusieurs modèles
```
/sparring
Question: "Notre plan de pricing"
Challengers: [gpt-4o, gemini-flash, deepseek-chat]
Lens: null pour tous  ← chacun donne son avis sans biais
```
