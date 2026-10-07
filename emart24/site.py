from __future__ import annotations

import re
import uuid
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


def visible_text(page, text):
    found = []
    for frame in page.frames:
        for locator in frame.get_by_text(text, exact=True).all():
            if locator.is_visible():
                found.append(locator)
    if len(found) != 1:
        raise StopRun(f"화면 항목을 유일하게 찾지 못했습니다: {text}")
    return found[0]


def rows_on_page(page):
    result = []
    for frame in page.frames:
        for row in frame.locator("tr").all():
            if not row.is_visible():
                continue
            cells = row.locator(":scope > td").all_inner_texts()
            record = parse_transfer(cells)
            if record:
                result.append((record, row))
    return result


def signature(page):
    return tuple(r.number for r, _ in rows_on_page(page))


def advance(page, page_number, next_text):
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
    old = signature(page)
    candidates[0].click()
    # Poll only until rendered row IDs actually change.
    for _ in range(100):
        if signature(page) and signature(page) != old:
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
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            page.set_default_timeout(site["timeout_ms"])
            dialogs = []
            def on_dialog(dialog):
                dialogs.append(dialog.type)
                dialog.dismiss()
            page.on("dialog", on_dialog)
            try:
                page.goto(site["url"], wait_until="domcontentloaded")
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
                    current = rows_on_page(page)
                    ids = tuple(r.number for r, _ in current)
                    if ids in seen:
                        raise StopRun("전송목록 페이지가 반복되어 선택을 중단했습니다.")
                    seen.add(ids)
                    for record, _ in current:
                        all_records[record.number] = record
                    if not advance(page, n, site["next_text"]):
                        break
                else:
                    raise StopRun("페이지 탐색 상한에 도달했습니다. 최신 항목을 확정할 수 없습니다.")
                if total is not None and len(all_records) != total:
                    raise StopRun("조회 건수와 탐색한 건수가 다릅니다. 페이지 탐색 검증이 필요합니다.")
                selected = choose_transfer(list(all_records.values()), day)
                # Reopen list, then locate exactly the selected transfer ID.
                visible_text(page, site["menu"]).click()
                page.wait_for_timeout(500)
                selected_row = None
                for n in range(1, site["max_pages"] + 1):
                    for record, row in rows_on_page(page):
                        if record.number == selected.number:
                            if record != selected:
                                raise Retryable("탐색 중 전송 항목이 변경됐습니다.")
                            selected_row = row
                            break
                    if selected_row is not None or not advance(page, n, site["next_text"]):
                        break
                if selected_row is None:
                    raise Retryable("선택한 전송 항목이 목록에서 변경됐습니다.")
                with page.expect_download(timeout=60000) as event:
                    selected_row.locator(":scope > td").nth(1).click()
                download = event.value
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
