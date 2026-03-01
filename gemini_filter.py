"""
Gemini Filter v1.0 — AI-Powered Result Filtering

Menggunakan Google Gemini untuk:
  - Language detection (sangat akurat)
  - Relevance scoring (apakah hasil benar-benar cocok)
  - Smart summary per hasil

Dikemas dalam batch call (1 API call untuk banyak hasil)
agar hemat quota dan cepat.
"""

import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# GeminiFilter
# ---------------------------------------------------------------------------

class GeminiFilter:
    """AI-powered filter menggunakan Gemini."""

    BATCH_SIZE = 15  # Kirim 15 hasil per API call

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY tidak ditemukan di .env")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    # ------------------------------------------------------------------
    # Natural language query parser
    # ------------------------------------------------------------------

    def parse_natural_query(self, user_input: str) -> dict:
        """
        Parse input natural user menjadi keyword + parameter pencarian.

        Contoh:
          "loker untuk Mayora" → keywords=["lowongan Mayora", "MDP Mayora"]
          "berita saham BUMI minggu ini" → keywords=["saham BUMI"], mode=news, time=w

        Returns:
            dict: {keywords: list[str], language: str, mode: str, time_range: str}
        """
        prompt = f"""Kamu adalah search query parser. User mengetik query pencarian dengan bahasa natural.

Input user: "{user_input}"

Tugas:
1. Ekstrak 2-4 keyword pencarian yang OPTIMAL untuk mesin pencari (singkat, tepat, tanpa kata-kata tidak perlu)
2. Deteksi bahasa konten yang dicari (id/en/es/…)
3. Deteksi mode pencarian: "text" (web umum), "news" (berita terkini), atau "stock" (prediksi/analisis saham)
4. Deteksi rentang waktu: "d" (hari ini), "w" (minggu ini), "m" (bulan ini), "y" (tahun ini), "" (semua)

Respond HANYA JSON, tanpa markdown:
{{"keywords": ["keyword1", "keyword2"], "language": "id", "mode": "stock", "time_range": "d"}}"""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()

            # Bersihkan markdown
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            parsed = json.loads(text)
            if isinstance(parsed, dict) and "keywords" in parsed:
                return parsed
        except Exception as e:
            print(f"   ⚠️  Parse error: {e}")

        # Fallback: split manual
        return {
            "keywords": [k.strip() for k in user_input.split(",") if k.strip()],
            "language": "id",
            "mode": "text",
            "time_range": "w",
        }

    # ------------------------------------------------------------------
    # Summarize results (optional)
    # ------------------------------------------------------------------

    def summarize_results(self, results: list[dict], keyword: str,
                          language: str = "id") -> str:
        """Minta Gemini membuat kesimpulan dari hasil pencarian."""
        items = []
        for i, r in enumerate(results[:15]):  # Max 15 hasil untuk hemat token
            items.append({
                "title": (r.get("title") or "")[:80],
                "desc": (r.get("ai_summary") or r.get("description") or "")[:120],
            })

        lang_name = {"id": "Indonesia", "en": "English", "es": "Español",
                     "fr": "Français", "de": "Deutsch"}.get(language, language)

        prompt = f"""Berdasarkan hasil pencarian untuk "{keyword}", buatkan kesimpulan singkat (3-5 kalimat) dalam bahasa {lang_name}.

Hasil pencarian:
{json.dumps(items, ensure_ascii=False)}

Tulis kesimpulan yang informatif dan padat. Sebutkan temuan utama, tren, dan insight penting."""

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"⚠️ Gagal membuat kesimpulan: {e}"

    # ------------------------------------------------------------------
    # Stock Sentiment Analysis
    # ------------------------------------------------------------------

    def analyze_stock_sentiment(self, results: list[dict], keyword: str,
                                language: str = "id") -> str:
        """Minta Gemini membuat kesimpulan khusus untuk trading/investasi saham."""
        items = []
        for i, r in enumerate(results[:20]):  # Max 20 hasil untuk konteks yang lebih kaya
            items.append({
                "title": (r.get("title") or "")[:100],
                "desc": (r.get("ai_summary") or r.get("description") or "")[:150],
            })

        lang_name = {"id": "Indonesia", "en": "English", "es": "Español",
                     "fr": "Français", "de": "Deutsch"}.get(language, language)

        prompt = f"""Kamu adalah analis saham profesional dan ahli trading.
Berdasarkan hasil pencarian berita dan data terbaru untuk kunci pencarian saham "{keyword}", buatlah analisis sentimen pasar dalam bahasa {lang_name}.

Hasil pencarian terkini:
{json.dumps(items, ensure_ascii=False)}

Format Laporan:
1. **📊 Sentimen Pasar**: (Bullish / Bearish / Netral) disertai 2-3 kalimat penjelasan utama penyebabnya.
2. **📈 Key Catalysts**: Poin-poin berita/katalis penting yang menggerakkan harga saham ini.
3. **🎯 Support & Resistance (Opsional)**: Sebutkan jika ada analis/berita yang menyebutkan level harga tertentu. Jika tidak ada, hilangkan bagian ini.
4. **💡 AI Signal**: Kesimpulan akhir rekomendasi sederhana: BUY, HOLD, atau SELL, untuk jangka pendek.

Tulis dengan gaya profesional namun mudah dipahami trader ritel. Pastikan tidak menambah informasi di luar dari data yang diberikan atau pengetahuan umum yang sangat relevan dan aman."""

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"⚠️ Gagal menganalisis sentimen saham: {e}"

    def filter_results(
        self,
        results: list[dict],
        target_language: str,
        keyword: str,
    ) -> list[dict]:
        """
        Filter hasil menggunakan Gemini AI.

        Untuk setiap hasil, Gemini menilai:
          - language: kode bahasa (id/en/es/…)
          - relevant: true/false apakah relevan dengan keyword
          - summary: ringkasan 1 kalimat

        Returns:
            Results yang lolos filter (bahasa cocok + relevan).
        """
        if not results:
            return results

        filtered = []
        total_batches = (len(results) + self.BATCH_SIZE - 1) // self.BATCH_SIZE

        for batch_idx in range(total_batches):
            start = batch_idx * self.BATCH_SIZE
            end = start + self.BATCH_SIZE
            batch = results[start:end]

            print(f"   🤖 Gemini batch {batch_idx + 1}/{total_batches} "
                  f"({len(batch)} hasil)…")

            ai_results = self._analyze_batch(batch, target_language, keyword)

            for i, r in enumerate(batch):
                if i < len(ai_results):
                    ai = ai_results[i]
                    r["ai_language"] = ai.get("language", "unknown")
                    r["ai_relevant"] = ai.get("relevant", True)
                    r["ai_summary"] = ai.get("summary", "")

                    # Filter: bahasa cocok DAN relevan
                    if (r["ai_language"] == target_language and r["ai_relevant"]):
                        filtered.append(r)
                    else:
                        reason = []
                        if r["ai_language"] != target_language:
                            reason.append(f"bahasa={r['ai_language']}")
                        if not r["ai_relevant"]:
                            reason.append("tidak relevan")
                        # Silent filter — hanya count
                else:
                    # Jika Gemini gagal parse, include by default
                    filtered.append(r)

        removed = len(results) - len(filtered)
        print(f"   ✅ Gemini filter: {len(filtered)} lolos | "
              f"{removed} dibuang")

        return filtered

    # ------------------------------------------------------------------
    # Internal: batch API call
    # ------------------------------------------------------------------

    def _analyze_batch(
        self,
        batch: list[dict],
        target_language: str,
        keyword: str,
    ) -> list[dict]:
        """Kirim batch ke Gemini dan parse hasilnya."""

        # Build compact items for prompt
        items = []
        for i, r in enumerate(batch):
            items.append({
                "id": i,
                "title": (r.get("title") or "")[:100],
                "desc": (r.get("description") or "")[:150],
                "url": (r.get("link") or "")[:100],
            })

        prompt = f"""Kamu adalah AI filter untuk search results.

Keyword pencarian: "{keyword}"
Bahasa target: {target_language}

Analisis setiap hasil berikut. Untuk masing-masing, tentukan:
1. "language": kode bahasa konten (id/en/es/fr/de/pt/dll)
2. "relevant": true jika konten BENAR-BENAR relevan dengan keyword "{keyword}", false jika tidak terkait
3. "summary": ringkasan 1 kalimat dalam bahasa {target_language}

ITEMS:
{json.dumps(items, ensure_ascii=False)}

Respond HANYA dalam format JSON array, tanpa markdown:
[{{"id":0,"language":"id","relevant":true,"summary":"..."}}, ...]"""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()

            # Bersihkan markdown wrapper jika ada
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            # Coba extract JSON dari response
            try:
                import re
                match = re.search(r'\[.*\]', text, re.DOTALL)
                if match:
                    return json.loads(match.group())
            except Exception:
                pass
        except Exception as e:
            print(f"   ⚠️  Gemini error: {e}")

        # Fallback: mark semua sebagai cocok
        return [{"id": i, "language": target_language, "relevant": True,
                 "summary": ""} for i in range(len(batch))]
