from __future__ import annotations

import re
import uuid
import logging
from datetime import datetime
from pathlib import Path

from .core import Retryable, StopRun, Transfer, choose_transfer, compact
from .windows import credential


def parse_transfer(cells):
    if len(cells) < 9 or not compact(cells[0]).isdigit():
        return None
    try:
        return Transfer(int(compact(cells[0])), cells[1].strip(), cells[3].strip(),
                        int(cells[4].replace(",", "").strip()),
                        int(cells[6].replace(",", "").strip()),
                        datetime.strptime(cells[8].strip(), "%Y-%m-%d %H:%M:%S"))
    except ValueError as exc:
        raise StopRun("전송목록 열 형식이 변경됐습니다. 목록 어댑터를 확인하세요.") from exc


def handle_login_dialog(dialog, blocked):
    # Only this observed routine re-login confirmation is auto-accepted.
    if dialog.type == "confirm" and compact(dialog.message) == "이미로그인되어있습니다.다시접속하시겠습니까?":
        dialog.accept()
    else:
        blocked.append(dialog.type)
        dialog.dismiss()


def visible_text(page, text):
    found = []
    label = re.compile(r"^\s*(?:[•·]\s*)?" + re.escape(text) + r"\s*$")
    for frame in page.frames:
        for locator in frame.get_by_text(label).all():
            if locator.is_visible():
                found.append(locator)
    if len(found) != 1:
        raise StopRun(f"화면 항목을 유일하게 찾지 못했습니다: {text}")
    return found[0]


GRID_CELLS = ".rMateH5__DataGridBaseContentHolder > .rMateH5__DataGridItemRenderer, .rMateH5__DataGridBaseContentHolder > .rMateH5__HtmlItemRenderer"


def group_grid_cells(cells):
    groups = {}
    for c in cells:
        groups.setdefault((c["holder"], c["top"]), []).append(c)
    result = []
    for group in groups.values():
        group.sort(key=lambda c: c["left"])
        if len(group) < 9:
            continue  # Partially rendered boundary row; read on next scroll.
        if any(compact(c["text"]) for c in group[9:]):
            raise StopRun("그리드에 알 수 없는 추가 열이 있습니다.")
        record = parse_transfer([c["text"] for c in group])
        if record:
            result.append((record, group[3]["index"]))
    return result


def rows_on_page(page):
    from playwright.sync_api import Error
    try:
        return _rows_on_page(page)
    except Error as exc:
        if "Execution context was destroyed" in str(exc) or "Frame was detached" in str(exc):
            return []  # Frame navigation in progress; caller waits for new rows.
        raise


def _rows_on_page(page):
    result = []
    frames = [f for f in page.frames if f.name == "body"] or page.frames
    for frame in frames:
        grid = frame.locator(GRID_CELLS)
        if grid.count():
            cells = grid.evaluate_all("""es => es.map((e,index)=>({index,
                holder:e.parentElement.id, top:parseFloat(e.style.top),
                left:parseFloat(e.style.left), text:e.innerText}))""")
            for record, index in group_grid_cells(cells):
                result.append((record, grid.nth(index)))
            continue
        for row in frame.locator("tr").all():
            if not row.is_visible():
                continue
            cells = row.locator(":scope > td").all_inner_texts()
            record = parse_transfer(cells)
            if record:
                result.append((record, row.locator(":scope > td").nth(3)))
    return result


def page_batches(page):
    scrollers = [f.locator('.rMateH5__VBrowserScrollBar') for f in page.frames
                 if f.locator('.rMateH5__VBrowserScrollBar').count()]
    if not scrollers:
        yield rows_on_page(page)
        return
    if len(scrollers) != 1 or scrollers[0].count() != 1:
        raise StopRun("전송목록 스크롤 영역을 유일하게 찾지 못했습니다.")
    scroll = scrollers[0]
    maximum, height = scroll.evaluate('(e)=>[e.scrollHeight-e.clientHeight,e.clientHeight]')
    positions = list(range(0, int(maximum), max(1, int(height * .8)))) + [int(maximum)]
    for position in positions:
        scroll.evaluate('(e,y)=>{e.scrollTop=y}', position)
        page.wait_for_timeout(120)
        yield rows_on_page(page)


def signature(page):
    return tuple(r.number for r, _ in rows_on_page(page))


def advance(page, page_number, next_text, previous_ids=None):
    # Prefer the next numbered page; '다음' commonly advances a page group.
    candidates = []
    for text in (str(page_number + 1), next_text, f"[{next_text}]"):
        for frame in page.frames:
            for link in frame.get_by_role("link", name=text, exact=True).all():
                if link.is_visible() and link.is_enabled() and link.get_attribute("aria-disabled") != "true":
                    candidates.append(link)
        if candidates:
            break
    if not candidates:
        return False
    if len(candidates) != 1:
        raise StopRun("다음 페이지 링크가 여러 개입니다. 사이트 설정 확인이 필요합니다.")
    # The last-page 'next' link may still be enabled but point to itself.
    handler = candidates[0].get_attribute("onclick") or ""
    destination = re.search(r"linkPage\((\d+)\)", handler)
    if destination and int(destination.group(1)) <= page_number:
        return False
    old = set(previous_ids if previous_ids is not None else signature(page))
    candidates[0].click()
    # Poll only until rendered row IDs actually change.
    for _ in range(100):
        current = set(signature(page))
        # Scroll resets before AJAX data arrives. A different viewport of the
        # old page is not evidence that navigation completed.
        if current and current.isdisjoint(old):
            return True
        page.wait_for_timeout(100)
    raise StopRun("페이지 이동 후 목록이 갱신되지 않았습니다.")


def fetch(cfg, day):
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    site = cfg["site"]
    user, password = credential(cfg["credential_name"])
    run_dir = Path(cfg["runtime"]) / "downloads" / str(day) / uuid.uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel=site["channel"], headless=site["headless"])
            context = browser.new_context(accept_downloads=True, viewport={"width":1920,"height":1080})
            page = context.new_page()
            page.set_default_timeout(site["timeout_ms"])
            dialogs = []
            def on_dialog(dialog):
                handle_login_dialog(dialog, dialogs)
            page.on("dialog", on_dialog)
            try:
                # The frameset DOM can be ready before its child frames exist.
                page.goto(site["url"], wait_until="load")
                login = page.frame(name=site["login_frame"])
                if login is None:
                    raise StopRun("로그인 프레임이 변경됐습니다.")
                login.locator(site["username"]).fill(user)
                login.locator(site["password"]).fill(password)
                login.get_by_role("button", name="Login", exact=True).click()
                password = ""
                menu = None
                for _ in range(100):
                    if dialogs:
                        raise StopRun("사이트 로그인 안내 창이 표시됐습니다. 로그인 정보를 직접 확인하세요.")
                    if page.is_closed():
                        raise StopRun("로그인 창이 닫혔습니다.")
                    try:
                        menu = visible_text(page, site["menu"])
                        break
                    except StopRun:
                        page.wait_for_timeout(100)
                if menu is None:
                    raise StopRun("로그인 실패 또는 추가 인증이 필요합니다. 로컬 로그인 정보를 확인하세요.")
                menu.click()
                for _ in range(100):
                    if rows_on_page(page):
                        break
                    page.wait_for_timeout(100)
                all_records = {}
                seen = set()
                total = None
                for frame in page.frames:
                    if not frame.locator("body").count():
                        continue
                    match = re.search(r"([\d,]+)\s*개의\s*자료", frame.locator("body").inner_text())
                    if match:
                        total = int(match.group(1).replace(",", ""))
                for n in range(1, site["max_pages"] + 1):
                    current_by_id = {}
                    for batch in page_batches(page):
                        current_by_id.update({r.number: (r, locator) for r, locator in batch})
                    current = list(current_by_id.values())
                    ids = tuple(r.number for r, _ in current)
                    if ids in seen:
                        raise StopRun("전송목록 페이지가 반복되어 선택을 중단했습니다.")
                    seen.add(ids)
                    for record, _ in current:
                        all_records[record.number] = record
                    if n % 20 == 0:
                        logging.info("site pages=%s records=%s", n, len(all_records))
                    if not advance(page, n, site["next_text"], current_by_id):
                        break
                else:
                    raise StopRun("페이지 탐색 상한에 도달했습니다. 최신 항목을 확정할 수 없습니다.")
                if total is not None and len(all_records) != total:
                    raise StopRun("조회 건수와 탐색한 건수가 다릅니다. 페이지 탐색 검증이 필요합니다.")
                logging.info("site scan complete pages=%s records=%s expected=%s", n, len(all_records), total)
                selected = choose_transfer(list(all_records.values()), day)
                logging.info("site selected transfer=%s date=%s input_count=%s", selected.number, day, selected.count)
                # Reopen list, then locate exactly the selected transfer ID.
                visible_text(page, site["menu"]).click()
                page.wait_for_timeout(500)
                selected_row = None
                for n in range(1, site["max_pages"] + 1):
                    scanned_ids = set()
                    for batch in page_batches(page):
                        scanned_ids.update(record.number for record, _ in batch)
                        for record, row in batch:
                            if record.number == selected.number:
                                if record != selected:
                                    raise Retryable("탐색 중 전송 항목이 변경됐습니다.")
                                selected_row = row
                                break
                        if selected_row is not None:
                            break
                    if selected_row is not None or not advance(page, n, site["next_text"], scanned_ids):
                        break
                if selected_row is None:
                    raise Retryable("선택한 전송 항목이 목록에서 변경됐습니다.")
                downloads = []
                def on_download(download):
                    downloads.append(download)
                page.on("download", on_download)
                context.on("page", lambda popup: popup.on("download", on_download))
                selected_row.click()
                for _ in range(600):
                    if downloads:
                        break
                    page.wait_for_timeout(100)
                if not downloads:
                    raise Retryable("파일명 클릭 후 다운로드가 시작되지 않았습니다.")
                download = downloads[0]
                if download.failure():
                    raise Retryable("다운로드에 실패했습니다.")
                name = Path(download.suggested_filename).name
                if Path(name).suffix.lower() not in (".xlsx", ".xlsm", ".xls"):
                    raise StopRun("다운로드가 Excel 파일 형식이 아닙니다.")
                output = run_dir / name
                download.save_as(output)
                if output.stat().st_size == 0:
                    raise Retryable("다운로드 파일이 비어 있습니다.")
                return selected, output
            finally:
                context.close()
                browser.close()
    except PlaywrightTimeout as exc:
        raise Retryable("사이트 응답 시간이 초과됐습니다.") from exc
