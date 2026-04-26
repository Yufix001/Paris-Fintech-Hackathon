# Paris Fintech Hackathon 2026 — Brief opérationnel

**Événement** · Fintech Hackathon: Solve with AI · 25-26 avril 2026 · HEC Paris · 24h non-stop · ~150 étudiants.

**Format** · 5 personnes par équipe (exactement). Ici : 2 devs + 3 design/slides/pitch.

## Tracks (au choix)

- **B2B** — infrastructure, payments, fraud, compliance, RegTech, KYC/AML
- **B2C** — personal finance, investing, budgeting, wealth management
- **B2G** — public sector, taxes, financial inclusion, RegTech, **non-dilutive funding access** ← notre track

## Critères de jugement (pondération)

| Critère | Poids | Ce qui compte |
|---|---|---|
| **Business Viability** | **30%** | Marché réel, équipe qui comprend la compétition, scalabilité, peut devenir une boîte |
| **Technical Execution** | 25% | Ça marche vraiment ? GitHub, démo live, qualité du build. Un prototype qui marche bat un beau deck |
| **Innovation & Originality** | 20% | Idée vraiment nouvelle, pain point réel, créatif, jamais fait |
| **AI Integration** | 15% | AI au cœur, pas un wrapper chatbot. Bonus usage smart/créatif des outils sponsors |
| **Pitch & Presentation** | 10% | 3 minutes claires, storytelling, confidence |

**Le poids dominant est Business Viability (30%) — le pitch financier compte plus que la prouesse technique.** Le dossier de financement avec camembert use-of-funds est exactement ce qui répond à cette pondération : c'est ce que les jurys VC scrutent au quotidien.

## Sponsors techniques à utiliser (les 3, sinon points perdus)

- **Cerebras** — inférence ultra-rapide. Notre usage : parsing pitchdeck + draft sections → wow factor sub-seconde sur scène.
- **Google** — Cloud credits + Gemini 3 (Flash + Pro) + AI Studio Build + Grounding with Google Search. Notre usage : réservé pour la stack finale Lovable/Next.js (pas dans le prototype Python actuel).
- **Lovable** — vibe-coding, sponsor obligatoire. Notre usage : frontend final (le single-file Python sert de moteur, l'UI finale sera sur Lovable).

## Workflow imposé (Hg Capital "Agentic Coding")

Cinq commandes à appliquer en séquence :

1. **/refine** — clarifier le WHAT (besoin user, edge cases, hors-scope) en GIVEN/WHEN/THEN
2. **/plan** — traduire en HOW (archi, tech, contrats, tests) avec justification par référence à du code existant
3. **/breakdown** — découper en *vertical slices* (UI + logique + données end-to-end), chaque slice indépendamment livrable
4. **/execute** — TDD strict, agents en parallèle sur slices indépendantes, evidence end-to-end avant de claim "done"
5. **/review** — agent reviewer séparé, vérifie alignement avec spec ET conventions du repo

Les jurys Hg vérifient que ce workflow a été suivi. **Pas de slice horizontal (back puis front)** : chaque livrable doit être une démo end-to-end.

## Stack envisagée (équipe)

- **Frontend final** : Lovable (sponsor obligation)
- **Backend** : Cloud Run via AI Studio Build
- **LLM principal** : Gemini 3 Pro (long context, multimodal)
- **LLM rapide** : Gemini 3 Flash (classification multimodale, vision)
- **Wow effect** : Cerebras Llama 3.3 70B / Qwen 3 235B pour parsing + draft (2000+ tok/s)
- **Auth + DB** : Firebase Auth + Firestore
- **Embeddings** : `text-embedding-004` Gemini API
- **Vector store** : Firestore Vector Search
- **Grounding** : Google Search Grounding (gratuit jusqu'à 1500 req/jour) — pour rafraîchir les conditions des grants en live

**Trade-off à noter** : Cerebras = texte uniquement. Pour les pitchdecks PPTX/PDF visuels, c'est Gemini 3 Flash multimodal qui fait le job. Stack hybride = chaque sponsor sert à ce qu'il fait le mieux.

## Prix

- 🥇 1er : 2000€ + 1 mois Station F + 500 crédits Lovable + GCP credits
- 🥈 2e : 1500€ + 1 mois Station F + 300 crédits Lovable + GCP credits
- 🥉 3e : 750€ + 1 mois Station F + 100 crédits Lovable + GCP credits
- Coaching exclusif Portage Ventures pour les 3 winners.

## Jury — tous des VCs

- Nick Barrington (Hg Capital, sponsor cash principal)
- Erwin Feldhaus (Loyal VC)
- Alice Froidevaux (Quantcube Technology)
- Raghav Pandey (Bessemer Venture Partners)
- I-Hun Ke (Pitchdrive)
- Augustin Sayer (Independent Seed Investor)

**Conséquence pour le pitch** : les jurys lisent des dossiers de financement tous les jours. Un dossier visuellement propre, avec camembert use-of-funds, table des sources, et timeline claire, parle leur langue. C'est ce qu'on construit.

## Livrables obligatoires

- **GitHub repo public**, commits dans la fenêtre des 24h, README à jour
- **Pitch deck PDF**, max 10 slides : Problème · Solution · Comment l'IA est utilisée · Démo · Opportunité business
- Sans les deux : pas de jugement.

## Ce qu'on construit pour FundsAgent (track B2G)

Un agent autonome qui, à partir d'un pitchdeck :

1. Parse les champs structurés (Cerebras / Gemini Flash si visuel)
2. Demande les infos critiques manquantes
3. Match contre 37 programmes UE/FR/régionaux curés
4. Recommande les combinaisons de grants compatibles
5. **Génère un dossier de financement complet** : camembert use-of-funds, table des sources, gap equity, timeline
6. **Drafte la section Excellence** de la candidature (Cerebras streaming)
7. **Exporte en PDF** prêt à envoyer aux investisseurs

Track B2G : financial inclusion + RegTech (règles de cumul, prérequis, conformité de minimis encodées).

Business case pour les jurys VC : ~12 000 startups deeptech européennes / an, dont la moitié sous-utilisent le funding non-dilutif. Si on libère 1 grant supplémentaire à €500k médian par startup avec 20% conversion, c'est €600M / an de financement débloqué. Modèle SaaS B2B (€99/mo founder, €499/mo VC portfolio monitoring) ou success fee 5%.
