# 🕷️ Scrapperia

**AI-Powered Search Engine** — Smart Expansion • Gemini AI • Trend Detection • Stock Prediction

Scrapperia adalah scraper pencarian cerdas yang menggunakan **Google Gemini AI** untuk parsing query natural, filter bahasa, analisis sentimen saham, dan ringkasan otomatis. Dibangun di atas DuckDuckGo — tanpa API key search engine, tanpa browser, tanpa CAPTCHA.

> Created by **Keegan**

---

## ✨ Fitur Utama

### 🤖 Gemini AI Integration
- **Natural Language Input** — Ketik bebas seperti `"loker untuk Mayora terbaru"` atau `"prediksi saham GOTO hari ini"`, Gemini otomatis parsing menjadi keyword, bahasa, mode, dan rentang waktu
- **AI Language Filter** — Gemini mendeteksi bahasa setiap hasil dengan akurat (batch 15 per API call)
- **AI Relevance Scoring** — Filter otomatis hasil yang tidak relevan
- **AI Summary** — Ringkasan 1 kalimat per hasil pencarian
- **AI Conclusion** — Ringkasan keseluruhan hasil pencarian (opsional, hemat quota)

### 📈 Stock Prediction Mode
- **Auto-detect** — Ketik keyword saham (misal `"saham BBCA"`, `"prediksi GOTO"`) dan mode `stock` otomatis aktif
- **Sumber Finansial** — Query diarahkan ke situs finansial (CNBC Indonesia, TradingView, dll)
- **Analisis Sentimen** — Gemini AI menganalisis berita dan menghasilkan:
  - Sentimen Pasar (Bullish / Bearish / Netral)
  - Key Catalysts (berita penggerak harga)
  - Support & Resistance (jika tersedia)
  - AI Signal: **BUY / HOLD / SELL**

### 🧠 Smart Keyword Expansion
- **DDG Autocomplete** — Fetch saran pencarian otomatis
- **Entity Detection** — Deteksi nama perusahaan, akronim (MDP, IPO, IHSG)
- **Intent Detection** — Otomatis kenali apakah keyword = job, news, stock, atau general
- **Operator Variants** — Exact match, site-specific queries

### 📊 Trend Detection
- Timeline analysis per minggu/bulan
- Trend scoring (📈 naik / ➡️ stabil / 📉 turun)
- Peak detection (tanggal puncak publikasi)
- ASCII chart di terminal
- Subtopic extraction

### 🛠️ Fitur Lainnya
- **Real Date Extraction** — Ambil tanggal asli dari meta tags artikel
- **Quality Scoring** — Grade A+ sampai F berdasarkan relevansi, sumber, dan kelengkapan
- **Dedup** — Hapus hasil duplikat otomatis
- **Export CSV & JSON**
- **Terminal UI Profesional** — ASCII banner + colorama styling

---

## 📦 Instalasi

### Prerequisites
- Python 3.10+
- Gemini API Key (gratis di [Google AI Studio](https://aistudio.google.com/))

### Setup

```bash
# 1. Install dependencies
pip install duckduckgo-search python-dateutil tqdm requests google-generativeai python-dotenv colorama

# 2. Buat file .env di folder project
echo GEMINI_API_KEY=your_api_key_here > .env
```

---

## 🚀 Cara Penggunaan

### Metode 1: Double-Click
Jalankan `Scrapperia.bat` — langsung terbuka di terminal.

### Metode 2: Terminal
```bash
python randSearch.py
```

### Contoh Interaksi

```
🔍 Mau cari apa? » loker untuk Mayora terbaru

🤖 Gemini parsing query…

  ┌─ Parsed Settings ──────────────────────
  │ 📋 Keywords : ['lowongan Mayora', 'MDP Mayora', 'karir Mayora']
  │ 🌐 Bahasa   : id
  │ 📰 Mode     : text
  │ ⏰ Waktu    : w
  └──────────────────────────────────────

  Override settings? (y/n, default n):
  Jumlah hasil (default 20): 10
  Ambil tanggal asli? (y/n, default y):
  Export JSON? (y/n, default n):
```

### Mode Saham
```
🔍 Mau cari apa? » prediksi saham GOTO hari ini

  📋 Keywords : ['saham GOTO', 'prediksi GOTO', 'GOTO analisis']
  📰 Mode     : stock
  ⏰ Waktu    : d

  ════════════════════════════════════════
    📈 TREN SAHAM & SENTIMEN AI
  ════════════════════════════════════════

  📊 Sentimen Pasar: Bullish — didorong oleh …
  📈 Key Catalysts: …
  🎯 Support & Resistance: …
  💡 AI Signal: HOLD
```

---

## 📁 Struktur File

| File | Deskripsi |
|---|---|
| `randSearch.py` | Engine utama + CLI |
| `gemini_filter.py` | Gemini AI: parser, filter, sentimen, summary |
| `query_optimizer.py` | Smart keyword expansion via DDG APIs |
| `quality_rater.py` | Quality scoring & dedup |
| `trend_detector.py` | Trend analysis & ASCII chart |
| `Scrapperia.bat` | Launcher Windows |
| `.env` | API key (jangan commit!) |

---

## ⚠️ Disclaimer

> Fitur Stock Prediction Mode bersifat **informasional saja**. Analisis sentimen dan sinyal AI dihasilkan dari berita publik dan **bukan nasihat investasi**. Selalu lakukan riset mandiri sebelum mengambil keputusan trading.

---

## 📄 License

MIT License — bebas digunakan dan dimodifikasi.
