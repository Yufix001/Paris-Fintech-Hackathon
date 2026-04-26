"""
FundsAgent — Single-file agentic webapp for European non-dilutive funding
==========================================================================

Paris Fintech Hackathon 2026 (Google Cloud / Cerebras / Lovable) — Track B2G.

Pitch
-----
European startups leave billions in non-dilutive funding on the table because
discovery is painful. FundsAgent is an autonomous AI agent that reads a
pitchdeck, identifies the 37+ public grants that match, asks for missing
information when uncertain, recommends compatible combinations, builds a
VC-grade financing dossier with use-of-funds breakdown, and drafts the
Excellence section of the application — all in seconds.

Why fintech? B2G — public sector funding access, RegTech for cumulability
rules, financial inclusion of underserved deeptech founders.

Sponsor integrations
--------------------
- **Cerebras**: instant pitchdeck parsing, financing-plan synthesis, and
  application drafting (Qwen 3 235B / Llama at 2000+ tok/s). The speed is
  the wow factor — sub-second every step.
- **Google Cloud**: deploy on Cloud Run (one Dockerfile). Gemini API as a
  multimodal fallback (PPTX/PDF visual parsing — Cerebras is text-only).
  BigQuery for the grants warehouse in production. Grounding with Google
  Search to refresh grant conditions live.
- **Lovable**: this Python file is the engine — the production frontend is
  built in Lovable consuming `/api/agent/run` (SSE) and `/dossier`.

Run
---
    pip install fastapi uvicorn httpx
    export CEREBRAS_API_KEY=csk-xxx          # optional, falls back to heuristic
    python fundsagent.py
    # → http://localhost:8000

Deploy on Cloud Run
-------------------
    gcloud run deploy fundsagent --source . --region europe-west1 \\
      --set-env-vars CEREBRAS_API_KEY=$CEREBRAS_API_KEY

Architecture
------------
    [Browser]  ──POST /agent/run──▶  [FastAPI]
        ▲                                │
        │                                ▼
        │         ┌──────────────────────┐
        │         │   GrantAgent (loop)  │
        │         │                      │
        │         │  1. parse pitchdeck  │ ───▶ Cerebras
        │         │  2. clarify missing  │ ───▶ asks user via SSE
        │         │  3. match 37 grants  │ ───▶ in-process scoring
        │         │  4. recommend combos │
        │         │  5. financing plan   │ ───▶ Cerebras (use-of-funds)
        │         │  6. draft Excellence │ ───▶ Cerebras
        │         │  7. dossier link     │ ───▶ /dossier (PDF-printable)
        │         └──────────────────────┘
        │                                │
        └─── SSE stream of agent steps ──┘

The browser sees the agent's reasoning live: "thinking", "asking",
"matching", "drafting" — the agentic UX.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import sys
import textwrap
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, AsyncGenerator

# -----------------------------------------------------------------------------
# Lazy optional deps
# -----------------------------------------------------------------------------

try:
    import httpx  # noqa
except ImportError:
    httpx = None

try:
    from fastapi import FastAPI, HTTPException, Request, UploadFile, File
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

try:
    # Prefer the modern `pypdf` package (PyPDF2 was renamed in 2023). Fall
    # back to PyPDF2 if only the legacy package is on the host.
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader  # type: ignore[no-redef]
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

try:
    from pptx import Presentation
    HAS_PPTX = True
except ImportError:
    HAS_PPTX = False

try:
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY", "csk-dkmj35c29wr4kvetnwrfer9ck838fexcty4rptvjfxy5txh4")
# Cerebras catalogue (Apr 2026): qwen-3-235b-a22b-instruct-2507, gpt-oss-120b,
# llama3.1-8b, zai-glm-4.7. Qwen 235B is the default — best quality/latency
# trade-off for structured JSON extraction at Cerebras speeds.
CEREBRAS_MODEL = os.environ.get("CEREBRAS_MODEL", "qwen-3-235b-a22b-instruct-2507")
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyAykfjWtlAkiXEzarvauJ2kmEi5_Hc9qXQ")

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

EU27 = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE",
}
EUREKA_COUNTRIES = EU27 | {"NO", "CH", "IS", "TR", "IL", "UK", "ZA", "KR", "CA"}

SECTOR_FUZZY = {
    "green_deal": {"clean_energy", "climate_tech", "circular_economy",
                   "advanced_materials", "mobility", "biodiversity"},
    "climate_neutral": {"clean_energy", "climate_tech", "energy_storage"},
    "fit_for_55": {"clean_energy", "climate_tech", "mobility", "energy_storage"},
    "digital": {"digital", "ai", "cybersecurity", "hpc", "semiconductors",
                "robotics", "photonics"},
    "strategic_autonomy": {"defence", "semiconductors", "ai", "cybersecurity",
                           "advanced_materials"},
    "deeptech": {"clean_energy", "biotech", "advanced_materials", "ai", "quantum",
                 "photonics", "semiconductors", "robotics", "space"},
    "health": {"health", "biotech", "medical_devices", "digital_health"},
    "circular_economy": {"circular_economy", "bioeconomy", "advanced_materials"},
    "biodiversity": {"biodiversity", "nature_conservation", "agritech"},
    "industrial_decarbonisation": {"clean_energy", "energy_storage",
                                    "carbon_capture", "low_carbon_industry"},
}


# -----------------------------------------------------------------------------
# Grant Eligibility Verification Protocol — Calibrated baselines (Rule 2)
# Baselines derived from public programme statistics. Fit score and probability
# are INDEPENDENT dimensions — do not inflate probability from sector fit alone.
# Format: grant_id -> (baseline_low_pct, baseline_high_pct)
# The agent uses the midpoint then applies adjustment factors.
# -----------------------------------------------------------------------------

CALIBRATED_BASELINES: dict[str, tuple[float, float]] = {
    "bpifrance_adi":                (35.0, 50.0),   # +10% if revenue>0, +5% if TRL>=5
    "france2030_inov":              (20.0, 35.0),   # competitive waves, sector dependent
    "france2030_ilab":              (15.0, 25.0),   # 1 wave/year, highly competitive
    "france2030_idemo":             (18.0, 30.0),   # industrial scale
    "eic_accelerator":              (5.0, 8.0),     # overall; short proposal ~15-20%
    "eic_pathfinder_open":          (8.0, 12.0),    # consortium required
    "eic_pathfinder_challenges":    (11.0, 15.0),   # thematic, slightly higher
    "eic_transition":               (10.0, 15.0),   # prior Pathfinder/ERC required
    "erc_starting":                 (10.0, 15.0),   # single PI, extremely competitive
    "erc_poc":                      (31.0, 31.0),   # ONLY if PI has active ERC
    "horizon_cluster1_health":      (10.0, 15.0),   # consortium mandatory
    "horizon_cluster4_digital":     (10.0, 15.0),   # consortium mandatory
    "horizon_cluster5_climate":     (10.0, 15.0),   # consortium mandatory
    "horizon_cluster6_food":        (10.0, 15.0),   # consortium mandatory
    "eurostars3":                   (20.0, 30.0),   # if consortium confirmed
    "ademe_perfecto":               (25.0, 40.0),   # only if ecodesign is core
    "ademe_demonstrateurs":         (20.0, 30.0),   # ADEME industrial demonstrators
    "bpifrance_concours_innovation":(25.0, 35.0),   # thematic waves
    "digital_europe":               (20.0, 30.0),   # deployment-focused
    "innovation_fund_small":        (15.0, 22.0),   # GHG-focused
    "innovation_fund_large":        (10.0, 16.0),   # very large scale
}

# Map blocker/warning types to concrete next-action advice for the founder
NEXT_ACTION_MAP: dict[str, str] = {
    "erc_prerequisite": "Verify that your PI holds an active or recently ended (post 01/2025) ERC grant before preparing this submission.",
    "eic_prior_project": "Identify and document the link to a previously funded EIC Pathfinder, ERC, or equivalent project.",
    "consortium_required": "Identify at least 2 independent partners from 2 other EU/EEA countries to form a consortium.",
    "foreign_partner": "Identify an R&D partner in another Eureka member country.",
    "ecodesign_lca": "Document a formal Life Cycle Assessment (LCA) or ecodesign methodology — marketing claims are insufficient.",
    "country_region": "Register an EU entity or verify Horizon Europe association status for your country.",
    "trl": "Adjust your TRL level — each level unlocks or blocks different programmes.",
    "sme_required": "Verify your SME status (<250 employees, <50M€ turnover).",
    "sector_mismatch": "Expand your sector keywords to match programme priorities.",
    "project_scale": "This programme targets large-scale projects — confirm your project budget matches.",
    "deadline_urgent": "Submitting in <45 days requires a complete, submission-ready dossier NOW — not a draft.",
    "default": "Review the specific call conditions on the programme page.",
}


# -----------------------------------------------------------------------------
# Embedded grants DB (37 programmes — abbreviated for single-file build)
# In production this lives in BigQuery; for the demo we ship the JSON.
# -----------------------------------------------------------------------------

GRANTS_DB_JSON = r"""
{
  "_meta": {
    "version": "1.0",
    "combinability_matrix": {
      "incompatible_pairs": [
        ["feder_idf_innovation", "horizon_cluster5_climate"],
        ["feder_idf_innovation", "eic_accelerator"],
        ["feder_idf_innovation", "innovation_fund_small"]
      ],
      "synergistic_pairs": [
        ["bpifrance_adi", "horizon_cluster5_climate"],
        ["bpifrance_adi", "eic_accelerator"],
        ["france2030_inov", "feder_idf_innovation"],
        ["ademe_demonstrateurs", "horizon_cluster5_climate"],
        ["innovup_idf", "bpifrance_adi"]
      ]
    }
  },
  "grants": [
    {"id":"erc_starting","name":"ERC Starting Grant","programme":"Horizon Europe - Pillar I","level":"EU","url":"https://erc.europa.eu/apply-grant/starting-grant","eligibility":{"countries":["EU27","associated_countries"],"sectors":["fundamental_research","any"],"trl_min":1,"trl_max":3,"host_institution_required":true,"phd_age_min_years":2,"phd_age_max_years":7,"consortium":"single_pi"},"budget":{"grant_min_eur":1500000,"grant_max_eur":2000000,"co_financing_rate_pct":100,"typical_total_project_eur":1500000},"timing":{"duration_months_typical":60},"success_rate_pct":13.0,"evaluation":{"excellence_weight":1.0},"priorities":["fundamental_research","frontier_science"]},
    {"id":"erc_poc","name":"ERC Proof of Concept","programme":"Horizon Europe - Pillar I","level":"EU","url":"https://erc.europa.eu/apply-grant/proof-concept","eligibility":{"countries":["EU27","associated_countries"],"sectors":["any"],"trl_min":2,"trl_max":5,"prerequisite":"Lauréat ERC en cours","consortium":"single_pi"},"budget":{"grant_min_eur":150000,"grant_max_eur":150000,"co_financing_rate_pct":100,"typical_total_project_eur":150000},"timing":{"duration_months_typical":18},"success_rate_pct":35.0,"evaluation":{"innovation_potential_weight":0.50,"concrete_plan_weight":0.30,"team_weight":0.20},"priorities":["frontier_to_market","deeptech"]},
    {"id":"msca_pf","name":"MSCA Postdoctoral Fellowships","programme":"Horizon Europe - Pillar I","level":"EU","url":"https://marie-sklodowska-curie-actions.ec.europa.eu/actions/postdoctoral-fellowships","eligibility":{"countries":["EU27","associated_countries"],"sectors":["any"],"trl_min":1,"trl_max":4,"phd_required":true,"consortium":"single_researcher_with_host"},"budget":{"grant_min_eur":170000,"grant_max_eur":290000,"co_financing_rate_pct":100,"typical_total_project_eur":230000},"timing":{"duration_months_typical":24},"success_rate_pct":16.0,"evaluation":{"excellence_weight":0.50,"impact_weight":0.30,"implementation_weight":0.20},"priorities":["mobility","talent_attraction"]},
    {"id":"horizon_cluster1_health","name":"Horizon Europe Cluster 1 - Health","programme":"Horizon Europe - Pillar II","level":"EU","url":"https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe/cluster-1-health_en","eligibility":{"countries":["EU27","associated_countries"],"sectors":["health","biotech","medical_devices","ai","digital_health"],"trl_min":3,"trl_max":8,"consortium":"min_3_partners_3_countries"},"budget":{"grant_min_eur":3000000,"grant_max_eur":20000000,"co_financing_rate_pct":100,"typical_total_project_eur":7000000},"timing":{"duration_months_typical":48},"success_rate_pct":11.0,"evaluation":{"excellence_weight":0.33,"impact_weight":0.34,"implementation_weight":0.33},"priorities":["health","ageing_society","pandemics","personalised_medicine"]},
    {"id":"horizon_cluster4_digital","name":"Horizon Europe Cluster 4 - Digital, Industry & Space","programme":"Horizon Europe - Pillar II","level":"EU","url":"https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe/cluster-4-digital-industry-and-space_en","eligibility":{"countries":["EU27","associated_countries"],"sectors":["digital","ai","advanced_materials","manufacturing","space","robotics","photonics","semiconductors"],"trl_min":3,"trl_max":8,"consortium":"min_3_partners_3_countries"},"budget":{"grant_min_eur":4000000,"grant_max_eur":25000000,"co_financing_rate_pct":100,"typical_total_project_eur":8000000},"timing":{"duration_months_typical":42},"success_rate_pct":12.0,"evaluation":{"excellence_weight":0.33,"impact_weight":0.34,"implementation_weight":0.33},"priorities":["digital","strategic_autonomy","industrial_competitiveness","ai_made_in_europe"]},
    {"id":"horizon_cluster5_climate","name":"Horizon Europe Cluster 5 - Climate, Energy, Mobility","programme":"Horizon Europe - Pillar II","level":"EU","url":"https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe/cluster-5-climate-energy-and-mobility_en","eligibility":{"countries":["EU27","associated_countries"],"sectors":["clean_energy","climate_tech","mobility","advanced_materials","energy_storage"],"trl_min":3,"trl_max":8,"consortium":"min_3_partners_3_countries"},"budget":{"grant_min_eur":3000000,"grant_max_eur":15000000,"co_financing_rate_pct":100,"typical_total_project_eur":6000000},"timing":{"duration_months_typical":42},"success_rate_pct":13.0,"evaluation":{"excellence_weight":0.33,"impact_weight":0.34,"implementation_weight":0.33},"priorities":["green_deal","climate_neutral_2050","fit_for_55","clean_energy"]},
    {"id":"horizon_cluster6_food","name":"Horizon Europe Cluster 6 - Food, Bioeconomy","programme":"Horizon Europe - Pillar II","level":"EU","url":"https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe/cluster-6-food-bioeconomy-natural-resources-agriculture-and-environment_en","eligibility":{"countries":["EU27","associated_countries"],"sectors":["agritech","bioeconomy","circular_economy","food","water","biodiversity"],"trl_min":3,"trl_max":8,"consortium":"min_3_partners_3_countries"},"budget":{"grant_min_eur":2000000,"grant_max_eur":12000000,"co_financing_rate_pct":100,"typical_total_project_eur":5000000},"timing":{"duration_months_typical":42},"success_rate_pct":14.0,"evaluation":{"excellence_weight":0.33,"impact_weight":0.34,"implementation_weight":0.33},"priorities":["green_deal","farm_to_fork","biodiversity","circular_economy"]},
    {"id":"eic_accelerator","name":"EIC Accelerator","programme":"Horizon Europe - Pillar III","level":"EU","url":"https://eic.ec.europa.eu/eic-funding-opportunities/eic-accelerator_en","eligibility":{"countries":["EU27","associated_countries"],"sectors":["any"],"trl_min":5,"trl_max":8,"sme_required":true,"startup_friendly":true,"consortium":"single_company","dual_use_allowed":false},"budget":{"grant_min_eur":500000,"grant_max_eur":2500000,"equity_max_eur":15000000,"co_financing_rate_pct":70,"typical_total_project_eur":5000000},"timing":{"duration_months_typical":24,"two_stage":true},"success_rate_pct":4.5,"evaluation":{"excellence_weight":0.40,"impact_weight":0.40,"implementation_weight":0.20},"priorities":["green_deal","digital","strategic_autonomy","deeptech"]},
    {"id":"eic_pathfinder_open","name":"EIC Pathfinder Open","programme":"Horizon Europe - Pillar III","level":"EU","url":"https://eic.ec.europa.eu/eic-funding-opportunities/eic-pathfinder_en","eligibility":{"countries":["EU27","associated_countries"],"sectors":["any"],"trl_min":1,"trl_max":4,"consortium":"min_3_partners_3_countries","dual_use_allowed":false},"budget":{"grant_min_eur":2000000,"grant_max_eur":4000000,"co_financing_rate_pct":100,"typical_total_project_eur":3000000},"timing":{"duration_months_typical":36},"success_rate_pct":8.0,"evaluation":{"excellence_weight":0.50,"impact_weight":0.30,"implementation_weight":0.20},"priorities":["breakthrough_science","deeptech"]},
    {"id":"eic_pathfinder_challenges","name":"EIC Pathfinder Challenges","programme":"Horizon Europe - Pillar III","level":"EU","url":"https://eic.ec.europa.eu/eic-funding-opportunities/eic-pathfinder_en","eligibility":{"countries":["EU27","associated_countries"],"sectors":["any_thematic_challenge"],"trl_min":1,"trl_max":4,"consortium":"single_or_consortium_max_4"},"budget":{"grant_min_eur":3000000,"grant_max_eur":4000000,"co_financing_rate_pct":100,"typical_total_project_eur":3500000},"timing":{"duration_months_typical":36},"success_rate_pct":11.0,"evaluation":{"excellence_weight":0.45,"impact_weight":0.35,"implementation_weight":0.20},"priorities":["strategic_challenges","deeptech"]},
    {"id":"eic_transition","name":"EIC Transition","programme":"Horizon Europe - Pillar III","level":"EU","url":"https://eic.ec.europa.eu/eic-funding-opportunities/eic-transition_en","eligibility":{"countries":["EU27","associated_countries"],"sectors":["any"],"trl_min":4,"trl_max":6,"consortium":"single_or_small_consortium_max_5","prerequisite":"résultats issus de Pathfinder, ERC PoC, ou équivalent"},"budget":{"grant_min_eur":1000000,"grant_max_eur":2500000,"co_financing_rate_pct":100,"typical_total_project_eur":2500000},"timing":{"duration_months_typical":24},"success_rate_pct":12.0,"evaluation":{"excellence_weight":0.33,"impact_weight":0.34,"implementation_weight":0.33},"priorities":["deeptech","translation_research"]},
    {"id":"eit_climate_kic","name":"EIT Climate-KIC","programme":"EIT (Pillar III)","level":"EU","url":"https://www.climate-kic.org/","eligibility":{"countries":["EU27","associated_countries"],"sectors":["climate_tech","clean_energy","circular_economy","sustainable_cities"],"trl_min":4,"trl_max":8,"consortium":"single_or_partnership"},"budget":{"grant_min_eur":50000,"grant_max_eur":1500000,"co_financing_rate_pct":70,"typical_total_project_eur":800000},"timing":{"duration_months_typical":18},"success_rate_pct":20.0,"evaluation":{"climate_impact_weight":0.40,"team_weight":0.25,"market_weight":0.35},"priorities":["climate_neutral","kic_ecosystem"]},
    {"id":"eit_health","name":"EIT Health","programme":"EIT (Pillar III)","level":"EU","url":"https://eithealth.eu/","eligibility":{"countries":["EU27","associated_countries"],"sectors":["health","medical_devices","digital_health","biotech"],"trl_min":4,"trl_max":8,"consortium":"consortium_typical_3_partners"},"budget":{"grant_min_eur":100000,"grant_max_eur":2000000,"co_financing_rate_pct":70,"typical_total_project_eur":1200000},"timing":{"duration_months_typical":18},"success_rate_pct":18.0,"evaluation":{"health_impact_weight":0.40,"team_weight":0.25,"commercialisation_weight":0.35},"priorities":["healthy_living","ageing","kic_ecosystem"]},
    {"id":"innovation_fund_small","name":"EU Innovation Fund - Small Scale","programme":"EU ETS Innovation Fund","level":"EU","url":"https://cinea.ec.europa.eu/programmes/innovation-fund_en","eligibility":{"countries":["EU27","EEA","associated_countries"],"sectors":["clean_energy","energy_storage","carbon_capture","low_carbon_industry"],"trl_min":7,"trl_max":9,"consortium":"single_or_consortium","min_capex_eur":2500000,"max_capex_eur":7500000},"budget":{"grant_min_eur":500000,"grant_max_eur":4500000,"co_financing_rate_pct":60,"typical_total_project_eur":5000000},"timing":{"duration_months_typical":36},"success_rate_pct":18.0,"evaluation":{"ghg_avoidance_weight":0.30,"innovation_weight":0.25,"maturity_weight":0.20,"scalability_weight":0.15,"cost_efficiency_weight":0.10},"priorities":["green_deal","fit_for_55","deployment"]},
    {"id":"innovation_fund_large","name":"EU Innovation Fund - Large Scale","programme":"EU ETS Innovation Fund","level":"EU","url":"https://cinea.ec.europa.eu/programmes/innovation-fund_en","eligibility":{"countries":["EU27","EEA","associated_countries"],"sectors":["clean_energy","energy_storage","carbon_capture","low_carbon_industry","renewable_h2"],"trl_min":8,"trl_max":9,"consortium":"single_or_consortium","min_capex_eur":20000000},"budget":{"grant_min_eur":7500000,"grant_max_eur":200000000,"co_financing_rate_pct":60,"typical_total_project_eur":80000000},"timing":{"duration_months_typical":48},"success_rate_pct":13.0,"evaluation":{"ghg_avoidance_weight":0.30,"innovation_weight":0.25,"maturity_weight":0.20,"scalability_weight":0.15,"cost_efficiency_weight":0.10},"priorities":["green_deal","fit_for_55","industrial_decarbonisation"]},
    {"id":"digital_europe","name":"Digital Europe Programme","programme":"Digital Europe","level":"EU","url":"https://digital-strategy.ec.europa.eu/en/activities/digital-programme","eligibility":{"countries":["EU27","associated_countries"],"sectors":["digital","ai","cybersecurity","hpc","semiconductors"],"trl_min":6,"trl_max":9,"consortium":"single_or_consortium"},"budget":{"grant_min_eur":1000000,"grant_max_eur":10000000,"co_financing_rate_pct":50,"typical_total_project_eur":4000000},"timing":{"duration_months_typical":24},"success_rate_pct":25.0,"evaluation":{"relevance_weight":0.30,"implementation_weight":0.30,"impact_weight":0.40},"priorities":["digital","strategic_autonomy"]},
    {"id":"life_clean_energy","name":"LIFE Clean Energy Transition","programme":"LIFE","level":"EU","url":"https://cinea.ec.europa.eu/programmes/life_en","eligibility":{"countries":["EU27","associated_countries"],"sectors":["clean_energy","energy_efficiency","behavior_change"],"trl_min":5,"trl_max":9,"consortium":"min_2_partners_typical"},"budget":{"grant_min_eur":1000000,"grant_max_eur":2500000,"co_financing_rate_pct":95,"typical_total_project_eur":2000000},"timing":{"duration_months_typical":36},"success_rate_pct":20.0,"evaluation":{"relevance_weight":0.35,"impact_weight":0.35,"quality_weight":0.30},"priorities":["green_deal","fit_for_55"]},
    {"id":"life_climate","name":"LIFE Climate Action","programme":"LIFE","level":"EU","url":"https://cinea.ec.europa.eu/programmes/life_en","eligibility":{"countries":["EU27","associated_countries"],"sectors":["climate_tech","circular_economy","adaptation"],"trl_min":5,"trl_max":9,"consortium":"min_2_partners_typical"},"budget":{"grant_min_eur":1000000,"grant_max_eur":5000000,"co_financing_rate_pct":60,"typical_total_project_eur":3000000},"timing":{"duration_months_typical":48},"success_rate_pct":22.0,"evaluation":{"relevance_weight":0.35,"impact_weight":0.35,"quality_weight":0.30},"priorities":["green_deal","climate_adaptation","climate_mitigation"]},
    {"id":"life_nature","name":"LIFE Nature & Biodiversity","programme":"LIFE","level":"EU","url":"https://cinea.ec.europa.eu/programmes/life_en","eligibility":{"countries":["EU27","associated_countries"],"sectors":["biodiversity","nature_conservation","circular_economy"],"trl_min":5,"trl_max":9,"consortium":"min_2_partners_typical"},"budget":{"grant_min_eur":2000000,"grant_max_eur":5000000,"co_financing_rate_pct":60,"typical_total_project_eur":3500000},"timing":{"duration_months_typical":60},"success_rate_pct":20.0,"evaluation":{"relevance_weight":0.40,"impact_weight":0.30,"quality_weight":0.30},"priorities":["biodiversity","natura_2000"]},
    {"id":"eurostars3","name":"Eurostars-3 (Eureka)","programme":"Eureka network / Horizon Europe","level":"EU","url":"https://www.eurekanetwork.org/eurostars","eligibility":{"countries":["Eureka_member_countries"],"sectors":["any"],"trl_min":4,"trl_max":8,"sme_required":true,"consortium":"min_2_partners_2_countries_with_sme_lead"},"budget":{"grant_min_eur":200000,"grant_max_eur":1500000,"co_financing_rate_pct":50,"typical_total_project_eur":1500000},"timing":{"duration_months_typical":36},"success_rate_pct":25.0,"evaluation":{"excellence_weight":0.30,"impact_weight":0.30,"implementation_weight":0.40},"priorities":["sme_innovation","international_collaboration"]},
    {"id":"edf","name":"European Defence Fund","programme":"EDF","level":"EU","url":"https://defence-industry-space.ec.europa.eu/eu-defence-industry/european-defence-fund-edf_en","eligibility":{"countries":["EU27","Norway"],"sectors":["defence","dual_use"],"trl_min":4,"trl_max":8,"consortium":"min_3_partners_3_countries","requires_dual_use":true},"budget":{"grant_min_eur":5000000,"grant_max_eur":50000000,"co_financing_rate_pct":100,"typical_total_project_eur":20000000},"timing":{"duration_months_typical":36},"success_rate_pct":30.0,"evaluation":{"contribution_to_excellence_weight":0.30,"contribution_to_innovation_weight":0.30,"industrial_weight":0.40},"priorities":["defence","strategic_autonomy"]},
    {"id":"cef_digital","name":"Connecting Europe Facility - Digital","programme":"CEF","level":"EU","url":"https://hadea.ec.europa.eu/programmes/connecting-europe-facility/cef-digital_en","eligibility":{"countries":["EU27"],"sectors":["digital","infrastructure","5g","cloud"],"trl_min":7,"trl_max":9,"consortium":"min_2_partners_2_countries"},"budget":{"grant_min_eur":1000000,"grant_max_eur":30000000,"co_financing_rate_pct":30,"typical_total_project_eur":10000000},"timing":{"duration_months_typical":36},"success_rate_pct":30.0,"evaluation":{"relevance_weight":0.30,"maturity_weight":0.30,"impact_weight":0.40},"priorities":["digital_infrastructure","cross_border"]},
    {"id":"france2030_inov","name":"France 2030 - i-Nov","programme":"France 2030 / Bpifrance","level":"national_FR","url":"https://www.bpifrance.fr/nos-appels-a-projets-concours/appel-a-projets-i-nov","eligibility":{"countries":["FR"],"sectors":["any_thematic_wave"],"trl_min":4,"trl_max":8,"sme_required":true,"startup_friendly":true,"consortium":"single_or_consortium_with_lab"},"budget":{"grant_min_eur":600000,"grant_max_eur":5000000,"co_financing_rate_pct":45,"typical_total_project_eur":3000000},"timing":{"duration_months_typical":30},"success_rate_pct":22.0,"evaluation":{"innovation_weight":0.30,"market_weight":0.30,"team_weight":0.20,"impact_weight":0.20},"priorities":["green_industry","digital_sovereignty","health"]},
    {"id":"france2030_idemo","name":"France 2030 - i-Démo","programme":"France 2030 / Bpifrance","level":"national_FR","url":"https://www.bpifrance.fr/nos-appels-a-projets-concours/concours-i-demo-france-2030","eligibility":{"countries":["FR"],"sectors":["deeptech_any","industrial_demonstrator"],"trl_min":5,"trl_max":8,"sme_required":false,"consortium":"single_or_consortium"},"budget":{"grant_min_eur":2000000,"grant_max_eur":30000000,"co_financing_rate_pct":40,"typical_total_project_eur":15000000},"timing":{"duration_months_typical":48},"success_rate_pct":18.0,"evaluation":{"innovation_weight":0.30,"market_weight":0.25,"industrial_impact_weight":0.25,"team_weight":0.20},"priorities":["deeptech_industrialisation","french_tech_2030"]},
    {"id":"france2030_ilab","name":"France 2030 - i-Lab","programme":"France 2030 / MESR","level":"national_FR","url":"https://www.enseignementsup-recherche.gouv.fr/fr/le-concours-d-innovation-i-lab","eligibility":{"countries":["FR"],"sectors":["deeptech_any"],"trl_min":3,"trl_max":6,"company_age_max_years":2,"consortium":"single"},"budget":{"grant_min_eur":200000,"grant_max_eur":600000,"co_financing_rate_pct":60,"typical_total_project_eur":800000},"timing":{"duration_months_typical":24},"success_rate_pct":15.0,"evaluation":{"innovation_weight":0.35,"team_weight":0.30,"market_weight":0.35},"priorities":["deeptech_creation"]},
    {"id":"frenchtech2030","name":"French Tech 2030","programme":"France 2030 / Mission French Tech","level":"national_FR","url":"https://lafrenchtech.gouv.fr/","eligibility":{"countries":["FR"],"sectors":["deeptech_any","strategic_french_priorities"],"trl_min":4,"trl_max":8,"company_age_max_years":10,"consortium":"single"},"budget":{"grant_min_eur":0,"grant_max_eur":0,"co_financing_rate_pct":0,"instrument":"support_program","typical_total_project_eur":0},"timing":{"duration_months_typical":36},"success_rate_pct":25.0,"evaluation":{"strategic_priority_weight":0.40,"team_weight":0.30,"ambition_weight":0.30},"priorities":["strategic_french_sovereignty","deeptech_scale"]},
    {"id":"bpifrance_adi","name":"Bpifrance - Aide au Développement de l'Innovation","programme":"Bpifrance","level":"national_FR","url":"https://www.bpifrance.fr/catalogue-offres/innovation/aide-pour-le-developpement-de-linnovation","eligibility":{"countries":["FR"],"sectors":["any"],"trl_min":4,"trl_max":8,"sme_required":true,"consortium":"single"},"budget":{"grant_min_eur":100000,"grant_max_eur":3000000,"co_financing_rate_pct":50,"instrument":"advance_recoverable","typical_total_project_eur":1500000},"timing":{"duration_months_typical":24},"success_rate_pct":35.0,"evaluation":{"innovation_weight":0.35,"market_weight":0.30,"financial_weight":0.35},"priorities":["innovation_general"]},
    {"id":"bpifrance_concours_innovation","name":"Bpifrance - Concours Innovation (i-PME)","programme":"France 2030 / Bpifrance","level":"national_FR","url":"https://www.bpifrance.fr/nos-appels-a-projets-concours/concours-innovation-i-pme","eligibility":{"countries":["FR"],"sectors":["any_thematic_wave"],"trl_min":4,"trl_max":7,"sme_required":true,"consortium":"single"},"budget":{"grant_min_eur":200000,"grant_max_eur":800000,"co_financing_rate_pct":50,"typical_total_project_eur":1200000},"timing":{"duration_months_typical":24},"success_rate_pct":28.0,"evaluation":{"innovation_weight":0.35,"market_weight":0.30,"team_weight":0.35},"priorities":["sme_innovation"]},
    {"id":"ademe_demonstrateurs","name":"ADEME - Démonstrateurs","programme":"France 2030 / ADEME","level":"national_FR","url":"https://www.ademe.fr/","eligibility":{"countries":["FR"],"sectors":["clean_energy","circular_economy","climate_tech","mobility"],"trl_min":6,"trl_max":8,"consortium":"consortium_with_industrial_partner_typical"},"budget":{"grant_min_eur":1000000,"grant_max_eur":8000000,"co_financing_rate_pct":50,"typical_total_project_eur":5000000},"timing":{"duration_months_typical":36},"success_rate_pct":25.0,"evaluation":{"environmental_impact_weight":0.40,"innovation_weight":0.25,"team_weight":0.15,"market_weight":0.20},"priorities":["green_deal","circular_economy"]},
    {"id":"ademe_perfecto","name":"ADEME PERFECTO","programme":"ADEME","level":"national_FR","url":"https://agirpourlatransition.ademe.fr/","eligibility":{"countries":["FR"],"sectors":["any_with_eco_design"],"trl_min":4,"trl_max":9,"consortium":"single"},"budget":{"grant_min_eur":50000,"grant_max_eur":200000,"co_financing_rate_pct":50,"typical_total_project_eur":200000},"timing":{"duration_months_typical":18},"success_rate_pct":50.0,"evaluation":{"environmental_relevance_weight":0.50,"team_weight":0.20,"methodology_weight":0.30},"priorities":["eco_design","lca"]},
    {"id":"feder_idf_innovation","name":"FEDER Île-de-France - Innovation","programme":"FEDER 2021-2027 IdF","level":"regional_FR_IDF","url":"https://www.iledefrance.fr/europe/feder-fse-en-ile-de-france","eligibility":{"countries":["FR"],"regions":["Île-de-France"],"sectors":["smart_specialisation_idf"],"trl_min":4,"trl_max":8,"consortium":"single_or_partnership"},"budget":{"grant_min_eur":200000,"grant_max_eur":2000000,"co_financing_rate_pct":40,"typical_total_project_eur":1500000},"timing":{"duration_months_typical":24},"success_rate_pct":30.0,"evaluation":{"regional_relevance_weight":0.35,"innovation_weight":0.30,"impact_weight":0.35},"priorities":["s3_idf","regional_employment"]},
    {"id":"innovup_idf","name":"Région Île-de-France - Innov'Up","programme":"Région IdF","level":"regional_FR_IDF","url":"https://www.iledefrance.fr/innovup-soutenir-vos-projets-dinnovation","eligibility":{"countries":["FR"],"regions":["Île-de-France"],"sectors":["any"],"trl_min":3,"trl_max":8,"sme_required":true,"consortium":"single"},"budget":{"grant_min_eur":100000,"grant_max_eur":1500000,"co_financing_rate_pct":50,"typical_total_project_eur":1000000},"timing":{"duration_months_typical":24},"success_rate_pct":40.0,"evaluation":{"innovation_weight":0.35,"team_weight":0.25,"market_weight":0.25,"regional_impact_weight":0.15},"priorities":["regional_innovation","employment_idf"]},
    {"id":"paris_saclay_pia","name":"Paris-Saclay - Booster cluster deeptech","programme":"PIA Régional","level":"regional_FR_IDF","url":"https://www.universite-paris-saclay.fr/innovation","eligibility":{"countries":["FR"],"regions":["Île-de-France"],"geo_specific":"Paris-Saclay","sectors":["deeptech_any"],"trl_min":3,"trl_max":7,"sme_required":true},"budget":{"grant_min_eur":50000,"grant_max_eur":500000,"co_financing_rate_pct":50,"typical_total_project_eur":400000},"timing":{"duration_months_typical":18},"success_rate_pct":45.0,"evaluation":{"deeptech_weight":0.40,"team_weight":0.30,"market_weight":0.30},"priorities":["deeptech_local","ecosystem_paris_saclay"]},
    {"id":"ara_pack_ambition","name":"Région Auvergne-Rhône-Alpes - Pack Ambition Innovation","programme":"Région ARA","level":"regional_FR_ARA","url":"https://www.auvergnerhonealpes.fr/aide/91/pack-ambition-innovation","eligibility":{"countries":["FR"],"regions":["Auvergne-Rhône-Alpes"],"sectors":["s3_ara"],"trl_min":3,"trl_max":8,"sme_required":true,"consortium":"single_or_collaborative"},"budget":{"grant_min_eur":100000,"grant_max_eur":1500000,"co_financing_rate_pct":50,"typical_total_project_eur":1000000},"timing":{"duration_months_typical":30},"success_rate_pct":35.0,"evaluation":{"innovation_weight":0.35,"regional_relevance_weight":0.25,"team_weight":0.20,"impact_weight":0.20},"priorities":["s3_ara","regional_innovation"]},
    {"id":"occitanie_readynov","name":"Région Occitanie - READYNOV","programme":"Région Occitanie","level":"regional_FR_OCC","url":"https://www.laregion.fr/Readynov-aide-a-l-innovation","eligibility":{"countries":["FR"],"regions":["Occitanie"],"sectors":["s3_occitanie"],"trl_min":3,"trl_max":8,"consortium":"single_or_collaborative"},"budget":{"grant_min_eur":75000,"grant_max_eur":800000,"co_financing_rate_pct":50,"typical_total_project_eur":800000},"timing":{"duration_months_typical":24},"success_rate_pct":38.0,"evaluation":{"innovation_weight":0.35,"regional_relevance_weight":0.30,"team_weight":0.20,"impact_weight":0.15},"priorities":["s3_occitanie","aerospace","agritech","health"]},
    {"id":"hdf_startinnov","name":"Région Hauts-de-France - Start'innov","programme":"Région HDF","level":"regional_FR_HDF","url":"https://hautsdefrance.fr/","eligibility":{"countries":["FR"],"regions":["Hauts-de-France"],"sectors":["s3_hdf"],"trl_min":4,"trl_max":8,"sme_required":true},"budget":{"grant_min_eur":50000,"grant_max_eur":500000,"co_financing_rate_pct":50,"typical_total_project_eur":600000},"timing":{"duration_months_typical":24},"success_rate_pct":40.0,"evaluation":{"innovation_weight":0.40,"regional_relevance_weight":0.35,"team_weight":0.25},"priorities":["s3_hdf","regional_innovation"]},
    {"id":"naq_aap_innovation","name":"Région Nouvelle-Aquitaine - AAP Innovation","programme":"Région NAQ","level":"regional_FR_NAQ","url":"https://les-aides.nouvelle-aquitaine.fr/","eligibility":{"countries":["FR"],"regions":["Nouvelle-Aquitaine"],"sectors":["s3_naq"],"trl_min":4,"trl_max":8,"consortium":"single_or_collaborative"},"budget":{"grant_min_eur":75000,"grant_max_eur":800000,"co_financing_rate_pct":45,"typical_total_project_eur":800000},"timing":{"duration_months_typical":24},"success_rate_pct":35.0,"evaluation":{"innovation_weight":0.35,"regional_relevance_weight":0.30,"team_weight":0.20,"impact_weight":0.15},"priorities":["s3_naq","photonics","marine"]}
  ]
}
"""

GRANTS_DB: dict = json.loads(GRANTS_DB_JSON)

# -----------------------------------------------------------------------------
# VC Database (European investors — matched to pitchdeck at runtime)
# -----------------------------------------------------------------------------

_VC_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "vc_db.json")
VC_DB: list[dict] = []
try:
    with open(_VC_DB_PATH, encoding="utf-8") as _f:
        _raw = json.load(_f)
        VC_DB = _raw.get("vcs", _raw) if isinstance(_raw, dict) else _raw
except (FileNotFoundError, json.JSONDecodeError):
    pass

SENSITIVE_SECTORS: set[str] = {"defence", "gambling", "weapons", "crypto", "adult_content", "dual_use"}

ISO2_TO_COUNTRY_NAME: dict[str, str] = {
    "FR": "France", "DE": "Germany", "GB": "UK", "UK": "UK",
    "ES": "Spain", "IT": "Italy", "NL": "Netherlands", "BE": "Belgium",
    "SE": "Sweden", "DK": "Denmark", "FI": "Finland", "NO": "Norway",
    "CH": "Switzerland", "AT": "Austria", "PL": "Poland", "PT": "Portugal",
    "IE": "Ireland", "CZ": "Czech Republic", "HU": "Hungary", "RO": "Romania",
}

EU_VC_COUNTRIES: set[str] = {
    "France", "Germany", "UK", "Spain", "Italy", "Netherlands", "Belgium",
    "Sweden", "Denmark", "Finland", "Norway", "Switzerland", "Austria",
    "Poland", "Portugal", "Ireland", "Czech Republic", "Hungary", "Romania",
    "Greece", "Luxembourg", "Estonia", "Latvia", "Lithuania", "Croatia",
    "Slovenia", "Slovakia", "Bulgaria", "Cyprus", "Malta",
}

SECTOR_TO_VC_KEYWORDS: dict[str, list[str]] = {
    "ai": ["ai", "artificial intelligence", "machine learning", "deep learning", "data science", "nlp", "generative"],
    "clean_energy": ["energy", "cleantech", "clean energy", "renewable", "solar", "wind", "hydrogen", "energy transition"],
    "climate_tech": ["climate", "carbon", "sustainability", "environmental", "net zero", "decarbonisation", "cleantech"],
    "biotech": ["biotech", "biotechnology", "life sciences", "pharmaceutical", "drug discovery", "therapeutics", "genomics"],
    "health": ["health", "healthtech", "digital health", "medtech", "medical", "clinical"],
    "cybersecurity": ["cybersecurity", "cyber", "security", "infosec", "information security"],
    "fintech": ["fintech", "financial technology", "payments", "banking", "insurtech"],
    "digital": ["digital", "software", "saas", "enterprise software", "b2b software"],
    "deeptech": ["deep tech", "deeptech", "hard tech", "scientific", "deep science"],
    "advanced_materials": ["materials", "advanced materials", "chemistry", "nanotechnology", "nano"],
    "space": ["space", "aerospace", "satellite", "new space", "orbit"],
    "robotics": ["robotics", "automation", "autonomous systems"],
    "quantum": ["quantum", "quantum computing", "quantum technology"],
    "semiconductors": ["semiconductor", "chip", "hardware", "photonics"],
    "agritech": ["agritech", "agriculture", "food tech", "foodtech", "agri"],
    "mobility": ["mobility", "transportation", "automotive", "electric vehicle", "ev", "transport"],
    "manufacturing": ["manufacturing", "industry 4.0", "industrial", "production"],
}

STAGE_STRATEGY_KEYWORDS: dict[str, list[str]] = {
    "pre_seed": ["pre-seed", "preseed", "pre seed", "seed", "early stage", "start-up"],
    "seed": ["seed", "early stage", "start-up", "startup"],
    "early_stage": ["early stage", "series a", "start-up", "venture", "growth"],
    "growth": ["growth", "expansion", "series b", "series c", "late stage", "expansion / late stage"],
}


def _country_name_for(iso2: str) -> str:
    return ISO2_TO_COUNTRY_NAME.get((iso2 or "").upper(), "")


def _deck_stage(deck: dict) -> str:
    trl = (deck.get("product") or {}).get("trl") or 5
    amount = (deck.get("funding_ask") or {}).get("amount_eur") or 0
    if trl <= 3 or amount < 500_000:
        return "pre_seed"
    elif trl <= 5 or amount < 2_000_000:
        return "seed"
    elif trl <= 7 or amount < 10_000_000:
        return "early_stage"
    return "growth"


def _vc_match_reason(sector_score: float, stage_score: float, geo_score: float,
                     stage: str, sectors: set, vc: dict) -> str:
    reasons = []
    if sector_score > 0.3:
        s_list = ", ".join(list(sectors)[:2])
        reasons.append(f"sector fit ({s_list})")
    if stage_score > 0.3:
        reasons.append(f"{stage.replace('_', ' ')} stage investor")
    if geo_score >= 1.0:
        reasons.append(f"same country ({vc.get('country', '')})")
    elif geo_score >= 0.6:
        reasons.append("European investor")
    return "; ".join(reasons) if reasons else "general European match"


def match_vcs(deck: dict, top_n: int = 8) -> list[dict]:
    """Match VCs from the European VC database to the pitchdeck profile."""
    if not VC_DB:
        return []
    sectors = set(s.lower() for s in (deck.get("product") or {}).get("sectors", []))
    country_name = _country_name_for((deck.get("company") or {}).get("country", ""))
    stage = _deck_stage(deck)
    stage_keywords = STAGE_STRATEGY_KEYWORDS.get(stage, [])
    scored: list[dict] = []
    for vc in VC_DB:
        bg = (vc.get("background") or "").lower()
        strategies = (vc.get("strategies") or "").lower()
        vc_country = vc.get("country", "")
        sector_score = 0.0
        for sector in sectors:
            kws = SECTOR_TO_VC_KEYWORDS.get(sector, [])
            hits = sum(1 for kw in kws if kw in bg)
            sector_score += min(1.0, hits * 0.3)
        sector_score = min(1.0, sector_score)
        stage_score = min(1.0, sum(0.35 for kw in stage_keywords if kw in strategies))
        if vc_country == country_name:
            geo_score = 1.0
        elif vc_country in EU_VC_COUNTRIES:
            geo_score = 0.6
        else:
            geo_score = 0.15
        total = 0.50 * sector_score + 0.30 * stage_score + 0.20 * geo_score
        if total > 0.2:
            scored.append({
                "name": vc["name"],
                "city": vc.get("city", ""),
                "country": vc_country,
                "background": (vc.get("background") or "")[:220],
                "strategies": vc.get("strategies", ""),
                "match_score": round(total * 100, 1),
                "match_reason": _vc_match_reason(sector_score, stage_score, geo_score, stage, sectors, vc),
            })
    scored.sort(key=lambda x: -x["match_score"])
    return scored[:top_n]


def _compute_top_blockers(matches: list) -> list[dict]:
    """Aggregate most common blockers across ineligible grants for the empty-state panel."""
    ACTION_MAP = {
        "country_region": ("Country / region not eligible",
                           "Register an EU entity or verify Horizon Europe association status for your country"),
        "trl": ("TRL mismatch", "Adjust your TRL in the what-if widget — each level unlocks or blocks different programmes"),
        "sme_required": ("SME status required", "Only SMEs (<250 employees, <50M€ turnover) qualify — verify your SME status"),
        "sector_mismatch": ("Sector not covered", "Expand your sector keywords to match programme priorities"),
        "dual_use": ("Dual-use exclusion / requirement", "Check if programme excludes or requires dual-use"),
        "capex": ("CAPEX below minimum", "Your funding ask doesn't reach the Innovation Fund minimum CAPEX threshold"),
        "phd": ("PhD required", "Add an academic partner or PI with a PhD to unlock research-track grants"),
        "consortium": ("Consortium required", "Join an EU consortium (3+ partners, 3+ countries) to access Horizon Clusters"),
        "company_age": ("Company too old for programme", "Some early-stage programmes cap company age — target growth programmes"),
        "other": ("Other eligibility criterion", "Review the specific call conditions on the programme page"),
    }
    counts: dict[str, int] = {}
    for m in matches:
        if m.eligible:
            continue
        for b in m.blockers:
            if "country" in b.lower() or "region" in b.lower():
                key = "country_region"
            elif "trl" in b.lower():
                key = "trl"
            elif "sme" in b.lower():
                key = "sme_required"
            elif "sector" in b.lower():
                key = "sector_mismatch"
            elif "dual" in b.lower():
                key = "dual_use"
            elif "capex" in b.lower():
                key = "capex"
            elif "phd" in b.lower():
                key = "phd"
            elif "consortium" in b.lower():
                key = "consortium"
            elif "company" in b.lower() and "y >" in b.lower():
                key = "company_age"
            else:
                key = "other"
            counts[key] = counts.get(key, 0) + 1
    top = sorted(counts.items(), key=lambda x: -x[1])[:3]
    return [
        {"blocker": k, "count": v, "label": ACTION_MAP[k][0], "action": ACTION_MAP[k][1]}
        for k, v in top
    ]


# -----------------------------------------------------------------------------
# Submission deadlines — INDICATIVE 2026 cycle
# -----------------------------------------------------------------------------
# These dates are typical-cycle estimates compiled from public Work Programmes
# (Horizon Europe 2026-2027), past cut-off patterns, and Bpifrance/ADEME
# vagues. They are intended for ranking and demo purposes — for production,
# refresh nightly from the SEDIA API (see grant-matcher plugin sedia.py)
# and the Bpifrance/ADEME publication feeds.
#
# Format per grant:
#   {"next_deadline": "YYYY-MM-DD" | None, "pattern": str, "stage": str | None}
# pattern is the human cadence ("rolling", "1 cut-off/year", etc.).
# stage indicates which stage if multi-stage (e.g. EIC Accelerator stage 1).
DEADLINES_2026: dict[str, dict] = {
    # EU Pillar I
    "erc_starting":            {"next_deadline": "2026-10-22", "pattern": "1 call/year (annual cut-off in October)"},
    "erc_poc":                 {"next_deadline": "2026-05-27", "pattern": "3 cut-offs/year (Mar, May, Oct)"},
    "msca_pf":                 {"next_deadline": "2026-09-09", "pattern": "1 call/year (Sept cut-off)"},
    # EU Pillar II — Horizon Europe Clusters
    "horizon_cluster1_health": {"next_deadline": "2026-09-16", "pattern": "1-2 calls/year per destination"},
    "horizon_cluster4_digital":{"next_deadline": "2026-09-22", "pattern": "1-2 calls/year per destination"},
    "horizon_cluster5_climate":{"next_deadline": "2026-09-16", "pattern": "1-2 calls/year per destination"},
    "horizon_cluster6_food":   {"next_deadline": "2026-09-08", "pattern": "1 call/year"},
    # EU Pillar III — EIC + EIT
    "eic_accelerator":         {"next_deadline": "2026-06-04", "pattern": "Short proposal: 3 cut-offs/year (Mar, Jun, Oct). Full proposal: continuously open.", "stage": "stage 1 (short proposal)"},
    "eic_pathfinder_open":     {"next_deadline": "2026-10-21", "pattern": "1 call/year (Oct cut-off)"},
    "eic_pathfinder_challenges":{"next_deadline":"2026-10-15", "pattern": "1 call/year (Oct cut-off)"},
    "eic_transition":          {"next_deadline": "2026-09-25", "pattern": "2 cut-offs/year (Apr, Sept)"},
    "eit_climate_kic":         {"next_deadline": None,         "pattern": "Rolling — multiple thematic calls per year"},
    "eit_health":              {"next_deadline": "2026-06-15", "pattern": "2 main calls/year (Jun, Nov)"},
    # EU Other
    "innovation_fund_small":   {"next_deadline": "2027-04-15", "pattern": "1 call/year (Apr cut-off) — 2026 cycle closed"},
    "innovation_fund_large":   {"next_deadline": "2027-04-15", "pattern": "1 call/year (Apr cut-off) — 2026 cycle closed"},
    "digital_europe":          {"next_deadline": "2026-06-30", "pattern": "Multiple thematic calls per year"},
    "life_clean_energy":       {"next_deadline": "2026-09-23", "pattern": "1 call/year (Sept cut-off)"},
    "life_climate":            {"next_deadline": "2026-09-23", "pattern": "1 call/year (Sept cut-off)"},
    "life_nature":             {"next_deadline": "2026-09-23", "pattern": "1 call/year (Sept cut-off)"},
    "eurostars3":              {"next_deadline": "2026-09-10", "pattern": "2 cut-offs/year (Mar, Sept)"},
    "edf":                     {"next_deadline": "2026-06-25", "pattern": "1 call/year (June cut-off)"},
    "cef_digital":             {"next_deadline": "2026-09-15", "pattern": "Annual calls — varies by topic"},
    # France national
    "france2030_inov":         {"next_deadline": "2026-06-30", "pattern": "Thematic waves 1-2/year — verify open wave covers your sector"},
    "france2030_idemo":        {"next_deadline": "2026-09-30", "pattern": "Annual waves"},
    "france2030_ilab":         {"next_deadline": "2027-03-15", "pattern": "1 wave/year (Mar) — 2026 vague closed"},
    "frenchtech2030":          {"next_deadline": None,         "pattern": "Closed cohort selection — by invitation/nomination"},
    "bpifrance_adi":           {"next_deadline": None,         "pattern": "Rolling (au fil de l'eau)"},
    "bpifrance_concours_innovation":{"next_deadline":"2026-07-08","pattern": "1-2 thematic waves/year"},
    "ademe_demonstrateurs":    {"next_deadline": "2026-09-30", "pattern": "Annual waves"},
    "ademe_perfecto":          {"next_deadline": None,         "pattern": "Rolling (au fil de l'eau)"},
    # France régional
    "feder_idf_innovation":    {"next_deadline": None,         "pattern": "Rolling — Smart Specialisation Strategy IdF"},
    "innovup_idf":             {"next_deadline": None,         "pattern": "Rolling (au fil de l'eau)"},
    "paris_saclay_pia":        {"next_deadline": None,         "pattern": "Rolling — Paris-Saclay cluster only"},
    "ara_pack_ambition":       {"next_deadline": "2026-06-30", "pattern": "2 waves/year (Mar + Jun + Sept variants)"},
    "occitanie_readynov":      {"next_deadline": None,         "pattern": "Rolling (au fil de l'eau)"},
    "hdf_startinnov":          {"next_deadline": None,         "pattern": "Rolling (au fil de l'eau)"},
    "naq_aap_innovation":      {"next_deadline": "2026-09-15", "pattern": "Annual waves"},
}


def deadline_info(grant_id: str, today: date | None = None) -> dict:
    """Return {next_deadline, days_until, urgency, pattern, stage}."""
    info = DEADLINES_2026.get(grant_id, {})
    pattern = info.get("pattern") or "Verify on programme page"
    stage = info.get("stage")
    next_dl = info.get("next_deadline")
    today = today or date.today()
    if not next_dl:
        return {"next_deadline": None, "days_until": None,
                "urgency": "rolling", "pattern": pattern, "stage": stage}
    try:
        dl = date.fromisoformat(next_dl)
    except ValueError:
        return {"next_deadline": None, "days_until": None,
                "urgency": "unknown", "pattern": pattern, "stage": stage}
    days = (dl - today).days
    if days < 0:
        urgency = "passed"
    elif days <= 30:
        urgency = "urgent"
    elif days <= 90:
        urgency = "soon"
    else:
        urgency = "comfortable"
    return {"next_deadline": next_dl, "days_until": days,
            "urgency": urgency, "pattern": pattern, "stage": stage}

# -----------------------------------------------------------------------------
# Matching engine (consolidated)
# -----------------------------------------------------------------------------

@dataclass
class GrantMatch:
    grant_id: str
    grant_name: str
    level: str
    eligible: bool
    blockers: list[str]
    warnings: list[str]
    fit_total: float
    fit_breakdown: dict[str, float]
    base_success_rate_pct: float
    statistical_estimate_pct: float
    evaluator: dict[str, float]
    blended_probability_pct: float
    confidence_interval_pct: tuple[float, float]
    funding_range_eur: tuple[int, int]
    url: str
    headline: str
    priority_tier: str
    next_deadline: str | None = None        # ISO date "YYYY-MM-DD" or None for rolling
    days_until_deadline: int | None = None
    urgency: str = "unknown"                # urgent | soon | comfortable | rolling | passed | unknown
    cut_off_pattern: str = ""
    stage_label: str | None = None
    # Rule 5: structured per-programme output fields
    eligibility_status: str = ""            # CONFIRMED / CONDITIONAL / EXCLUDED
    probability_explanation: str = ""       # "X% (baseline: Y%, adjustments: ...)"
    expected_value_eur: float = 0.0         # prob × midpoint(funding_range)
    key_risk: str = ""                      # single sentence on main failure mode
    next_action: str = ""                   # concrete step for the founder in next 7 days

    def to_dict(self) -> dict:
        return asdict(self)


def check_eligibility(deck: dict, grant: dict) -> tuple[bool, list[str], list[str]]:
    """
    RULE 1 — Hard Eligibility Gate.
    Verifies binary criteria BEFORE any scoring.
    If any criterion fails → EXCLUDE (blocker added, eligible=False).
    """
    blockers: list[str] = []
    warnings: list[str] = []
    elig = grant["eligibility"]
    grant_id = grant.get("id", "")
    company = deck.get("company") or {}
    product = deck.get("product") or {}
    funding = deck.get("funding_ask") or {}
    team = deck.get("team") or {}

    # --- HARD GATE: ERC Proof of Concept ---
    # Requires PI to hold an active ERC grant (Starting/Consolidator/Advanced/Synergy)
    # or an ERC grant that ended after 1 January 2025.
    if grant_id == "erc_poc":
        has_erc = team.get("prior_erc_grant", False)
        erc_type = team.get("erc_grant_type")
        if not has_erc and not erc_type:
            blockers.append("EXCLUDED: No prior ERC grant (required for ERC Proof of Concept)")

    # --- HARD GATE: EIC Transition ---
    # Requires a proven link to a previously funded EIC Pathfinder or Horizon ERC project.
    if grant_id == "eic_transition":
        has_prior = (product.get("prior_eic_pathfinder", False)
                     or product.get("prior_erc_poc", False))
        if not has_prior:
            blockers.append("EXCLUDED: No prior EIC Pathfinder or ERC project link (required for EIC Transition)")

    # --- HARD GATE: Horizon Europe Clusters (RIA/IA) + EIC Pathfinder Open ---
    # Require minimum 3 independent entities from 3 different countries.
    # A solo startup CANNOT lead or apply alone.
    consortium_req = elig.get("consortium", "single")
    if "min_3_partners" in consortium_req:
        consortium_confirmed = funding.get("consortium_confirmed", False)
        if funding.get("open_to_consortium") is False:
            blockers.append("≥3-partner consortium required and not open to consortium")
        elif not consortium_confirmed:
            blockers.append("Consortium required — not standalone eligible (need ≥3 partners from ≥3 EU countries)")
            warnings.append("Identify at least 2 additional independent partners from 2 other EU countries to unlock this programme")
    elif "min_2_partners" in consortium_req:
        consortium_confirmed = funding.get("consortium_confirmed", False)
        if not consortium_confirmed:
            warnings.append("Requires ≥2-partner consortium — confirm partner availability")

    # --- CONDITIONAL: Eurostars-3 ---
    # Requires at least one foreign partner in another Eureka member country.
    if grant_id == "eurostars3":
        foreign_partner = funding.get("foreign_partner_confirmed", False)
        if not foreign_partner:
            warnings.append("Partner in another Eureka country required — probability will be halved until confirmed")

    # --- CONDITIONAL: ADEME PERFECTO ---
    # Core ecodesign/LCA methodology required, not just marketing claims.
    if grant_id == "ademe_perfecto":
        has_lca = product.get("lca_methodology", False)
        has_expert = team.get("ecodesign_expert", False)
        if not has_lca and not has_expert:
            warnings.append("Ecodesign claim requires LCA methodology substantiation — fit score downgraded")

    # --- Standard country/region check ---
    country = company.get("country")
    region = company.get("region")
    allowed = elig.get("countries", [])
    if "EU27" in allowed and country in EU27:
        pass
    elif "Eureka_member_countries" in allowed and country in EUREKA_COUNTRIES:
        pass
    elif country and country in allowed:
        pass
    elif elig.get("regions") and region in elig.get("regions", []):
        pass
    elif country is None:
        warnings.append("Country not specified")
    else:
        blockers.append(f"Country/region not eligible ({country}/{region})")

    if grant["level"].startswith("regional"):
        if region not in elig.get("regions", []):
            blockers.append(f"Outside target region {elig.get('regions')}")

    # --- TRL range check ---
    trl = product.get("trl")
    if trl is None:
        warnings.append("TRL not specified")
    else:
        if trl < elig.get("trl_min", 1):
            blockers.append(f"TRL {trl} < required min {elig['trl_min']}")
        if trl > elig.get("trl_max", 9):
            blockers.append(f"TRL {trl} > required max {elig['trl_max']}")

    # --- SME status ---
    if elig.get("sme_required") and company.get("sme") is False:
        blockers.append("SME status required")

    # --- Dual-use ---
    if elig.get("requires_dual_use") and not product.get("dual_use"):
        blockers.append("Dual-use required")
    if not elig.get("dual_use_allowed", True) and product.get("dual_use"):
        blockers.append("Dual-use excluded")

    # --- Sector matching ---
    sectors_needed = set(s.lower() for s in elig.get("sectors", []))
    sectors_have = set(s.lower() for s in product.get("sectors", []))
    if sectors_needed and "any" not in sectors_needed:
        match = bool(sectors_needed & sectors_have)
        if not match:
            for ng in sectors_needed:
                if ng in SECTOR_FUZZY and SECTOR_FUZZY[ng] & sectors_have:
                    match = True
                    break
            if "deeptech_any" in sectors_needed and company.get("deeptech"):
                match = True
            if "any_thematic_wave" in sectors_needed:
                match = True
                warnings.append("Thematic wave — verify the open wave covers your sector")
            if "smart_specialisation" in " ".join(sectors_needed):
                match = True
                warnings.append("Verify regional S3 alignment")
            if "any_with_eco_design" in sectors_needed:
                match = True
            if "fundamental_research" in sectors_needed:
                match = True
            if "industrial_demonstrator" in sectors_needed and (trl or 0) >= 5:
                match = True
        if not match:
            blockers.append(f"Sector mismatch")

    # --- Company age cap ---
    max_age = elig.get("company_age_max_years")
    if max_age is not None:
        founded = company.get("founded")
        if founded and (date.today().year - founded) > max_age:
            blockers.append(f"Company {date.today().year - founded}y > max {max_age}y")

    # --- CAPEX minimum ---
    if "min_capex_eur" in elig:
        ask = funding.get("amount_eur") or 0
        proj = ask + (funding.get("co_financing_capacity_eur") or 0)
        if proj < elig["min_capex_eur"]:
            blockers.append(f"CAPEX {proj/1e6:.1f}M€ < min {elig['min_capex_eur']/1e6:.1f}M€")

    # --- PhD requirement ---
    if elig.get("phd_required") and (team.get("phds") or 0) == 0:
        blockers.append("PhD required in team")

    # --- Prerequisites (informational) ---
    if elig.get("prerequisite") and not blockers:
        # Only add as warning if we haven't already hard-blocked for this
        prereq_text = elig["prerequisite"]
        already_blocked = any("prior" in b.lower() or "erc" in b.lower() or "eic" in b.lower() for b in blockers)
        if not already_blocked:
            warnings.append(f"Prerequisite: {prereq_text}")
    if elig.get("host_institution_required"):
        warnings.append("European host institution required")

    return (not blockers), blockers, warnings


def _sector_overlap(deck_sectors, grant_priorities, grant_sectors):
    deck_set = set(s.lower() for s in deck_sectors)
    grant_set = set(s.lower() for s in (grant_priorities + grant_sectors))
    if not grant_set or "any" in grant_set:
        return 0.7
    inter = deck_set & grant_set
    fuzzy_hits = sum(1 for p in grant_set if p in SECTOR_FUZZY and SECTOR_FUZZY[p] & deck_set)
    if not inter and not fuzzy_hits:
        return 0.2
    return min(1.0, 0.5 + 0.15 * len(inter) + 0.10 * fuzzy_hits)


def _trl_fit(trl, trl_min, trl_max):
    if trl is None:
        return 0.5
    if trl < trl_min or trl > trl_max:
        return 0.0
    band = trl_max - trl_min
    if band == 0:
        return 1.0
    center = (trl_min + trl_max) / 2
    return 1.0 - abs(trl - center) / (band / 2 + 0.5) * 0.4


def _budget_fit(ask_eur, grant):
    if ask_eur is None:
        return 0.5
    g = grant["budget"]
    lo, hi = g.get("grant_min_eur", 0), g.get("grant_max_eur", 0)
    if hi == 0:
        return 0.6
    rate = g.get("co_financing_rate_pct", 100) / 100
    expected = ask_eur * rate
    if expected < lo:
        return max(0.3, 0.7 + (expected - lo) / max(lo, 1) * 0.5)
    if expected > hi:
        return max(0.2, 1.0 - (expected - hi) / hi * 0.5)
    mid = (lo + hi) / 2
    return 1.0 - abs(expected - mid) / (mid + 1) * 0.2


def compute_fit(deck, grant) -> tuple[float, dict]:
    elig = grant["eligibility"]
    p = deck.get("product") or {}
    fa = deck.get("funding_ask") or {}
    t = deck.get("team") or {}
    weights = {"sector": 0.20, "trl": 0.20, "budget": 0.15, "priorities": 0.20,
               "team": 0.10, "ip": 0.05, "impact": 0.10}
    sector = _sector_overlap(p.get("sectors", []), grant.get("priorities", []), elig.get("sectors", []))
    trl = _trl_fit(p.get("trl"), elig.get("trl_min", 1), elig.get("trl_max", 9))
    budget = _budget_fit(fa.get("amount_eur"), grant)
    impact = deck.get("impact") or {}
    deck_kw = set()
    for v in impact.values():
        if isinstance(v, list):
            deck_kw.update(str(s).lower() for s in v if isinstance(s, str))
    deck_kw.update(str(s).lower() for s in p.get("sectors", []))
    if (deck.get("company") or {}).get("deeptech"):
        deck_kw.add("deeptech")
    priorities_set = set(p_.lower() for p_ in grant.get("priorities", []))
    direct = deck_kw & priorities_set
    fuzzy = sum(1 for pp in priorities_set if pp in SECTOR_FUZZY and SECTOR_FUZZY[pp] & deck_kw)
    priorities_score = 0.6 if not priorities_set else (
        0.3 if not direct and fuzzy == 0 else min(1.0, 0.5 + 0.15 * len(direct) + 0.10 * fuzzy)
    )
    team_score = 0.4
    if (t.get("phds") or 0) >= 2: team_score += 0.2
    if (t.get("phds") or 0) >= 4: team_score += 0.1
    if (t.get("size") or 0) >= 5: team_score += 0.1
    gb = t.get("gender_balance_pct_female") or 0
    if 30 <= gb <= 70: team_score += 0.1
    if t.get("advisors"): team_score += 0.1
    team_score = min(1.0, team_score)
    ip_str = str(p.get("ip_status", "")).lower()
    ip_score = 0.9 if ("brevet" in ip_str or "patent" in ip_str) else (0.6 if "open" in ip_str else 0.4)
    impact_score = 0.9 if (impact.get("co2_reduction_t_yr5") or 0) else 0.5
    breakdown = {
        "sector": round(sector * 100, 1),
        "trl": round(trl * 100, 1),
        "budget": round(budget * 100, 1),
        "priorities": round(priorities_score * 100, 1),
        "team": round(team_score * 100, 1),
        "ip": round(ip_score * 100, 1),
        "impact": round(impact_score * 100, 1),
    }
    total = sum(breakdown[k] * weights[k] for k in weights)
    return round(total, 1), breakdown


def statistical_estimate(base_rate, fit_score):
    multiplier = 0.2 + 1.8 * (fit_score / 100)
    return round(min(95.0, base_rate * multiplier), 1)


def simulate_evaluator(deck, grant, fit_breakdown):
    p = deck.get("product") or {}
    t = deck.get("team") or {}
    m = deck.get("market") or {}
    trc = deck.get("traction") or {}
    fa = deck.get("funding_ask") or {}
    imp = deck.get("impact") or {}
    excellence = 2.0
    if (p.get("trl") or 5) <= 5: excellence += 0.5
    if "brevet" in str(p.get("ip_status", "")).lower(): excellence += 0.5
    if (t.get("phds") or 0) >= 4: excellence += 0.5
    if "Nature" in str(t) or "Science" in str(t): excellence += 0.3
    if fit_breakdown.get("sector", 0) >= 70: excellence += 0.2
    excellence = min(5.0, excellence)
    impact = 1.5
    impact += min(1.5, math.log10(max(1, m.get("som_eur_m_yr5") or 1)) * 0.5)
    if (imp.get("co2_reduction_t_yr5") or 0) >= 100000: impact += 1.0
    if fit_breakdown.get("priorities", 0) >= 75: impact += 0.7
    if trc.get("letters_of_intent") or m.get("letters_of_intent"): impact += 0.3
    impact = min(5.0, impact)
    implementation = 2.0
    if (t.get("size") or 0) >= 8: implementation += 0.5
    if (trc.get("grants_received_eur") or 0) > 0: implementation += 0.5
    if fit_breakdown.get("budget", 0) >= 70: implementation += 0.5
    if trc.get("pilot_partners"): implementation += 0.5
    if (fa.get("co_financing_capacity_eur") or 0) > 0: implementation += 0.4
    implementation = min(5.0, implementation)
    ev = grant.get("evaluation", {})
    we = ev.get("excellence_weight", ev.get("innovation_weight", ev.get("relevance_weight", 0.34)))
    wi = ev.get("impact_weight", ev.get("environmental_impact_weight", ev.get("market_weight", 0.33)))
    wim = ev.get("implementation_weight", ev.get("team_weight", ev.get("maturity_weight", 0.33)))
    s = (we + wi + wim) or 1.0
    we, wi, wim = we / s, wi / s, wim / s
    weighted = excellence * we + impact * wi + implementation * wim
    return {
        "excellence": round(excellence, 2),
        "impact": round(impact, 2),
        "implementation": round(implementation, 2),
        "weighted": round(weighted, 2),
    }


def blend_probability(fit, statistical, evaluator_weighted):
    ev01 = 1 / (1 + math.exp(-(evaluator_weighted - 3.0) * 1.5))
    return round(0.45 * statistical + 0.30 * fit + 0.25 * ev01 * 100, 1)


def confidence_interval(blended, fit):
    band = 8 if fit >= 80 else 15 if fit >= 60 else 25
    return (max(0.0, round(blended - band, 1)), min(100.0, round(blended + band, 1)))


def tier_for(eligible, blended, fit):
    if not eligible:
        return "ineligible"
    if blended >= 55 or (fit >= 80 and blended >= 35):
        return "top"
    if blended >= 35:
        return "credible"
    if blended >= 15:
        return "stretch"
    return "discard"


def _calibrated_base_rate(grant_id: str, deck: dict, grant: dict) -> tuple[float, str]:
    """
    RULE 2 — Probability Calibration.
    Returns (base_rate, explanation) using calibrated baselines instead of
    inflating from fit score alone.
    """
    product = deck.get("product") or {}
    funding = deck.get("funding_ask") or {}
    traction = deck.get("traction") or {}
    trl = product.get("trl") or 5

    if grant_id in CALIBRATED_BASELINES:
        lo, hi = CALIBRATED_BASELINES[grant_id]
        base = (lo + hi) / 2
        adjustments = []

        # Programme-specific adjustments
        if grant_id == "bpifrance_adi":
            if (traction.get("revenue_eur_last_year") or 0) > 0:
                base = min(hi, base + 10)
                adjustments.append("+10% revenue > 0")
            if trl >= 5:
                base = min(hi, base + 5)
                adjustments.append(f"+5% TRL {trl} >= 5")

        elif grant_id == "eurostars3":
            if not funding.get("foreign_partner_confirmed", False):
                base = base * 0.5
                adjustments.append("×0.5 no foreign partner confirmed")

        elif grant_id == "ademe_perfecto":
            has_lca = product.get("lca_methodology", False)
            if not has_lca:
                base = lo  # floor at low end
                adjustments.append(f"floored at {lo}% — ecodesign not substantiated")

        elif grant_id == "eic_accelerator":
            # Stage 1 (short proposal) is 15-20%, full pipeline is 5-8%
            adjustments.append("overall pipeline rate")

        elif grant_id.startswith("horizon_cluster"):
            if not funding.get("consortium_confirmed", False):
                base = 0.0  # Cannot apply solo
                adjustments.append("=0% consortium not confirmed")

        # Cap at range ceiling
        base = min(hi, max(0.0, base))
        adj_str = "; ".join(adjustments) if adjustments else "standard"
        explanation = f"{base:.0f}% (baseline: {lo:.0f}–{hi:.0f}%, adjustments: {adj_str})"
        return base, explanation
    else:
        # Fallback to grant's embedded success_rate_pct
        rate = grant.get("success_rate_pct", 10.0)
        return rate, f"{rate:.0f}% (from programme metadata)"


def _derive_key_risk(grant_id: str, warnings: list[str], blockers: list[str]) -> str:
    """Derive a single-sentence key risk for the programme."""
    if blockers:
        return blockers[0]
    if warnings:
        return warnings[0]
    risk_map = {
        "eic_accelerator": "Very low acceptance rate (~5-8%) — high competition from EU-wide deep tech SMEs.",
        "erc_poc": "Requires active ERC grant — verify PI eligibility before any preparation work.",
        "france2030_ilab": "Single annual wave, extremely competitive — only 75 laureates/year across all sectors.",
    }
    return risk_map.get(grant_id, "Standard competitive process — prepare a complete, evidence-backed submission.")


def _derive_next_action(grant_id: str, warnings: list[str], blockers: list[str]) -> str:
    """Derive a concrete next step for the founder within 7 days."""
    for b in blockers:
        bl = b.lower()
        if "erc" in bl: return NEXT_ACTION_MAP.get("erc_prerequisite", "")
        if "eic" in bl and "transition" in bl: return NEXT_ACTION_MAP.get("eic_prior_project", "")
        if "consortium" in bl: return NEXT_ACTION_MAP.get("consortium_required", "")
        if "country" in bl or "region" in bl: return NEXT_ACTION_MAP.get("country_region", "")
        if "trl" in bl: return NEXT_ACTION_MAP.get("trl", "")
        if "sme" in bl: return NEXT_ACTION_MAP.get("sme_required", "")
    for w in warnings:
        wl = w.lower()
        if "partner" in wl and "eureka" in wl: return NEXT_ACTION_MAP.get("foreign_partner", "")
        if "ecodesign" in wl or "lca" in wl: return NEXT_ACTION_MAP.get("ecodesign_lca", "")
        if "consortium" in wl: return NEXT_ACTION_MAP.get("consortium_required", "")
    if grant_id == "eic_accelerator":
        return "Prepare a 5-page Short Proposal aligned to the current EIC work programme challenge areas."
    return "Review the programme page for the current call and prepare your submission outline."


def _amount_coherence_warnings(grant: dict, deck: dict) -> list[str]:
    """RULE 3 — Amount coherence check: project scale, coverage cap."""
    warns = []
    funding = deck.get("funding_ask") or {}
    ask = funding.get("amount_eur") or 0
    typical = grant.get("budget", {}).get("typical_total_project_eur", 0)
    grant_max = grant.get("budget", {}).get("grant_max_eur", 0)

    # Check 1: minimum project scale
    if typical >= 4_000_000 and ask > 0 and ask < 500_000:
        warns.append(f"Project scale mismatch — programme targets €{typical/1e6:.0f}M+ projects, your ask is €{ask/1e3:.0f}k")

    # Check 2: coverage cap — no single grant > 70% of total ask (unless direct subvention)
    if ask > 0 and grant_max > 0:
        coverage = grant_max / ask
        instrument = grant.get("budget", {}).get("instrument", "")
        if coverage > 0.70 and instrument not in ("advance_recoverable", "subvention"):
            pass  # OK for subventions; for others, note it
            # Actually only warn if coverage > 100% which is more useful
    return warns


def match_grant(deck: dict, grant: dict) -> GrantMatch:
    """
    Core matching function with:
    - RULE 1: Hard eligibility gates (via check_eligibility)
    - RULE 2: Calibrated probability baselines
    - RULE 3: Amount coherence warnings
    - RULE 4: Deadline urgency protocol (45-day threshold)
    - RULE 5: Structured per-programme output fields
    """
    eligible, blockers, warnings = check_eligibility(deck, grant)
    fit_total, fit_breakdown = compute_fit(deck, grant)

    # RULE 2: calibrated base rate
    base_rate, prob_explanation = _calibrated_base_rate(grant["id"], deck, grant)
    stat = statistical_estimate(base_rate, fit_total) if eligible else 0.0
    evaluator = simulate_evaluator(deck, grant, fit_breakdown)
    blended = blend_probability(fit_total, stat, evaluator["weighted"]) if eligible else 0.0

    # RULE 2: cap blended probability at calibrated ceiling
    if grant["id"] in CALIBRATED_BASELINES and eligible:
        _, hi = CALIBRATED_BASELINES[grant["id"]]
        # Allow blended to exceed hi by at most 50% (fit bonus), never way beyond
        cap = hi * 1.5
        if blended > cap:
            blended = round(cap, 1)

    ci = confidence_interval(blended, fit_total) if eligible else (0.0, 0.0)
    tier = tier_for(eligible, blended, fit_total)

    # RULE 3: Amount coherence
    coherence_warns = _amount_coherence_warnings(grant, deck)
    warnings.extend(coherence_warns)

    # RULE 4: Deadline urgency protocol
    dl = deadline_info(grant["id"])
    if not eligible:
        headline = f"Not eligible — {blockers[0]}"
    else:
        base_hl = {"top": "Top match — prioritize",
                   "credible": "Credible — work it",
                   "stretch": "Long shot — high upside",
                   "discard": "Low probability"}[tier]
        if dl["urgency"] == "urgent":
            days = dl["days_until"] or 0
            if days <= 45:
                # RULE 4: strict 45-day protocol
                headline = f"{base_hl} · 🔴 URGENT — {days} days to deadline"
                warnings.append(
                    f"URGENT: Submitting in {days} days requires a complete, submission-ready "
                    f"dossier NOW — not a draft. Confirm readiness before including in the plan."
                )
                # If eligibility has warnings (conditional), flag risk
                if any("consortium" in w.lower() or "partner" in w.lower() for w in warnings[:-1]):
                    warnings.append(
                        "Uncertain eligibility + imminent deadline — confirm all conditions "
                        "before investing submission effort."
                    )
            else:
                headline = f"{base_hl} · ⚠ deadline in {days} days"
        elif dl["urgency"] == "soon":
            headline = f"{base_hl} · deadline in {dl['days_until']} days"
        elif dl["urgency"] == "passed":
            headline = f"{base_hl} · ⚠ 2026 cycle closed — next 2027"
        else:
            headline = base_hl

    # RULE 5: structured output fields
    if not eligible:
        elig_status = f"EXCLUDED ({blockers[0]})"
    elif warnings:
        elig_status = f"CONDITIONAL ({warnings[0]})"
    else:
        elig_status = "CONFIRMED"

    mid_funding = (grant["budget"]["grant_min_eur"] + grant["budget"]["grant_max_eur"]) / 2
    expected_value = round(blended / 100 * mid_funding, 0) if eligible else 0
    key_risk = _derive_key_risk(grant["id"], warnings, blockers)
    next_action = _derive_next_action(grant["id"], warnings, blockers)

    return GrantMatch(
        grant_id=grant["id"],
        grant_name=grant["name"],
        level=grant["level"],
        eligible=eligible,
        blockers=blockers,
        warnings=warnings,
        fit_total=fit_total,
        fit_breakdown=fit_breakdown,
        base_success_rate_pct=base_rate,
        statistical_estimate_pct=stat,
        evaluator=evaluator,
        blended_probability_pct=blended,
        confidence_interval_pct=ci,
        funding_range_eur=(grant["budget"]["grant_min_eur"], grant["budget"]["grant_max_eur"]),
        url=grant.get("url", ""),
        headline=headline,
        priority_tier=tier,
        next_deadline=dl["next_deadline"],
        days_until_deadline=dl["days_until"],
        urgency=dl["urgency"],
        cut_off_pattern=dl["pattern"],
        stage_label=dl.get("stage"),
        eligibility_status=elig_status,
        probability_explanation=prob_explanation,
        expected_value_eur=expected_value,
        key_risk=key_risk,
        next_action=next_action,
    )


def evaluate_combinations(matches: list[GrantMatch], db_meta: dict) -> list[dict]:
    incompatible = {tuple(sorted(p)) for p in db_meta.get("incompatible_pairs", [])}
    synergies = {tuple(sorted(p)) for p in db_meta.get("synergistic_pairs", [])}
    eligible = sorted([m for m in matches if m.eligible],
                      key=lambda m: -m.blended_probability_pct)[:12]
    candidates = []
    n = len(eligible)
    for i in range(n):
        for j in range(i + 1, n):
            for k in [-1] + list(range(j + 1, n)):
                combo = [eligible[i], eligible[j]] + ([eligible[k]] if k >= 0 else [])
                ids = tuple(m.grant_id for m in combo)
                ok = True
                syn = 0
                for ii in range(len(ids)):
                    for jj in range(ii + 1, len(ids)):
                        pair = tuple(sorted([ids[ii], ids[jj]]))
                        if pair in incompatible:
                            ok = False
                            break
                        if pair in synergies:
                            syn += 1
                    if not ok: break
                if not ok: continue
                ev = sum(m.blended_probability_pct / 100 *
                         (m.funding_range_eur[0] + m.funding_range_eur[1]) / 2 for m in combo)
                candidates.append({
                    "grants": list(ids),
                    "names": [m.grant_name for m in combo],
                    "expected_value_eur": round(ev * (1.0 + 0.10 * syn), 0),
                    "synergy_pairs": syn,
                    "total_max_funding_eur": sum(m.funding_range_eur[1] for m in combo),
                })
    return sorted(candidates, key=lambda c: -c["expected_value_eur"])[:5]


# -----------------------------------------------------------------------------
# Financing plan (use-of-funds + funding sources) — VC-grade dossier
# -----------------------------------------------------------------------------

USE_OF_FUNDS_TEMPLATES = {
    # Per-sector default split. Keys are normalized weights summing to 1.0.
    # Categories: rd, team, equipment, ip, gtm, ops
    "deeptech_default": {
        "rd": 0.45, "team": 0.25, "equipment": 0.10, "ip": 0.08, "gtm": 0.07, "ops": 0.05,
    },
    "clean_energy": {
        "rd": 0.35, "team": 0.20, "equipment": 0.25, "ip": 0.08, "gtm": 0.07, "ops": 0.05,
    },
    "advanced_materials": {
        "rd": 0.40, "team": 0.20, "equipment": 0.20, "ip": 0.10, "gtm": 0.05, "ops": 0.05,
    },
    "manufacturing": {
        "rd": 0.30, "team": 0.20, "equipment": 0.30, "ip": 0.05, "gtm": 0.10, "ops": 0.05,
    },
    "health": {
        "rd": 0.40, "team": 0.20, "equipment": 0.10, "ip": 0.10, "gtm": 0.10, "ops": 0.10,
        # NB: in health, "ip" includes regulatory (CE, FDA) costs
    },
    "biotech": {
        "rd": 0.50, "team": 0.20, "equipment": 0.10, "ip": 0.10, "gtm": 0.05, "ops": 0.05,
    },
    "ai": {
        "rd": 0.30, "team": 0.40, "equipment": 0.10, "ip": 0.05, "gtm": 0.10, "ops": 0.05,
    },
    "digital": {
        "rd": 0.30, "team": 0.40, "equipment": 0.05, "ip": 0.05, "gtm": 0.15, "ops": 0.05,
    },
    "cybersecurity": {
        "rd": 0.35, "team": 0.35, "equipment": 0.05, "ip": 0.10, "gtm": 0.10, "ops": 0.05,
    },
    "agritech": {
        "rd": 0.35, "team": 0.20, "equipment": 0.20, "ip": 0.05, "gtm": 0.15, "ops": 0.05,
    },
}

# What budget categories each grant programme typically funds.
GRANT_CATEGORIES_COVERED = {
    # EU
    "erc_starting": {"rd": 1.0, "team": 1.0},
    "erc_poc": {"rd": 0.8, "ip": 0.2},
    "msca_pf": {"team": 1.0, "rd": 0.5},
    "horizon_cluster1_health": {"rd": 0.7, "team": 0.6, "equipment": 0.4, "gtm": 0.2, "ip": 0.3},
    "horizon_cluster4_digital": {"rd": 0.7, "team": 0.6, "equipment": 0.4, "gtm": 0.2},
    "horizon_cluster5_climate": {"rd": 0.7, "team": 0.6, "equipment": 0.5, "gtm": 0.2},
    "horizon_cluster6_food": {"rd": 0.7, "team": 0.6, "equipment": 0.5, "gtm": 0.2},
    "eic_accelerator": {"rd": 0.5, "team": 0.4, "equipment": 0.3, "ip": 0.3, "gtm": 0.5},
    "eic_pathfinder_open": {"rd": 0.9, "team": 0.7},
    "eic_pathfinder_challenges": {"rd": 0.9, "team": 0.7},
    "eic_transition": {"rd": 0.7, "team": 0.5, "ip": 0.4, "gtm": 0.3},
    "eit_climate_kic": {"rd": 0.5, "gtm": 0.6, "team": 0.4},
    "eit_health": {"rd": 0.5, "ip": 0.5, "gtm": 0.5, "team": 0.4},
    "innovation_fund_small": {"equipment": 0.8, "rd": 0.4},
    "innovation_fund_large": {"equipment": 0.8, "rd": 0.3},
    "digital_europe": {"rd": 0.5, "equipment": 0.5, "gtm": 0.3},
    "life_clean_energy": {"rd": 0.4, "gtm": 0.5, "team": 0.4},
    "life_climate": {"rd": 0.5, "team": 0.5, "gtm": 0.4},
    "life_nature": {"rd": 0.5, "team": 0.5, "ops": 0.4},
    "eurostars3": {"rd": 0.7, "team": 0.5, "ip": 0.3, "gtm": 0.3},
    "edf": {"rd": 0.7, "team": 0.5, "equipment": 0.5},
    "cef_digital": {"equipment": 0.7, "rd": 0.3},
    # France national
    "france2030_inov": {"rd": 0.6, "team": 0.5, "equipment": 0.3, "ip": 0.3, "gtm": 0.3},
    "france2030_idemo": {"rd": 0.5, "equipment": 0.5, "team": 0.3, "gtm": 0.3},
    "france2030_ilab": {"rd": 0.7, "ip": 0.3, "team": 0.3},
    "frenchtech2030": {"team": 0.3, "gtm": 0.3, "rd": 0.3},
    "bpifrance_adi": {"rd": 0.6, "team": 0.5, "ip": 0.3, "gtm": 0.3},
    "bpifrance_concours_innovation": {"rd": 0.6, "team": 0.5, "ip": 0.3, "gtm": 0.3},
    "ademe_demonstrateurs": {"rd": 0.5, "equipment": 0.6, "team": 0.4, "gtm": 0.3},
    "ademe_perfecto": {"ip": 0.7, "rd": 0.3},
    # FR regional
    "feder_idf_innovation": {"rd": 0.5, "team": 0.4, "equipment": 0.3, "gtm": 0.2},
    "innovup_idf": {"rd": 0.6, "team": 0.4, "ip": 0.3, "gtm": 0.3},
    "paris_saclay_pia": {"rd": 0.7, "team": 0.4, "ip": 0.3},
    "ara_pack_ambition": {"rd": 0.5, "team": 0.4, "equipment": 0.3, "gtm": 0.2},
    "occitanie_readynov": {"rd": 0.5, "team": 0.4, "equipment": 0.3, "gtm": 0.2},
    "hdf_startinnov": {"rd": 0.5, "team": 0.4, "equipment": 0.3, "gtm": 0.2},
    "naq_aap_innovation": {"rd": 0.5, "team": 0.4, "equipment": 0.3, "gtm": 0.2},
}

CATEGORY_LABELS = {
    "rd": "R&D / Pilot Line",
    "team": "Team Expansion",
    "equipment": "Equipment / Lab",
    "ip": "IP, Certifications & Regulatory",
    "gtm": "Go-To-Market",
    "ops": "Operating",
}

CATEGORY_COLORS = {
    "rd":        "#c2410c",  # accent
    "team":      "#1e3a5f",  # navy
    "equipment": "#4d7c0f",  # olive
    "ip":        "#7e22ce",  # purple
    "gtm":       "#a16207",  # amber
    "ops":       "#475569",  # slate
}


def _credible_funding_ask(deck: dict) -> float:
    """
    If the founder hasn't given a credible amount, infer one from sector + TRL.
    Used as a fallback so VCs see a number they expect to see.
    """
    fa = (deck.get("funding_ask") or {})
    if fa.get("amount_eur"):
        return float(fa["amount_eur"])
    trl = (deck.get("product") or {}).get("trl") or 5
    sectors = set(s.lower() for s in (deck.get("product") or {}).get("sectors", []))
    is_capex_heavy = bool(sectors & {"clean_energy", "manufacturing", "advanced_materials",
                                      "energy_storage", "biotech", "agritech"})
    # TRL 4 → 1.5M, TRL 5 → 3M, TRL 6 → 5M, TRL 7 → 8M (capex heavy +50%)
    base = {3: 1_000_000, 4: 1_500_000, 5: 3_000_000, 6: 5_000_000,
            7: 8_000_000, 8: 12_000_000}.get(trl, 3_000_000)
    return base * (1.5 if is_capex_heavy else 1.0)


def _pick_template(deck: dict) -> dict[str, float]:
    sectors = [s.lower() for s in (deck.get("product") or {}).get("sectors", [])]
    for s in sectors:
        if s in USE_OF_FUNDS_TEMPLATES:
            return USE_OF_FUNDS_TEMPLATES[s]
    return USE_OF_FUNDS_TEMPLATES["deeptech_default"]


async def _llm_use_of_funds(deck: dict, total_eur: float) -> dict[str, float] | None:
    """Use Cerebras to refine the use-of-funds breakdown. Returns weights summing to 1.0."""
    if not CEREBRAS_API_KEY or not httpx:
        return None
    prompt = f"""Given this startup pitchdeck and a total funding ask of {total_eur:.0f} EUR, propose a credible use-of-funds breakdown that a VC investor would expect to see. Return ONLY a JSON object with these six keys (weights must sum to 1.0):

{{"rd": float, "team": float, "equipment": float, "ip": float, "gtm": float, "ops": float}}

Guidelines:
- rd = research, prototype iteration, pilot line
- team = salaries for team expansion (engineers, scientists, ops)
- equipment = lab gear, manufacturing tooling, specialized hardware
- ip = patents, certifications (CE, FDA, IEC), regulatory work
- gtm = sales, marketing, partnerships, customer success
- ops = legal, finance, real estate, general overhead
- Be sector-aware: clean energy/manufacturing → equipment-heavy; AI/SaaS → team-heavy; health/biotech → ip-heavy.

Pitchdeck:
{json.dumps(deck, ensure_ascii=False)[:4000]}"""
    try:
        content = await cerebras_chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
        data = json.loads(content)
        # Normalize
        s = sum(float(data.get(k, 0)) for k in CATEGORY_LABELS)
        if s <= 0:
            return None
        return {k: float(data.get(k, 0)) / s for k in CATEGORY_LABELS}
    except Exception as e:
        sys.stderr.write(f"[plan] LLM use-of-funds failed: {e}\n")
        return None


def _allocate_grants_to_categories(matches: list[GrantMatch],
                                    use_of_funds_eur: dict[str, float]) -> tuple[dict[str, list[dict]], dict[str, float]]:
    """
    Greedy allocation: for each top eligible grant (sorted by probability),
    cover budget categories it can finance. Returns:
      - allocation_by_grant: {grant_id: [{category, eur}]}
      - covered_by_category: {category: total_eur_covered}
    """
    allocation: dict[str, list[dict]] = {}
    remaining = dict(use_of_funds_eur)
    covered: dict[str, float] = {k: 0.0 for k in use_of_funds_eur}
    eligible = [m for m in matches if m.eligible][:6]
    eligible.sort(key=lambda m: -m.blended_probability_pct)

    for m in eligible:
        # How much grant can deliver: midpoint of its range × its blended probability
        mid_grant = (m.funding_range_eur[0] + m.funding_range_eur[1]) / 2
        # We weight by probability to be honest with VCs (expected value, not theoretical max)
        expected = mid_grant * m.blended_probability_pct / 100
        if expected < 50_000:
            continue
        cats_map = GRANT_CATEGORIES_COVERED.get(m.grant_id, {"rd": 0.5, "team": 0.5})
        # Sort categories by coverage strength × remaining budget
        eligible_cats = sorted(
            ((c, w) for c, w in cats_map.items() if remaining.get(c, 0) > 0),
            key=lambda cw: -(cw[1] * remaining.get(cw[0], 0))
        )
        if not eligible_cats:
            continue
        # Distribute the grant amount across covered categories proportionally
        weight_sum = sum(w for _, w in eligible_cats)
        allocation[m.grant_id] = []
        amount_left = expected
        for cat, weight in eligible_cats:
            if amount_left <= 0:
                break
            target = expected * (weight / weight_sum)
            give = min(target, remaining[cat], amount_left)
            if give < 1000:
                continue
            allocation[m.grant_id].append({
                "category": cat,
                "category_label": CATEGORY_LABELS[cat],
                "eur": round(give, 0),
            })
            covered[cat] = round(covered[cat] + give, 0)
            remaining[cat] = max(0.0, remaining[cat] - give)
            amount_left -= give

    return allocation, covered


async def build_financing_plan(deck: dict, matches: list[GrantMatch],
                                combos: list[dict]) -> dict:
    """
    Build a VC-grade financing plan:
      - total_ask_eur (from deck or inferred)
      - use_of_funds: {category: {eur, pct}}  (sums to 100%)
      - funding_sources: {grants_total_eur, equity_gap_eur, founder_cofi_eur}
      - allocation_by_grant: which grant covers which category
      - covered_by_category: total covered per line item
      - synthetic_summary: 2-3 sentence VC-style summary (Cerebras)
    """
    total = _credible_funding_ask(deck)
    weights = await _llm_use_of_funds(deck, total) or _pick_template(deck)
    use_of_funds = {
        cat: {
            "label": CATEGORY_LABELS[cat],
            "color": CATEGORY_COLORS[cat],
            "pct": round(weights[cat] * 100, 1),
            "eur": round(total * weights[cat], 0),
        }
        for cat in CATEGORY_LABELS
    }
    use_of_funds_eur = {cat: total * weights[cat] for cat in CATEGORY_LABELS}

    allocation, covered = _allocate_grants_to_categories(matches, use_of_funds_eur)
    grants_total = sum(sum(a["eur"] for a in items) for items in allocation.values())
    cofi = float((deck.get("funding_ask") or {}).get("co_financing_capacity_eur") or 0)
    equity_gap = max(0.0, total - grants_total - cofi)

    funding_sources = [
        {"label": "Grants (expected, prob-weighted)", "eur": round(grants_total, 0),
         "color": "#c2410c"},
        {"label": "Founder co-financing", "eur": round(cofi, 0), "color": "#4d7c0f"},
        {"label": "Equity to raise", "eur": round(equity_gap, 0), "color": "#1e3a5f"},
    ]

    # Per-grant breakdown for the dossier table
    grants_breakdown = []
    for grant_id, items in allocation.items():
        m = next((m for m in matches if m.grant_id == grant_id), None)
        if not m:
            continue
        grants_breakdown.append({
            "grant_id": grant_id,
            "grant_name": m.grant_name,
            "level": m.level,
            "probability_pct": m.blended_probability_pct,
            "funding_range_eur": list(m.funding_range_eur),
            "expected_eur": round(sum(a["eur"] for a in items), 0),
            "categories_covered": items,
        })
    grants_breakdown.sort(key=lambda x: -x["expected_eur"])

    summary = await _plan_summary(deck, total, grants_total, equity_gap, grants_breakdown)

    # Pre-render SVG so the frontend can drop it in directly (no JS chart lib needed)
    pie_html = pie_chart_svg(use_of_funds)
    stack_html = funding_stack_svg(funding_sources, total)

    return {
        "total_ask_eur": round(total, 0),
        "ask_inferred": (deck.get("funding_ask") or {}).get("amount_eur") in (None, 0),
        "use_of_funds": use_of_funds,
        "funding_sources": funding_sources,
        "grants_breakdown": grants_breakdown[:5],
        "covered_by_category": {k: round(v, 0) for k, v in covered.items()},
        "summary": summary,
        "pie_chart_svg": pie_html,
        "stack_bar_svg": stack_html,
    }


async def _plan_summary(deck: dict, total: float, grants_total: float,
                          equity_gap: float, breakdown: list[dict]) -> str:
    """One-paragraph VC-style summary."""
    if not CEREBRAS_API_KEY or not httpx:
        top = breakdown[0]["grant_name"] if breakdown else "the top eligible grant"
        return (f"This plan finances a {total/1e6:.1f} M€ project with "
                f"{grants_total/1e6:.1f} M€ of probability-weighted grant funding "
                f"(led by {top}) and a remaining {equity_gap/1e6:.1f} M€ equity gap.")
    company = (deck.get("company") or {}).get("name", "The company")
    grants_summary = ", ".join(f"{b['grant_name']} ({b['expected_eur']/1e6:.1f}M)"
                                  for b in breakdown[:3])
    prompt = f"""Write a single 2-sentence VC-grade executive summary of this financing plan. Tone: factual, anchored, no buzzwords.

Company: {company}
Total ask: {total:.0f} EUR
Grants expected (prob-weighted): {grants_total:.0f} EUR
Top grant sources: {grants_summary}
Equity gap to raise: {equity_gap:.0f} EUR

Output: 2 sentences, no markdown, no bullet points."""
    try:
        return (await cerebras_chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=200,
        )).strip()
    except Exception:
        top = breakdown[0]["grant_name"] if breakdown else "the top eligible grant"
        return (f"This plan finances a {total/1e6:.1f} M€ project with "
                f"{grants_total/1e6:.1f} M€ of probability-weighted grant funding "
                f"(led by {top}) and a remaining {equity_gap/1e6:.1f} M€ equity gap.")


# -----------------------------------------------------------------------------
# SVG visualizations
# -----------------------------------------------------------------------------

def pie_chart_svg(use_of_funds: dict[str, dict], size: int = 320) -> str:
    """
    Inline donut SVG of the use-of-funds breakdown. Print-friendly,
    no external CSS or fonts needed.
    """
    cx, cy = size / 2, size / 2
    radius = size * 0.42
    inner = size * 0.25  # donut hole
    cumul = 0.0
    paths = []
    legend = []
    for cat, info in use_of_funds.items():
        if info["pct"] <= 0:
            continue
        start_angle = cumul / 100 * 2 * math.pi - math.pi / 2
        cumul += info["pct"]
        end_angle = cumul / 100 * 2 * math.pi - math.pi / 2
        large = 1 if (end_angle - start_angle) > math.pi else 0
        x1, y1 = cx + radius * math.cos(start_angle), cy + radius * math.sin(start_angle)
        x2, y2 = cx + radius * math.cos(end_angle), cy + radius * math.sin(end_angle)
        x3, y3 = cx + inner * math.cos(end_angle), cy + inner * math.sin(end_angle)
        x4, y4 = cx + inner * math.cos(start_angle), cy + inner * math.sin(start_angle)
        d = (f"M {x1:.2f} {y1:.2f} A {radius} {radius} 0 {large} 1 {x2:.2f} {y2:.2f} "
             f"L {x3:.2f} {y3:.2f} A {inner} {inner} 0 {large} 0 {x4:.2f} {y4:.2f} Z")
        paths.append(f'<path d="{d}" fill="{info["color"]}" />')
        # Label outside the slice
        mid = (start_angle + end_angle) / 2
        lx = cx + (radius + 8) * math.cos(mid)
        ly = cy + (radius + 8) * math.sin(mid)
        anchor = "start" if math.cos(mid) > 0.1 else ("end" if math.cos(mid) < -0.1 else "middle")
        if info["pct"] >= 5:  # only label slices ≥5%
            paths.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
                f'font-size="11" fill="#1a1a18" font-weight="600">{info["pct"]:.0f}%</text>'
            )
        legend.append(
            f'<div class="lg-row"><span class="lg-sw" style="background:{info["color"]}"></span>'
            f'<span class="lg-lb">{info["label"]}</span>'
            f'<span class="lg-vl">{info["eur"]/1e3:.0f} k€ <em>({info["pct"]:.0f}%)</em></span></div>'
        )
    svg = (f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">'
           + "".join(paths) + '</svg>')
    return f'<div class="piechart">{svg}<div class="pielegend">{"".join(legend)}</div></div>'


def funding_stack_svg(funding_sources: list[dict], total: float, width: int = 480) -> str:
    """Horizontal stacked bar of funding sources."""
    if total <= 0:
        return ""
    height = 36
    cumul = 0.0
    bars = []
    legend = []
    for src in funding_sources:
        if src["eur"] <= 0:
            continue
        w = src["eur"] / total * width
        bars.append(f'<rect x="{cumul:.1f}" y="0" width="{w:.1f}" height="{height}" fill="{src["color"]}" />')
        if w >= 30:
            label = f'{src["eur"]/1e6:.1f}M€'
            bars.append(f'<text x="{cumul + w/2:.1f}" y="{height/2 + 4}" '
                        f'text-anchor="middle" font-size="11" fill="white" font-weight="600">{label}</text>')
        cumul += w
        legend.append(
            f'<div class="lg-row"><span class="lg-sw" style="background:{src["color"]}"></span>'
            f'<span class="lg-lb">{src["label"]}</span>'
            f'<span class="lg-vl">{src["eur"]/1e6:.2f} M€</span></div>'
        )
    svg = (f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
           f'xmlns="http://www.w3.org/2000/svg" style="border-radius:6px;">'
           + "".join(bars) + '</svg>')
    return f'<div class="stackbar">{svg}<div class="pielegend">{"".join(legend)}</div></div>'


# -----------------------------------------------------------------------------
# Cerebras client (LLM)
# -----------------------------------------------------------------------------

PARSE_SYSTEM_PROMPT = """You are a precise extraction agent. Read the pitchdeck text and output a JSON object conforming to this schema. Use null for missing values, never invent. Output ONLY the JSON object, no prose, no markdown fences.

Schema:
{
  "company": {"name": str, "country": "ISO2 code (FR, DE, ...)", "region": str|null, "city": str|null, "founded": int|null, "employees": int|null, "sme": bool|null, "deeptech": bool|null},
  "product": {"one_liner": str, "sectors": ["clean_energy"|"climate_tech"|"circular_economy"|"advanced_materials"|"manufacturing"|"mobility"|"energy_storage"|"health"|"biotech"|"medical_devices"|"digital_health"|"digital"|"ai"|"cybersecurity"|"semiconductors"|"robotics"|"photonics"|"quantum"|"space"|"defence"|"agritech"|"bioeconomy"|"food"|"water"|"biodiversity"], "trl": int 1-9 | null, "ip_status": str|null, "dual_use": bool|null},
  "team": {"size": int|null, "phds": int|null, "gender_balance_pct_female": int|null, "prior_erc_grant": bool|null, "erc_grant_type": "Starting|Consolidator|Advanced|Synergy"|null, "ecodesign_expert": bool|null},
  "traction": {"revenue_eur_last_year": number|null, "grants_received_eur": number|null, "letters_of_intent": int|null, "pilot_partners": [str]},
  "funding_ask": {"amount_eur": number|null, "horizon_months": int|null, "co_financing_capacity_eur": number|null, "open_to_consortium": bool|null, "consortium_confirmed": bool|null, "foreign_partner_confirmed": bool|null},
  "product_eligibility": {"prior_eic_pathfinder": bool|null, "prior_erc_poc": bool|null, "lca_methodology": bool|null},
  "impact": {"co2_reduction_t_yr5": number|null, "green_deal_alignment": [str]}
}"""

DRAFT_SYSTEM_PROMPT = """You are a senior grant application writer specializing in European and French funding programmes (Horizon Europe, EIC, Bpifrance, ADEME, France 2030).

Given a pitchdeck JSON and a target grant, write a 200-word draft of the "Excellence" section tailored to the startup's specific sector, TRL, and team profile.

Sector-specific emphasis:
- clean_energy / climate_tech: quantify CO2/GHG reduction, Green Deal & Fit-for-55 alignment, CAPEX maturity
- health / biotech: clinical evidence pathway, regulatory milestones (CE, FDA), patient outcome metrics
- ai / digital: technical differentiation, dataset scale, generalization evidence, benchmark comparisons
- advanced_materials / deeptech: IP position (patents filed/granted), publications in peer-reviewed journals, scale-up pathway
- cybersecurity: threat model, certification roadmap (ANSSI, Common Criteria), national security relevance
- space: TRL progression, launch timeline, payload specifications

Tone: precise, technical, factual — no buzzwords. Anchor every claim in the pitchdeck data (numbers, names, TRL, patents). End with one sentence on the strategic fit with the grant's stated priorities."""


async def cerebras_chat(messages: list[dict], temperature: float = 0.2,
                         max_tokens: int = 2000) -> str:
    """Call Cerebras OpenAI-compatible API. Returns content string."""
    if not CEREBRAS_API_KEY or not httpx:
        raise RuntimeError("CEREBRAS_API_KEY not set or httpx missing")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            CEREBRAS_URL,
            headers={
                "Authorization": f"Bearer {CEREBRAS_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": CEREBRAS_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


# -----------------------------------------------------------------------------
# Pitchdeck parser (Cerebras → structured JSON; fallback to heuristic)
# -----------------------------------------------------------------------------

async def parse_pitchdeck(text: str) -> dict:
    """LLM-based extraction with a deterministic fallback if no API key."""
    if CEREBRAS_API_KEY and httpx:
        try:
            content = await cerebras_chat(
                messages=[
                    {"role": "system", "content": PARSE_SYSTEM_PROMPT},
                    {"role": "user", "content": text[:12000]},
                ],
                temperature=0.0,
                max_tokens=1500,
            )
            content = content.strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\n?", "", content)
                content = re.sub(r"\n?```$", "", content)
            deck = json.loads(content)
            # Merge product_eligibility fields into product for check_eligibility()
            pe = deck.pop("product_eligibility", None)
            if pe and isinstance(pe, dict):
                prod = deck.setdefault("product", {})
                for k, v in pe.items():
                    if v is not None:
                        prod[k] = v
            return deck
        except Exception as e:
            sys.stderr.write(f"[parse] Cerebras failed, falling back: {e}\n")
    return heuristic_parse(text)



def heuristic_parse(text: str) -> dict:
    """Best-effort regex extraction. Used when no LLM is available."""
    t = text.lower()
    sectors = []
    sector_kw = {
        "clean_energy": ["solar", "wind", "renewable", "energy", "h2", "hydrogen"],
        "climate_tech": ["climate", "carbon", "co2", "ghg", "decarbon"],
        "ai": ["ai ", "artificial intelligence", "machine learning", "ml ", "llm", "deep learning"],
        "biotech": ["biotech", "molecule", "protein", "genom", "drug"],
        "health": ["medical", "patient", "clinical", "health"],
        "advanced_materials": ["material", "perovskite", "graphene", "nano"],
        "manufacturing": ["manufactur", "production", "factory", "pilot line"],
        "circular_economy": ["circular", "recycling", "reuse"],
        "agritech": ["agritech", "farm", "crop"],
        "mobility": ["mobility", "transport", "vehicle", "aircraft"],
        "space": ["satellite", "space", "orbit"],
        "cybersecurity": ["cyber", "security", "encrypt"],
        "quantum": ["quantum"],
        "robotics": ["robot"],
        "semiconductors": ["semiconductor", "chip", "wafer"],
    }
    for k, kws in sector_kw.items():
        if any(w in t for w in kws):
            sectors.append(k)

    country = None
    for code, kws in {"FR": ["france", "french", "paris"], "DE": ["germany", "german", "berlin"],
                      "ES": ["spain", "spanish", "madrid"], "IT": ["italy", "italian", "milan"],
                      "NL": ["netherlands", "dutch", "amsterdam"], "BE": ["belgium", "brussels"]}.items():
        if any(w in t for w in kws):
            country = code
            break

    region = None
    for r in ["île-de-france", "ile-de-france", "auvergne-rhône-alpes", "occitanie",
              "hauts-de-france", "nouvelle-aquitaine", "paca", "bretagne", "paris-saclay"]:
        if r in t:
            region = r.title().replace("-", "-")
            break

    trl_match = re.search(r"trl\s*[:=]?\s*(\d)", t)
    trl = int(trl_match.group(1)) if trl_match else None

    amt = None
    am = re.search(r"(?:asking|raise|seek|cherche|demande)[^.€$]{0,40}([\d.,]+)\s*(?:m€|m\s*euro|million)", t)
    if am:
        try:
            amt = float(am.group(1).replace(",", ".")) * 1_000_000
        except ValueError:
            pass

    name_match = re.search(r"(?:^|\n)\s*([A-Z][A-Za-z0-9]{2,30})(?:\s+(?:is|develop|builds|fait|développe))", text)
    name = name_match.group(1) if name_match else "Unknown Company"

    phds = len(re.findall(r"\b(?:phd|ph\.d|doctorat)", t))
    size_match = re.search(r"(\d+)\s*(?:people|persons?|employees|employés|personnes)", t)
    size = int(size_match.group(1)) if size_match else None

    return {
        "company": {
            "name": name,
            "country": country,
            "region": region,
            "sme": True,
            "deeptech": "deeptech" in t or "research" in t or "patent" in t,
        },
        "product": {
            "one_liner": text[:200],
            "sectors": sectors or ["any"],
            "trl": trl,
            "ip_status": ("brevet" if "brevet" in t or "patent" in t else None),
            "dual_use": False,
        },
        "team": {"size": size, "phds": phds},
        "traction": {},
        "funding_ask": {
            "amount_eur": amt,
            "open_to_consortium": True,
        },
        "impact": {"green_deal_alignment": [s for s in ["clean_energy", "climate_tech", "circular_economy"] if s in sectors]},
    }


# -----------------------------------------------------------------------------
# File extraction (PDF / PPTX)
# -----------------------------------------------------------------------------

def extract_text_from_pdf(data: bytes) -> str:
    """Extract text from a PDF file."""
    if not HAS_PYPDF2:
        raise RuntimeError("pypdf not installed. Run: pip install pypdf")
    import io
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def extract_text_from_pptx(data: bytes) -> str:
    """Extract text from a PPTX file."""
    if not HAS_PPTX:
        raise RuntimeError("python-pptx not installed. Run: pip install python-pptx")
    import io
    prs = Presentation(io.BytesIO(data))
    slides = []
    for slide in prs.slides:
        parts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        parts.append(text)
            if shape.has_table:
                for row in shape.table.rows:
                    row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_text:
                        parts.append(" | ".join(row_text))
        if parts:
            slides.append("\n".join(parts))
    return "\n\n".join(slides)


# -----------------------------------------------------------------------------
# Agent (the "agentic" loop)
# -----------------------------------------------------------------------------

@dataclass
class AgentEvent:
    type: str  # "thinking" | "parsed" | "ask" | "matched" | "combos" | "plan" | "draft" | "dossier" | "done" | "error"
    payload: Any = None
    ts: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def sse(self) -> str:
        return f"data: {json.dumps({'type': self.type, 'payload': self.payload, 'ts': self.ts}, default=str)}\n\n"


# In-memory store for dossiers so the printable /dossier page can fetch by id.
# In production: Firestore. For hackathon demo: dict keyed by short id.
DOSSIER_STORE: dict[str, dict] = {}


class GrantAgent:
    """
    Multi-agent orchestrator. Each step is a named sub-agent that streams its
    reasoning live as Server-Sent Events. Sub-agents adapt their behaviour to
    the pitchdeck profile (sector, TRL, country, team) — different pitch, different output.

    Sub-agents:
      ParseAgent      — Cerebras Qwen 3 235B extraction → structured JSON
      ClarifyAgent    — detect and ask for critical missing fields
      GrantMatchAgent — score all 37 EU/FR programmes, detect sensitive sectors
      ComboAgent      — evaluate cumulable grant combinations
      PlanAgent       — VC-grade use-of-funds + funding sources
      VCMatchAgent    — scan European VC database for matching investors
      DraftAgent      — sector-adaptive Excellence section (Cerebras)
      DossierAgent    — assemble and persist the full dossier
    """

    CRITICAL_FIELDS = [
        ("product.trl", "What's your current TRL? (1=concept, 5=lab prototype validated, 7=industrial demonstrator, 9=deployed)"),
        ("funding_ask.amount_eur", "How much funding are you seeking, in euros?"),
        ("company.country", "What country is your company registered in? (ISO2, e.g. FR, DE)"),
    ]

    def __init__(self, pitchdeck_text: str = "", pitchdeck_json: dict | None = None,
                 user_clarifications: dict | None = None,
                 want_draft: bool = True):
        self.pitchdeck_text = pitchdeck_text
        self.pitchdeck_json = pitchdeck_json or {}
        self.user_clarifications = user_clarifications or {}
        self.want_draft = want_draft

    async def run(self) -> AsyncGenerator[AgentEvent, None]:
        try:
            # ── ParseAgent ───────────────────────────────────────────────────
            yield AgentEvent("thinking", "🔍 ParseAgent — reading pitchdeck with Cerebras Qwen 3 235B...")
            if not self.pitchdeck_json and self.pitchdeck_text:
                self.pitchdeck_json = await parse_pitchdeck(self.pitchdeck_text)
            self.pitchdeck_json = _deep_merge(self.pitchdeck_json, self.user_clarifications)
            yield AgentEvent("parsed", self.pitchdeck_json)

            # ── ClarifyAgent ─────────────────────────────────────────────────
            missing = self._critical_missing()
            if missing and not self.user_clarifications:
                yield AgentEvent("ask", {
                    "questions": missing,
                    "rationale": "These 3 fields determine eligibility for all 37 programmes — without them I can only give a degraded ranking.",
                })
                return

            # ── GrantMatchAgent ──────────────────────────────────────────────
            sectors = set(s.lower() for s in (self.pitchdeck_json.get("product") or {}).get("sectors", []))
            sensitive = sectors & SENSITIVE_SECTORS
            trl = (self.pitchdeck_json.get("product") or {}).get("trl")
            country = (self.pitchdeck_json.get("company") or {}).get("country", "?")
            yield AgentEvent("thinking",
                f"🎯 GrantMatchAgent — matching {country} · TRL {trl} · {', '.join(sectors) or 'unknown sectors'} "
                f"against {len(GRANTS_DB['grants'])} EU/FR programmes...")
            matches = [match_grant(self.pitchdeck_json, g) for g in GRANTS_DB["grants"]]
            matches.sort(key=lambda m: (not m.eligible, -m.blended_probability_pct))
            eligible_matches = [m for m in matches if m.eligible]
            stats = _matches_stats(matches)
            stats["sensitive_sectors"] = list(sensitive)
            yield AgentEvent("matched", {
                "matches": [m.to_dict() for m in matches],
                "stats": stats,
            })

            # Empty-state: zero eligible → surface blockers
            if not eligible_matches:
                blockers = _compute_top_blockers(matches)
                yield AgentEvent("no_match", {"blockers": blockers})

            # ── ComboAgent ───────────────────────────────────────────────────
            yield AgentEvent("thinking", "🔗 ComboAgent — evaluating cumulable grant combinations...")
            combos = evaluate_combinations(matches, GRANTS_DB["_meta"]["combinability_matrix"])
            yield AgentEvent("combos", combos)

            # ── PlanAgent ────────────────────────────────────────────────────
            yield AgentEvent("thinking", "📊 PlanAgent — building VC-grade financing plan with use-of-funds breakdown...")
            plan = await build_financing_plan(self.pitchdeck_json, matches, combos)
            yield AgentEvent("plan", plan)

            # ── VCMatchAgent ─────────────────────────────────────────────────
            yield AgentEvent("thinking",
                f"🏦 VCMatchAgent — scanning {len(VC_DB)} European VCs for sector + stage alignment...")
            vc_matches = match_vcs(self.pitchdeck_json, top_n=8)
            yield AgentEvent("vc_matches", vc_matches)

            # ── DraftAgent ───────────────────────────────────────────────────
            draft_text = None
            top = next((m for m in matches if m.eligible), None)
            if self.want_draft and top:
                yield AgentEvent("thinking",
                    f"✍️ DraftAgent — writing sector-adapted Excellence section for {top.grant_name}...")
                draft_text = await self._draft_application(top, sectors)
                yield AgentEvent("draft", {"grant": top.grant_name, "text": draft_text})

            # ── DossierAgent ─────────────────────────────────────────────────
            yield AgentEvent("thinking", "📄 DossierAgent — assembling printable dossier...")
            dossier_id = _store_dossier({
                "deck": self.pitchdeck_json,
                "matches": [m.to_dict() for m in matches],
                "combos": combos,
                "plan": plan,
                "draft": {"grant": top.grant_name, "text": draft_text} if draft_text else None,
                "vc_matches": vc_matches,
                "stats": stats,
                "generated_at": datetime.utcnow().isoformat() + "Z",
            })
            yield AgentEvent("dossier", {
                "id": dossier_id,
                "url": f"/dossier/{dossier_id}",
                "print_url": f"/dossier/{dossier_id}?print=1",
            })

            yield AgentEvent("done")
        except Exception as e:
            yield AgentEvent("error", str(e))

    def _critical_missing(self) -> list[dict]:
        out = []
        for path, question in self.CRITICAL_FIELDS:
            v = self._get_path(path)
            if v in (None, "", []):
                out.append({"field": path, "question": question})
        return out

    def _get_path(self, path: str):
        cur = self.pitchdeck_json
        for p in path.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(p)
        return cur

    async def _draft_application(self, top: GrantMatch, sectors: set) -> str:
        if not CEREBRAS_API_KEY or not httpx:
            sector_hint = ", ".join(list(sectors)[:2]) if sectors else "deeptech"
            return (
                f"[Draft for {top.grant_name} — Cerebras Qwen 3 235B would generate a sector-specific "
                f"({sector_hint}) 200-word Excellence section anchored on your pitchdeck data. "
                f"Set CEREBRAS_API_KEY to enable live generation.]"
            )
        deck_str = json.dumps(self.pitchdeck_json, ensure_ascii=False)
        grant = next(g for g in GRANTS_DB["grants"] if g["id"] == top.grant_id)
        sector_context = f"\nPrimary sectors: {', '.join(list(sectors))}" if sectors else ""
        try:
            return await cerebras_chat(
                messages=[
                    {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
                    {"role": "user",
                     "content": (
                         f"PITCHDECK:{sector_context}\n{deck_str[:6000]}"
                         f"\n\nTARGET GRANT:\n{json.dumps(grant)[:2000]}"
                     )},
                ],
                temperature=0.3,
                max_tokens=450,
            )
        except Exception as e:
            return f"[Cerebras draft error: {e}]"


# -----------------------------------------------------------------------------
# Dossier storage (in-memory; replace with Firestore for prod)
# -----------------------------------------------------------------------------

import secrets

def _store_dossier(data: dict) -> str:
    """Store dossier data and return a short id for the printable URL."""
    did = secrets.token_urlsafe(8)
    DOSSIER_STORE[did] = data
    # Cap memory: keep only the most recent 32 dossiers.
    if len(DOSSIER_STORE) > 32:
        oldest = next(iter(DOSSIER_STORE))
        DOSSIER_STORE.pop(oldest, None)
    return did


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _matches_stats(matches: list[GrantMatch]) -> dict:
    eligible = [m for m in matches if m.eligible]
    return {
        "total": len(matches),
        "eligible": len(eligible),
        "top_tier": sum(1 for m in matches if m.priority_tier == "top"),
        "expected_total_funding_eur": round(sum(
            m.blended_probability_pct / 100 *
            (m.funding_range_eur[0] + m.funding_range_eur[1]) / 2
            for m in eligible), 0),
    }


# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------

if HAS_FASTAPI:
    import os as _os
    from fastapi.responses import FileResponse as _FileResponse

    app = FastAPI(title="Fundr", version="0.1.0")

    # Resolve the frontend HTML: prefer the Lovable-based file in /frontend/index.html
    # (copied into the image by the Dockerfile), falling back to the embedded HTML_PAGE.
    _FRONTEND_HTML_PATH = _os.path.join(_os.path.dirname(__file__), "frontend", "index.html")
    _STATIC_DIR = _os.path.join(_os.path.dirname(__file__), "static")

    def _get_frontend_html() -> str:
        if _os.path.isfile(_FRONTEND_HTML_PATH):
            with open(_FRONTEND_HTML_PATH, encoding="utf-8") as f:
                return f.read()
        return HTML_PAGE

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTMLResponse(content=_get_frontend_html())

    @app.get("/static/{filename}")
    async def serve_static(filename: str):
        """Serve static files (pitch deck examples, etc.) from the /static directory."""
        # Sanitize: no path traversal
        safe = _os.path.basename(filename)
        # Look in ./static/ first, then in the project root (for NeuroLedger PPTX at root)
        candidates = [
            _os.path.join(_STATIC_DIR, safe),
            _os.path.join(_os.path.dirname(__file__), safe),
        ]
        for path in candidates:
            if _os.path.isfile(path):
                return _FileResponse(path, filename=safe)
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Static file '{safe}' not found")

    @app.post("/api/match")
    async def api_match(req: Request):
        body = await req.json()
        deck = body.get("pitchdeck_json") or await parse_pitchdeck(body.get("pitchdeck_text", ""))
        clarifications = body.get("clarifications") or {}
        deck = _deep_merge(deck, clarifications)
        matches = [match_grant(deck, g) for g in GRANTS_DB["grants"]]
        matches.sort(key=lambda m: (not m.eligible, -m.blended_probability_pct))
        combos = evaluate_combinations(matches, GRANTS_DB["_meta"]["combinability_matrix"])
        return {
            "deck": deck,
            "matches": [m.to_dict() for m in matches],
            "stats": _matches_stats(matches),
            "combos": combos,
        }

    @app.post("/api/agent/run")
    async def api_agent_run(req: Request):
        body = await req.json()
        agent = GrantAgent(
            pitchdeck_text=body.get("pitchdeck_text", ""),
            pitchdeck_json=body.get("pitchdeck_json"),
            user_clarifications=body.get("clarifications") or {},
            want_draft=bool(body.get("want_draft", True)),
        )

        async def gen():
            async for event in agent.run():
                yield event.sse()

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/dossier/{dossier_id}", response_class=HTMLResponse)
    async def dossier(dossier_id: str, print: int = 0):
        data = DOSSIER_STORE.get(dossier_id)
        if not data:
            raise HTTPException(404, "Dossier not found or expired")
        return HTMLResponse(content=render_dossier(data, auto_print=bool(print)))

    @app.get("/api/dossier/{dossier_id}")
    async def api_dossier(dossier_id: str):
        data = DOSSIER_STORE.get(dossier_id)
        if not data:
            raise HTTPException(404, "Dossier not found or expired")
        return data

    @app.post("/api/upload")
    async def api_upload(file: UploadFile = File(...)):
        """Upload a PDF or PPTX pitchdeck and extract text."""
        filename = (file.filename or "").lower()
        data = await file.read()
        if filename.endswith(".pdf"):
            try:
                text = extract_text_from_pdf(data)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"PDF extraction failed: {e}")
        elif filename.endswith(".pptx"):
            try:
                text = extract_text_from_pptx(data)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"PPTX extraction failed: {e}")
        else:
            raise HTTPException(status_code=400, detail="Unsupported format. Please upload a .pdf or .pptx file.")
        if not text.strip():
            raise HTTPException(status_code=400, detail="No text could be extracted from the file.")
        return {"text": text, "filename": file.filename, "chars": len(text)}

    @app.get("/api/grants")
    async def api_grants():
        return GRANTS_DB

    @app.get("/api/health")
    async def api_health():
        return {
            "status": "ok",
            "grants_loaded": len(GRANTS_DB["grants"]),
            "vcs_loaded": len(VC_DB),
            "cerebras_configured": bool(CEREBRAS_API_KEY),
        }

# -----------------------------------------------------------------------------
# Dossier rendering (printable A4 page → PDF via browser print)
# -----------------------------------------------------------------------------

def render_dossier(data: dict, auto_print: bool = False) -> str:
    """Render the full financing dossier as a print-optimized HTML page."""
    deck = data.get("deck") or {}
    plan = data.get("plan") or {}
    matches = data.get("matches") or []
    combos = data.get("combos") or []
    stats = data.get("stats") or {}
    draft = data.get("draft") or {}
    vc_matches = data.get("vc_matches") or []
    company = (deck.get("company") or {}).get("name") or "—"
    country = (deck.get("company") or {}).get("country") or ""
    region = (deck.get("company") or {}).get("region") or ""
    one_liner = (deck.get("product") or {}).get("one_liner") or ""
    sectors = ", ".join((deck.get("product") or {}).get("sectors") or [])
    trl = (deck.get("product") or {}).get("trl") or "?"
    generated_at = data.get("generated_at", datetime.utcnow().isoformat() + "Z")

    pie = pie_chart_svg(plan.get("use_of_funds", {}))
    stack = funding_stack_svg(plan.get("funding_sources", []), plan.get("total_ask_eur", 1))

    # Top 5 grants table
    eligible = [m for m in matches if m["eligible"]][:5]
    grants_rows = ""
    for m in eligible:
        dl_str = ""
        urgency = m.get("urgency", "unknown")
        if m.get("next_deadline"):
            urg_class = {"urgent": "urgent", "soon": "soon",
                          "comfortable": "comfortable", "passed": "passed"}.get(urgency, "")
            dl_str = (f"<span class='dl-pill {urg_class}'>{m['next_deadline']}</span>"
                      f"<span style='color:var(--muted);font-size:10px;display:block;margin-top:2px;'>J-{m['days_until_deadline']}</span>")
        elif urgency == "rolling":
            dl_str = "<span class='dl-pill rolling'>rolling</span>"
        elig_badge = {"CONFIRMED": "🟢", "CONDITIONAL": "🟡", "EXCLUDED": "🔴"}.get(
            m.get("eligibility_status", "").split("(")[0].strip(), "⚪")
        grants_rows += (
            f"<tr><td><strong>{html_escape(m['grant_name'])}</strong><br>"
            f"<span style='color:var(--muted);font-size:10px;'>{html_escape(m['level'])}</span><br>"
            f"<span style='font-size:10px;'>{elig_badge} {html_escape(m.get('eligibility_status',''))}</span></td>"
            f"<td style='text-align:right;'>{m['blended_probability_pct']:.0f}%<br>"
            f"<span style='color:var(--muted);font-size:10px;'>{html_escape(m.get('probability_explanation',''))}</span></td>"
            f"<td style='text-align:right;'>{m['fit_total']:.0f}/100</td>"
            f"<td style='text-align:right;'>{m['funding_range_eur'][0]/1e6:.1f}–{m['funding_range_eur'][1]/1e6:.1f} M€<br>"
            f"<span style='color:var(--muted);font-size:10px;'>EV: {m.get('expected_value_eur',0)/1e3:.0f} k€</span></td>"
            f"<td>{dl_str}</td>"
            f"<td>{html_escape(m['headline'])}<br>"
            f"<span style='font-size:10px;color:var(--muted);'>Risk: {html_escape(m.get('key_risk',''))}</span><br>"
            f"<span style='font-size:10px;color:var(--accent);'>Next: {html_escape(m.get('next_action',''))}</span></td></tr>"
        )

    # Submission timeline — eligible grants sorted by next deadline
    eligible_for_timeline = sorted(
        [m for m in matches if m["eligible"] and m.get("next_deadline")],
        key=lambda m: m["days_until_deadline"] if m.get("days_until_deadline") is not None else 9999
    )[:10]
    rolling_grants = [m for m in matches if m["eligible"] and m.get("urgency") == "rolling"][:6]
    timeline_rows = ""
    for m in eligible_for_timeline:
        u = m.get("urgency", "")
        urg_label = {"urgent": "🔴 urgent", "soon": "🟡 soon", "comfortable": "🟢 comfortable", "passed": "⚫ passed"}.get(u, "")
        timeline_rows += (
            f"<tr><td><strong>{m['next_deadline']}</strong></td>"
            f"<td>J-{m['days_until_deadline']}</td>"
            f"<td>{urg_label}</td>"
            f"<td>{html_escape(m['grant_name'])}</td>"
            f"<td style='color:var(--muted);font-size:11px;'>{html_escape(m.get('cut_off_pattern',''))}</td></tr>"
        )
    if rolling_grants:
        timeline_rows += (
            f"<tr><td colspan='5' style='background:var(--panel-2);font-style:italic;color:var(--muted);font-size:11px;padding:6px 10px;'>"
            f"Rolling (au fil de l'eau): "
            + ", ".join(html_escape(g["grant_name"]) for g in rolling_grants)
            + "</td></tr>"
        )

    # Per-grant allocation table
    alloc_rows = ""
    for b in (plan.get("grants_breakdown") or []):
        cats = "<br>".join(
            f"&nbsp;&nbsp;· {html_escape(c['category_label'])}: {c['eur']/1e3:.0f} k€"
            for c in (b.get("categories_covered") or [])
        )
        alloc_rows += (
            f"<tr><td><strong>{html_escape(b['grant_name'])}</strong><br>"
            f"<span style='color:var(--muted);font-size:10px;'>"
            f"prob {b['probability_pct']:.0f}% · range {b['funding_range_eur'][0]/1e6:.1f}–{b['funding_range_eur'][1]/1e6:.1f} M€</span></td>"
            f"<td style='text-align:right;font-weight:600;'>{b['expected_eur']/1e3:.0f} k€</td>"
            f"<td>{cats}</td></tr>"
        )

    # Combo sentence
    combo_str = ""
    if combos:
        c = combos[0]
        combo_str = (
            f"<strong>Recommended combination:</strong> {' + '.join(html_escape(n) for n in c['names'])} — "
            f"<strong>{c['expected_value_eur']/1e6:.1f} M€</strong> probability-weighted expected value."
        )

    draft_block = ""
    if draft and draft.get("text"):
        draft_block = f"""
        <section class="page-break">
          <h2>Draft — Excellence section ({html_escape(draft.get('grant') or '')})</h2>
          <div class="draft-text">{html_escape(draft.get('text') or '')}</div>
          <p class="caveat">Generated by Cerebras Qwen 3 235B with sector-specific adaptation. Anchor every claim in supporting evidence; verify against the call's evaluation criteria before submission.</p>
        </section>
        """

    # VC matches block
    vc_block = ""
    if vc_matches:
        vc_rows = ""
        for vc in vc_matches[:6]:
            score = vc.get("match_score", 0)
            score_bar = f"<div style='height:4px;background:#e5e7eb;border-radius:2px;margin-top:4px;'><div style='height:4px;background:var(--accent-2);border-radius:2px;width:{min(100,score):.0f}%;'></div></div>"
            vc_rows += (
                f"<tr><td><strong>{html_escape(vc['name'])}</strong><br>"
                f"<span style='color:var(--muted);font-size:10px;'>{html_escape(vc['city'])}, {html_escape(vc['country'])}</span></td>"
                f"<td style='font-size:11px;'>{html_escape(vc.get('strategies','')[:80])}</td>"
                f"<td style='font-size:11px;color:var(--muted);'>{html_escape(vc.get('match_reason',''))}</td>"
                f"<td style='text-align:right;'><strong>{score:.0f}</strong>/100{score_bar}</td></tr>"
            )
        vc_block = f"""
        <section>
          <h2>Matching investors (European VC database)</h2>
          <p style="margin:0 0 8px;color:var(--muted);font-size:12px;">Top VCs matched by sector alignment, investment stage, and geography. Not investment advice — use as a starting point for outreach.</p>
          <table>
            <thead><tr><th>Investor</th><th>Strategies</th><th>Match reason</th><th style="text-align:right">Score</th></tr></thead>
            <tbody>{vc_rows}</tbody>
          </table>
        </section>
        """

    auto_print_script = (
        '<script>window.addEventListener("load", () => setTimeout(() => window.print(), 600));</script>'
        if auto_print else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Financing Dossier — {html_escape(company)}</title>
<style>
  :root {{
    color-scheme: light;
    --bg:#ffffff; --panel:#fafaf7; --panel-2:#f3f1eb;
    --line:#d8d4c7; --text:#1a1a18; --muted:#6e6a5d;
    --accent:#c2410c; --accent-2:#1e3a5f;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,'Inter',system-ui,sans-serif;
    background:var(--bg); color:var(--text); line-height:1.55; font-size:13px; }}
  .page {{ max-width:880px; margin:0 auto; padding:48px 56px; }}
  .actions {{ position:sticky; top:0; background:#fafaf7; border-bottom:1px solid var(--line);
    padding:12px 24px; display:flex; justify-content:space-between; align-items:center; z-index:100;
    box-shadow:0 2px 4px rgba(0,0,0,0.04); }}
  .actions button {{ background:var(--accent); color:#fff; border:0; padding:8px 16px; border-radius:6px;
    font-size:13px; font-weight:600; cursor:pointer; font-family:inherit; }}
  .actions a {{ color:var(--muted); text-decoration:none; font-size:12px; }}
  header.dossier-h {{ border-bottom:2px solid var(--accent); padding-bottom:16px; margin-bottom:24px; }}
  header.dossier-h h1 {{ margin:0 0 4px; font-size:28px; letter-spacing:-0.01em; }}
  header.dossier-h .subtitle {{ color:var(--muted); font-size:12px; }}
  header.dossier-h .one-liner {{ font-size:14px; margin-top:10px; font-style:italic; color:var(--text); }}
  h2 {{ font-size:14px; text-transform:uppercase; letter-spacing:0.08em; color:var(--accent); margin:28px 0 12px; font-weight:700; border-bottom:1px solid var(--line); padding-bottom:6px; }}
  h3 {{ font-size:13px; margin:18px 0 8px; }}
  table {{ width:100%; border-collapse:collapse; margin:8px 0; font-size:12px; }}
  th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
  th {{ background:var(--panel-2); color:var(--muted); font-weight:600; font-size:10px;
    text-transform:uppercase; letter-spacing:0.05em; }}
  .summary-card {{ background:var(--panel); border:1px solid var(--line); padding:16px; border-radius:8px; margin:8px 0 16px; }}
  .summary-card p {{ margin:0; font-size:13px; }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin:14px 0; }}
  .kpi-card {{ background:var(--panel-2); border:1px solid var(--line); padding:12px 14px; border-radius:6px; }}
  .kpi-card label {{ display:block; color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:0.06em; }}
  .kpi-card strong {{ display:block; font-size:22px; font-weight:700; margin-top:2px; color:var(--text); }}
  .viz-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:24px; margin:12px 0; align-items:start; }}
  .piechart, .stackbar {{ display:flex; flex-direction:column; gap:14px; }}
  .piechart svg, .stackbar svg {{ display:block; max-width:100%; height:auto; }}
  .pielegend {{ display:flex; flex-direction:column; gap:4px; font-size:11px; }}
  .lg-row {{ display:grid; grid-template-columns:14px 1fr auto; gap:8px; align-items:center; }}
  .lg-sw {{ width:12px; height:12px; border-radius:2px; display:inline-block; }}
  .lg-lb {{ color:var(--text); }}
  .lg-vl {{ color:var(--muted); font-variant-numeric:tabular-nums; }}
  .lg-vl em {{ font-style:normal; opacity:0.7; }}
  .draft-text {{ background:var(--panel); border:1px solid var(--line); padding:16px; border-radius:6px;
    font-family:ui-serif,Georgia,serif; font-size:13px; line-height:1.65; white-space:pre-wrap; }}
  .caveat {{ font-size:10px; color:var(--muted); margin:8px 0 0; font-style:italic; }}
  footer {{ margin-top:40px; padding-top:14px; border-top:1px solid var(--line);
    color:var(--muted); font-size:10px; }}
  .combo-callout {{ background:var(--panel-2); border-left:3px solid var(--accent); padding:10px 14px;
    border-radius:4px; font-size:12px; margin:8px 0; }}
  .dl-pill {{ font-size:10px; padding:2px 8px; border-radius:10px; font-weight:600; white-space:nowrap;
    display:inline-block; }}
  .dl-pill.urgent {{ background:#fee2e2; color:#991b1b; }}
  .dl-pill.soon {{ background:#fef3c7; color:#92400e; }}
  .dl-pill.comfortable {{ background:#d1fae5; color:#065f46; }}
  .dl-pill.rolling {{ background:#f1f5f9; color:#64748b; }}
  .dl-pill.passed {{ background:#f1f5f9; color:#64748b; text-decoration:line-through; }}

  @media print {{
    .actions {{ display:none; }}
    body {{ background:#fff; font-size:11px; line-height:1.4; }}
    .page {{ padding:0; max-width:100%; }}
    h2 {{ font-size:13px; margin:18px 0 8px; }}
    .page-break {{ page-break-before:auto; break-inside:avoid; }}
    table {{ font-size:10.5px; }}
    th, td {{ padding:6px 8px; }}
    @page {{ size:A4; margin:18mm 16mm; }}
  }}
</style>
</head>
<body>
<div class="actions">
  <a href="/">← Back to Fundr</a>
  <div style="display:flex;gap:8px;align-items:center;">
    <button id="copy-btn" onclick="copyDossierLink()" style="background:var(--accent-2);color:#fff;border:0;padding:8px 14px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;">📋 Copy link</button>
    <button onclick="window.print()">Download PDF</button>
  </div>
</div>
<script>
function copyDossierLink() {{
  navigator.clipboard.writeText(window.location.href).then(() => {{
    const btn = document.getElementById('copy-btn');
    const orig = btn.textContent;
    btn.textContent = '✓ Link copied';
    btn.style.background = '#065f46';
    setTimeout(() => {{ btn.textContent = orig; btn.style.background = ''; }}, 2000);
  }}).catch(() => {{ alert('Copy: ' + window.location.href); }});
}}
</script>
<div class="page">
  <header class="dossier-h">
    <h1>{html_escape(company)} — Financing Dossier</h1>
    <div class="subtitle">{html_escape(country)} {('· ' + html_escape(region)) if region else ''} · TRL {trl} · sectors: {html_escape(sectors)} · generated {generated_at[:10]}</div>
    <div class="one-liner">{html_escape(one_liner)}</div>
  </header>

  <h2>Executive summary</h2>
  <div class="summary-card">
    <p>{html_escape(plan.get('summary') or '—')}</p>
  </div>
  <div class="kpi-grid">
    <div class="kpi-card"><label>Total funding ask</label><strong>{plan.get('total_ask_eur', 0)/1e6:.2f} M€</strong></div>
    <div class="kpi-card"><label>Eligible programmes</label><strong>{stats.get('eligible', 0)} / {stats.get('total', 0)}</strong></div>
    <div class="kpi-card"><label>Probability-weighted grant funding</label><strong>{sum(s['eur'] for s in plan.get('funding_sources', []) if 'Grant' in s.get('label',''))/1e6:.2f} M€</strong></div>
  </div>
  {f'<div class="combo-callout">{combo_str}</div>' if combo_str else ''}

  <h2>Use of funds</h2>
  <p style="margin:0 0 10px;color:var(--muted);font-size:12px;">
    {('Inferred from sector + TRL — refine when you have a budget plan.' if plan.get('ask_inferred') else 'Based on the funding ask provided in the pitchdeck.')}
  </p>
  <div class="viz-grid">
    <div>{pie}</div>
    <div>
      <h3 style="margin-top:0;">Funding sources</h3>
      {stack}
    </div>
  </div>

  <h2>Top eligible grants</h2>
  <table>
    <thead><tr><th>Programme</th><th style="text-align:right">Probability</th><th style="text-align:right">Fit</th><th style="text-align:right">Range</th><th>Next deadline</th><th>Headline</th></tr></thead>
    <tbody>{grants_rows or '<tr><td colspan="6" style="color:var(--muted);text-align:center;padding:16px;">No eligible programmes — review the pitchdeck for blockers.</td></tr>'}</tbody>
  </table>

  <h2>Submission timeline</h2>
  <p style="margin:0 0 8px;color:var(--muted);font-size:12px;">Indicative 2026 deadlines compiled from public Work Programmes — refresh from the SEDIA API for the day's exact cut-offs before submitting.</p>
  <table>
    <thead><tr><th>Deadline</th><th>Countdown</th><th>Urgency</th><th>Programme</th><th>Pattern</th></tr></thead>
    <tbody>{timeline_rows or '<tr><td colspan="5" style="color:var(--muted);text-align:center;padding:16px;">No dated deadlines for eligible programmes (mostly rolling).</td></tr>'}</tbody>
  </table>

  <h2>Funding allocation by grant</h2>
  <p style="margin:0 0 8px;color:var(--muted);font-size:12px;">Probability-weighted expected coverage per category. Greedy allocation — the cleanest way to map sources to use-of-funds without double-counting.</p>
  <table>
    <thead><tr><th>Programme</th><th style="text-align:right">Expected coverage</th><th>Lines covered</th></tr></thead>
    <tbody>{alloc_rows or '<tr><td colspan="3" style="color:var(--muted);text-align:center;padding:16px;">No grant allocation generated.</td></tr>'}</tbody>
  </table>

  {draft_block}

  {vc_block}

  <h2>Disclaimers</h2>
  <div style="font-size:11px;color:var(--muted);background:var(--panel-2);padding:14px 16px;border-radius:6px;border-left:3px solid var(--accent);line-height:1.6;">
    Eligibility has been verified against public programme documentation as of 2026-04-26.<br>
    ERC PoC requires a prior ERC grant — confirm PI eligibility before any submission.<br>
    Horizon Europe RIA/IA require a confirmed multi-country consortium — solo applications
    are not accepted.<br>
    Probabilities are indicative baselines, not calibrated on a private success cohort.<br>
    Validate cumulability rules with the granting authority before committing to a budget plan.<br>
    No dossier generated here constitutes a regulatory filing.
  </div>

  <footer>Fundr · Paris Fintech Hackathon 2026 · Track B2G — financial inclusion + RegTech for non-dilutive funding access.</footer>
</div>
{auto_print_script}
</body>
</html>"""


def html_escape(s: Any) -> str:
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                  .replace('"', "&quot;").replace("'", "&#39;"))


# -----------------------------------------------------------------------------
# Embedded HTML frontend
# -----------------------------------------------------------------------------

HTML_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fundr — AI agent for European non-dilutive funding</title>
<style>
  :root {
    color-scheme: light;
    --bg:#fafaf7; --panel:#ffffff; --panel-2:#f3f1eb;
    --line:#d8d4c7; --text:#1a1a18; --muted:#6e6a5d;
    --accent:#c2410c; --accent-2:#1e3a5f;
    --ok-bg:#d1fae5; --ok-fg:#065f46;
    --warn-bg:#fef3c7; --warn-fg:#92400e;
    --low-bg:#fee2e2; --low-fg:#991b1b;
    --vlow-bg:#f3f4f6; --vlow-fg:#4b5563;
  }
  * { box-sizing: border-box; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,'Inter',system-ui,sans-serif;
    background:var(--bg); color:var(--text); line-height:1.5; }
  .wrap { max-width:1200px; margin:0 auto; padding:32px 24px; }
  header { border-bottom:1px solid var(--line); padding-bottom:16px; margin-bottom:24px; }
  header h1 { font-size:24px; margin:0 0 4px; letter-spacing:-0.01em; }
  header h1 .accent { color:var(--accent); }
  header .sub { color:var(--muted); font-size:13px; }
  .hackathon { display:inline-block; background:var(--accent); color:#fff;
    padding:2px 8px; border-radius:12px; font-size:10px; text-transform:uppercase; letter-spacing:0.08em; margin-left:8px; vertical-align:middle; font-weight:600; }
  .layout { display:grid; grid-template-columns:1fr 2fr; gap:24px; }
  @media (max-width:900px) { .layout { grid-template-columns:1fr; } }
  .input-panel, .output-panel { background:var(--panel); border:1px solid var(--line);
    border-radius:8px; padding:20px; }
  .input-panel h2, .output-panel h2 { font-size:11px; text-transform:uppercase;
    letter-spacing:0.1em; color:var(--muted); margin:0 0 12px; font-weight:600; }
  textarea { width:100%; min-height:240px; padding:12px; border:1px solid var(--line);
    border-radius:6px; font-family:ui-monospace,monospace; font-size:12px; resize:vertical;
    background:var(--bg); color:var(--text); }
  .opts { display:flex; gap:14px; margin:12px 0; flex-wrap:wrap; font-size:12px; color:var(--muted); }
  .opts label { display:flex; align-items:center; gap:6px; cursor:pointer; }
  button.primary { background:var(--accent); color:#fff; border:0; padding:10px 18px;
    border-radius:6px; font-size:13px; font-weight:600; cursor:pointer; width:100%; }
  button.primary:hover { background:#9a3508; }
  button.primary:disabled { background:var(--muted); cursor:not-allowed; }
  .upload-zone { display:flex; align-items:center; gap:10px; margin:10px 0; }
  .upload-btn { background:var(--accent-2); color:#fff; border:0; padding:8px 14px;
    border-radius:6px; font-size:12px; font-weight:600; cursor:pointer; font-family:inherit; }
  .upload-btn:hover { background:#152d4a; }
  .file-status { font-size:11px; color:var(--muted); }
  .file-status.ok { color:var(--ok-fg); }
  .file-status.err { color:var(--low-fg); }
  .examples { margin-top:14px; }
  .examples button { background:var(--panel-2); border:1px solid var(--line); color:var(--muted);
    padding:6px 10px; border-radius:14px; font-size:11px; cursor:pointer; margin:2px; font-family:inherit; }
  .examples button:hover { background:var(--line); }

  .stream { display:flex; flex-direction:column; gap:8px; }
  .step { background:var(--panel-2); border-left:3px solid var(--muted); padding:8px 12px;
    border-radius:4px; font-size:12px; }
  .step.thinking { border-color:var(--accent); }
  .step.thinking::before { content:"⏳ "; }
  .step.parsed { border-color:var(--ok-fg); background:var(--ok-bg); color:var(--ok-fg); }
  .step.parsed::before { content:"✓ "; }
  .step.matched { border-color:var(--ok-fg); }
  .step.matched::before { content:"✓ "; }
  .step.combos { border-color:var(--accent-2); }
  .step.draft { border-color:var(--accent); background:var(--panel-2); }
  .step.error { border-color:var(--low-fg); background:var(--low-bg); color:var(--low-fg); }
  .step.error::before { content:"⚠ "; }

  .ask { background:var(--warn-bg); border-left:3px solid var(--warn-fg); padding:14px;
    border-radius:6px; margin:12px 0; }
  .ask h3 { margin:0 0 8px; font-size:13px; color:var(--warn-fg); }
  .ask .q { margin:8px 0; }
  .ask .q label { display:block; font-size:12px; color:var(--text); margin-bottom:4px; }
  .ask .q input { width:100%; padding:6px 10px; border:1px solid var(--line); border-radius:4px;
    font-family:inherit; font-size:12px; }
  .ask button { margin-top:10px; background:var(--warn-fg); color:#fff; border:0;
    padding:8px 16px; border-radius:4px; font-size:12px; font-weight:600; cursor:pointer; }

  .stats { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin:16px 0; }
  .stat { background:var(--panel-2); border:1px solid var(--line); padding:10px; border-radius:6px; }
  .stat label { color:var(--muted); font-size:9px; text-transform:uppercase; letter-spacing:0.07em; }
  .stat strong { display:block; font-size:18px; font-weight:700; margin-top:2px; }

  .matches { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:8px; margin-top:16px; }
  .card { background:var(--panel-2); border:1px solid var(--line); border-radius:6px;
    padding:12px; font-size:12px; }
  .card.ineligible { opacity:0.6; }
  .card-h { display:flex; justify-content:space-between; align-items:flex-start; gap:8px; margin-bottom:6px; }
  .card-h h4 { margin:0; font-size:13px; line-height:1.3; flex:1; }
  .card-h .lvl { color:var(--muted); font-size:10px; text-transform:uppercase; }
  .pchip { font-weight:700; padding:3px 8px; border-radius:4px; font-size:13px; white-space:nowrap; }
  .pchip.high { background:var(--ok-bg); color:var(--ok-fg); }
  .pchip.med { background:var(--warn-bg); color:var(--warn-fg); }
  .pchip.low { background:var(--low-bg); color:var(--low-fg); }
  .pchip.vlow { background:var(--vlow-bg); color:var(--vlow-fg); }
  .pchip.ineligible { background:var(--vlow-bg); color:var(--vlow-fg); font-size:10px; }
  .ci { color:var(--muted); font-size:10px; margin-top:2px; }
  .head { color:var(--muted); font-size:11px; margin:4px 0; }
  .meta { display:flex; gap:14px; font-size:10px; color:var(--muted); border-top:1px solid var(--line); padding-top:6px; margin-top:6px; }
  .meta strong { color:var(--text); }

  .combos { background:var(--panel-2); border:1px solid var(--line); padding:12px; border-radius:6px; margin-top:16px; }
  .combo { background:var(--panel); border:1px solid var(--line); padding:10px;
    border-radius:6px; margin-top:8px; font-size:12px; }
  .combo h4 { margin:0 0 4px; font-size:13px; }
  .combo .ev { color:var(--accent); font-weight:700; font-size:14px; }
  .combo ul { margin:6px 0; padding-left:18px; }

  .draft-block { background:var(--bg); border:1px solid var(--line); padding:14px;
    border-radius:6px; margin-top:14px; font-family:ui-serif,Georgia,serif; font-size:13px; line-height:1.6;
    white-space:pre-wrap; }

  .plan-block { background:var(--panel-2); border:1px solid var(--line); padding:16px; border-radius:6px; margin-top:14px; }
  .plan-block h3 { margin:0 0 10px; font-size:13px; color:var(--accent); text-transform:uppercase; letter-spacing:0.06em; }
  .plan-summary { font-size:12px; padding:10px 12px; background:var(--bg); border-radius:6px; border-left:3px solid var(--accent); margin-bottom:14px; }
  .plan-grid { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
  @media (max-width:760px) { .plan-grid { grid-template-columns:1fr; } }
  .piechart svg, .stackbar svg { display:block; max-width:100%; height:auto; }
  .pielegend { display:flex; flex-direction:column; gap:4px; font-size:11px; margin-top:8px; }
  .lg-row { display:grid; grid-template-columns:14px 1fr auto; gap:8px; align-items:center; }
  .lg-sw { width:12px; height:12px; border-radius:2px; display:inline-block; }
  .lg-vl { color:var(--muted); font-variant-numeric:tabular-nums; }
  .lg-vl em { font-style:normal; opacity:0.7; }

  .dl-row { display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin:6px 0 8px; }
  .dl-pill { font-size:10px; padding:2px 8px; border-radius:10px; font-weight:600; white-space:nowrap; }
  .dl-pill.urgent { background:var(--low-bg); color:var(--low-fg); }
  .dl-pill.soon { background:var(--warn-bg); color:var(--warn-fg); }
  .dl-pill.comfortable { background:var(--ok-bg); color:var(--ok-fg); }
  .dl-pill.rolling { background:var(--vlow-bg); color:var(--vlow-fg); }
  .dl-pill.passed { background:var(--vlow-bg); color:var(--vlow-fg); text-decoration:line-through; }
  .dl-pattern { font-size:10px; color:var(--muted); font-style:italic; }

  .timeline-rail { display:flex; gap:6px; padding:10px; background:var(--panel-2);
    border:1px solid var(--line); border-radius:6px; margin:12px 0; overflow-x:auto; }
  .tl-label { font-size:10px; color:var(--muted); text-transform:uppercase; letter-spacing:0.06em;
    white-space:nowrap; align-self:center; padding-right:6px; border-right:1px solid var(--line); margin-right:6px; }
  .tl-item { background:var(--panel); border:1px solid var(--line); padding:6px 10px; border-radius:6px;
    min-width:140px; flex-shrink:0; }
  .tl-item.urgent { border-left:3px solid var(--low-fg); }
  .tl-item.soon { border-left:3px solid var(--warn-fg); }
  .tl-item.comfortable { border-left:3px solid var(--ok-fg); }
  .tl-date { font-size:10px; color:var(--muted); }
  .tl-name { font-size:11px; font-weight:600; line-height:1.25; margin:2px 0; }
  .tl-days { font-size:11px; color:var(--accent); font-weight:700; }

  .dossier-cta { background:var(--accent); color:#fff; padding:14px 16px; border-radius:6px; margin-top:14px;
    display:flex; justify-content:space-between; align-items:center; gap:10px; }
  .dossier-cta a, .dossier-cta button.link-btn { color:#fff; background:rgba(255,255,255,0.18); padding:6px 12px; border-radius:4px;
    text-decoration:none; font-size:12px; font-weight:600; border:0; cursor:pointer; font-family:inherit; }
  .dossier-cta a:hover, .dossier-cta button.link-btn:hover { background:rgba(255,255,255,0.28); }

  .sensitive-warn { background:#fef3c7; border-left:3px solid #92400e; padding:10px 14px;
    border-radius:4px; font-size:12px; margin:8px 0; color:#92400e; }
  .sensitive-warn strong { color:#78350f; }

  .no-match-panel { background:var(--low-bg); border:1px solid #fca5a5; padding:16px;
    border-radius:8px; margin:12px 0; }
  .no-match-panel h3 { margin:0 0 8px; color:var(--low-fg); font-size:13px; }
  .no-match-panel .blocker { background:#fff; border:1px solid #fca5a5; border-radius:6px;
    padding:10px 12px; margin:6px 0; }
  .no-match-panel .blocker strong { color:var(--low-fg); font-size:12px; }
  .no-match-panel .blocker p { margin:4px 0 0; font-size:11px; color:var(--text); }

  .whatif-panel { background:var(--panel-2); border:1px solid var(--line); padding:14px;
    border-radius:6px; margin-top:14px; }
  .whatif-panel h3 { margin:0 0 8px; font-size:13px; color:var(--accent-2); }
  .whatif-row { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
  .whatif-row label { font-size:12px; color:var(--muted); }
  .whatif-row input[type=number] { width:70px; padding:6px 8px; border:1px solid var(--line);
    border-radius:4px; font-size:13px; font-weight:700; text-align:center; font-family:inherit; }
  .whatif-row button { background:var(--accent-2); color:#fff; border:0; padding:7px 14px;
    border-radius:4px; font-size:12px; font-weight:600; cursor:pointer; font-family:inherit; }

  .vc-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:8px; margin-top:10px; }
  .vc-card { background:var(--panel-2); border:1px solid var(--line); border-radius:6px; padding:12px; font-size:12px; }
  .vc-card h4 { margin:0 0 2px; font-size:13px; }
  .vc-card .vc-loc { color:var(--muted); font-size:10px; margin-bottom:6px; }
  .vc-card .vc-strat { font-size:10px; color:var(--muted); border-top:1px solid var(--line); padding-top:4px; margin-top:4px; }
  .vc-score-bar { height:4px; background:#e5e7eb; border-radius:2px; margin-top:6px; }
  .vc-score-fill { height:4px; background:var(--accent-2); border-radius:2px; }

  footer { margin-top:48px; padding-top:14px; border-top:1px solid var(--line);
    color:var(--muted); font-size:10px; line-height:1.5; }
  footer code { background:var(--panel-2); padding:1px 4px; border-radius:3px; }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>Funds<span class="accent">Agent</span> <span class="hackathon">B2G · Paris Fintech 2026</span></h1>
  <div class="sub">An autonomous AI agent that reads a pitchdeck, identifies the European non-dilutive funding programmes (Horizon Europe, EIC, France 2030, Bpifrance, ADEME, FEDER, regional) you can win, builds a VC-grade financing dossier with use-of-funds breakdown, and exports it as PDF — in seconds. Powered by Cerebras Qwen 3 235B + Google Cloud + Lovable.</div>
</header>

<div class="layout">
  <section class="input-panel">
    <h2>Pitchdeck</h2>
    <textarea id="pitch" placeholder="Paste your pitchdeck text here or upload a PDF/PPTX file below. The agent extracts company, sectors, TRL, team, funding ask, impact."></textarea>
    <div class="upload-zone" id="upload-zone">
      <input type="file" id="file-input" accept=".pdf,.pptx" style="display:none" onchange="handleFileUpload(event)">
      <button class="upload-btn" onclick="document.getElementById('file-input').click()">Upload PDF or PPTX</button>
      <span id="file-status" class="file-status"></span>
    </div>
    <div class="examples">
      <button onclick="loadExample('greensilicon')">Example: GreenSilicon (climate)</button>
      <button onclick="loadExample('healthai')">Example: HealthAI (health)</button>
      <button onclick="loadExample('cybernetic')">Example: Cybernetic (cyber)</button>
    </div>
    <div class="opts">
      <label><input type="checkbox" id="want_draft" checked> Generate application draft (Cerebras)</label>
    </div>
    <button class="primary" id="run-btn" onclick="runAgent()">▶ Run agent</button>
  </section>

  <section class="output-panel">
    <h2>Agent stream</h2>
    <div id="stream" class="stream">
      <div class="step" style="border-color:var(--line);">Paste a pitchdeck on the left and press <strong>Run agent</strong>. The agent will parse it, ask for any missing critical info, match against 37 programmes, propose combinations, and (optionally) draft the Excellence section for the top match.</div>
    </div>
  </section>
</div>

<footer>
  <strong>Fundr v0.2</strong> — single-file webapp · 37 programmes · scoring = 0.45×statistical + 0.30×fit + 0.25×evaluator-sim · Cerebras Qwen 3 235B for parsing, plan synthesis & drafting · printable A4 dossier with use-of-funds breakdown.
  Track: B2G (financial inclusion + RegTech for grant cumulability rules). Every reasoning step streams as <code>SSE</code> so judges see the autonomous loop.
  Limitations: success rates are public multi-year averages, not calibrated on private cohort.
</footer>
</div>

<script>
const STREAM = document.getElementById('stream');
const PITCH = document.getElementById('pitch');
let lastDeck = null;
let lastDossierUrl = null;

const EXAMPLES = {
  greensilicon: `GreenSilicon (SAS) — Paris-Saclay, France, founded 2023, 8 people (4 PhDs, 50% female).
Tandem perovskite/silicon solar cells with >30% laboratory efficiency, manufactured via a low-temperature deposition process that cuts CO2 by 60% versus crystalline silicon.
Two patents filed (FR + PCT). Currently TRL 5 (validated in lab environment), targeting TRL 7 in 24 months.
Market: European PV module makers, 22B€ SAM, 2 letters of intent signed with Voltec Solar (FR) and Meyer Burger (DE).
Team: CEO ex-CEA, CTO PhD with 8 publications in Nature/Science.
Funding ask: 4.5M€ over 24 months for pilot line industrialization. We can co-finance 1.5M€ from existing equity. Open to consortium.
Impact: 250 kt CO2/year by year 5. Aligned with Green Deal, Fit for 55, Industry 4.0.`,

  healthai: `MedScribe AI — Berlin, Germany, founded 2024, 12 people including 3 MD-PhDs.
SaaS clinical scribe that auto-generates structured medical notes from doctor-patient conversations using on-prem fine-tuned LLM. GDPR by design.
TRL 6, deployed in 2 university hospitals (Charité, La Pitié) on a research basis. ISO 13485 in progress. CE marking targeted Q4 2026.
Market: 2M+ EU physicians, 8B€ SAM. 5 LOIs from German hospital networks.
Funding ask: 3M€ over 18 months for clinical validation + CE certification. Open to consortium.
Aligned with Cluster 1 Health priorities: digital health, ageing society, healthcare workforce relief.`,

  cybernetic: `Cybernetic — Toulouse, France (Occitanie), founded 2022, 6 people (2 PhDs in cryptography).
Post-quantum cryptography library for embedded systems. ANSSI evaluation in progress. Patents pending.
TRL 4, prototype validated in lab. Targeting space and defence customers. Discussions with Airbus Defence and CNES.
Market: 1.2B€ SAM. Ask: 1.8M€ over 24 months for productization + certification.
Open to consortium. Dual-use possible.`,
};

function loadExample(key) {
  PITCH.value = EXAMPLES[key];
}

async function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  const status = document.getElementById('file-status');
  const name = file.name.toLowerCase();
  if (!name.endsWith('.pdf') && !name.endsWith('.pptx')) {
    status.textContent = 'Unsupported format — use .pdf or .pptx';
    status.className = 'file-status err';
    return;
  }
  status.textContent = 'Extracting text...';
  status.className = 'file-status';
  const form = new FormData();
  form.append('file', file);
  try {
    const resp = await fetch('/api/upload', { method: 'POST', body: form });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Upload failed');
    }
    const data = await resp.json();
    PITCH.value = data.text;
    status.textContent = file.name + ' — ' + data.chars + ' chars extracted';
    status.className = 'file-status ok';
  } catch (e) {
    status.textContent = 'Error: ' + e.message;
    status.className = 'file-status err';
  }
  event.target.value = '';
}

function pchipClass(p, eligible) {
  if (!eligible) return 'ineligible';
  if (p >= 60) return 'high';
  if (p >= 40) return 'med';
  if (p >= 20) return 'low';
  return 'vlow';
}

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}

function appendStep(type, content) {
  const div = document.createElement('div');
  div.className = 'step ' + type;
  div.innerHTML = content;
  STREAM.appendChild(div);
  STREAM.scrollTop = STREAM.scrollHeight;
  return div;
}

function deadlinePill(m) {
  if (m.urgency === 'rolling') return `<span class="dl-pill rolling">rolling</span>`;
  if (m.urgency === 'passed') return `<span class="dl-pill passed">cycle closed</span>`;
  if (!m.next_deadline) return '';
  const cls = m.urgency === 'urgent' ? 'urgent' : (m.urgency === 'soon' ? 'soon' : 'comfortable');
  return `<span class="dl-pill ${cls}">📅 ${m.next_deadline} · J-${m.days_until_deadline}</span>`;
}

function renderMatches(payload) {
  const matches = payload.matches || [];
  const stats = payload.stats || {};
  const eligible = matches.filter(m => m.eligible);
  const ineligible = matches.filter(m => !m.eligible);

  // Build "Next deadlines" rail — top 3 urgent dated grants
  const dated = eligible
    .filter(m => m.next_deadline && m.urgency !== 'passed')
    .sort((a, b) => a.days_until_deadline - b.days_until_deadline)
    .slice(0, 4);
  let timelineHtml = '';
  if (dated.length) {
    timelineHtml = `<div class="timeline-rail">
      <div class="tl-label">Upcoming deadlines</div>
      ${dated.map(m => `
        <div class="tl-item ${m.urgency}">
          <div class="tl-date">${m.next_deadline}</div>
          <div class="tl-name">${escapeHtml(m.grant_name)}</div>
          <div class="tl-days">J-${m.days_until_deadline}</div>
        </div>`).join('')}
    </div>`;
  }

  let html = `<div class="stats">
    <div class="stat"><label>Scanned</label><strong>${stats.total || 0}</strong></div>
    <div class="stat"><label>Eligible</label><strong>${stats.eligible || 0}</strong></div>
    <div class="stat"><label>Top tier</label><strong>${stats.top_tier || 0}</strong></div>
    <div class="stat"><label>Expected</label><strong>${((stats.expected_total_funding_eur||0)/1e6).toFixed(1)} M€</strong></div>
  </div>${timelineHtml}`;

  html += '<div class="matches">';
  for (const m of eligible.slice(0, 12)) {
    html += `<div class="card">
      <div class="card-h">
        <div><h4>${escapeHtml(m.grant_name)}</h4><div class="lvl">${escapeHtml(m.level)}</div></div>
        <div>
          <span class="pchip ${pchipClass(m.blended_probability_pct, m.eligible)}">${m.blended_probability_pct.toFixed(0)}%</span>
          <div class="ci">CI ${m.confidence_interval_pct[0].toFixed(0)}–${m.confidence_interval_pct[1].toFixed(0)}%</div>
        </div>
      </div>
      <div class="head">${escapeHtml(m.headline)}</div>
      <div class="dl-row">${deadlinePill(m)}<span class="dl-pattern">${escapeHtml(m.cut_off_pattern || '')}</span></div>
      <div class="meta">
        <span>fit <strong>${m.fit_total.toFixed(0)}/100</strong></span>
        <span>stat <strong>${m.statistical_estimate_pct.toFixed(0)}%</strong></span>
        <span>eval <strong>${m.evaluator.weighted.toFixed(2)}/5</strong></span>
        <span>${(m.funding_range_eur[0]/1e6).toFixed(1)}–${(m.funding_range_eur[1]/1e6).toFixed(1)} M€</span>
      </div>
    </div>`;
  }
  for (const m of ineligible.slice(0, 3)) {
    html += `<div class="card ineligible">
      <div class="card-h"><h4>${escapeHtml(m.grant_name)}</h4>
        <span class="pchip ineligible">N/A</span></div>
      <div class="head">${escapeHtml(m.blockers[0] || 'Ineligible')}</div>
    </div>`;
  }
  html += '</div>';
  return html;
}

function renderCombos(combos) {
  if (!combos || !combos.length) return 'No compatible combinations found.';
  let html = '<div class="combos"><h3 style="margin:0 0 8px;font-size:13px;">Top combinations (compatible + synergistic)</h3>';
  for (const [i, c] of combos.slice(0, 3).entries()) {
    html += `<div class="combo">
      <h4>Combo #${i+1} — <span class="ev">${(c.expected_value_eur/1e6).toFixed(1)} M€ expected</span></h4>
      <ul>${c.names.map(n => `<li>${escapeHtml(n)}</li>`).join('')}</ul>
      <div style="font-size:11px;color:var(--muted);">Cap théorique cumulé : ${(c.total_max_funding_eur/1e6).toFixed(1)} M€ · ${c.synergy_pairs} synergistic pair(s)</div>
    </div>`;
  }
  html += '</div>';
  return html;
}

function renderAsk(payload, deck) {
  let html = `<div class="ask"><h3>I need a few details to give you a precise ranking</h3>
    <div style="font-size:11px;color:var(--warn-fg);margin-bottom:8px;">${escapeHtml(payload.rationale || '')}</div>`;
  for (const q of payload.questions) {
    const fid = q.field.replace(/\./g, '_');
    html += `<div class="q"><label>${escapeHtml(q.question)}</label>
      <input type="text" id="ask_${fid}" data-field="${escapeHtml(q.field)}" placeholder="${escapeHtml(q.field)}" /></div>`;
  }
  html += `<button onclick="submitClarifications()">Re-run with answers</button></div>`;
  return html;
}

async function runAgent(clarifications) {
  const text = PITCH.value.trim();
  if (!text) {
    alert('Paste a pitchdeck first');
    return;
  }
  STREAM.innerHTML = '';
  const btn = document.getElementById('run-btn');
  btn.disabled = true;
  btn.textContent = '⏳ running...';

  try {
    const resp = await fetch('/api/agent/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        pitchdeck_text: text,
        pitchdeck_json: clarifications ? lastDeck : null,
        clarifications: clarifications || null,
        want_draft: document.getElementById('want_draft').checked,
      }),
    });
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const chunk = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const line = chunk.split('\n').find(l => l.startsWith('data: '));
        if (!line) continue;
        const ev = JSON.parse(line.slice(6));
        handleEvent(ev);
      }
    }
  } catch (e) {
    appendStep('error', 'Network error: ' + escapeHtml(e.message));
  } finally {
    btn.disabled = false;
    btn.textContent = '▶ Run agent';
  }
}

function renderPlan(plan) {
  const inferred = plan.ask_inferred ? `<span style="color:var(--muted);font-size:10px;font-weight:normal;"> · ask inferred from sector + TRL</span>` : '';
  let breakdown = '';
  for (const b of (plan.grants_breakdown || [])) {
    const cats = (b.categories_covered || []).map(c =>
      `<li><strong>${escapeHtml(c.category_label)}</strong>: ${(c.eur/1e3).toFixed(0)} k€</li>`
    ).join('');
    breakdown += `
    <div style="background:var(--bg);border:1px solid var(--line);padding:10px 12px;border-radius:6px;margin:6px 0;">
      <div style="display:flex;justify-content:space-between;align-items:baseline;">
        <strong style="font-size:12px;">${escapeHtml(b.grant_name)}</strong>
        <span style="color:var(--accent);font-weight:700;">${(b.expected_eur/1e3).toFixed(0)} k€</span>
      </div>
      <ul style="margin:6px 0 0;padding-left:16px;font-size:11px;color:var(--muted);">${cats}</ul>
    </div>`;
  }
  return `
  <div class="plan-block">
    <h3>Financing plan — ${(plan.total_ask_eur/1e6).toFixed(2)} M€${inferred}</h3>
    <div class="plan-summary">${escapeHtml(plan.summary || '')}</div>
    <div class="plan-grid">
      <div>
        <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;">Use of funds</div>
        ${plan.pie_chart_svg || ''}
      </div>
      <div>
        <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;">Funding sources</div>
        ${plan.stack_bar_svg || ''}
      </div>
    </div>
    <div style="margin-top:14px;">
      <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;">Allocation per grant (probability-weighted)</div>
      ${breakdown || '<div style="color:var(--muted);font-size:11px;">No grant allocation generated.</div>'}
    </div>
  </div>`;
}

function renderDossier(payload) {
  lastDossierUrl = payload.url;
  return `<div class="dossier-cta">
    <div>
      <strong>📄 VC-grade dossier ready</strong>
      <div style="font-size:11px;opacity:0.9;margin-top:2px;">Grants + VC matches + Excellence draft — A4 printable.</div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      <button class="link-btn" onclick="copyDossierLink('${payload.url}')">📋 Copy link</button>
      <a href="${payload.url}" target="_blank">Open dossier</a>
      <a href="${payload.print_url}" target="_blank">Download PDF</a>
    </div>
  </div>`;
}

function copyDossierLink(url) {
  const full = window.location.origin + url;
  navigator.clipboard.writeText(full).then(() => {
    const toasts = document.querySelectorAll('.copy-toast');
    toasts.forEach(t => t.remove());
    const toast = document.createElement('div');
    toast.className = 'copy-toast';
    toast.textContent = '✓ Link copied to clipboard';
    toast.style.cssText = 'position:fixed;bottom:20px;right:20px;background:#065f46;color:#fff;padding:10px 16px;border-radius:6px;font-size:13px;font-weight:600;z-index:999;';
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2500);
  }).catch(() => alert('Dossier URL: ' + window.location.origin + url));
}

function renderNoMatch(payload) {
  const blockers = payload.blockers || [];
  let rows = blockers.map(b => `
    <div class="blocker">
      <strong>${escapeHtml(b.label)}</strong> — affects ${b.count} programme(s)
      <p>${escapeHtml(b.action)}</p>
    </div>`).join('');
  return `<div class="no-match-panel">
    <h3>No eligible programmes found — here are the top blockers</h3>
    ${rows || '<p>Run with more complete pitchdeck data to get precise blockers.</p>'}
    <p style="font-size:11px;margin-top:8px;">Use the <strong>what-if TRL widget</strong> below to explore which TRL level unlocks programmes.</p>
  </div>`;
}

function renderVCMatches(vcs) {
  if (!vcs || !vcs.length) return '';
  let cards = vcs.map(vc => `
    <div class="vc-card">
      <h4>${escapeHtml(vc.name)}</h4>
      <div class="vc-loc">${escapeHtml(vc.city)}, ${escapeHtml(vc.country)}</div>
      <div style="font-size:11px;color:var(--muted);margin-bottom:4px;">${escapeHtml(vc.match_reason)}</div>
      <div style="font-size:10px;color:var(--muted);">${escapeHtml((vc.background||'').slice(0,140))}...</div>
      <div class="vc-score-bar"><div class="vc-score-fill" style="width:${Math.min(100,vc.match_score).toFixed(0)}%"></div></div>
      <div style="font-size:10px;color:var(--accent-2);font-weight:600;margin-top:2px;">Match ${vc.match_score.toFixed(0)}/100</div>
      <div class="vc-strat">${escapeHtml((vc.strategies||'').slice(0,80))}</div>
    </div>`).join('');
  return `<div style="margin-top:14px;">
    <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;">Matching investors (European VC database)</div>
    <div class="vc-grid">${cards}</div>
  </div>`;
}

function renderWhatIf(currentTrl) {
  return `<div class="whatif-panel" id="whatif-panel">
    <h3>What-if scenario</h3>
    <div class="whatif-row">
      <label>Change TRL:</label>
      <input type="number" id="whatif-trl" min="1" max="9" value="${currentTrl || 5}">
      <button onclick="runWhatIf()">Re-run ↺</button>
      <span style="font-size:11px;color:var(--muted);">See which grants unlock or drop out at a different TRL level</span>
    </div>
  </div>`;
}

function runWhatIf() {
  const trl = parseInt(document.getElementById('whatif-trl').value);
  if (!trl || trl < 1 || trl > 9 || !lastDeck) return;
  const clarifications = { product: { trl } };
  runAgent(clarifications);
}

function handleEvent(ev) {
  if (ev.type === 'thinking') {
    appendStep('thinking', escapeHtml(ev.payload));
  } else if (ev.type === 'parsed') {
    lastDeck = ev.payload;
    const c = ev.payload.company || {};
    const p = ev.payload.product || {};
    const f = ev.payload.funding_ask || {};
    appendStep('parsed',
      `Pitchdeck parsed: <strong>${escapeHtml(c.name||'?')}</strong> · ${escapeHtml(c.country||'?')}${c.region ? '/'+escapeHtml(c.region) : ''} · sectors: ${(p.sectors||[]).map(escapeHtml).join(', ')||'?'} · TRL ${p.trl??'?'} · ask ${((f.amount_eur||0)/1e6).toFixed(1)} M€`);
  } else if (ev.type === 'ask') {
    appendStep('thinking', renderAsk(ev.payload, lastDeck));
  } else if (ev.type === 'matched') {
    // Sensitive sector warning
    const sensitive = (ev.payload.stats || {}).sensitive_sectors || [];
    if (sensitive.length) {
      appendStep('thinking', `<div class="sensitive-warn"><strong>Sensitive sector detected: ${sensitive.map(escapeHtml).join(', ')}</strong> — most public programmes apply specific exclusions or requirements; verify each call's policy before applying.</div>`);
    }
    appendStep('matched', renderMatches(ev.payload));
  } else if (ev.type === 'no_match') {
    appendStep('error', renderNoMatch(ev.payload));
  } else if (ev.type === 'combos') {
    appendStep('combos', renderCombos(ev.payload));
  } else if (ev.type === 'plan') {
    appendStep('combos', renderPlan(ev.payload));
  } else if (ev.type === 'vc_matches') {
    if (ev.payload && ev.payload.length) {
      appendStep('combos', renderVCMatches(ev.payload));
    }
  } else if (ev.type === 'draft') {
    appendStep('draft', `<h3 style="margin:0 0 8px;font-size:13px;">Excellence draft — ${escapeHtml(ev.payload.grant)}</h3>
      <div style="font-size:10px;color:var(--muted);margin-bottom:6px;">Sector-adapted by Cerebras Qwen 3 235B · starting point only</div>
      <div class="draft-block">${escapeHtml(ev.payload.text)}</div>`);
  } else if (ev.type === 'dossier') {
    appendStep('combos', renderDossier(ev.payload));
    // Show what-if TRL widget after dossier
    if (lastDeck) {
      const trl = (lastDeck.product || {}).trl || 5;
      appendStep('combos', renderWhatIf(trl));
    }
  } else if (ev.type === 'done') {
    appendStep('parsed', '<strong>All agents done. Dossier ready.</strong>');
  } else if (ev.type === 'error') {
    appendStep('error', escapeHtml(ev.payload));
  }
}

function submitClarifications() {
  const inputs = STREAM.querySelectorAll('.ask input');
  const clarifications = {};
  for (const inp of inputs) {
    const field = inp.dataset.field;
    let val = inp.value.trim();
    if (!val) continue;
    // Coerce
    if (field.endsWith('amount_eur')) {
      val = parseFloat(val.replace(/[^0-9.]/g, ''));
      if (val < 1000) val *= 1e6; // assume "4.5" means 4.5M
    } else if (field.endsWith('trl')) {
      val = parseInt(val);
    }
    const parts = field.split('.');
    let cur = clarifications;
    for (let i = 0; i < parts.length - 1; i++) {
      cur[parts[i]] = cur[parts[i]] || {};
      cur = cur[parts[i]];
    }
    cur[parts[parts.length - 1]] = val;
  }
  runAgent(clarifications);
}
</script>
</body>
</html>
"""


# -----------------------------------------------------------------------------
# CLI entry
# -----------------------------------------------------------------------------

def main():
    if not HAS_FASTAPI:
        sys.stderr.write("ERROR: FastAPI not installed. Run: pip install fastapi uvicorn httpx\n")
        sys.exit(1)
    try:
        import uvicorn
    except ImportError:
        sys.stderr.write("ERROR: uvicorn not installed. Run: pip install uvicorn\n")
        sys.exit(1)
    print(textwrap.dedent(f"""
    ┌────────────────────────────────────────────────────────────────┐
    │  FundsAgent · Paris Fintech Hackathon 2026 · Track B2G        │
    │                                                                │
    │  {len(GRANTS_DB['grants'])} EU/FR grants loaded                                  │
    │  {len(VC_DB)} European VCs loaded                                   │
    │  Cerebras: {'configured ✓' if CEREBRAS_API_KEY else 'NOT configured (heuristic fallback)':52s}│
    │                                                                │
    │  → http://localhost:8000                                       │
    └────────────────────────────────────────────────────────────────┘
    """))
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))



if __name__ == "__main__":
    main()
