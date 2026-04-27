"""
Scrapperia Desktop App - Flet GUI
AI-Powered Search Engine - v7.0
Created by Keegan
"""

import threading
from datetime import datetime

import flet as ft

from gemini_filter import GeminiFilter
from osint_analyzer import OSINTAnalyzer
from randSearch import run_scrape

# Global state to store results per page session
_session_results = {}


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
BG = "#f3f6fb"
SURFACE = "#ffffff"
CARD = "#f8fafc"
CARD_ALT = "#eef2f7"
ACCENT = "#0f62fe"
ACCENT_SOFT = "#dbe8ff"
BORDER = "#d9e2f0"
TEXT = "#0f172a"
TEXT_MUTED = "#64748b"
TEXT_SOFT = "#94a3b8"
WARNING = "#f59e0b"
DANGER = "#ef4444"
SUCCESS = "#16a34a"
MAGENTA = "#c026d3"


def main(page: ft.Page):
    page.title = "Scrapperia - AI-Powered Search Engine"
    page.bgcolor = BG
    page.padding = 0
    page.window.width = 1180
    page.window.height = 780
    page.window.min_width = 980
    page.window.min_height = 640
    page.theme = ft.Theme(font_family="Segoe UI")
    page.theme_mode = ft.ThemeMode.LIGHT

    search_running = False
    current_mode = "text"

    def safe_update(context: str = "ui"):
        try:
            page.update()
        except Exception as ex:
            print(f"[GUI] page.update() failed in {context}: {ex}")

    def build_panel(title: str, subtitle: str, icon: str, content: ft.Control):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Icon(icon, size=18, color=ACCENT),
                                bgcolor=ACCENT_SOFT,
                                border_radius=12,
                                padding=10,
                            ),
                            ft.Column(
                                [
                                    ft.Text(title, size=16, weight=ft.FontWeight.W_600, color=TEXT),
                                    ft.Text(subtitle, size=11, color=TEXT_MUTED),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    content,
                ],
                spacing=16,
            ),
            bgcolor=SURFACE,
            border_radius=20,
            padding=20,
            border=ft.border.all(1, BORDER),
        )

    header = ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text("Scrapperia", size=30, weight=ft.FontWeight.BOLD, color=TEXT),
                        ft.Text(
                            "AI-powered search workspace for discovery, filtering, and OSINT review.",
                            size=13,
                            color=TEXT_MUTED,
                        ),
                    ],
                    spacing=4,
                    expand=True,
                ),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("Version 7.0", size=11, color=TEXT_MUTED),
                            ft.Text("Professional Workspace", size=13, weight=ft.FontWeight.W_600, color=ACCENT),
                        ],
                        spacing=2,
                        horizontal_alignment=ft.CrossAxisAlignment.END,
                    ),
                    bgcolor=CARD,
                    border_radius=16,
                    padding=ft.padding.symmetric(horizontal=16, vertical=12),
                    border=ft.border.all(1, BORDER),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.symmetric(horizontal=24, vertical=22),
        bgcolor=SURFACE,
        border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
    )

    search_field = ft.TextField(
        hint_text="Masukkan topik, perusahaan, nama, atau pertanyaan pencarian",
        border_color=BORDER,
        focused_border_color=ACCENT,
        color=TEXT,
        hint_style=ft.TextStyle(color=TEXT_SOFT, size=14),
        bgcolor=CARD,
        border_radius=14,
        prefix_icon=ft.Icons.SEARCH,
        text_size=15,
        expand=True,
        content_padding=ft.padding.symmetric(horizontal=16, vertical=16),
    )

    lang_dd = ft.Dropdown(
        label="Bahasa",
        value="id",
        width=140,
        options=[
            ft.dropdown.Option("id", "Indonesia"),
            ft.dropdown.Option("en", "English"),
            ft.dropdown.Option("es", "Espanol"),
            ft.dropdown.Option("fr", "Francais"),
        ],
        border_color=BORDER,
        focused_border_color=ACCENT,
        color=TEXT,
        bgcolor=CARD,
        text_size=13,
        border_radius=14,
    )

    time_dd = ft.Dropdown(
        label="Waktu",
        value="w",
        width=140,
        options=[
            ft.dropdown.Option("d", "Hari ini"),
            ft.dropdown.Option("w", "Minggu ini"),
            ft.dropdown.Option("m", "Bulan ini"),
            ft.dropdown.Option("y", "Tahun ini"),
            ft.dropdown.Option("", "Semua"),
        ],
        border_color=BORDER,
        focused_border_color=ACCENT,
        color=TEXT,
        bgcolor=CARD,
        text_size=13,
        border_radius=14,
    )

    num_slider = ft.Slider(
        min=5,
        max=50,
        value=20,
        divisions=9,
        label="{value}",
        active_color=ACCENT,
        inactive_color=ACCENT_SOFT,
    )
    num_label = ft.Text("Jumlah hasil: 20", size=12, color=TEXT_MUTED)

    def slider_changed(e):
        num_label.value = f"Jumlah hasil: {int(num_slider.value)}"
        page.update()

    num_slider.on_change = slider_changed

    enrich_switch = ft.Switch(label="Ambil tanggal asli", value=True, active_color=ACCENT)

    def mode_changed(e):
        nonlocal current_mode
        sel = mode_selector.selected
        current_mode = sel[0] if isinstance(sel, list) and sel else (list(sel)[0] if sel else "text")

        is_osint = current_mode == "osint"
        lang_dd.visible = not is_osint
        time_dd.visible = not is_osint
        result_count_block.visible = not is_osint
        enrich_container.visible = not is_osint
        page.update()

    mode_selector = ft.SegmentedButton(
        segments=[
            ft.Segment(
                value="text",
                label=ft.Container(
                    content=ft.Text("Text", no_wrap=True, size=12, weight=ft.FontWeight.W_600),
                    width=56,
                ),
            ),
            ft.Segment(
                value="news",
                label=ft.Container(
                    content=ft.Text("News", no_wrap=True, size=12, weight=ft.FontWeight.W_600),
                    width=56,
                ),
            ),
            ft.Segment(
                value="stock",
                label=ft.Container(
                    content=ft.Text("Stock", no_wrap=True, size=12, weight=ft.FontWeight.W_600),
                    width=56,
                ),
            ),
            ft.Segment(
                value="osint",
                label=ft.Container(
                    content=ft.Text("OSINT", no_wrap=True, size=12, weight=ft.FontWeight.W_600),
                    width=56,
                ),
            ),
        ],
        selected=["text"],
        on_change=mode_changed,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=14),
            side={ft.ControlState.DEFAULT: ft.BorderSide(1, BORDER)},
        ),
        show_selected_icon=False,
    )

    progress_bar = ft.ProgressBar(value=0, color=ACCENT, bgcolor=ACCENT_SOFT, visible=False, bar_height=8)
    status_text = ft.Text("", size=11, color=ACCENT, italic=True)
    log_list = ft.ListView(spacing=4, height=120, auto_scroll=True)

    def add_log(msg: str):
        log_list.controls.append(ft.Text(msg, size=11, color=TEXT_MUTED, selectable=True))
        safe_update("add_log")

    results_column = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    results_count = ft.Text("Belum ada hasil", size=12, color=TEXT_MUTED)

    empty_results = ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.Icons.SEARCH_OFF, size=40, color=TEXT_SOFT),
                ft.Text("Belum ada hasil pencarian", size=16, weight=ft.FontWeight.W_600, color=TEXT),
                ft.Text(
                    "Masukkan query lalu klik Run Search untuk mulai mencari.",
                    size=12,
                    color=TEXT_MUTED,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            spacing=8,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        expand=True,
    )

    results_area = ft.Container(
        content=empty_results,
        bgcolor=CARD,
        border_radius=16,
        padding=14,
        border=ft.border.all(1, BORDER),
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        expand=True,
    )

    def build_result_card(r, index):
        d = r.get("date")
        fmt = d.strftime("%Y-%m-%d") if isinstance(d, datetime) else "N/A"
        score = r.get("quality_score", 0)
        grade = r.get("quality_grade", "-")
        src = r.get("source", "")
        desc = r.get("ai_summary") or (r.get("description") or "")[:170]
        link = r.get("link") or ""

        grade_color = SUCCESS if grade.startswith(("A", "B")) else (WARNING if grade.startswith("C") else DANGER)

        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(
                                    f"#{index + 1}",
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color=TEXT_MUTED,
                                ),
                                bgcolor=CARD_ALT,
                                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                border_radius=999,
                            ),
                            ft.Container(
                                content=ft.Text(grade, size=11, weight=ft.FontWeight.BOLD, color="#ffffff"),
                                bgcolor=grade_color,
                                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                border_radius=999,
                            ),
                            ft.Container(
                                content=ft.Text(f"Score {score:.0f}", size=11, color=TEXT_MUTED),
                                bgcolor=CARD_ALT,
                                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                border_radius=999,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Text(
                        r.get("title", "")[:95],
                        size=14,
                        weight=ft.FontWeight.W_600,
                        color=TEXT,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CALENDAR_TODAY, size=12, color=TEXT_SOFT),
                            ft.Text(fmt, size=11, color=TEXT_MUTED),
                            ft.Text(src if src else "Sumber tidak diketahui", size=11, color=ACCENT),
                        ],
                        spacing=6,
                        wrap=True,
                    ),
                    ft.Text(link[:95], size=10, color=ACCENT, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(desc, size=11, color=TEXT_MUTED, max_lines=3),
                ],
                spacing=8,
            ),
            bgcolor=CARD,
            border_radius=16,
            padding=14,
            border=ft.border.all(1, BORDER),
        )

    ai_content = ft.Text("", size=12, color=TEXT, selectable=True)
    ai_panel = ft.Container(
        content=ft.Column(
            [
                ft.Text("AI Insight", size=14, weight=ft.FontWeight.BOLD, color=ACCENT),
                ai_content,
            ],
            spacing=6,
        ),
        bgcolor=CARD,
        border_radius=16,
        padding=16,
        border=ft.border.all(1, BORDER),
        visible=False,
    )

    osint_content = ft.Column(spacing=6)
    osint_panel = ft.Container(
        content=ft.Column(
            [
                ft.Text("OSINT Entities", size=14, weight=ft.FontWeight.BOLD, color=WARNING),
                osint_content,
            ],
            spacing=6,
        ),
        bgcolor=CARD,
        border_radius=16,
        padding=16,
        border=ft.border.all(1, BORDER),
        visible=False,
    )

    def on_search(e):
        nonlocal search_running, current_mode
        if search_running:
            return

        query = search_field.value.strip()
        if not query:
            return

        search_running = True
        search_btn.disabled = True
        progress_bar.visible = True
        progress_wrap.visible = True
        progress_bar.value = 0
        status_text.value = "Memproses query..."
        log_list.controls.clear()
        results_column.controls.clear()
        results_area.content = empty_results
        results_count.value = "Menunggu hasil..."
        ai_panel.visible = False
        osint_panel.visible = False
        osint_content.controls.clear()
        safe_update("on_search:start")

        sel = mode_selector.selected
        selected_mode = sel[0] if isinstance(sel, list) and sel else (list(sel)[0] if sel else "text")
        current_mode = selected_mode

        add_log("Gemini memproses query...")
        try:
            gf = GeminiFilter()
            parsed = gf.parse_natural_query(query)
        except Exception:
            parsed = {"keywords": [query], "language": "id", "mode": "text", "time_range": "w"}

        keywords = parsed.get("keywords", [query])
        lang = parsed.get("language", lang_dd.value)
        mode = parsed.get("mode", selected_mode)
        tr = parsed.get("time_range", time_dd.value)

        if lang_dd.value != "id":
            lang = lang_dd.value
        if selected_mode != "text":
            mode = selected_mode
        if time_dd.value != "w":
            tr = time_dd.value

        add_log(f"Keywords: {keywords}")
        add_log(f"Bahasa={lang} | Mode={mode} | Waktu={tr}")

        def _on_log(msg):
            add_log(msg)

        def _on_progress(pct):
            progress_bar.value = pct
            status_text.value = f"Progress {int(pct * 100)}%"
            safe_update("progress")

        def _on_complete(data):
            nonlocal search_running
            _session_results[page.session.id] = data.get("results", [])

            results = data.get("results", [])
            summary = data.get("ai_summary", "")
            print(f"[GUI] Rendering {len(results)} results")
            results_column.controls.clear()
            results_count.value = f"{len(results)} hasil ditemukan"

            if results:
                for i, r in enumerate(results):
                    results_column.controls.append(build_result_card(r, i))
                results_area.content = results_column
            else:
                results_area.content = empty_results

            if mode == "osint":
                oa = OSINTAnalyzer()
                combined_text = " ".join(
                    [r.get("title", "") + " " + r.get("description", "") for r in results]
                )
                entities = oa.extract_entities_regex(combined_text)
                osint_content.controls.clear()

                if entities.get("emails"):
                    osint_content.controls.append(
                        ft.Text("Emails", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD)
                    )
                    for value in entities["emails"]:
                        osint_content.controls.append(ft.Text(f"- {value}", size=11, color=TEXT, selectable=True))

                if entities.get("phones"):
                    osint_content.controls.append(
                        ft.Text("Phones", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD)
                    )
                    for value in entities["phones"]:
                        osint_content.controls.append(ft.Text(f"- {value}", size=11, color=TEXT, selectable=True))

                if entities.get("links"):
                    osint_content.controls.append(
                        ft.Text("Key footprints", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD)
                    )
                    for value in entities["links"][:5]:
                        osint_content.controls.append(ft.Text(f"- {value}", size=11, color=ACCENT, selectable=True))

                if not osint_content.controls:
                    osint_content.controls.append(
                        ft.Text("No key entities automatically detected.", size=11, color=TEXT_MUTED)
                    )

                osint_panel.visible = True
            else:
                osint_panel.visible = False

            if summary:
                ai_content.value = summary
                ai_panel.visible = True
            else:
                ai_panel.visible = False

            progress_bar.visible = False
            progress_wrap.visible = False
            status_text.value = "Selesai"
            search_btn.disabled = False
            search_running = False
            safe_update("complete")

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
        "Run Search",
        icon=ft.Icons.SEARCH,
        style=ft.ButtonStyle(
            bgcolor=ACCENT,
            color="#ffffff",
            shape=ft.RoundedRectangleBorder(radius=14),
            padding=ft.padding.symmetric(horizontal=18, vertical=16),
        ),
        height=52,
        on_click=on_search,
    )

    def on_conclude(e):
        if not results_column.controls:
            return
        conclude_btn.disabled = True
        safe_update("conclude:start")
        add_log("Menyusun kesimpulan AI...")

        def _worker():
            try:
                gf = GeminiFilter()
                kw = search_field.value.strip()
                results = _session_results.get(page.session.id, [])
                if not results:
                    add_log("Tidak ada data untuk disimpulkan")
                    conclude_btn.disabled = False
                    safe_update("conclude:no_results")
                    return

                if current_mode == "osint":
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
                add_log("Kesimpulan AI selesai")
            except Exception as ex:
                add_log(f"Error: {ex}")
                conclude_btn.disabled = False
            safe_update("conclude:done")

        threading.Thread(target=_worker, daemon=True).start()

    conclude_btn = ft.OutlinedButton(
        "AI Conclusion",
        icon=ft.Icons.AUTO_AWESOME,
        on_click=on_conclude,
        style=ft.ButtonStyle(
            color=MAGENTA,
            side=ft.BorderSide(1, "#e9d5ff"),
            bgcolor="#faf5ff",
            shape=ft.RoundedRectangleBorder(radius=12),
        ),
    )

    search_summary = ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text("Workflow", size=11, color=TEXT_MUTED),
                        ft.Text("Natural Search", size=14, weight=ft.FontWeight.W_600, color=TEXT),
                    ],
                    spacing=3,
                    expand=True,
                ),
                ft.VerticalDivider(width=1, color=BORDER),
                ft.Column(
                    [
                        ft.Text("AI Layer", size=11, color=TEXT_MUTED),
                        ft.Text("Gemini + OSINT", size=14, weight=ft.FontWeight.W_600, color=TEXT),
                    ],
                    spacing=3,
                    expand=True,
                ),
            ],
            spacing=12,
        ),
        bgcolor=CARD_ALT,
        border_radius=16,
        padding=14,
    )

    result_count_block = ft.Container(
        content=ft.Column([num_label, num_slider], spacing=6),
        bgcolor=CARD,
        border_radius=16,
        padding=14,
        border=ft.border.all(1, BORDER),
    )

    enrich_container = ft.Container(
        content=enrich_switch,
        bgcolor=CARD,
        border_radius=16,
        padding=ft.padding.symmetric(horizontal=14, vertical=6),
        border=ft.border.all(1, BORDER),
    )

    left_panel = build_panel(
        "Search Configuration",
        "Set query, search mode, and retrieval filters.",
        ft.Icons.TUNE,
        ft.Column(
            [
                search_summary,
                search_field,
                ft.Column([ft.Text("Mode pencarian", size=11, color=TEXT_MUTED), mode_selector], spacing=8),
                ft.Row([lang_dd, time_dd], spacing=10, wrap=True),
                result_count_block,
                enrich_container,
                search_btn,
                status_text,
            ],
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
        ),
    )
    left_panel.width = 340

    progress_wrap = ft.Container(
        content=progress_bar,
        bgcolor=CARD_ALT,
        border_radius=999,
        padding=2,
        visible=False,
    )

    log_wrap = ft.Container(
        content=ft.Column(
            [
                ft.Text("Activity log", size=11, color=TEXT_MUTED, weight=ft.FontWeight.W_600),
                log_list,
            ],
            spacing=6,
        ),
        bgcolor=CARD,
        border_radius=16,
        padding=12,
        border=ft.border.all(1, BORDER),
    )

    right_panel = build_panel(
        "Results Workspace",
        "Reviewed results, AI summary, and execution log.",
        ft.Icons.DASHBOARD_OUTLINED,
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text("Search results", size=16, weight=ft.FontWeight.W_600, color=TEXT),
                                results_count,
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        conclude_btn,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                progress_wrap,
                results_area,
                osint_panel,
                ai_panel,
                log_wrap,
            ],
            spacing=12,
            expand=True,
        ),
    )
    right_panel.expand = True

    body = ft.Row(
        [left_panel, right_panel],
        spacing=16,
        expand=True,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    page.add(
        ft.Column(
            [
                header,
                ft.Container(content=body, expand=True, padding=20),
            ],
            expand=True,
            spacing=0,
        )
    )


if __name__ == "__main__":
    ft.app(target=main)
