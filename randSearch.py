"""
SearchScraper v8.0 — AI-Powered Smart Search Engine

Fitur:
  - Google Search backend for better result quality
  - Smart keyword expansion via Google APIs
  - Gemini AI language filter + relevance scoring
  - Trend detection (timeline, peak, subtopics)
  - Real date extraction dari meta tags
  - Quality scoring + dedup
  - Export CSV + JSON
"""

import csv
import json
import time
import random
import re
import sys
import requests
from datetime import datetime
from dateutil.parser import parse as date_parse

from tqdm import tqdm
from google_scraper import google_search, GoogleScraper
from colorama import init, Fore, Style
init(autoreset=True)

# Modul pendukung
from query_optimizer import get_optimized_queries, analyze_search_effectiveness
from quality_rater import rate_and_rank_results, remove_duplicate_results
from trend_detector import TrendDetector
from gemini_filter import GeminiFilter
from osint_analyzer import OSINTAnalyzer
from osint_scorer import OSINTScorer


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GOOGLE_TBS_MAP = {
    "d": "qdr:d", "w": "qdr:w", "m": "qdr:m", "y": "qdr:y",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_keyword_list(raw_input: str, parsed_keywords: list[str], mode: str) -> list[str]:
    """Ensure OSINT mode preserves the full raw query as primary keyword.

    For OSINT, the original full name / input is always first so that
    exact-match queries run before partial-match ones.  Other modes are
    left unchanged.
    """
    keywords = [k.strip() for k in parsed_keywords if k and k.strip()]

    if mode == "osint":
        raw_clean = raw_input.strip().strip('"')
        if raw_clean and len(raw_clean.split()) >= 2:
            keywords = [raw_clean] + keywords

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for kw in keywords:
        key = kw.lower()
        if key not in seen:
            seen.add(key)
            unique.append(kw)

    return unique


def extract_date_from_url(url: str) -> datetime | None:
    """Coba ekstrak tanggal dari URL pattern."""
    patterns = [
        r'/(\d{4})/(\d{1,2})/(\d{1,2})/',
        r'/(\d{4})-(\d{1,2})-(\d{1,2})/',
        r'(\d{4})(\d{2})(\d{2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            try:
                y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if 2000 <= y <= 2030 and 1 <= m <= 12 and 1 <= d <= 31:
                    return datetime(y, m, d)
            except (ValueError, IndexError):
                pass
    return None


def enrich_result(result: dict) -> dict:
    """Fetch real title + date dari halaman artikel."""
    url = result.get("link", "")
    if not url or not url.startswith("http"):
        return result

    # 1. Tanggal dari URL pattern (cepat)
    date = extract_date_from_url(url)

    # 2. Fetch halaman untuk meta tags
    try:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            html = resp.text[:15000]

            # Title dari <title>
            if not result.get("title") or result["title"] == url:
                title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
                if title_match:
                    title = title_match.group(1).strip()
                    for sep in [" - ", " | ", " — ", " · "]:
                        if sep in title:
                            parts = title.split(sep)
                            if len(parts[-1]) < 30:
                                title = sep.join(parts[:-1])
                            break
                    result["title"] = title

            # Description dari meta
            if not result.get("description"):
                desc_match = re.search(
                    r'<meta[^>]*name="description"[^>]*content="([^"]*)"',
                    html, re.IGNORECASE
                )
                if not desc_match:
                    desc_match = re.search(
                        r'<meta[^>]*content="([^"]*)"[^>]*name="description"',
                        html, re.IGNORECASE
                    )
                if desc_match:
                    result["description"] = desc_match.group(1).strip()

            # Date dari meta tags
            if not date:
                meta_date_patterns = [
                    r'property="article:published_time"\s+content="([^"]+)"',
                    r'content="([^"]+)"\s+property="article:published_time"',
                    r'"datePublished"\s*:\s*"([^"]+)"',
                    r'itemprop="datePublished"\s+content="([^"]+)"',
                    r'content="([^"]+)"\s+itemprop="datePublished"',
                    r'name="pubdate"\s+content="([^"]+)"',
                    r'name="publishdate"\s+content="([^"]+)"',
                ]
                for pattern in meta_date_patterns:
                    match = re.search(pattern, html, re.IGNORECASE)
                    if match:
                        try:
                            date = date_parse(match.group(1), fuzzy=True)
                            break
                        except (ValueError, TypeError):
                            pass
    except Exception:
        pass

    result["date"] = date.replace(tzinfo=None) if date else None
    return result


# ---------------------------------------------------------------------------
# SearchScraper
# ---------------------------------------------------------------------------

class SearchScraper:
    """Google Search scraper with AI-powered analysis."""

    MAX_PER_QUERY = 50
    DELAY_RANGE = (3.0, 6.0)
    MAX_RETRIES = 3

    def __init__(self):
        self.results: list[dict] = []
        self.filtered_count = 0

        self.search_mode = "text"
        self.osint_correlation: dict = {}



    def _init_scraper(self):
        """Initialize or reuse Google scraper instance."""
        if not hasattr(self, '_scraper') or self._scraper is None:
            self._scraper = GoogleScraper()
        return self._scraper

    def _google_search(self, keyword: str, lang: str,
                       max_results: int, mode: str = "text",
                       time_range: str = "") -> list[dict]:
        """Google search via Chrome headless."""
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                scraper = self._init_scraper()
                results = scraper.search(
                    query=keyword,
                    lang=lang,
                    num_results=max_results,
                    time_range=time_range,
                    mode=mode,
                )
                return [
                    {
                        "title": r.title,
                        "description": r.description,
                        "link": r.url,
                        "date": r.date,
                        "source": r.source,
                    }
                    for r in results
                ]
            except Exception as e:
                err_msg = str(e)
                # Reset scraper on failure
                try:
                    self._scraper.close()
                except Exception:
                    pass
                self._scraper = None
                if attempt < self.MAX_RETRIES:
                    wait = 3 * attempt + random.uniform(1, 3)
                    print(f"   ⚠️  Retry {attempt}/{self.MAX_RETRIES}: {err_msg[:60]}…")
                    time.sleep(wait)
                else:
                    print(f"   ❌ Gagal setelah {self.MAX_RETRIES} percobaan: {err_msg[:80]}")
        return []

    # ------------------------------------------------------------------
    # Main scraping loop
    # ------------------------------------------------------------------

    def scrape(
        self,
        keywords: list[str],
        language: str = "en",
        time_range: str = "",
        num_results: int = 50,
        use_language_filter: bool = True,
        search_mode: str = "text",
        enrich_dates: bool = True,
    ):
        self.search_mode = search_mode

        mode_label = {
            "text": "🌐 Text",
            "news": "📰 News",
            "stock": "📈 Stock",
            "osint": "🕵️ OSINT",
        }.get(search_mode, "🌐 Text")
        print(f"\n🔍 Mode: {mode_label}")
        print(f"🌏 Language: {language} | ⏰ Waktu: {time_range or 'semua'}")
        print(f"📅 Enrich tanggal asli: {'YA' if enrich_dates else 'TIDAK'}")

        # --- Smart keyword expansion ---
        print("\n=== 🧠 SMART KEYWORD EXPANSION ===")
        optimized: list[str] = []
        for kw in keywords:
            variants = get_optimized_queries(kw, language, intent=search_mode)
            # Max 2 variasi per keyword untuk search biasa, ambil semua untuk osint
            max_vars = len(variants) if search_mode == "osint" else 2
            combined = [kw] + variants[:max_vars]
            optimized.extend(combined)

        seen = set()
        unique = [q for q in optimized if q.lower() not in seen and not seen.add(q.lower())]
        optimized = unique
        # OSINT queries are ordered by precision — exact full-name first
        if search_mode != "osint":
            random.shuffle(optimized)
        print(f"\n  📊 Total query unik: {len(optimized)}")

        eff = analyze_search_effectiveness(optimized[:5], language)
        print(f"  ⚡ Efektivitas: avg={eff['average_score']:.0f} | "
              f"best='{eff['best_query']}' | worst='{eff['worst_query']}'")

        # --- Collecting ---
        rpq = min(self.MAX_PER_QUERY, max(10, num_results // len(optimized) + 5))
        progress = tqdm(total=num_results, desc="🔍 Collecting", unit="hasil")

        for keyword in optimized:
            if len(self.results) >= num_results:
                break

            time.sleep(random.uniform(*self.DELAY_RANGE))
            print(f"\n  🔎 '{keyword}' (max {rpq})")

            # Google search
            raw = self._google_search(keyword, language, rpq, mode=search_mode, time_range=time_range)

            # Jika news gagal, fallback ke text
            if not raw and search_mode == "news":
                print("     ↳ News kosong, fallback ke text…")
                raw = self._google_search(keyword, language, rpq, mode="text", time_range=time_range)

            print(f"     ↳ {len(raw)} hasil")

            for r in raw:
                if len(self.results) >= num_results:
                    break
                r["keyword"] = keyword
                r["language"] = language
                self.results.append(r)
                progress.update(1)

        progress.close()

        # --- Enrich dates ---
        if enrich_dates and self.results:
            needs_date = sum(1 for r in self.results if r.get("date") is None)
            if needs_date > 0:
                print(f"\n📡 Extracting real dates dari {needs_date} artikel…")
                enriched = 0
                for i, r in enumerate(tqdm(self.results, desc="📡 Enriching", unit="pg")):
                    if r.get("date") is None:
                        self.results[i] = enrich_result(r)
                        if self.results[i].get("date"):
                            enriched += 1
                        time.sleep(0.3)
                print(f"   ✅ {enriched} tanggal asli diekstrak")

        # --- Gemini AI filter ---
        before_filter = len(self.results)
        if search_mode == "osint" and use_language_filter:
            print("\n🕵️ OSINT mode: skip language filter to preserve public evidence.")
            use_language_filter = False
        if use_language_filter:
            print(f"\n🤖 Gemini AI Filter (bahasa={language})…")
            try:
                gf = GeminiFilter()
                keyword_hint = keywords[0] if keywords else ""
                self.results = gf.filter_results(
                    self.results, language, keyword_hint
                )
                self.filtered_count = before_filter - len(self.results)
            except Exception as e:
                print(f"   ⚠️  Gemini error, skip filter: {e}")

        print(f"\n📊 Total: {len(self.results)} | Difilter: {self.filtered_count}")

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    def deduplicate(self, threshold: float = 0.85):
        n = len(self.results)
        self.results, dup = remove_duplicate_results(self.results, threshold)
        print(f"🗑️  Duplikat: {dup} dihapus | Tersisa: {len(self.results)}")

    def score_and_rank(self, keyword_hint: str = "", language: str = "en",
                       mode: str | None = None, raw_query: str = ""):
        if not self.results:
            return
        kw = keyword_hint or (self.results[0].get("keyword", "") if self.results else "")
        active_mode = mode or self.search_mode

        if active_mode == "osint":
            # Use the full raw query as OSINT target hint for best matching
            osint_target = raw_query.strip() if raw_query.strip() else kw
            analyzer = OSINTAnalyzer()
            scorer = OSINTScorer()
            self.results = [analyzer.enrich_result_entities(r) for r in self.results]
            self.results = scorer.rank_results(self.results, osint_target)
            self.osint_correlation = analyzer.correlate_identity(self.results, osint_target)
            print(f"🕵️ {len(self.results)} hasil OSINT diurutkan (target: '{osint_target}').")
            return

        self.results = rate_and_rank_results(self.results, kw, language)
        print(f"⭐ {len(self.results)} hasil diurutkan.")

    def detect_trends(self):
        """Run trend analysis on results."""
        detector = TrendDetector(self.results)
        detector.analyze()
        print(detector.summary())
        return detector

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_csv(self, filepath: str = "search_results.csv"):
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "No", "Quality_Score", "Quality_Grade", "Keyword",
                "Title", "Description", "Link", "Date", "Source", "Language",
                "OSINT_Score", "OSINT_Confidence", "OSINT_Platform",
                "OSINT_Emails", "OSINT_Phones", "OSINT_Usernames", "OSINT_Links",
            ])
            for i, r in enumerate(self.results, 1):
                d = r.get("date")
                fmt = d.strftime("%Y-%m-%d") if isinstance(d, datetime) else "N/A"
                entities = r.get("osint_entities", {}) or {}
                w.writerow([
                    i,
                    f"{r.get('quality_score', 0):.2f}",
                    r.get("quality_grade", "-"),
                    r.get("keyword", ""),
                    r.get("title", ""),
                    r.get("description", ""),
                    r.get("link", ""),
                    fmt,
                    r.get("source", ""),
                    r.get("language", ""),
                    r.get("osint_score", ""),
                    r.get("osint_confidence", ""),
                    r.get("osint_platform", ""),
                    "; ".join(entities.get("emails", [])),
                    "; ".join(entities.get("phones", [])),
                    "; ".join(entities.get("usernames", [])),
                    "; ".join(entities.get("links", [])),
                ])
        print(f"✅ CSV: '{filepath}' ({len(self.results)} baris)")

    def export_json(self, filepath: str = "search_results.json"):
        out = []
        for r in self.results:
            e = dict(r)
            if isinstance(e.get("date"), datetime):
                e["date"] = e["date"].isoformat()
            e.pop("quality_breakdown", None)
            out.append(e)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON: '{filepath}' ({len(out)} entri)")

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def preview(self, n: int = 5):
        count = min(n, len(self.results))
        print(f"\n{Fore.CYAN}{'═'*60}")
        print(f"  TOP {count} HASIL")
        print(f"{'═'*60}{Style.RESET_ALL}")
        for i, r in enumerate(self.results[:n], 1):
            d = r.get("date")
            fmt = d.strftime("%Y-%m-%d") if isinstance(d, datetime) else "N/A"
            score = r.get("quality_score", 0)
            grade = r.get("quality_grade", "-")
            src = r.get("source", "")
            src_str = f" │ 📰 {src}" if src else ""

            if "osint_score" in r:
                osint_score = r.get("osint_score", 0)
                osint_conf = r.get("osint_confidence", "Unverified")
                print(f"\n{Fore.WHITE}{Style.BRIGHT}{i}. [{osint_conf} | {osint_score:.0f}] {r.get('title', '')[:80]}{Style.RESET_ALL}")
            else:
                print(f"\n{Fore.WHITE}{Style.BRIGHT}{i}. [{grade} │ {score:.0f}] {r.get('title', '')[:80]}{Style.RESET_ALL}")
            print(f"   {Fore.BLUE}📅 {fmt}{src_str}{Style.RESET_ALL}")
            print(f"   {Fore.CYAN}🔗 {(r.get('link') or 'No Link')[:90]}{Style.RESET_ALL}")
            desc = r.get("ai_summary") or r.get("description", "")[:120]
            if desc:
                print(f"   {Fore.WHITE}📝 {desc}…{Style.RESET_ALL}")
            if "osint_score" in r:
                entities = r.get("osint_entities", {}) or {}
                platform = r.get("osint_platform", "unknown")
                summary = r.get("osint_evidence_summary", "limited public evidence")
                usernames = ", ".join(entities.get("usernames", [])[:2]) or "-"
                print(f"   {Fore.YELLOW}🕵️ Platform: {platform}{Style.RESET_ALL}")
                print(f"   {Fore.YELLOW}Evidence: {summary}{Style.RESET_ALL}")
                print(f"   {Fore.YELLOW}Public entities: username={usernames}{Style.RESET_ALL}")

        if self.osint_correlation:
            corr = self.osint_correlation
            print(f"\n{Fore.MAGENTA}OSINT Correlation Confidence: {corr.get('confidence', 0)}{Style.RESET_ALL}")
            if corr.get("matched_platforms"):
                print(f"   Platforms: {', '.join(corr['matched_platforms'])}")
            if corr.get("notes"):
                print(f"   Notes: {corr['notes'][0]}")


# ---------------------------------------------------------------------------
# GUI-compatible runner (callback-based)
# ---------------------------------------------------------------------------

def run_scrape(
    keywords: list[str],
    language: str = "id",
    time_range: str = "w",
    num_results: int = 20,
    search_mode: str = "text",
    enrich_dates: bool = True,
    on_log=None,
    on_progress=None,
    on_complete=None,
):
    """
    Run scraping with callbacks for GUI integration.

    on_log(msg: str)         — log message
    on_progress(pct: float)  — progress 0.0-1.0
    on_complete(data: dict)  — final results
    """
    def log(msg):
        if on_log:
            on_log(msg)

    def progress(pct):
        if on_progress:
            on_progress(pct)

    try:
        log("🔍 Starting search…")
        progress(0.05)

        # Smart expansion
        log("🧠 Smart keyword expansion…")
        optimized = []
        for kw in keywords:
            variants = get_optimized_queries(kw, language, intent=search_mode)
            max_vars = len(variants) if search_mode == "osint" else 2
            combined = [kw] + variants[:max_vars]
            optimized.extend(combined)

        seen = set()
        unique = [q for q in optimized if q.lower() not in seen and not seen.add(q.lower())]
        optimized = unique
        # OSINT queries are ordered by precision — keep order
        if search_mode != "osint":
            import random as _rng
            _rng.shuffle(optimized)
        log(f"   📊 {len(optimized)} queries")
        progress(0.1)

        # Scrape
        scraper = SearchScraper()
        scraper.scrape(
            keywords=keywords,
            language=language,
            time_range=time_range,
            num_results=num_results,
            use_language_filter=True,
            search_mode="news" if search_mode == "stock" else search_mode,
            enrich_dates=enrich_dates,
        )
        progress(0.6)

        if not scraper.results:
            log("⚠️ Tidak ada hasil.")
            if on_complete:
                on_complete({"results": [], "ai_summary": ""})
            return

        log(f"📦 {len(scraper.results)} hasil mentah")

        # Dedup & score
        scraper.deduplicate()
        raw_query = keywords[0] if keywords else ""
        scraper.score_and_rank(language=language, mode=search_mode, raw_query=raw_query)
        log(f"⭐ {len(scraper.results)} hasil setelah dedup + scoring")
        progress(0.7)

        # Gemini filter
        if search_mode != "osint":
            log("🤖 Gemini AI filter…")
            try:
                from gemini_filter import GeminiFilter
                gf = GeminiFilter()
                keyword_hint = keywords[0] if keywords else ""
                scraper.results = gf.filter_results(scraper.results, language, keyword_hint)
                log(f"✅ {len(scraper.results)} lolos filter")
            except Exception as e:
                log(f"⚠️ Gemini filter error: {e}")
        progress(0.85)

        # Trend / Stock analysis
        ai_summary = ""
        if search_mode == "stock":
            log("📈 Generating stock sentiment…")
            try:
                gf = GeminiFilter()
                ai_summary = gf.analyze_stock_sentiment(
                    scraper.results, keywords[0] if keywords else "", language
                )
            except Exception as e:
                ai_summary = f"⚠️ Error: {e}"
        elif search_mode != "osint":
            scraper.detect_trends()

        progress(0.95)

        # Export
        scraper.export_csv()
        log("💾 Exported to search_results.csv")

        progress(1.0)
        log("✅ Selesai!")

        if on_complete:
            on_complete({
                "results": scraper.results,
                "ai_summary": ai_summary,
                "mode": search_mode,
                "osint_correlation": scraper.osint_correlation,
            })

    except Exception as e:
        log(f"❌ Error: {e}")
        if on_complete:
            on_complete({"results": [], "ai_summary": f"Error: {e}"})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

BANNER = f"""
{Fore.CYAN}{Style.BRIGHT}
  ╔═══════════════════════════════════════════════════════╗
  ║                                                       ║
  ║   ███████╗ ██████╗██████╗  █████╗ ██████╗ ██████╗    ║
  ║   ██╔════╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██╔══██╗   ║
  ║   ███████╗██║     ██████╔╝███████║██████╔╝██████╔╝   ║
  ║   ╚════██║██║     ██╔══██╗██╔══██║██╔═══╝ ██╔═══╝    ║
  ║   ███████║╚██████╗██║  ██║██║  ██║██║     ██║        ║
  ║   ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝        ║
  ║           {Fore.YELLOW}E  R  I  A{Fore.CYAN}                                   ║
  ║                                                       ║
  ║   {Fore.WHITE}AI-Powered Search Engine  ·  v7.0{Fore.CYAN}                  ║
  ║   {Fore.MAGENTA}Gemini AI  ·  Smart Expansion  ·  Trends{Fore.CYAN}          ║
  ║                                                       ║
  ║           {Fore.GREEN}created by Keegan{Fore.CYAN}                          ║
  ║                                                       ║
  ╚═══════════════════════════════════════════════════════╝
{Style.RESET_ALL}"""

def main():
    print(BANNER)

    raw_input = input(f"{Fore.YELLOW}  🔍 Mau cari apa? » {Style.RESET_ALL}").strip()
    if not raw_input:
        print(f"{Fore.RED}  ⚠️  Input kosong.{Style.RESET_ALL}")
        return

    # --- Gemini parse natural query ---
    print(f"\n{Fore.MAGENTA}  🤖 Gemini parsing query…{Style.RESET_ALL}")
    try:
        gf = GeminiFilter()
        parsed = gf.parse_natural_query(raw_input)
    except Exception as e:
        print(f"   ⚠️  Gemini error: {e}")
        parsed = {
            "keywords": [k.strip() for k in raw_input.split(",") if k.strip()],
            "language": "id", "mode": "text", "time_range": "w",
        }

    keywords = parsed.get("keywords", [raw_input])
    language = parsed.get("language", "id")
    mode = parsed.get("mode", "text")
    time_range = parsed.get("time_range", "w")

    # For OSINT, ensure raw input is always the primary keyword
    keywords = normalize_keyword_list(raw_input, keywords, mode)

    print(f"\n{Fore.CYAN}  ┌─ Parsed Settings ──────────────────────{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  │{Style.RESET_ALL} 📋 Keywords : {Fore.WHITE}{keywords}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  │{Style.RESET_ALL} 🌐 Bahasa   : {Fore.WHITE}{language}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  │{Style.RESET_ALL} 📰 Mode     : {Fore.WHITE}{mode}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  │{Style.RESET_ALL} ⏰ Waktu    : {Fore.WHITE}{time_range or 'semua'}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  └──────────────────────────────────────{Style.RESET_ALL}")

    # Beri user kesempatan override
    override = input(f"\n{Fore.YELLOW}  Override settings? (y/n, default n): {Style.RESET_ALL}").strip().lower()
    if override == "y":
        kw_override = input(f"  Keywords [{', '.join(keywords)}]: ").strip()
        if kw_override:
            keywords = [k.strip() for k in kw_override.split(",") if k.strip()]

        mode_override = input(f"  Mode [{mode}]: ").strip().lower()
        if mode_override in ("text", "news", "stock", "osint"):
            mode = mode_override

        lang_override = input(f"  Bahasa [{language}]: ").strip().lower()
        if lang_override:
            language = lang_override

        time_override = input(f"  Waktu [{time_range}]: ").strip().lower()
        if time_override in ("d", "w", "m", "y", ""):
            time_range = time_override

    num_results = int(input(f"{Fore.YELLOW}  Jumlah hasil (default 20): {Style.RESET_ALL}").strip() or "20")

    enrich_input = input(f"{Fore.YELLOW}  Ambil tanggal asli? (y/n, default y): {Style.RESET_ALL}").strip().lower()
    enrich = enrich_input != "n"

    json_input = input(f"{Fore.YELLOW}  Export JSON? (y/n, default n): {Style.RESET_ALL}").strip().lower()
    do_json = json_input == "y"

    # --- Run ---
    scraper = SearchScraper()
    scraper.scrape(
        keywords=keywords,
        language=language,
        time_range=time_range,
        num_results=num_results,
        use_language_filter=True,
        search_mode=mode,
        enrich_dates=enrich,
    )

    if not scraper.results:
        print(f"\n{Fore.RED}  ⚠️  Tidak ada hasil.{Style.RESET_ALL}")
        return

    scraper.deduplicate()
    scraper.score_and_rank(language=language, mode=mode, raw_query=raw_input)

    # --- Trend Analysis / Stock Analysis ---
    if mode == "stock":
        print(f"\n{Fore.CYAN}  📈 Analisis saham sedang disiapkan...{Style.RESET_ALL}")
        # Skip normal trend detection for stock mode to save time
    elif mode != "osint":
        scraper.detect_trends()

    # --- Export ---
    scraper.export_csv()
    if do_json:
        scraper.export_json()
    scraper.preview()

    # --- Optional/Stock AI Conclusion ---
    if mode == "stock":
        print(f"\n{Fore.MAGENTA}  🤖 Generating AI Stock Sentiment Analysis…{Style.RESET_ALL}")
        try:
            gf = GeminiFilter()
            keyword_hint = keywords[0] if keywords else raw_input
            summary = gf.analyze_stock_sentiment(scraper.results, keyword_hint, language)
            print(f"\n{Fore.CYAN}{'═'*60}")
            print(f"  📈 TREN SAHAM & SENTIMEN AI")
            print(f"{'═'*60}{Style.RESET_ALL}")
            print(f"\n{Fore.WHITE}{summary}{Style.RESET_ALL}")
        except Exception as e:
            print(f"   ⚠️  Error: {e}")
    else:
        conclude = input(f"\n{Fore.MAGENTA}  🤖 Mau Gemini buat kesimpulan? (y/n, default n): {Style.RESET_ALL}").strip().lower()
        if conclude == "y":
            print(f"\n{Fore.MAGENTA}  🤖 Generating AI conclusion…{Style.RESET_ALL}")
            try:
                gf = GeminiFilter()
                keyword_hint = keywords[0] if keywords else raw_input
                summary = gf.summarize_results(scraper.results, keyword_hint, language)
                print(f"\n{Fore.CYAN}{'═'*60}")
                print(f"  📋 KESIMPULAN AI")
                print(f"{'═'*60}{Style.RESET_ALL}")
                print(f"\n{Fore.WHITE}{summary}{Style.RESET_ALL}")
            except Exception as e:
                print(f"   ⚠️  Error: {e}")

    print(f"\n{Fore.GREEN}{'═'*60}")
    print(f"  ✅ Selesai! Powered by Scrapperia")
    print(f"{'═'*60}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
