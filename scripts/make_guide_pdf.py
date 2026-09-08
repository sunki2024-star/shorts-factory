"""Print each guide to A4. Chromium is what rendered the page in the first
place, so the PDF is the same layout rather than a re-typeset approximation."""
import os, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
# The built pages live outside the repo; point this at wherever they are.
SRC = Path(os.environ.get("GUIDE_SRC", HERE.parent / "docs" / "_build"))
JOBS = [
    ("guide-mac.html",       "쇼츠-만들기-맥.pdf",       "쇼츠 만들기 · 맥"),
    ("guide-win.html",       "쇼츠-만들기-윈도우.pdf",   "쇼츠 만들기 · 윈도우"),
    ("guide-anychurch.html", "우리교회-쇼츠-만들기.pdf", "우리 교회 설교 쇼츠 만들기"),
]

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium",
                            args=["--no-sandbox"])
    for src, out, title in JOBS:
        page = b.new_page()
        # A full HTML document, so the head/link tags are honoured.
        html = (SRC / src).read_text(encoding="utf-8")
        page.set_content(f"<!doctype html><html lang=ko><head><meta charset=utf-8>{html}",
                         wait_until="networkidle")
        try:
            page.wait_for_function("document.fonts.ready.then(()=>true)", timeout=20000)
        except Exception:
            print(f"  {src}: 폰트 대기 실패 — 그대로 진행")
        time.sleep(1.0)

        # 종이(PDF)에서 명령어 줄이 화면 폭에 안 맞아 줄바꿈되면, 그 줄을
        # 그대로 긁어 터미널에 붙였을 때 진짜 개행 문자가 끼어들어가 명령어가
        # 반토막나 실행된다 (실제로 이렇게 실패한 사례가 있었음). 인쇄용
        # 본문 폭(A4 - 좌우 여백)을 뷰포트로 잡고 명령어 글자 크기를 한 줄에
        # 들어갈 때까지 줄여서, 어떤 명령어도 PDF 안에서 줄바꿈되지 않게 한다.
        content_w_px = round((210 - 14 - 14) / 25.4 * 96)  # A4 폭 - 좌우 14mm 여백
        page.set_viewport_size({"width": content_w_px, "height": 1200})
        page.emulate_media(media="print")
        wrapped = page.evaluate(
            """() => {
                const fixed = [];
                document.querySelectorAll('.cmd code, .out code').forEach((el, i) => {
                    el.style.whiteSpace = 'pre';  // 줄바꿈 금지 상태로 실제 폭을 측정
                    let size = parseFloat(getComputedStyle(el).fontSize);
                    const floor = 6.5;
                    let shrunk = false;
                    while (el.scrollWidth > el.clientWidth + 1 && size > floor) {
                        size -= 0.25;
                        el.style.fontSize = size + 'px';
                        shrunk = true;
                    }
                    if (el.scrollWidth > el.clientWidth + 1) {
                        fixed.push({i, ok: false, text: el.textContent.slice(0, 40)});
                    } else if (shrunk) {
                        fixed.push({i, ok: true, size});
                    }
                });
                return fixed;
            }"""
        )
        for w in wrapped:
            if w.get("ok") is False:
                print(f"  ⚠ {src}: 줄여도 한 줄에 안 들어가는 명령어 — {w['text']}…")

        page.pdf(path=str(HERE.parent / "docs" / "pdf" / out), format="A4",
                 print_background=True,
                 margin={"top": "16mm", "bottom": "18mm", "left": "14mm", "right": "14mm"},
                 display_header_footer=True,
                 header_template="<div></div>",
                 footer_template=(
                     '<div style="width:100%;font-size:8pt;color:#8C8474;'
                     'font-family:sans-serif;padding:0 14mm;display:flex;'
                     'justify-content:space-between">'
                     f'<span>{title}</span>'
                     '<span class="pageNumber"></span></div>'))
        page.close()
        print(f"  wrote docs/pdf/{out}")
    b.close()
