"""
Query Optimizer v3.1 — API-Driven Smart Expansion

Keyword expansion menggunakan Google + DuckDuckGo APIs:
  - DuckDuckGo Instant Answer API → definisi, akronim, entitas
  - Google Autocomplete API → suggestions
  - Tanpa hardcode database, semua dinamis
"""

import re
import requests


OSINT_SITE_GROUPS = {
    "professional": ["linkedin.com", "github.com", "medium.com", "dev.to"],
    "social": ["instagram.com", "facebook.com", "x.com", "twitter.com", "tiktok.com"],
    "documents": ["filetype:pdf", "filetype:doc", "filetype:docx"],
    "contact": ["email", "contact", "kontak", "profile", "profil"],
}


# ---------------------------------------------------------------------------
# SmartExpander (API-driven)
# ---------------------------------------------------------------------------

class SmartExpander:
    """Expand keyword secara cerdas via Google + DDG APIs."""

    INSTANT_URL = "https://api.duckduckgo.com/"
    SUGGEST_URL = "https://suggestqueries.google.com/complete/search"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        })
        self._cache: dict[str, dict] = {}

    @staticmethod
    def _is_indonesian_target(keyword: str) -> bool:
        kw = keyword.lower()
        id_hints = ["nama", "orang", "kontak", "profil", "organisasi", "indonesia", "jakarta", "bandung"]
        return any(h in kw for h in id_hints)

    def _build_osint_queries(self, keyword: str, location: str = "") -> list[str]:
        """Build controlled OSINT query set prioritising the exact full name and location."""
        clean = keyword.replace('"', "").strip()
        exact = f'"{clean}"' if " " in clean else clean
        
        loc_str = f' "{location.strip()}"' if location.strip() else ""
        loc_unquoted = f' {location.strip()}' if location.strip() else ""

        queries: list[str] = []

        # 1. Exact phrase + location — must always come first
        queries.append(f"{exact}{loc_str}")
        if exact != clean:
            queries.append(f"{clean}{loc_unquoted}")

        # 2. Major social / professional site searches
        priority_sites = [
            "instagram.com", "linkedin.com", "github.com", "facebook.com",
        ]
        for site in priority_sites:
            queries.append(f'{exact}{loc_unquoted} site:{site}')

        # 3. Contact / profile angle
        queries.append(f'{exact}{loc_unquoted} profil')
        queries.append(f'{exact}{loc_unquoted} kontak')

        # 4. Backfill with more platforms and document queries
        backfill = [
            f'{exact}{loc_unquoted} site:twitter.com OR site:x.com',
            f'{exact}{loc_unquoted} site:tiktok.com',
            f'{exact}{loc_unquoted} site:medium.com',
            f'{exact}{loc_unquoted} {OSINT_SITE_GROUPS["documents"][0]}',
            f'{exact}{loc_unquoted} email OR contact',
        ]

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for q in queries:
            qn = q.lower().strip()
            if qn and qn not in seen:
                seen.add(qn)
                unique.append(q)

        # Top up from backfill to reach at least 8
        for bf in backfill:
            bn = bf.lower().strip()
            if bn not in seen:
                seen.add(bn)
                unique.append(bf)
            if len(unique) >= 12:
                break

        return unique[:12]

    # ------------------------------------------------------------------
    # DDG Instant Answer API
    # ------------------------------------------------------------------

    def _instant_answer(self, query: str) -> dict:
        """Fetch definisi, abstract, related topics dari DDG Instant Answer."""
        if query in self._cache:
            return self._cache[query]

        try:
            resp = self.session.get(self.INSTANT_URL, params={
                "q": query, "format": "json", "no_html": "1",
                "skip_disambig": "0",
            }, timeout=5)
            data = resp.json() if resp.status_code == 200 else {}
        except Exception:
            data = {}

        self._cache[query] = data
        return data

    def get_definition(self, keyword: str) -> str | None:
        """Ambil definisi/abstract dari DDG."""
        data = self._instant_answer(keyword)
        abstract = data.get("AbstractText", "")
        if abstract:
            return abstract[:200]
        # Cek definisi
        definition = data.get("Definition", "")
        if definition:
            return definition[:200]
        return None

    def get_entity_info(self, keyword: str) -> dict:
        """Deteksi entitas: nama lengkap, tipe, related topics."""
        data = self._instant_answer(keyword)
        info = {
            "heading": data.get("Heading", ""),
            "type": data.get("AbstractSource", ""),
            "abstract": data.get("AbstractText", "")[:150] if data.get("AbstractText") else "",
            "related": [],
        }

        # Extract related topics
        for topic in data.get("RelatedTopics", [])[:5]:
            if isinstance(topic, dict) and topic.get("Text"):
                info["related"].append(topic["Text"][:80])
            # Handle sub-topics (grouped)
            if isinstance(topic, dict) and "Topics" in topic:
                for sub in topic["Topics"][:3]:
                    if sub.get("Text"):
                        info["related"].append(sub["Text"][:80])

        return info

    # ------------------------------------------------------------------
    # DDG Suggestions API
    # ------------------------------------------------------------------

    def get_suggestions(self, keyword: str, language: str = "id") -> list[str]:
        """Fetch autocomplete suggestions from Google."""
        try:
            resp = self.session.get(self.SUGGEST_URL,
                                    params={"client": "chrome", "q": keyword, "hl": language},
                                    timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                # Google returns [query, [suggestions], ...]  
                if isinstance(data, list) and len(data) > 1:
                    return [s for s in data[1]
                            if s.lower() != keyword.lower()][:5]
        except Exception:
            pass
        return []

    # ------------------------------------------------------------------
    # Intent detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_intent(keyword: str) -> str:
        """Deteksi intent dari keyword."""
        kw = keyword.lower()
        if any(w in kw for w in ["lowongan", "loker", "kerja", "karir", "magang",
                                  "job", "hiring", "vacancy", "intern", "mdp", "mt",
                                  "odp", "trainee", "recruitment"]):
            return "job"
        if any(w in kw for w in ["berita", "news", "terbaru", "update", "breaking"]):
            return "news"
        if any(w in kw for w in ["saham", "stock", "investasi", "harga", "price", "ihsg", "emiten", "prediksi"]):
            return "stock"
        if any(w in kw for w in ["email", "nomor hp", "kebocoran", "leak", "profil", "dork", "osint", "lacak", "identitas", "breach"]):
            return "osint"
        return "general"

    # ------------------------------------------------------------------
    # Master expand
    # ------------------------------------------------------------------

    def expand(self, keyword: str, language: str = "id", force_intent: str = None, location: str = "") -> list[str]:
        """Orchestrate semua teknik expansion."""
        queries = []
        print(f"  🧠 Analyzing: '{keyword}'")

        # 1. DDG Instant Answer (entitas, definisi)
        entity = self.get_entity_info(keyword)
        if entity["heading"] and entity["heading"].lower() != keyword.lower():
            queries.append(entity["heading"])
            print(f"     📌 Entity: {entity['heading']}")
        if entity["abstract"]:
            print(f"     📝 {entity['abstract'][:80]}…")

        # 2. Intent detection
        intent = force_intent if force_intent else self.detect_intent(keyword)
        print(f"     🎯 Intent: {intent}")

        # --- SPECIAL HANDLING FOR OSINT ---
        if intent == "osint":
            osint_queries = self._build_osint_queries(keyword, location)
            print(f"     🕵️ OSINT query groups active ({len(osint_queries)} variants)")
            return osint_queries

        # --- NORMAL EXPANION ---
        # 3. Per-word lookup (untuk akronim & entitas individual)
        words = keyword.split()
        if len(words) >= 2:
            for word in words:
                if len(word) <= 5 and word.upper() == word:
                    # Kemungkinan akronim → lookup definisi
                    defn = self.get_definition(word)
                    if defn:
                        print(f"     🔤 {word} → {defn[:60]}…")
                        # Ganti akronim dengan full form
                        expanded = keyword.replace(word, defn.split(".")[0].split(",")[0][:40])
                        if expanded != keyword:
                            queries.append(expanded)

        # 3. DDG Suggestions (autocomplete)
        suggestions = self.get_suggestions(keyword, language)
        if suggestions:
            print(f"     💡 Suggestions: {suggestions[:3]}")
            queries.extend(suggestions[:3])

        # 6. Intent-based variants
        site_map = {
            "job": "linkedin.com",
            "news": "detik.com",
            "stock": "cnbcindonesia.com",
        }
        if intent in site_map:
            queries.append(f"{keyword} site:{site_map[intent]}")

        # 7. Operator variants
        if " " in keyword:
            queries.append(f'"{keyword}"')  # exact match

        if intent == "stock":
            queries.append(f"{keyword} analisis teknikal")
            queries.append(f"{keyword} fundamental")
        else:
            time_words = {"id": "terbaru", "en": "latest"}
            tw = time_words.get(language, "")
            if tw:
                queries.append(f"{keyword} {tw}")

        # 6. Related topics sebagai query tambahan
        for related in entity.get("related", [])[:2]:
            # Ambil kata2 penting dari related text
            clean = re.sub(r'[^\w\s]', '', related)
            words_r = clean.split()[:4]
            if len(words_r) >= 2:
                queries.append(" ".join(words_r))

        # Deduplicate
        seen = set()
        unique = []
        for q in queries:
            ql = q.lower().strip()
            if ql not in seen and ql != keyword.lower():
                seen.add(ql)
                unique.append(q)

        print(f"     📊 {len(unique)} expanded queries")
        return unique


# ---------------------------------------------------------------------------
# Public API (backward compatible)
# ---------------------------------------------------------------------------

_expander = SmartExpander()


def get_optimized_queries(keyword, language='en', intent='news', time_range='w', location=''):
    """Get expanded & optimized queries for a keyword."""
    return _expander.expand(keyword, language, force_intent=intent, location=location)


def analyze_search_effectiveness(keywords_list, language='en'):
    """Analyze effectiveness across multiple keywords."""
    scores = []
    best_q, worst_q = "", ""
    best_s, worst_s = 0, 100

    for kw in keywords_list:
        score = 50
        words = kw.split()
        if len(words) >= 2:
            score += 15
        if '"' in kw:
            score += 10
        if 'site:' in kw:
            score += 10
        if len(kw) > 20:
            score += 5
        score = min(100, score)
        scores.append(score)

        if score > best_s:
            best_s, best_q = score, kw
        if score < worst_s:
            worst_s, worst_q = score, kw

    return {
        'average_score': sum(scores) / len(scores) if scores else 0,
        'best_query': best_q or (keywords_list[0] if keywords_list else ""),
        'worst_query': worst_q or (keywords_list[-1] if keywords_list else ""),
        'total_queries': len(keywords_list),
    }
