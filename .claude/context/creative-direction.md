# Creative Direction — Sparring

> Document de référence pour l'identité conceptuelle du projet.  
> Maintenu par : Creative Director  
> Créé : 2025-01 | Dernière révision : 2025-01-29

---

## Essence

**3 mots** : Friction productive intentionnelle

**1 phrase** : Un orchestrateur qui fait délibérément s'affronter les LLMs pour extraire des insights qu'aucun n'aurait produit seul.

**Tagline** : "Make your LLMs disagree"

---

## Intention

### Le problème

Les LLMs sont des "yes-men" par défaut. Un modèle seul a des angles morts : il confirme nos biais, rate des perspectives, tourne en boucle dans son raisonnement.

### Notre position

**Le désaccord est une feature, pas un bug.**

Quand on confronte plusieurs modèles sur la même question, quand on les fait se challenger mutuellement, on obtient une vue plus complète, nuancée et robuste.

Sparring n'orchestre pas des LLMs pour qu'ils convergent.  
Il les orchestre pour qu'ils **divergent utilement**.

---

## Ce que Sparring n'est PAS

**Sparring n'est pas un "conseil".**

Un conseil évoque des sages qui délibèrent calmement pour atteindre un consensus. C'est statique, hiérarchique, formel.

Sparring est l'inverse :
- Pas de consensus mou — on cultive le désaccord productif
- Pas de hiérarchie — ce sont des pairs qui s'entraînent ensemble
- Pas de formalisme — c'est un atelier, pas une assemblée

**Sparring n'est pas :**
- Un ring de boxe (pas de vainqueur/perdant)
- Un débat politique (pas de position à défendre)
- Une dispute (pas d'égo, pas d'émotion)
- Un oracle (pas de réponse définitive)

---

## Nom : Sparring

### La métaphore

Le sparring en boxe, c'est l'entraînement entre partenaires. On n'essaie pas de se blesser. On essaie de progresser ensemble, en ne se ménageant pas.

Un partenaire de sparring n'est pas un adversaire. C'est un allié qui te rend meilleur en te challengeant vraiment.

### Pourquoi ce nom

| Critère | Évaluation |
|---------|------------|
| **Métaphore** | Combat d'entraînement — friction sans hostilité |
| **Double sens** | Confrontation + Partnership |
| **Accessibilité** | Universel, pas besoin de refs philosophiques |
| **Unicité** | Peu utilisé dans l'écosystème MCP/LLM |
| **Sonorité** | Court, percutant, le double "r" ajoute de l'énergie |

### Alternatives écartées

| Nom | Pourquoi écarté |
|-----|-----------------|
| **Council / Quorum** | Évoque le consensus, pas la friction |
| **Agora** | Trop utilisé, connotation "place publique harmonieuse" |
| **Chorus** | Implique l'unisson, l'opposé de ce qu'on veut |
| **Dialectic** | Académique, froid, imprononçable pour certains |
| **Crucible** | Bonne énergie mais trop "alchimique", moins accessible |
| **Elenchus** | Précis (méthode socratique) mais obscur |

---

## Principes directeurs

Ces principes guident toutes les décisions — créatives, techniques, produit.

### 1. La friction productive est le produit

La primitive de base s'appelle `challenge()`, pas `agree()`. Le désaccord est une feature, pas un bug.

→ *Implication :* Ne jamais "résoudre" le désaccord automatiquement. Le présenter.

### 2. Relation de pairs

Les LLMs ne sont pas des oracles infaillibles à consulter. Ce sont des collègues avec des perspectives différentes. On les interroge, on les confronte, on synthétise.

→ *Implication :* Pas de hiérarchie entre modèles. Pas de "modèle principal".

### 3. Éclairer, pas décider

Sparring ne donne pas LA réponse. Il illumine un sujet sous plusieurs angles pour que l'humain puisse décider en connaissance de cause.

→ *Implication :* Output = positions divergentes + tensions identifiées. Pas de "synthèse finale" qui tranche.

### 4. Discipline budgétaire

Interroger plusieurs LLMs coûte de l'argent. Le budget tracking est intégré dès le départ — pas comme une contrainte, mais comme une discipline qui force à poser les bonnes questions.

→ *Implication :* Toujours afficher le coût. Permettre de fixer des limites.

---

## Tone of Voice

### On est
- **Direct** : Pas de hedging, pas de "il semblerait que"
- **Énergique** : Verbes d'action, phrases courtes
- **Technique sans jargon** : Précis mais accessible
- **Confiant** : On sait ce qu'on fait et pourquoi
- **Honnête** : On ne survend pas

### On n'est pas
- Agressif ou arrogant
- Académique ou pompeux
- Cute ou fantaisiste
- Corporate ou lisse
- Apologétique

### Exemples

| ❌ Non | ✅ Oui |
|--------|--------|
| "Sparring permet potentiellement d'améliorer la qualité des outputs" | "Sparring fait s'affronter vos LLMs. Les idées faibles ne survivent pas." |
| "Une solution innovante d'orchestration multi-modèles" | "Vos modèles sont trop polis. On règle ça." |
| "N'hésitez pas à essayer notre outil" | "Installez. Lancez un débat. Voyez ce qui casse." |

### Taglines alternatives (validées)

- "Make your LLMs disagree" ← **Principal**
- "Productive friction for AI"
- "Where models clash, insights emerge"

### Taglines rejetées

- "AI debate platform" → trop littéral, pas d'énergie
- "Multi-LLM orchestration" → technique, oubliable
- "Better thinking through disagreement" → trop soft

---

## Nomenclature

Termes à utiliser de façon cohérente :

| Concept | Terme | Note |
|---------|-------|------|
| Une confrontation complète | **Session** | Pas "debate", pas "conversation" |
| Un échange modèle→modèle | **Round** | Évoque le sparring |
| Faire réagir un modèle à un autre | **Challenge** | La primitive de base |
| Le résultat d'une session | **Map** | "Carte des positions", pas "conclusion" |
| Les modèles participants | **Sparring partners** | Pas "agents", pas "oracles" |

---

## Public cible

Développeurs et créatifs utilisant Claude Code qui veulent :
- Tester une idée contre plusieurs perspectives
- Identifier les failles d'un raisonnement
- Explorer un sujet complexe sans s'enfermer dans une seule vision
- Avoir des "collègues IA" qui ne disent pas toujours oui

**Pas pour :**
- Utilisateurs cherchant LA bonne réponse
- Cas d'usage nécessitant un consensus
- Personnes allergiques à la contradiction

---

## Ce document fait autorité sur

- Le nom et son usage
- La tagline et le messaging
- Le tone of voice
- Les principes directeurs
- La nomenclature

Toute déviation doit être validée par une mise à jour de ce document.

---

## Backlog créatif

- [ ] Identité visuelle (couleurs, picto si pertinent pour CLI)
- [ ] Format de sortie des "maps" — comment visualiser les positions ?
- [ ] Exemples/démos : quels cas d'usage mettre en avant en premier ?
- [ ] Onboarding : premier message quand on lance Sparring ?

---

## Documents liés

- `INTENT.md` — Manifeste public (repo root)
- `README.md` — Documentation technique
