"""OSINT-specific scoring and ranking utilities."""

from __future__ import annotations

import re
from urllib.parse import urlparse


SOURCE_WEIGHTS = {
    "linkedin.com": 20,
    "github.com": 18,
    "medium.com": 12,
    "dev.to": 12,
    "instagram.com": 12,
    "facebook.com": 10,
    "x.com": 10,
    "twitter.com": 10,
    "tiktok.com": 8,
    "academia.edu": 12,
    "researchgate.net": 12,
}

OSINT_NOISE_KEYWORDS = [
    "free lookup",
    "people finder",
    "background check",
    "password dump",
    "database leak",
    "leaked password",
    "hack",
    "dox",
    "doxx",
    "pastebin dump",
]

SEVERE_NOISE_KEYWORDS = {
    "password dump",
    "database leak",
    "leaked password",
    "pastebin dump",
    "dox",
    "doxx",
}

SUSPICIOUS_TLDS = {
    ".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".click",
}

SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "ow.ly", "cutt.ly",
}

GENERIC_TITLE_TERMS = {
    "home", "profile", "search", "result", "results", "index", "welcome", "untitled",
}


class OSINTScorer:
    """Score OSINT results using deterministic evidence-focused rules."""

    def _extract_domain(self, link: str) -> str:
        try:
            return urlparse(link).netloc.lower().replace("www.", "")
        except Exception:
            return ""

    def _normalize(self, value: str) -> str:
        return re.sub(r"\s+", " ", (value or "").strip().lower())

    def _tokens(self, value: str) -> list[str]:
        return [t for t in re.split(r"\s+", self._normalize(value)) if t]

    def _identity_match_score(self, result: dict, target: str) -> int:
        score = 0
        title = self._normalize(result.get("title", ""))
        desc = self._normalize(result.get("description", ""))
        link = result.get("link", "")
        target_norm = self._normalize(target)
        target_tokens = self._tokens(target_norm)

        if target_norm and target_norm in title:
            score += 20
        if target_norm and target_norm in desc:
            score += 10

        if target_tokens and len(target_tokens) >= 2:
            title_words = title.split()
            positions = []
            for token in target_tokens:
                if token in title_words:
                    positions.append(title_words.index(token))
            if len(positions) >= 2:
                distance = max(positions) - min(positions)
                if distance <= 3:
                    score += 5

        domain = self._extract_domain(link)
        entities = result.get("osint_entities", {}) or {}
        usernames = entities.get("usernames", []) or []
        joined_usernames = " ".join([self._normalize(u) for u in usernames])
        if any(t in domain for t in target_tokens if len(t) >= 3) or any(
            t in joined_usernames for t in target_tokens if len(t) >= 3
        ):
            score += 5

        return min(35, score)

    def _source_reliability_score(self, result: dict) -> int:
        domain = self._extract_domain(result.get("link", ""))
        score = 0
        for source, weight in SOURCE_WEIGHTS.items():
            if domain == source or domain.endswith(f".{source}"):
                score = max(score, weight)
        return min(20, score)

    def _entity_density_score(self, result: dict) -> int:
        entities = result.get("osint_entities", {}) or {}
        score = 0

        if entities.get("emails"):
            score += 8
        if entities.get("phones"):
            score += 8
        if entities.get("usernames"):
            score += 5
        if entities.get("profile_urls"):
            score += 5
        if len(entities.get("links", [])) > 1:
            score += 3

        return min(20, score)

    def _evidence_quality_score(self, result: dict) -> int:
        score = 0
        title = (result.get("title") or "").strip()
        desc = (result.get("description") or "").strip()
        domain = self._extract_domain(result.get("link", ""))
        platform = (result.get("osint_platform") or "").strip()

        if len(desc) >= 50:
            score += 5

        title_norm = self._normalize(title)
        if title_norm and title_norm not in GENERIC_TITLE_TERMS:
            score += 5

        if platform and platform != "unknown":
            score += 5
        elif any(domain == d or domain.endswith(f".{d}") for d in SOURCE_WEIGHTS):
            score += 5

        return min(15, score)

    def _technical_score(self, result: dict) -> int:
        score = 0
        link = result.get("link", "") or ""
        domain = self._extract_domain(link)

        if link.startswith("http://") or link.startswith("https://"):
            score += 5
        if domain and domain not in SHORTENER_DOMAINS:
            score += 3
        try:
            parsed = urlparse(link)
            if parsed.path and parsed.path not in {"", "/"}:
                score += 2
        except Exception:
            pass

        return min(10, score)

    def _noise_penalty(self, result: dict) -> tuple[int, bool]:
        text = " ".join(
            [
                self._normalize(result.get("title", "")),
                self._normalize(result.get("description", "")),
                self._normalize(result.get("link", "")),
            ]
        )
        link = result.get("link", "")
        domain = self._extract_domain(link)
        penalty = 0
        severe = False

        if any(k in text for k in ["password dump", "leaked password", "database leak", "pastebin dump"]):
            penalty += 15
            severe = True

        if any(k in text for k in ["free lookup", "people finder", "background check"]):
            penalty += 10

        if any(domain.endswith(tld) for tld in SUSPICIOUS_TLDS) or domain in SHORTENER_DOMAINS:
            penalty += 10

        title = self._normalize(result.get("title", ""))
        desc = self._normalize(result.get("description", ""))
        if len(title) < 6 or len(desc) < 20:
            penalty += 5

        if any(keyword in text for keyword in SEVERE_NOISE_KEYWORDS):
            severe = True

        for keyword in OSINT_NOISE_KEYWORDS:
            if keyword in text:
                penalty += 1

        return min(30, penalty), severe

    def _confidence_label(self, score: int) -> str:
        if score >= 80:
            return "High confidence"
        if score >= 60:
            return "Medium confidence"
        if score >= 40:
            return "Low confidence"
        return "Unverified"

    def _build_evidence_summary(self, result: dict, breakdown: dict) -> str:
        reasons = []
        if breakdown.get("identity_match_score", 0) >= 20:
            reasons.append("exact target match")
        if breakdown.get("source_reliability_score", 0) >= 12:
            reasons.append("reliable public profile source")
        entities = result.get("osint_entities", {}) or {}
        if entities.get("usernames"):
            reasons.append("username found")
        if entities.get("emails"):
            reasons.append("public email found")
        if entities.get("phones"):
            reasons.append("public phone found")

        if not reasons:
            reasons.append("limited public evidence")
        return ", ".join(reasons[:4])

    def score_result(self, result: dict, target: str) -> dict:
        identity = self._identity_match_score(result, target)
        source = self._source_reliability_score(result)
        entity = self._entity_density_score(result)
        evidence = self._evidence_quality_score(result)
        technical = self._technical_score(result)
        penalty, severe_noise = self._noise_penalty(result)

        total = max(0, min(100, identity + source + entity + evidence + technical - penalty))

        result["osint_score"] = total
        result["osint_confidence"] = self._confidence_label(total)
        result["osint_score_breakdown"] = {
            "identity_match_score": identity,
            "source_reliability_score": source,
            "entity_density_score": entity,
            "evidence_quality_score": evidence,
            "technical_score": technical,
            "noise_penalty": penalty,
            "total_score": total,
        }
        result["osint_noise_flag"] = severe_noise or penalty >= 15
        result["osint_safety_note"] = (
            "Potentially unsafe/noisy result; treat as unverified public evidence."
            if result["osint_noise_flag"]
            else "Publicly visible evidence only; possible match, not confirmed identity."
        )
        result["osint_evidence_summary"] = self._build_evidence_summary(result, result["osint_score_breakdown"])
        return result

    def rank_results(self, results: list[dict], target: str) -> list[dict]:
        scored = [self.score_result(dict(r), target) for r in results]
        def _date_key(item: dict) -> float:
            d = item.get("date")
            try:
                return d.timestamp() if d else 0.0
            except Exception:
                return 0.0
        scored.sort(
            key=lambda x: (
                x.get("osint_score", 0),
                x.get("quality_score", 0),
                _date_key(x),
            ),
            reverse=True,
        )
        return scored
