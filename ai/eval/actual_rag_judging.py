from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

from ai.eval.actual_rag_dataset import EvalItem, ExpectedEvidence


DEFAULT_ABSTENTION_PHRASES = (
    "문서에서 찾을 수 없습니다",
    "문서에서 관련 정보를 찾을 수 없습니다",
    "제공된 context에 답이 없습니다",
    "제공된 문맥에 답이 없습니다",
    "제공된 근거만으로는 답할 수 없습니다",
    "답변할 수 없습니다",
    "근거가 없습니다",
    "not available from the provided context",
    "not found in the provided context",
    "cannot answer from the provided context",
    "no relevant passages were retrieved",
    "not enough information",
)

GENERIC_ANCHOR_STOPWORDS = {
    "a",
    "an",
    "and",
    "answer",
    "animation",
    "anime",
    "context",
    "document",
    "from",
    "source",
    "text",
    "the",
    "tv",
    "애니",
    "애니메이션",
    "감독",
    "기반",
    "대한",
    "만화",
    "문서",
    "방영",
    "시기",
    "시기는",
    "시리즈",
    "라이트",
    "노벨",
    "원작",
    "일본",
    "제3기",
    "정보",
}

KOREAN_GENERIC_SUFFIXES = ("은", "는", "이", "가", "을", "를", "의", "에", "에서", "으로", "로", "와", "과", "도", "만")


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def normalize_answer_text(value: str) -> str:
    lowered = _clean(value).casefold()
    lowered = re.sub(r"[^\w\s가-힣ぁ-んァ-ン一-龯々]", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", lowered).strip()


def answer_correct(generated_answer: str, *, expected_answer: str = "", aliases: Sequence[str] = ()) -> bool:
    generated = normalize_answer_text(generated_answer)
    if not generated:
        return False
    expected_values = [expected_answer, *aliases]
    normalized_expected = [normalize_answer_text(value) for value in expected_values if normalize_answer_text(value)]
    return generated in normalized_expected


def abstains(answer: str, *, phrases: Sequence[str] = DEFAULT_ABSTENTION_PHRASES) -> bool:
    normalized = _clean(answer).casefold()
    if not normalized:
        return False
    return any(_clean(phrase).casefold() in normalized for phrase in phrases if _clean(phrase))


def _token_set(value: str) -> set[str]:
    normalized = normalize_answer_text(value)
    return {token for token in normalized.split() if len(token) > 1}


def _token_overlap_ratio(left: str, right: str) -> float:
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))


def _anchor_stopwords() -> set[str]:
    return {normalize_answer_text(value) for value in GENERIC_ANCHOR_STOPWORDS}


def _is_generic_anchor(normalized: str, stopwords: set[str]) -> bool:
    if normalized in stopwords:
        return True
    for stopword in stopwords:
        if not re.fullmatch(r"[가-힣]+", stopword):
            continue
        if any(normalized == f"{stopword}{suffix}" for suffix in KOREAN_GENERIC_SUFFIXES):
            return True
    return False


def _candidate_anchors(*values: str) -> set[str]:
    anchors: set[str] = set()
    stopwords = _anchor_stopwords()
    for value in values:
        raw = _clean(value)
        if not raw:
            continue
        bracketed = re.findall(r"[\[(（【](.*?)[\])）】]", raw)
        scan_values = [raw, *bracketed]
        for scan in scan_values:
            for token in re.findall(
                r"\d{1,4}(?:년|월|일)|\d{1,4}[가-힣]{1,8}|\d{2,}|[A-Za-z][A-Za-z0-9_-]{3,}|[가-힣]{3,}|[ぁ-んァ-ン一-龯々]{2,}",
                scan,
            ):
                normalized = normalize_answer_text(token)
                if not normalized or _is_generic_anchor(normalized, stopwords):
                    continue
                anchors.add(normalized)
    return anchors


def _evidence_match_anchors(item: EvalItem, evidence: ExpectedEvidence) -> set[str]:
    return _candidate_anchors(item.expected_answer, *item.expected_answer_aliases, evidence.text)


def _evidence_resolution_anchors(item: EvalItem, evidence: ExpectedEvidence) -> set[str]:
    return _candidate_anchors(item.query, item.expected_answer, *item.expected_answer_aliases, evidence.text)


def _anchor_in_text(anchors: Iterable[str], text: str) -> bool:
    normalized = normalize_answer_text(text)
    token_set = set(normalized.split())
    compact_korean = re.sub(r"\s+", "", normalized) if re.search(r"[가-힣]", normalized) else ""
    for anchor in anchors:
        if not anchor:
            continue
        if anchor in token_set or anchor in normalized:
            return True
        if (
            compact_korean
            and len(anchor) >= 3
            and re.fullmatch(r"[가-힣]+", anchor)
            and anchor in compact_korean
        ):
            return True
    return False


def _numeric_or_date_anchors(anchors: Iterable[str]) -> set[str]:
    return {anchor for anchor in anchors if re.search(r"\d", anchor)}


def _anchor_requirements_satisfied(anchors: Iterable[str], text: str) -> bool:
    anchor_set = {anchor for anchor in anchors if anchor}
    if not _anchor_in_text(anchor_set, text):
        return False
    numeric_anchors = _numeric_or_date_anchors(anchor_set)
    if numeric_anchors and not all(_anchor_in_text([anchor], text) for anchor in numeric_anchors):
        return False
    return True


def heuristic_judge_answer(
    *,
    generated_answer: str,
    expected_answer: str = "",
    aliases: Sequence[str] = (),
    expected_evidence_texts: Sequence[str] = (),
    retrieved_context_texts: Sequence[str] = (),
    notes: str = "",
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Deterministic provisional judge used when exact matching is too strict."""

    generated = _clean(generated_answer)
    if not generated:
        return {
            "passed": False,
            "provisional": True,
            "judge_version": "heuristic_overlap_v1",
            "judge_kind": "deterministic_heuristic",
            "threshold": threshold,
            "reason": "generation_empty",
        }
    expected_values = [expected_answer, *aliases]
    generated_norm = normalize_answer_text(generated)
    for value in expected_values:
        expected_norm = normalize_answer_text(value)
        if expected_norm and expected_norm in generated_norm:
            return {
                "passed": True,
                "provisional": True,
                "judge_version": "heuristic_overlap_v1",
                "judge_kind": "deterministic_heuristic",
                "threshold": threshold,
                "reason": "expected_answer_contained_in_generated_answer",
            }
    anchor_source_values = [value for value in expected_values if _clean(value)] or list(expected_evidence_texts)
    required_numeric_anchors = _numeric_or_date_anchors(_candidate_anchors(*anchor_source_values))
    if required_numeric_anchors and not all(
        _anchor_in_text([anchor], generated)
        for anchor in required_numeric_anchors
    ):
        return {
            "passed": False,
            "provisional": True,
            "judge_version": "heuristic_overlap_v1",
            "judge_kind": "deterministic_heuristic",
            "threshold": threshold,
            "reason": "expected_numeric_or_date_anchor_missing_from_generated_answer",
            "required_numeric_or_date_anchors": sorted(required_numeric_anchors),
        }
    best_evidence_overlap = max(
        [_token_overlap_ratio(generated, evidence_text) for evidence_text in expected_evidence_texts if _clean(evidence_text)]
        or [0.0]
    )
    if best_evidence_overlap >= threshold:
        return {
            "passed": True,
            "provisional": True,
            "judge_version": "heuristic_overlap_v1",
            "judge_kind": "deterministic_heuristic",
            "threshold": threshold,
            "reason": "generated_answer_overlaps_expected_evidence",
            "overlap": round(best_evidence_overlap, 6),
        }
    best_context_overlap = max(
        [_token_overlap_ratio(generated, context_text) for context_text in retrieved_context_texts if _clean(context_text)]
        or [0.0]
    )
    if best_context_overlap >= threshold and not expected_values and not expected_evidence_texts and _clean(notes):
        return {
            "passed": True,
            "provisional": True,
            "judge_version": "heuristic_overlap_v1",
            "judge_kind": "deterministic_heuristic",
            "threshold": threshold,
            "reason": "generated_answer_context_supported_with_notes_only",
            "overlap": round(best_context_overlap, 6),
        }
    return {
        "passed": False,
        "provisional": True,
        "judge_version": "heuristic_overlap_v1",
        "judge_kind": "deterministic_heuristic",
        "threshold": threshold,
        "reason": "insufficient_expected_answer_or_evidence_overlap",
        "best_evidence_overlap": round(best_evidence_overlap, 6),
        "best_context_overlap": round(best_context_overlap, 6),
    }


class HeuristicJudgeAdapter:
    def __init__(self, *, threshold: float = 0.5) -> None:
        self.threshold = float(threshold)

    @property
    def config(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "tier": "provisional",
            "judge_kind": "deterministic_heuristic",
            "judge_version": "heuristic_overlap_v1",
            "threshold": self.threshold,
            "prompt": "No LLM prompt is used by heuristic_overlap_v1; future LLM adapters must record prompt/model/config here.",
            "external_api_calls": False,
        }

    def evaluate(
        self,
        *,
        item: EvalItem,
        generated_answer: str,
        retrieved_context_texts: Sequence[str],
        expected_evidence_texts: Sequence[str],
    ) -> dict[str, Any]:
        return heuristic_judge_answer(
            generated_answer=generated_answer,
            expected_answer=item.expected_answer,
            aliases=item.expected_answer_aliases,
            expected_evidence_texts=expected_evidence_texts,
            retrieved_context_texts=retrieved_context_texts,
            notes=item.notes,
            threshold=self.threshold,
        )
