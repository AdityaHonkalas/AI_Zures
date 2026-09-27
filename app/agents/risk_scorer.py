"""
Agent 3 — Risk Scorer & Test Prioritiser

Sub-modules:
  3.1 Defect History Scorer    — normalised score from defect_history.json (weight 35%)
  3.2 Code Churn Scorer        — normalised from recent_commits field (weight 20%)
  3.3 Telemetry Signal Scorer  — normalised from telemetry.json error_rate + page_views (weight 25%)
  3.4 Semantic Similarity Scorer — ChromaDB cosine similarity to diff content (weight 20%)
  3.5 Composite Risk Ranker    — weighted sum + LLM justifications for top tests

Input:  context["impact_map"] (ImpactMap from Agent 2)
        context["diff_raw"]   (raw diff from Agent 1)
Output: context["risk_ranked_tests"] = RiskRankedTestList dict

Scoring weights: defect=0.35, telemetry=0.25, churn=0.20, semantic=0.20
"""
from __future__ import annotations

import logging
import math
from typing import Any

from app.utils import llm_client, vector_store
from app.utils.fixture_loader import load_fixture, load_fixture_as_dict

logger = logging.getLogger(__name__)

# Scoring weights
W_DEFECT   = 0.35
W_TELEMETRY = 0.25
W_CHURN    = 0.20
W_SEMANTIC = 0.20

# How many test cases to ask the LLM to justify
TOP_N_JUSTIFY = 10


# ── Normalisation helpers ─────────────────────────────────────────────────────

def _minmax(value: float, min_val: float, max_val: float) -> float:
    """Normalise a value to [0, 1] using min-max scaling. Returns 0.5 if range is zero."""
    if max_val == min_val:
        return 0.5
    return (value - min_val) / (max_val - min_val)


# ── 3.1 Defect History Scorer ────────────────────────────────────────────────

def _defect_scores(modules: list[str]) -> dict[str, float]:
    """
    Return a dict of module → normalised defect score [0, 1].
    Score is based on defect_count weighted by severity_avg.
    """
    defect_data: list[dict] = load_fixture("defect_history")
    defect_by_module: dict[str, dict] = {d["module"]: d for d in defect_data}

    raw: dict[str, float] = {}
    for module in modules:
        d = defect_by_module.get(module)
        if d:
            raw[module] = d["defect_count"] * d["severity_avg"]
        else:
            raw[module] = 0.0

    vals = list(raw.values())
    mn, mx = min(vals, default=0.0), max(vals, default=1.0)
    return {m: _minmax(v, mn, mx) for m, v in raw.items()}


# ── 3.2 Code Churn Scorer ─────────────────────────────────────────────────────

def _churn_scores(modules: list[str]) -> dict[str, float]:
    """
    Return a dict of module → normalised churn score [0, 1].
    Uses recent_commits from defect_history fixture as a proxy for churn.
    """
    defect_data: list[dict] = load_fixture("defect_history")
    churn_by_module: dict[str, float] = {d["module"]: float(d.get("recent_commits", 0)) for d in defect_data}

    raw = {m: churn_by_module.get(m, 0.0) for m in modules}
    vals = list(raw.values())
    mn, mx = min(vals, default=0.0), max(vals, default=1.0)
    return {m: _minmax(v, mn, mx) for m, v in raw.items()}


# ── 3.3 Telemetry Signal Scorer ───────────────────────────────────────────────

def _telemetry_scores(modules: list[str]) -> dict[str, float]:
    """
    Return a dict of module → normalised telemetry score [0, 1].
    Combines error_rate (higher = riskier) and page_views_per_day (higher = more important).
    Score = sqrt(error_rate * page_views) to balance both signals.
    """
    telemetry_data: list[dict] = load_fixture("telemetry")
    tel_by_module: dict[str, dict] = {t["module"]: t for t in telemetry_data}

    raw: dict[str, float] = {}
    for module in modules:
        t = tel_by_module.get(module)
        if t:
            # Geometric mean of error_rate and normalised page views
            views_norm = t["page_views_per_day"] / 20000.0  # normalise against max expected
            raw[module] = math.sqrt(t["error_rate"] * max(views_norm, 0.0001))
        else:
            raw[module] = 0.0

    vals = list(raw.values())
    mn, mx = min(vals, default=0.0), max(vals, default=1.0)
    return {m: _minmax(v, mn, mx) for m, v in raw.items()}


# ── 3.4 Semantic Similarity Scorer ───────────────────────────────────────────

def _semantic_scores(
    diff_text: str,
    candidate_test_ids: list[str],
) -> dict[str, float]:
    """
    Embed the diff text and query ChromaDB for semantic similarity to test cases.
    Returns dict of test_id → similarity score [0, 1].
    Distance from ChromaDB (cosine) is in [0, 2] where 0=identical.
    We convert to similarity = 1 - (distance / 2).
    """
    if not diff_text or not diff_text.strip():
        return {tid: 0.0 for tid in candidate_test_ids}

    try:
        query_embedding = llm_client.embed(diff_text[:4000])  # cap text to avoid token overflow
        results = vector_store.query(
            collection="test-case-index",
            query_embedding=query_embedding,
            n_results=min(len(candidate_test_ids), 20),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Semantic scoring failed: %s. Using 0.0 scores.", exc)
        return {tid: 0.0 for tid in candidate_test_ids}

    score_by_id: dict[str, float] = {}
    for r in results:
        tid = r["metadata"].get("test_id", r["id"])
        distance = r["distance"]
        # Cosine distance in [0, 2]; convert to similarity in [0, 1]
        score_by_id[tid] = max(0.0, 1.0 - (distance / 2.0))

    # Tests not found in ChromaDB get a neutral score
    for tid in candidate_test_ids:
        if tid not in score_by_id:
            score_by_id[tid] = 0.0

    return score_by_id


# ── 3.5 Composite Risk Ranker ─────────────────────────────────────────────────

_RANKER_SYSTEM = """You are a QA risk analyst. Given test cases with risk scores,
provide a concise one-sentence justification for why the top-ranked tests are highest priority.
Respond ONLY with valid JSON."""

_RANKER_PROMPT = """The following test cases have been scored by risk signals.
Provide a one-sentence justification for each of the top {n} tests explaining why it is high priority.

Tests (in ranked order):
{tests_json}

Return JSON in exactly this format:
{{
  "justifications": {{
    "TC-001": "High defect density in payment module with frequent user traffic.",
    "TC-002": "..."
  }}
}}"""


def _generate_justifications(top_tests: list[dict]) -> dict[str, str]:
    """Use LLM to generate one-line justification for each top-ranked test."""
    import json
    slim = [
        {
            "test_id":   t["test_id"],
            "test_name": t["test_name"],
            "module":    t.get("module", ""),
            "risk_score": round(t["risk_score"], 3),
            "defect_score":    round(t["score_breakdown"]["defect_score"], 3),
            "telemetry_score": round(t["score_breakdown"]["telemetry_score"], 3),
            "churn_score":     round(t["score_breakdown"]["churn_score"], 3),
            "semantic_score":  round(t["score_breakdown"]["semantic_score"], 3),
        }
        for t in top_tests
    ]
    prompt = _RANKER_PROMPT.format(
        n=len(top_tests),
        tests_json=json.dumps(slim, indent=2),
    )
    try:
        result = llm_client.chat(
            prompt=prompt,
            system=_RANKER_SYSTEM,
            model=llm_client.REASONING_MODEL,
            expect_json=True,
        )
        return result.get("justifications", {})
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM justification generation failed: %s", exc)
        return {}


# ── Main agent entry point ────────────────────────────────────────────────────

def run(context: dict[str, Any]) -> dict[str, Any]:
    """
    Run Agent 3 — Risk Scorer & Test Prioritiser.

    Populates context["risk_ranked_tests"] with RiskRankedTestList.
    """
    impact_map: dict = context.get("impact_map", {})
    all_impacted = (
        impact_map.get("directly_impacted_modules", [])
        + impact_map.get("transitively_impacted_modules", [])
    )
    all_impacted = list(dict.fromkeys(all_impacted))  # dedupe preserving order

    if not all_impacted:
        logger.warning("Agent 3 — no impacted modules; returning empty risk list.")
        context["risk_ranked_tests"] = {"ranked_tests": []}
        return context

    logger.info("Agent 3 — Risk Scorer: scoring tests for modules %s", all_impacted)

    # ── Load candidate test cases ────────────────────────────────────────────
    all_tests: list[dict] = load_fixture("test_cases")
    candidates = [tc for tc in all_tests if tc.get("module") in set(all_impacted)]
    if not candidates:
        logger.warning("No test cases found for impacted modules.")
        context["risk_ranked_tests"] = {"ranked_tests": []}
        return context

    # ── Compute individual scorer outputs ────────────────────────────────────
    defect_map    = _defect_scores(all_impacted)
    churn_map     = _churn_scores(all_impacted)
    telemetry_map = _telemetry_scores(all_impacted)
    candidate_ids = [tc["test_id"] for tc in candidates]
    semantic_map  = _semantic_scores(context.get("diff_raw", ""), candidate_ids)

    # ── Composite scoring ────────────────────────────────────────────────────
    ranked: list[dict] = []
    for tc in candidates:
        module = tc.get("module", "")
        d_score = defect_map.get(module, 0.0)
        c_score = churn_map.get(module, 0.0)
        t_score = telemetry_map.get(module, 0.0)
        s_score = semantic_map.get(tc["test_id"], 0.0)

        composite = (
            W_DEFECT    * d_score
            + W_TELEMETRY * t_score
            + W_CHURN     * c_score
            + W_SEMANTIC  * s_score
        )

        ranked.append({
            "test_id":   tc["test_id"],
            "test_name": tc["test_name"],
            "module":    module,
            "journey_id": tc.get("journey_id", ""),
            "browser":   tc.get("browser", ""),
            "environment": tc.get("environment", ""),
            "risk_score": round(composite, 4),
            "score_breakdown": {
                "defect_score":    round(d_score, 4),
                "churn_score":     round(c_score, 4),
                "telemetry_score": round(t_score, 4),
                "semantic_score":  round(s_score, 4),
            },
            "rank": 0,  # set after sort
            "justification": "",
        })

    ranked.sort(key=lambda x: x["risk_score"], reverse=True)
    for i, item in enumerate(ranked):
        item["rank"] = i + 1

    # ── Generate LLM justifications for top N ────────────────────────────────
    top_n = ranked[:TOP_N_JUSTIFY]
    justifications = _generate_justifications(top_n)
    for item in ranked:
        if item["test_id"] in justifications:
            item["justification"] = justifications[item["test_id"]]

    logger.info("Agent 3 complete: %d tests ranked.", len(ranked))

    context["risk_ranked_tests"] = {"ranked_tests": ranked}
    return context
