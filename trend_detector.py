"""
Trend Detector v1.0

Analisis temporal dari hasil scraping untuk mendeteksi trend:
  - Timeline: jumlah artikel per periode waktu
  - Trend scoring: naik 📈, stabil ➡️, turun 📉
  - Peak detection: tanggal puncak publikasi
  - ASCII chart: visualisasi trend di terminal
  - Subtopic extraction: kata kunci populer dalam hasil
"""

import re
from datetime import datetime, timedelta
from collections import Counter, defaultdict


# ---------------------------------------------------------------------------
# TrendDetector
# ---------------------------------------------------------------------------

class TrendDetector:
    """Analisis trend dari hasil scraping berdasarkan tanggal publikasi."""

    def __init__(self, results: list[dict]):
        self.results = results
        self.dated_results = [r for r in results if isinstance(r.get("date"), datetime)]
        self.timeline: dict[str, int] = {}
        self.trend_score: float = 0.0
        self.trend_direction: str = ""
        self.peaks: list[dict] = []
        self.subtopics: list[tuple[str, int]] = []
        self._analyzed = False

    # ------------------------------------------------------------------
    # Main analysis
    # ------------------------------------------------------------------

    def analyze(self):
        """Run semua analisis."""
        if not self.dated_results:
            print("   ⚠️  Tidak ada hasil dengan tanggal — trend analysis dilewati.")
            self._analyzed = True
            return self

        self._build_timeline()
        self._calculate_trend_score()
        self._detect_peaks()
        self._extract_subtopics()
        self._analyzed = True
        return self

    # ------------------------------------------------------------------
    # Timeline builder
    # ------------------------------------------------------------------

    def _build_timeline(self):
        """Kelompokkan artikel per hari."""
        day_counts: dict[str, int] = defaultdict(int)

        for r in self.dated_results:
            day_key = r["date"].strftime("%Y-%m-%d")
            day_counts[day_key] += 1

        # Sort secara kronologis
        self.timeline = dict(sorted(day_counts.items()))

    # ------------------------------------------------------------------
    # Trend scoring
    # ------------------------------------------------------------------

    def _calculate_trend_score(self):
        """
        Hitung trend score:
          > 0 = naik (📈)
          = 0 = stabil (➡️)
          < 0 = turun (📉)

        Metode: bandingkan rata-rata count di paruh pertama vs kedua.
        """
        if len(self.timeline) < 2:
            self.trend_score = 0.0
            self.trend_direction = "➡️ Stabil"
            return

        dates = list(self.timeline.keys())
        counts = list(self.timeline.values())
        mid = len(counts) // 2

        first_half_avg = sum(counts[:mid]) / max(mid, 1)
        second_half_avg = sum(counts[mid:]) / max(len(counts) - mid, 1)

        if first_half_avg == 0:
            self.trend_score = 100.0 if second_half_avg > 0 else 0.0
        else:
            self.trend_score = ((second_half_avg - first_half_avg) / first_half_avg) * 100

        if self.trend_score > 20:
            self.trend_direction = "📈 Naik"
        elif self.trend_score < -20:
            self.trend_direction = "📉 Turun"
        else:
            self.trend_direction = "➡️ Stabil"

    # ------------------------------------------------------------------
    # Peak detection
    # ------------------------------------------------------------------

    def _detect_peaks(self):
        """Identifikasi tanggal dengan jumlah artikel terbanyak."""
        if not self.timeline:
            return

        max_count = max(self.timeline.values())
        avg_count = sum(self.timeline.values()) / len(self.timeline)

        # Peak = hari dengan count di atas rata-rata
        self.peaks = [
            {"date": d, "count": c}
            for d, c in self.timeline.items()
            if c >= max(avg_count * 1.2, 2)
        ]
        self.peaks.sort(key=lambda x: x["count"], reverse=True)

    # ------------------------------------------------------------------
    # Subtopic extraction
    # ------------------------------------------------------------------

    def _extract_subtopics(self):
        """Ekstrak kata kunci yang sering muncul di hasil."""
        # Stopwords (ID + EN)
        stopwords = {
            "dan", "yang", "untuk", "dari", "pada", "dengan", "ini", "itu",
            "adalah", "akan", "tidak", "atau", "juga", "telah", "dapat",
            "seperti", "oleh", "dalam", "saat", "karena", "di", "ke", "se",
            "the", "and", "for", "are", "but", "not", "you", "all", "any",
            "can", "had", "her", "was", "one", "our", "out", "day", "get",
            "has", "him", "this", "that", "with", "have", "from", "they",
            "been", "said", "each", "which", "their", "will", "other",
            "about", "many", "then", "them", "its", "over", "after",
            "more", "also", "how", "when", "what", "who", "where",
            "no", "description", "available", "http", "https", "www",
            "com", "co", "id", "org", "net",
        }

        word_counter: Counter = Counter()

        for r in self.results:
            text = f"{r.get('title', '')} {r.get('description', '')}"
            words = re.findall(r"\b[a-zA-Z\u00C0-\u024F]{3,}\b", text.lower())
            for w in words:
                if w not in stopwords and len(w) > 2:
                    word_counter[w] += 1

        # Top subtopics (minimal muncul 2x)
        self.subtopics = [
            (word, count) for word, count in word_counter.most_common(15)
            if count >= 2
        ]

    # ------------------------------------------------------------------
    # ASCII Chart
    # ------------------------------------------------------------------

    def render_chart(self, width: int = 40) -> str:
        """Render ASCII timeline chart."""
        if not self.timeline:
            return "   (Tidak ada data timeline)"

        lines = []
        max_count = max(self.timeline.values())

        lines.append(f"   {'─' * (width + 12)}")

        for date_str, count in self.timeline.items():
            bar_len = int((count / max_count) * width) if max_count > 0 else 0
            bar = "█" * bar_len
            # Singkatkan tanggal
            short_date = date_str[5:]  # MM-DD
            lines.append(f"   {short_date} │{bar} {count}")

        lines.append(f"   {'─' * (width + 12)}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Generate human-readable trend summary."""
        if not self._analyzed:
            self.analyze()

        lines = []
        lines.append(f"\n{'='*60}")
        lines.append(f"  📊 TREND ANALYSIS")
        lines.append(f"{'='*60}")

        total = len(self.results)
        dated = len(self.dated_results)
        lines.append(f"\n  Total hasil: {total} | Punya tanggal: {dated}")

        if not self.dated_results:
            lines.append("  ⚠️ Tidak cukup data tanggal untuk analisis trend.")
            return "\n".join(lines)

        # Date range
        dates = sorted(r["date"] for r in self.dated_results)
        lines.append(f"  Rentang: {dates[0].strftime('%Y-%m-%d')} → "
                      f"{dates[-1].strftime('%Y-%m-%d')}")

        # Trend direction
        lines.append(f"\n  Trend: {self.trend_direction} "
                      f"({self.trend_score:+.0f}%)")

        # Peaks
        if self.peaks:
            lines.append(f"\n  🔥 Peak dates:")
            for p in self.peaks[:3]:
                lines.append(f"     {p['date']}: {p['count']} artikel")

        # Chart
        lines.append(f"\n  📈 Timeline:")
        lines.append(self.render_chart())

        # Subtopics
        if self.subtopics:
            lines.append(f"\n  🏷️  Hot subtopics:")
            for word, count in self.subtopics[:8]:
                bar = "▪" * min(count, 10)
                lines.append(f"     {word:<20} {bar} ({count})")

        lines.append(f"\n{'='*60}")
        return "\n".join(lines)
