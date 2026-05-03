# OSINT Algorithm Improvement Plan for Scrapperia

Dokumen ini berisi arahan teknis untuk meningkatkan fitur OSINT di Scrapperia agar Codex/agent coder bisa memahami konteks, batasan, dan target implementasi dengan lebih jelas.

## 1. Context

Scrapperia adalah AI-powered search engine berbasis DuckDuckGo dengan fitur smart keyword expansion, Gemini/Groq AI filtering, quality scoring, trend detection, dan export CSV/JSON.

Saat ini fitur OSINT sudah memiliki fondasi berikut:

- `query_optimizer.py` sudah memiliki intent detection untuk `osint` berdasarkan keyword seperti `email`, `nomor hp`, `kebocoran`, `leak`, `profil`, `dork`, `osint`, `lacak`, `identitas`, dan `breach`.
- Saat intent adalah `osint`, query expansion sudah membuat:
  - exact phrase query
  - loose/unquoted query
  - AI-generated dork melalui `OSINTAnalyzer.generate_dork()`
  - targeted site search ke LinkedIn, Instagram, dan Facebook
- `osint_analyzer.py` sudah memiliki basic regex extraction untuk:
  - emails
  - Indonesian phone numbers
  - links
- `quality_rater.py` masih bersifat general/news-oriented, sehingga belum ideal untuk ranking hasil OSINT.

Tujuan improvement ini adalah mengubah OSINT mode dari sekadar search + dork menjadi mini OSINT analysis engine yang bisa:

- menilai kecocokan identitas target,
- mengekstrak entity publik,
- mengelompokkan bukti lintas sumber,
- memberi confidence label,
- mengurangi noise/spam result,
- tetap menjaga batasan etis dan keamanan.

## 2. Important Ethical Boundary

Fitur OSINT ini hanya boleh menganalisis informasi publik dari hasil pencarian.

Do:

- Analyze public search result title, snippet/description, URL, and public page metadata.
- Extract publicly visible emails, phone numbers, usernames, links, organizations, and profile hints.
- Provide confidence labels instead of claiming certainty.
- Keep outputs framed as "possible match", "likely related", or "publicly visible evidence".

Do not:

- Build features for doxxing, harassment, stalking, credential abuse, password dumps, private leaks, or bypassing access control.
- Add scraping against login-protected/private pages.
- Suggest exploitation, breach checking, or credential validation.
- Make unsupported claims about a person's identity.

Any result related to password leaks, dump sites, private databases, or hacking should be downranked or flagged as unsafe/noisy.

## 3. Current Files to Understand

Before coding, inspect these files:

- `randSearch.py`
  - main scraping flow
  - `SearchScraper.scrape()`
  - `run_scrape()` GUI-compatible runner
  - dedup, ranking, preview, export flow

- `query_optimizer.py`
  - `SmartExpander.detect_intent()`
  - OSINT-specific branch inside `SmartExpander.expand()`
  - `get_optimized_queries()` public API

- `osint_analyzer.py`
  - `OSINTAnalyzer.extract_entities_regex()`
  - `OSINTAnalyzer.analyze_profile()`
  - `OSINTAnalyzer.generate_dork()`

- `quality_rater.py`
  - current general-purpose scoring
  - do not replace this for other modes
  - add OSINT-specific scoring separately

## 4. Target Architecture

Add a dedicated OSINT processing layer instead of forcing OSINT into the existing general quality scoring.

Recommended new files:

```text
osint_scorer.py
osint_reporter.py       # optional, only if needed
```

Recommended updated files:

```text
osint_analyzer.py
query_optimizer.py
randSearch.py
```

The intended flow for OSINT mode:

```text
user query
  -> Gemini/parser detects mode = osint
  -> query_optimizer generates controlled OSINT queries
  -> SearchScraper collects DDG results
  -> OSINTAnalyzer enriches each result with extracted entities
  -> OSINTScorer scores each result using OSINT-specific criteria
  -> deduplication runs
  -> cross-source correlation groups likely related evidence
  -> output includes confidence label + evidence summary
  -> CSV/JSON export includes OSINT fields
```

## 5. Query Expansion Improvement

Current OSINT query expansion is too simple. Improve it with controlled query groups.

### 5.1 Add OSINT query groups

In `query_optimizer.py`, add constants like:

```python
OSINT_SITE_GROUPS = {
    "professional": ["linkedin.com", "github.com", "medium.com", "dev.to"],
    "social": ["instagram.com", "facebook.com", "x.com", "twitter.com", "tiktok.com"],
    "documents": ["filetype:pdf", "filetype:doc", "filetype:docx"],
    "contact": ["email", "contact", "kontak", "profile", "profil"],
}
```

### 5.2 Generate focused queries

For a target like `John Doe`, generate queries similar to:

```text
"John Doe"
John Doe
"John Doe" site:linkedin.com
"John Doe" site:github.com
"John Doe" site:instagram.com
"John Doe" site:facebook.com
"John Doe" filetype:pdf
"John Doe" email OR contact
```

For Indonesian targets, include:

```text
"Nama Target" kontak
"Nama Target" profil
"Nama Target" organisasi
```

### 5.3 Limit query count

Keep OSINT expansion controlled.

Requirement:

```text
Max OSINT queries per keyword: 8-12
```

Avoid generating too many broad queries because OSINT search quality drops quickly when the query set becomes noisy.

## 6. Entity Extraction Improvement

Improve `OSINTAnalyzer.extract_entities_regex()`.

Current extraction:

- emails
- Indonesian phone numbers
- links

Add extraction for:

- usernames
- platform profile URLs
- domains
- possible organization names from title/snippet, if simple enough

### 6.1 Suggested username patterns

```python
USERNAME_PATTERNS = {
    "linkedin": r"linkedin\.com/in/([A-Za-z0-9\-_%]+)",
    "github": r"github\.com/([A-Za-z0-9\-]+)",
    "instagram": r"instagram\.com/([A-Za-z0-9._]+)",
    "facebook": r"facebook\.com/([A-Za-z0-9.]+)",
    "twitter": r"(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)",
    "tiktok": r"tiktok\.com/@([A-Za-z0-9._]+)",
}
```

### 6.2 Suggested domain extraction

Use `urllib.parse.urlparse()` instead of regex-only URL parsing.

```python
from urllib.parse import urlparse

def extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""
```

### 6.3 Enrich each result

Add a method:

```python
def enrich_result_entities(self, result: dict) -> dict:
    text = " ".join([
        result.get("title", ""),
        result.get("description", ""),
        result.get("link", ""),
    ])
    result["osint_entities"] = self.extract_entities_regex(text)
    result["osint_platform"] = self.detect_platform(result.get("link", ""))
    return result
```

## 7. OSINT-Specific Scoring

Create a new file:

```text
osint_scorer.py
```

Add class:

```python
class OSINTScorer:
    def score_result(self, result: dict, target: str) -> dict:
        ...

    def rank_results(self, results: list[dict], target: str) -> list[dict]:
        ...
```

### 7.1 Scoring dimensions

Use a 100-point score.

Suggested breakdown:

```text
identity_match_score       max 35
source_reliability_score   max 20
entity_density_score       max 20
evidence_quality_score     max 15
technical_score            max 10
noise_penalty              subtract up to 30
```

### 7.2 Identity match score

Give higher score if the target appears exactly.

Rules:

```text
+20 exact target appears in title
+10 exact target appears in description
+5 target words appear close together
+5 if URL username/domain resembles target
```

Use lowercase normalized comparison.

### 7.3 Source reliability score

Preferred OSINT source categories:

```python
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
```

Do not treat news authority domains as the main OSINT authority signal.

### 7.4 Entity density score

Increase score when useful public entities are found.

```text
+8 public email found
+8 public phone found
+5 username found
+5 profile/platform URL found
+3 additional useful link found
```

Cap at 20.

### 7.5 Evidence quality score

Score based on whether the snippet actually contains meaningful context.

```text
+5 description length >= 50
+5 title is not empty and not generic
+5 platform/source is detectable
```

### 7.6 Noise penalty

Add negative scoring for noisy or unsafe sources.

```python
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
```

Penalty examples:

```text
-15 if result contains password dump / leaked password terms
-10 if result is a people-search spam page
-10 if URL uses suspicious TLD or shortener
-5 if title/description is too generic
```

## 8. Confidence Label

Each OSINT result should include a confidence label.

Suggested thresholds:

```text
High confidence       score >= 80
Medium confidence     score >= 60
Low confidence        score >= 40
Unverified            score < 40
```

Add fields to result:

```python
result["osint_score"] = 87
result["osint_confidence"] = "High confidence"
result["osint_score_breakdown"] = {...}
```

Important: avoid language like "confirmed identity". Use cautious wording.

## 9. Cross-Source Correlation

Add a simple correlation function in `osint_analyzer.py` or `osint_scorer.py`.

Goal:

- detect repeated usernames,
- repeated emails,
- repeated domains,
- repeated name mentions,
- related platforms.

Suggested function:

```python
def correlate_identity(results: list[dict], target: str) -> dict:
    return {
        "target": target,
        "confidence": 0,
        "matched_platforms": [],
        "possible_usernames": [],
        "public_emails": [],
        "public_phones": [],
        "evidence_count": 0,
        "notes": [],
    }
```

Suggested scoring:

```text
+20 exact target appears across 2+ different domains
+15 same username appears across 2+ platforms
+15 email appears and target name also appears nearby
+10 LinkedIn/GitHub + another social profile found
+10 document evidence found
```

Cap final correlation confidence at 100.

## 10. Integration in randSearch.py

In `SearchScraper.scrape()` or after collection, add special handling for OSINT mode.

Current flow already checks:

```python
max_vars = len(variants) if search_mode == "osint" else 2
```

Keep that behavior, but after collecting results:

```python
if search_mode == "osint":
    analyzer = OSINTAnalyzer()
    scorer = OSINTScorer()

    self.results = [analyzer.enrich_result_entities(r) for r in self.results]
    self.results = scorer.rank_results(self.results, keywords[0] if keywords else "")
    self.osint_correlation = analyzer.correlate_identity(self.results, keywords[0] if keywords else "")
else:
    self.results = rate_and_rank_results(...)
```

Make sure existing `text`, `news`, and `stock` modes are not broken.

## 11. Export Changes

Update CSV export to include optional OSINT fields when present:

```text
OSINT_Score
OSINT_Confidence
OSINT_Platform
OSINT_Emails
OSINT_Phones
OSINT_Usernames
OSINT_Links
```

Update JSON export to preserve:

```json
{
  "osint_score": 87,
  "osint_confidence": "High confidence",
  "osint_platform": "linkedin",
  "osint_entities": {
    "emails": [],
    "phones": [],
    "links": [],
    "usernames": []
  },
  "osint_score_breakdown": {}
}
```

Do not remove existing fields.

## 12. Preview Output

For OSINT mode, preview should show:

```text
1. [High confidence | 87] John Doe - Software Engineer
   Platform: LinkedIn
   Evidence: exact name match, professional profile, username found
   Public entities: username=johndoe
   URL: https://linkedin.com/in/johndoe
```

Do not expose overly sensitive formatting. Keep it factual and evidence-based.

## 13. Tests / Manual Checks

If there is no formal test suite yet, at least do manual checks with these cases:

### Case 1: Normal person/profile query

```text
osint John Doe
```

Expected:

- LinkedIn/GitHub/social profiles rank higher than random pages.
- Exact name match gets higher score.
- Confidence label appears.

### Case 2: Username query

```text
osint johndoe github
```

Expected:

- GitHub profile/source gets higher score.
- Username extractor works.

### Case 3: Indonesian name query

```text
osint Nama Orang Indonesia
```

Expected:

- Indonesian terms like `profil`, `kontak`, and `organisasi` are included.
- Results are not overly dominated by news scoring.

### Case 4: Unsafe/noisy leak query

```text
osint john doe password dump
```

Expected:

- Password/leak/dump results are downranked or flagged.
- Tool should not encourage credential abuse.

### Case 5: Non-OSINT regression

```text
berita gempa hari ini
prediksi saham GOTO hari ini
loker Mayora terbaru
```

Expected:

- Existing news, stock, and job/general flows still work.

## 14. Acceptance Criteria

Implementation is considered successful when:

- `osint_scorer.py` exists and is used only for OSINT mode.
- `osint_analyzer.py` extracts emails, phones, links, usernames, domains/platforms.
- OSINT results include `osint_score`, `osint_confidence`, and `osint_entities`.
- Query expansion for OSINT is controlled and grouped by source type.
- Cross-source correlation summary exists, even if simple.
- CSV and JSON export do not break.
- Existing modes (`text`, `news`, `stock`) still work.
- Unsafe leak/password/doxxing-oriented results are downranked or flagged.
- The output uses cautious wording and avoids claiming certainty.

## 15. Suggested Implementation Order

1. Create `osint_scorer.py`.
2. Extend `OSINTAnalyzer.extract_entities_regex()`.
3. Add `detect_platform()` and `enrich_result_entities()` to `OSINTAnalyzer`.
4. Improve OSINT query expansion in `query_optimizer.py`.
5. Integrate OSINT scoring in `randSearch.py`.
6. Add cross-source correlation.
7. Update preview/export fields.
8. Run manual regression checks.

## 16. Notes for Codex

Be careful not to over-engineer this in one pass. Prioritize a clean, working implementation over complex AI reasoning.

Avoid changing public APIs unless necessary:

- Keep `get_optimized_queries()` backward compatible.
- Keep `SearchScraper.scrape()` arguments compatible.
- Keep CSV/JSON exports compatible with old data.

When uncertain, prefer deterministic scoring and clear evidence over AI-generated assumptions.
