"""
Scrapperia Desktop App — Flet GUI
AI-Powered Search Engine · v7.0
Created by Keegan
"""

import flet as ft
import threading
from datetime import datetime

# Import engine
from randSearch import run_scrape
from gemini_filter import GeminiFilter
from osint_analyzer import OSINTAnalyzer

# Global state to store results per page session
_session_results = {}


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
BG = "#0f0f1a"
SURFACE = "#1a1a2e"
CARD = "#16213e"
ACCENT = "#00d4aa"
ACCENT2 = "#0f3460"
TEXT = "#e0e0e0"
TEXT_DIM = "#888899"
YELLOW = "#f5c518"
RED = "#ff4757"
GREEN = "#2ed573"
MAGENTA = "#e056a0"


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

def main(page: ft.Page):
    page.title = "Scrapperia — AI-Powered Search Engine"
    page.bgcolor = BG
    page.padding = 0
    page.window.width = 1100
    page.window.height = 750
    page.window.min_width = 900
    page.window.min_height = 600
    page.theme = ft.Theme(font_family="Inter")

    # ---- State ----
    search_running = False

    # ---- Header ----
    header = ft.Container(
        content=ft.Column([
            ft.Text("S C R A P P E R I A", size=28, weight=ft.FontWeight.BOLD,
                     color=ACCENT, text_align=ft.TextAlign.CENTER),
            ft.Text("AI-Powered Search Engine  ·  v7.0",
                     size=12, color=TEXT_DIM, text_align=ft.TextAlign.CENTER),
            ft.Text("created by Keegan", size=10, color=GREEN,
                     text_align=ft.TextAlign.CENTER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
        padding=ft.padding.symmetric(vertical=18),
        bgcolor=SURFACE,
        border_radius=ft.border_radius.only(bottom_left=12, bottom_right=12),
    )

    # ---- Search input ----
    search_field = ft.TextField(
        hint_text="Mau cari apa? Ketik bebas…",
        border_color=ACCENT2,
        focused_border_color=ACCENT,
        color=TEXT,
        bgcolor=CARD,
        border_radius=10,
        prefix_icon=ft.Icons.SEARCH,
        text_size=15,
        expand=True,
    )

    # ---- Mode selector ----
    # (Defined later to attach on_change after settings controls are defined)

    # ---- Settings ----
    lang_dd = ft.Dropdown(
        label="Bahasa", value="id", width=120,
        options=[ft.dropdown.Option("id", "Indonesia"), ft.dropdown.Option("en", "English"),
                 ft.dropdown.Option("es", "Español"), ft.dropdown.Option("fr", "Français")],
        border_color=ACCENT2, focused_border_color=ACCENT, color=TEXT,
        bgcolor=CARD, text_size=13,
    )

    time_dd = ft.Dropdown(
        label="Waktu", value="w", width=120,
        options=[ft.dropdown.Option("d", "Hari ini"), ft.dropdown.Option("w", "Minggu ini"),
                 ft.dropdown.Option("m", "Bulan ini"), ft.dropdown.Option("y", "Tahun ini"),
                 ft.dropdown.Option("", "Semua")],
        border_color=ACCENT2, focused_border_color=ACCENT, color=TEXT,
        bgcolor=CARD, text_size=13,
    )

    num_slider = ft.Slider(
        min=5, max=50, value=20, divisions=9, label="{value}",
        active_color=ACCENT, inactive_color=ACCENT2, width=180,
    )
    num_label = ft.Text("Hasil: 20", size=12, color=TEXT_DIM)

    def slider_changed(e):
        num_label.value = f"Hasil: {int(num_slider.value)}"
        page.update()

    num_slider.on_change = slider_changed

    enrich_switch = ft.Switch(label="Tanggal asli", value=True, active_color=ACCENT)

    # ---- Mode selector ----
    def mode_changed(e):
        sel = mode_selector.selected
        selected_mode = sel[0] if isinstance(sel, list) and sel else (list(sel)[0] if sel else "text")
        
        # Sembunyikan setting scraper spesifik jika masuk mode OSINT
        is_osint = selected_mode == "osint"
        lang_dd.visible = not is_osint
        time_dd.visible = not is_osint
        num_slider.visible = not is_osint
        num_label.visible = not is_osint
        enrich_switch.visible = not is_osint
        page.update()

    mode_selector = ft.SegmentedButton(
        segments=[
            ft.Segment(value="text", label=ft.Text("🌐 Text")),
            ft.Segment(value="news", label=ft.Text("📰 News")),
            ft.Segment(value="stock", label=ft.Text("📈 Stock")),
            ft.Segment(value="osint", label=ft.Text("🕵️ OSINT")),
        ],
        selected=["text"],
        on_change=mode_changed
    )

    # ---- Progress ----
    progress_bar = ft.ProgressBar(value=0, color=ACCENT, bgcolor=ACCENT2, visible=False)
    status_text = ft.Text("", size=11, color=ACCENT, italic=True)

    # ---- Log panel ----
    log_list = ft.ListView(spacing=2, height=100, auto_scroll=True)

    def add_log(msg: str):
        log_list.controls.append(
            ft.Text(msg, size=11, color=TEXT_DIM, selectable=True)
        )
        try:
            page.update()
        except Exception:
            pass

    # ---- Results panel ----
    results_list = ft.ListView(spacing=8, expand=True)
    results_count = ft.Text("", size=12, color=TEXT_DIM)

    def build_result_card(r, index):
        d = r.get("date")
        fmt = d.strftime("%Y-%m-%d") if isinstance(d, datetime) else "N/A"
        score = r.get("quality_score", 0)
        grade = r.get("quality_grade", "-")
        src = r.get("source", "")
        desc = r.get("ai_summary") or (r.get("description") or "")[:150]
        link = r.get("link") or ""

        grade_color = GREEN if grade.startswith(("A", "B")) else (YELLOW if grade.startswith("C") else RED)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Text(grade, size=12, weight=ft.FontWeight.BOLD, color="#fff"),
                        bgcolor=grade_color, padding=ft.padding.symmetric(horizontal=8, vertical=3),
                        border_radius=6,
                    ),
                    ft.Text(f"{score:.0f}", size=11, color=TEXT_DIM),
                    ft.Text(r.get("title", "")[:75], size=13, weight=ft.FontWeight.W_600,
                            color=TEXT, expand=True, overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=8),
                ft.Row([
                    ft.Icon(ft.Icons.CALENDAR_TODAY, size=12, color=TEXT_DIM),
                    ft.Text(fmt, size=11, color=TEXT_DIM),
                    ft.Text(f"· {src}" if src else "", size=11, color=ACCENT),
                ], spacing=4),
                ft.Text(link[:80], size=10, color=ACCENT2,
                        overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(desc, size=11, color=TEXT_DIM, max_lines=2),
            ], spacing=4),
            bgcolor=CARD,
            border_radius=8,
            padding=12,
        )

    # ---- AI panel ----
    ai_content = ft.Text("", size=12, color=TEXT, selectable=True)
    ai_panel = ft.Container(
        content=ft.Column([
            ft.Text("🤖 AI Insight", size=14, weight=ft.FontWeight.BOLD, color=ACCENT),
            ai_content,
        ], spacing=6),
        bgcolor=SURFACE,
        border_radius=10,
        padding=16,
        visible=False,
    )

    # ---- OSINT panel ----
    osint_content = ft.Column(spacing=4)
    osint_panel = ft.Container(
        content=ft.Column([
            ft.Text("🕵️ OSINT Entities Found", size=14, weight=ft.FontWeight.BOLD, color="#ff9f43"),
            osint_content,
        ], spacing=6),
        bgcolor=SURFACE,
        border_radius=10,
        padding=16,
        visible=False,
    )

    # ---- Search button ----
    def on_search(e):
        nonlocal search_running
        if search_running:
            return

        query = search_field.value.strip()
        if not query:
            return

        search_running = True
        search_btn.disabled = True
        progress_bar.visible = True
        progress_bar.value = 0
        status_text.value = "Parsing query…"
        log_list.controls.clear()
        results_list.controls.clear()
        results_count.value = ""
        ai_panel.visible = False
        osint_panel.visible = False
        osint_content.controls.clear()
        page.update()

        sel = mode_selector.selected
        selected_mode = sel[0] if isinstance(sel, list) and sel else (list(sel)[0] if sel else "text")

        # Parse with Gemini first
        add_log("🤖 Gemini parsing query…")
        try:
            gf = GeminiFilter()
            parsed = gf.parse_natural_query(query)
        except Exception:
            parsed = {"keywords": [query], "language": "id", "mode": "text", "time_range": "w"}

        keywords = parsed.get("keywords", [query])
        lang = parsed.get("language", lang_dd.value)
        mode = parsed.get("mode", selected_mode)
        tr = parsed.get("time_range", time_dd.value)

        # Override with explicit UI settings if user changed them
        if lang_dd.value != "id":
            lang = lang_dd.value
        if selected_mode != "text":
            mode = selected_mode
        if time_dd.value != "w":
            tr = time_dd.value

        add_log(f"📋 Keywords: {keywords}")
        add_log(f"🌐 {lang} | 📰 {mode} | ⏰ {tr}")

        def _on_log(msg):
            add_log(msg)

        def _on_progress(pct):
            progress_bar.value = pct
            status_text.value = f"Progress: {int(pct*100)}%"
            try:
                page.update()
            except Exception:
                pass

        def _on_complete(data):
            nonlocal search_running
            # Store results globally for this page
            _session_results[page.session.id] = data.get("results", [])
            
            results = data.get("results", [])
            summary = data.get("ai_summary", "")

            results_count.value = f"{len(results)} hasil ditemukan"

            for i, r in enumerate(results):
                results_list.controls.append(build_result_card(r, i))

            if mode == "osint":
                # Extract entities automatically
                oa = OSINTAnalyzer()
                combined_text = " ".join([r.get("title", "") + " " + r.get("description", "") for r in results])
                entities = oa.extract_entities_regex(combined_text)
                
                osint_content.controls.clear()
                
                if entities.get("emails"):
                    osint_content.controls.append(ft.Text("📧 Emails:", size=11, color=TEXT_DIM, weight=ft.FontWeight.BOLD))
                    for e in entities["emails"]:
                        osint_content.controls.append(ft.Text(f" • {e}", size=11, color=TEXT, selectable=True))
                
                if entities.get("phones"):
                    osint_content.controls.append(ft.Text("📞 Phones:", size=11, color=TEXT_DIM, weight=ft.FontWeight.BOLD))
                    for p in entities["phones"]:
                        osint_content.controls.append(ft.Text(f" • {p}", size=11, color=TEXT, selectable=True))

                if entities.get("links"):
                    # Show up to 5 social/footprint links
                    osint_content.controls.append(ft.Text("🔗 Key Footprints:", size=11, color=TEXT_DIM, weight=ft.FontWeight.BOLD))
                    for l in entities["links"][:5]:
                        osint_content.controls.append(ft.Text(f" • {l}", size=11, color=ACCENT2, selectable=True))
                
                if not osint_content.controls:
                    osint_content.controls.append(ft.Text("No key entities automatically detected.", size=11, color=TEXT_DIM))
                    
                osint_panel.visible = True
            
            if summary:
                ai_content.value = summary
                ai_panel.visible = True

            progress_bar.visible = False
            status_text.value = "✅ Selesai!"
            search_btn.disabled = False
            search_running = False
            try:
                page.update()
            except Exception:
                pass

        # Run scraping in background thread
        def _worker():
            run_scrape(
                keywords=keywords,
                language=lang,
                time_range=tr,
                num_results=int(num_slider.value),
                search_mode=mode,
                enrich_dates=enrich_switch.value,
                on_log=_on_log,
                on_progress=_on_progress,
                on_complete=_on_complete,
            )

        threading.Thread(target=_worker, daemon=True).start()

    search_btn = ft.FilledButton(
        "Search",
        icon=ft.Icons.SEARCH,
        style=ft.ButtonStyle(
            bgcolor=ACCENT,
            color="#000",
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
        height=48,
        width=280,
        on_click=on_search,
    )

    # ---- Conclusion button ----
    def on_conclude(e):
        if not results_list.controls:
            return
        conclude_btn.disabled = True
        page.update()
        add_log("🤖 Generating AI conclusion…")

        def _worker():
            try:
                gf = GeminiFilter()
                kw = search_field.value.strip()
                
                # Retrieve results from memory
                results = _session_results.get(page.session.id, [])
                if not results:
                    add_log("⚠️ Tidak ada data untuk disimpulkan")
                    conclude_btn.disabled = False
                    try:
                        page.update()
                    except: pass
                    return

                if selected_mode == "osint":
                    oa = OSINTAnalyzer()
                    profile = oa.analyze_profile(kw, results)
                    summary = f"**Profile Summary**\n{profile.get('profile_summary', 'N/A')}\n\n"
                    summary += f"**Affiliations**: {', '.join(profile.get('affiliations', []))}\n"
                    summary += f"**Locations**: {', '.join(profile.get('locations', []))}\n"
                    summary += f"**Usernames**: {', '.join(profile.get('associated_usernames', []))}\n"
                else:
                    summary = gf.summarize_results(results, kw, lang_dd.value)
                    
                ai_content.value = summary
                ai_panel.visible = True
                conclude_btn.disabled = False
                add_log("✅ Kesimpulan AI selesai")
            except Exception as ex:
                add_log(f"⚠️ Error: {ex}")
                conclude_btn.disabled = False
            try:
                page.update()
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    conclude_btn = ft.Container(
        content=ft.Text("🤖 AI Conclusion", size=12, color=MAGENTA),
        on_click=on_conclude,
        padding=ft.padding.symmetric(horizontal=8, vertical=4),
    )

    # ---- Layout ----
    left_panel = ft.Container(
        content=ft.Column([
            ft.Text("🔍 Pencarian", size=14, weight=ft.FontWeight.BOLD, color=TEXT),
            search_field,
            ft.Text("Mode", size=11, color=TEXT_DIM),
            mode_selector,
            ft.Divider(height=1, color=ACCENT2),
            ft.Row([lang_dd, time_dd], spacing=8),
            ft.Column([num_label, num_slider], spacing=0),
            enrich_switch,
            ft.Divider(height=1, color=ACCENT2),
            search_btn,
            status_text,
        ], spacing=10, scroll=ft.ScrollMode.AUTO),
        width=320,
        bgcolor=SURFACE,
        border_radius=12,
        padding=20,
    )

    right_panel = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("📋 Hasil", size=14, weight=ft.FontWeight.BOLD, color=TEXT),
                results_count,
                conclude_btn,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            progress_bar,
            results_list,
            osint_panel,
            ai_panel,
            ft.Container(
                content=ft.Column([
                    ft.Text("📡 Log", size=11, color=TEXT_DIM),
                    log_list,
                ], spacing=4),
                bgcolor=CARD,
                border_radius=8,
                padding=10,
            ),
        ], spacing=8, expand=True),
        expand=True,
        bgcolor=SURFACE,
        border_radius=12,
        padding=16,
    )

    body = ft.Row(
        [left_panel, right_panel],
        spacing=12,
        expand=True,
    )

    page.add(
        ft.Column([
            header,
            ft.Container(content=body, expand=True, padding=12),
        ], expand=True, spacing=0)
    )


if __name__ == "__main__":
    ft.app(target=main)
