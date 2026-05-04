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
from randSearch import run_scrape, normalize_keyword_list

_session_results = {}


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

    def run_on_ui_thread(fn, *args, **kwargs):
        try:
            if hasattr(page, "call_from_thread"):
                page.call_from_thread(lambda: fn(*args, **kwargs))
                return
            if hasattr(page, "invoke_later"):
                page.invoke_later(lambda: fn(*args, **kwargs))
                return
        except Exception as ex:
            print(f"[GUI] ui dispatch fallback: {ex}")
        fn(*args, **kwargs)

    def safe_update(context: str = "ui"):
        try:
            page.update()
        except Exception as ex:
            print(f"[GUI] page.update() failed in {context}: {ex}")

    def card(content, expand=False, padding=18):
        return ft.Container(
            content=content,
            bgcolor=SURFACE,
            border_radius=18,
            padding=padding,
            border=ft.border.all(1, BORDER),
            expand=expand,
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
                            ft.Text("Desktop Workspace", size=13, weight=ft.FontWeight.W_600, color=ACCENT),
                        ],
                        spacing=2,
                        horizontal_alignment=ft.CrossAxisAlignment.END,
                    ),
                    bgcolor=CARD,
                    border_radius=14,
                    padding=ft.padding.symmetric(horizontal=16, vertical=12),
                    border=ft.border.all(1, BORDER),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=SURFACE,
        padding=ft.padding.symmetric(horizontal=24, vertical=20),
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
        content_padding=ft.padding.symmetric(horizontal=16, vertical=16),
    )

    location_field = ft.TextField(
        hint_text="Lokasi (kota/negara) - Opsional",
        border_color=BORDER,
        focused_border_color=ACCENT,
        color=TEXT,
        hint_style=ft.TextStyle(color=TEXT_SOFT, size=13),
        bgcolor=CARD,
        border_radius=14,
        prefix_icon=ft.Icons.LOCATION_ON,
        text_size=14,
        content_padding=ft.padding.symmetric(horizontal=16, vertical=12),
        visible=False,
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
        safe_update("slider")

    num_slider.on_change = slider_changed

    enrich_switch = ft.Switch(label="Ambil tanggal asli", value=True, active_color=ACCENT)

    def mode_label(text: str):
        return ft.Container(
            content=ft.Text(text, no_wrap=True, size=12, weight=ft.FontWeight.W_600),
            width=58,
        )

    def mode_changed(e):
        nonlocal current_mode
        sel = mode_selector.selected
        current_mode = sel[0] if isinstance(sel, list) and sel else (list(sel)[0] if sel else "text")
        is_osint = current_mode == "osint"
        lang_dd.visible = not is_osint
        time_dd.visible = not is_osint
        count_box.visible = not is_osint
        enrich_box.visible = not is_osint
        location_field.visible = is_osint
        safe_update("mode")

    mode_selector = ft.SegmentedButton(
        segments=[
            ft.Segment(value="text", label=mode_label("Text")),
            ft.Segment(value="news", label=mode_label("News")),
            ft.Segment(value="stock", label=mode_label("Stock")),
            ft.Segment(value="osint", label=mode_label("OSINT")),
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
    progress_wrap = ft.Container(
        content=progress_bar,
        bgcolor=CARD_ALT,
        border_radius=999,
        padding=2,
        visible=False,
    )
    status_text = ft.Text("", size=11, color=ACCENT, italic=True)

    log_list = ft.ListView(spacing=4, auto_scroll=True, height=120)

    def add_log(msg: str):
        log_list.controls.append(ft.Text(msg, size=11, color=TEXT_MUTED, selectable=True))
        safe_update("log")

    results_count = ft.Text("Belum ada hasil", size=12, color=TEXT_MUTED)
    results_column = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

    def build_empty_results():
        return ft.Container(
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
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            expand=True,
        )

    results_area = ft.Container(
        content=build_empty_results(),
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
            bgcolor=SURFACE,
            border_radius=16,
            padding=14,
            border=ft.border.all(1, BORDER),
        )

    ai_content = ft.Text("", size=12, color=TEXT, selectable=True)
    ai_scroll = ft.ListView(
        controls=[ai_content],
        spacing=0,
        auto_scroll=False,
        expand=True,
    )
    ai_panel = ft.Container(
        content=ft.Column(
            [
                ft.Text("AI Insight", size=14, weight=ft.FontWeight.BOLD, color=ACCENT),
                ft.Container(
                    content=ai_scroll,
                    height=240,
                    border_radius=10,
                ),
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
    osint_scroll = ft.ListView(
        controls=[osint_content],
        spacing=0,
        auto_scroll=False,
        height=280,
    )
    osint_panel = ft.Container(
        content=ft.Column(
            [
                ft.Text("OSINT Entities", size=14, weight=ft.FontWeight.BOLD, color=WARNING),
                osint_scroll,
            ],
            spacing=6,
        ),
        bgcolor=CARD,
        border_radius=16,
        padding=16,
        border=ft.border.all(1, BORDER),
        visible=False,
    )

    def show_results_empty():
        results_area.content = build_empty_results()

    def show_results_cards():
        results_area.content = ft.Container(content=results_column, expand=True)

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
        results_count.value = "Menunggu hasil..."
        show_results_empty()
        ai_panel.visible = False
        osint_panel.visible = False
        osint_content.controls.clear()
        safe_update("search:start")

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

        # For OSINT, ensure raw input is always the primary keyword
        keywords = normalize_keyword_list(query, keywords, mode)

        add_log(f"Keywords: {keywords}")
        add_log(f"Bahasa={lang} | Mode={mode} | Waktu={tr}")

        def _on_log(msg):
            run_on_ui_thread(add_log, msg)

        def _on_progress(pct):
            def _apply():
                progress_bar.value = pct
                status_text.value = f"Progress {int(pct * 100)}%"
                safe_update("progress")

            run_on_ui_thread(_apply)

        def _on_complete(data):
            def _apply():
                nonlocal search_running
                try:
                    _session_results[page.session.id] = data.get("results", [])
                    results = data.get("results", [])
                    summary = data.get("ai_summary", "")
                    print(f"[GUI] Rendering {len(results)} results")

                    results_column.controls.clear()
                    results_count.value = f"{len(results)} hasil ditemukan"

                    if results:
                        for i, item in enumerate(results):
                            results_column.controls.append(build_result_card(item, i))
                        show_results_cards()
                    else:
                        show_results_empty()

                    if mode == "osint":
                        # Aggregate entities from per-result osint_entities
                        all_platforms = set()
                        all_usernames = set()
                        all_profile_urls = set()
                        all_emails = set()
                        all_phones = set()
                        all_links = set()

                        for r in results:
                            ent = r.get("osint_entities") or {}
                            for p in ent.get("platforms", []):
                                all_platforms.add(p)
                            plat = r.get("osint_platform", "")
                            if plat and plat != "unknown":
                                all_platforms.add(plat)
                            for u in ent.get("usernames", []):
                                all_usernames.add(u)
                            for pu in ent.get("profile_urls", []):
                                all_profile_urls.add(pu)
                            for em in ent.get("emails", []):
                                all_emails.add(em)
                            for ph in ent.get("phones", []):
                                all_phones.add(ph)
                            for lk in ent.get("links", []):
                                all_links.add(lk)

                        osint_content.controls.clear()

                        if all_platforms:
                            osint_content.controls.append(
                                ft.Text("Platforms", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD)
                            )
                            for value in sorted(all_platforms):
                                osint_content.controls.append(
                                    ft.Text(f"  • {value.title()}", size=11, color=TEXT, selectable=True)
                                )

                        if all_usernames:
                            osint_content.controls.append(
                                ft.Text("Usernames", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD)
                            )
                            for value in sorted(all_usernames):
                                osint_content.controls.append(
                                    ft.Text(f"  • {value}", size=11, color=TEXT, selectable=True)
                                )

                        if all_profile_urls:
                            osint_content.controls.append(
                                ft.Text("Profile URLs", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD)
                            )
                            for value in sorted(all_profile_urls)[:8]:
                                osint_content.controls.append(
                                    ft.Text(f"  • {value}", size=11, color=ACCENT, selectable=True)
                                )

                        if all_emails:
                            osint_content.controls.append(
                                ft.Text("Emails", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD)
                            )
                            for value in sorted(all_emails):
                                osint_content.controls.append(
                                    ft.Text(f"  • {value}", size=11, color=TEXT, selectable=True)
                                )

                        if all_phones:
                            osint_content.controls.append(
                                ft.Text("Phones", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD)
                            )
                            for value in sorted(all_phones):
                                osint_content.controls.append(
                                    ft.Text(f"  • {value}", size=11, color=TEXT, selectable=True)
                                )

                        if all_links:
                            osint_content.controls.append(
                                ft.Text("Key Footprints", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD)
                            )
                            for value in sorted(all_links)[:10]:
                                osint_content.controls.append(
                                    ft.Text(f"  • {value}", size=11, color=ACCENT, selectable=True)
                                )

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
                except Exception as ex:
                    print(f"[GUI] render failed: {ex}")
                    add_log(f"Error render hasil: {ex}")
                    show_results_empty()
                    osint_panel.visible = False
                    ai_panel.visible = False
                finally:
                    progress_bar.visible = False
                    progress_wrap.visible = False
                    status_text.value = "Selesai"
                    search_btn.disabled = False
                    search_running = False
                    safe_update("complete")

            run_on_ui_thread(_apply)

        def _worker():
            run_scrape(
                keywords=keywords,
                language=lang,
                time_range=tr,
                num_results=int(num_slider.value),
                search_mode=mode,
                enrich_dates=enrich_switch.value,
                location=loc,
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
                    run_on_ui_thread(add_log, "Tidak ada data untuk disimpulkan")

                    def _restore():
                        conclude_btn.disabled = False
                        safe_update("conclude:no_results")

                    run_on_ui_thread(_restore)
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

                def _apply():
                    ai_content.value = summary
                    ai_panel.visible = True
                    conclude_btn.disabled = False
                    add_log("Kesimpulan AI selesai")
                    safe_update("conclude:done")

                run_on_ui_thread(_apply)
            except Exception as ex:
                def _fail():
                    add_log(f"Error: {ex}")
                    conclude_btn.disabled = False
                    safe_update("conclude:error")

                run_on_ui_thread(_fail)

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

    count_box = ft.Container(
        content=ft.Column([num_label, num_slider], spacing=6),
        bgcolor=CARD,
        border_radius=16,
        padding=14,
        border=ft.border.all(1, BORDER),
    )

    enrich_box = ft.Container(
        content=enrich_switch,
        bgcolor=CARD,
        border_radius=16,
        padding=ft.padding.symmetric(horizontal=14, vertical=6),
        border=ft.border.all(1, BORDER),
    )

    left_panel = card(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(ft.Icons.TUNE, color=ACCENT, size=18),
                            bgcolor=ACCENT_SOFT,
                            border_radius=12,
                            padding=10,
                        ),
                        ft.Column(
                            [
                                ft.Text("Search Configuration", size=16, weight=ft.FontWeight.W_600, color=TEXT),
                                ft.Text("Set query, mode, and retrieval filters.", size=11, color=TEXT_MUTED),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                    ],
                    spacing=12,
                ),
                ft.Container(
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
                ),
                search_field,
                location_field,
                ft.Column(
                    [
                        ft.Text("Mode pencarian", size=11, color=TEXT_MUTED),
                        mode_selector,
                    ],
                    spacing=8,
                ),
                ft.Row([lang_dd, time_dd], spacing=10, wrap=True),
                count_box,
                enrich_box,
                search_btn,
                status_text,
            ],
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=20,
    )
    left_panel.width = 340

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

    results_section = ft.Column(
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
    )

    right_panel = card(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(ft.Icons.DASHBOARD_OUTLINED, color=ACCENT, size=18),
                            bgcolor=ACCENT_SOFT,
                            border_radius=12,
                            padding=10,
                        ),
                        ft.Column(
                            [
                                ft.Text("Results Workspace", size=16, weight=ft.FontWeight.W_600, color=TEXT),
                                ft.Text("Reviewed results, AI summary, and execution log.", size=11, color=TEXT_MUTED),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                    ],
                    spacing=12,
                ),
                results_section,
            ],
            spacing=16,
            expand=True,
        ),
        expand=True,
        padding=20,
    )

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
            spacing=0,
            expand=True,
        )
    )


if __name__ == "__main__":
    ft.app(target=main)
