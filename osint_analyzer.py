import re
from collections import Counter, defaultdict
from urllib.parse import urlparse

from ai_engine import AIEngine


USERNAME_PATTERNS = {
    "linkedin": r"linkedin\.com/in/([A-Za-z0-9\-_%]+)",
    "github": r"github\.com/([A-Za-z0-9\-]+)",
    "instagram": r"instagram\.com/([A-Za-z0-9._]+)",
    "facebook": r"facebook\.com/([A-Za-z0-9.]+)",
    "twitter": r"(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)",
    "tiktok": r"tiktok\.com/@([A-Za-z0-9._]+)",
}

ORG_SUFFIXES = (
    "inc", "llc", "ltd", "corp", "corporation", "company", "co", "pt", "tbk", "foundation", "universitas",
)


class OSINTAnalyzer:
    """Analyze publicly visible entities from search-result text and links."""

    def __init__(self):
        self.ai = AIEngine()

    def extract_domain(self, url: str) -> str:
        try:
            return urlparse(url).netloc.lower().replace("www.", "")
        except Exception:
            return ""

    def detect_platform(self, url: str) -> str:
        domain = self.extract_domain(url)
        if not domain:
            return "unknown"

        platform_map = {
            "linkedin.com": "linkedin",
            "github.com": "github",
            "instagram.com": "instagram",
            "facebook.com": "facebook",
            "twitter.com": "twitter",
            "x.com": "x",
            "tiktok.com": "tiktok",
            "medium.com": "medium",
            "dev.to": "devto",
            "researchgate.net": "researchgate",
            "academia.edu": "academia",
        }

        for host, platform in platform_map.items():
            if domain == host or domain.endswith(f".{host}"):
                return platform
        return "unknown"

    def _extract_organizations(self, text: str) -> list[str]:
        organizations = set()

        # Pattern: capitalized multi-word names ending with common organization suffixes
        suffix_pattern = "|".join(ORG_SUFFIXES)
        pattern = re.compile(
            rf"\b([A-Z][A-Za-z0-9&\-]*(?:\s+[A-Z][A-Za-z0-9&\-]*){{0,4}}\s+(?:{suffix_pattern})\b(?:\.?))",
            re.IGNORECASE,
        )
        for m in pattern.findall(text or ""):
            cleaned = " ".join(m.split()).strip(" ,.;:-")
            if len(cleaned) >= 4:
                organizations.add(cleaned)

        return sorted(organizations)

    def extract_entities_regex(self, text: str) -> dict:
        """Extract publicly visible entities from text using deterministic regexes."""
        src = text or ""

        emails = sorted(set(re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", src)))
        phones = sorted(set(re.findall(r"(?:\+?62|0)[2-9]\d{7,11}", src)))

        raw_links = re.findall(r"https?://[^\s\]\[\)\(\"'<>]+", src)
        links = []
        for link in sorted(set(raw_links)):
            low = link.lower().rstrip(".,;!?")
            if any(ext in low for ext in [".jpg", ".jpeg", ".png", ".gif", ".css", ".js", ".woff"]):
                continue
            links.append(link.rstrip(".,;!?"))

        usernames = set()
        usernames_by_platform = defaultdict(list)
        profile_urls = set()

        for platform, pattern in USERNAME_PATTERNS.items():
            matches = re.findall(pattern, src, flags=re.IGNORECASE)
            for uname in matches:
                clean = uname.strip("/@ ")
                if clean:
                    usernames.add(clean)
                    usernames_by_platform[platform].append(clean)

        for link in links:
            platform = self.detect_platform(link)
            if platform != "unknown":
                profile_urls.add(link)

        domains = sorted({self.extract_domain(link) for link in links if self.extract_domain(link)})

        entities = {
            "emails": emails,
            "phones": phones,
            "links": links,
            "usernames": sorted(usernames),
            "usernames_by_platform": {
                k: sorted(set(v)) for k, v in usernames_by_platform.items() if v
            },
            "profile_urls": sorted(profile_urls),
            "domains": domains,
            "organizations": self._extract_organizations(src),
        }
        return entities

    def enrich_result_entities(self, result: dict) -> dict:
        text = " ".join([
            result.get("title", "") or "",
            result.get("description", "") or "",
            result.get("link", "") or "",
        ])
        result["osint_entities"] = self.extract_entities_regex(text)
        result["osint_platform"] = self.detect_platform(result.get("link", ""))
        return result

    def correlate_identity(self, results: list[dict], target: str) -> dict:
        target_norm = (target or "").strip().lower()

        domains_with_target = set()
        username_platforms = defaultdict(set)
        all_usernames = Counter()
        matched_platforms = set()
        document_evidence = 0

        public_emails = set()
        public_phones = set()

        for r in results:
            title = (r.get("title") or "").lower()
            desc = (r.get("description") or "").lower()
            link = r.get("link", "") or ""
            domain = self.extract_domain(link)
            platform = r.get("osint_platform") or self.detect_platform(link)

            entities = r.get("osint_entities") or self.extract_entities_regex(
                " ".join([r.get("title", "") or "", r.get("description", "") or "", link])
            )

            for email in entities.get("emails", []):
                public_emails.add(email)
            for phone in entities.get("phones", []):
                public_phones.add(phone)

            if platform and platform != "unknown":
                matched_platforms.add(platform)

            for uname in entities.get("usernames", []):
                clean_uname = uname.lower()
                all_usernames[clean_uname] += 1

            for platform_name, values in (entities.get("usernames_by_platform") or {}).items():
                for uname in values:
                    username_platforms[uname.lower()].add(platform_name)

            if any(doc_type in link.lower() for doc_type in [".pdf", ".doc", ".docx"]):
                document_evidence += 1

            if target_norm and (target_norm in title or target_norm in desc):
                if domain:
                    domains_with_target.add(domain)

        confidence = 0
        notes = []

        if len(domains_with_target) >= 2:
            confidence += 20
            notes.append("Target name appears across multiple domains.")

        repeated_username = [u for u, c in all_usernames.items() if c >= 2]
        cross_platform_username = [u for u, p in username_platforms.items() if len(p) >= 2]
        if repeated_username or cross_platform_username:
            confidence += 15
            notes.append("Similar username appears across multiple sources/platforms.")

        if public_emails and target_norm:
            target_found_with_email = any(
                target_norm in ((r.get("title", "") + " " + r.get("description", "")).lower())
                and bool((r.get("osint_entities") or {}).get("emails"))
                for r in results
            )
            if target_found_with_email:
                confidence += 15
                notes.append("Public email appears alongside target mention.")

        has_professional = any(p in matched_platforms for p in ["linkedin", "github"])
        has_social = any(p in matched_platforms for p in ["instagram", "facebook", "twitter", "x", "tiktok"])
        if has_professional and has_social:
            confidence += 10
            notes.append("Professional and social profile traces are both present.")

        if document_evidence > 0:
            confidence += 10
            notes.append("Document-style evidence found in search results.")

        confidence = min(100, confidence)

        return {
            "target": target,
            "confidence": confidence,
            "matched_platforms": sorted(matched_platforms),
            "possible_usernames": sorted(set(cross_platform_username or repeated_username))[:20],
            "public_emails": sorted(public_emails),
            "public_phones": sorted(public_phones),
            "evidence_count": len(results),
            "notes": notes or ["Correlation is limited; treat matches as unverified public evidence."],
        }

    def analyze_profile(self, target_name: str, results: list[dict]) -> dict:
        """Use AI (Groq) to build a profile summary from search results."""
        if not results:
            return {"profile": "No data found"}

        context = ""
        for i, r in enumerate(results[:15]):
            context += (
                f"Result {i + 1}:\n"
                f"Title: {r.get('title')}\n"
                f"URL: {r.get('link')}\n"
                f"Desc: {r.get('description')}\n"
                "---\n"
            )

        prompt = f"""
You are an expert OSINT analyst. Analyze these search results about the target: '{target_name}'.
Extract a concise but comprehensive profile summary.
Focus on: Job/Role, Affiliations/Organizations, Known locations, and Key activities.
Do NOT make up information. If something is unknown, leave it out.

Search Results:
{context}

Respond in JSON format:
{{
  "profile_summary": "Paragraph summarizing who they are based on results",
  "affiliations": ["org1", "org2"],
  "locations": ["loc1"],
  "associated_usernames": ["user1"]
}}
"""
        return self.ai.generate_json(prompt, prefer_groq=True)

    def generate_dork(self, natural_query: str) -> str:
        """Use AI to convert natural query to DuckDuckGo/Google dork string."""
        prompt = f"""
You are an OSINT search expert. Convert this natural query into a highly effective DuckDuckGo / Google search Dork.
Natural Query: "{natural_query}"

Rules for Dork:
1. ALWAYS use exact quotes if the query is a person's name with spaces (e.g. "John Doe").
2. If looking for documents, append filetype:pdf OR filetype:xls etc if relevant.
3. If tracking a person, include typical social footprints (site:linkedin.com | site:twitter.com | site:instagram.com).
4. Keep it concise but highly targeted. Include the exact name inside quotes at the beginning.

Respond ONLY with a JSON object containing the dork string. Example:
{{"dork": "\\"target name\\" (site:linkedin.com | site:twitter.com)"}}
"""
        res = self.ai.generate_json(prompt, prefer_groq=True)
        return res.get("dork", natural_query)
