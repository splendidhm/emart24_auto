"""Offline Edge check: virtual-grid DOM reordering must not change the file."""
from html import escape
from playwright.sync_api import sync_playwright
from emart24.site import rows_on_page


def main():
    cells=[]
    for number, filename, top in [(1,'requested.xlsx',0),(2,'requested.xlsx',30)]:
        values=[str(number),'10월 09일 7F 주문정보(7F 이마트24) 전송',
                '주문정보',filename,'78','0','0','0','2026-10-09 10:30:00']
        cells.extend(f'<span class="rMateH5__DataGridItemRenderer" style="top: {top}px; left: {i*60}px;">{escape(v)}</span>'
                     for i,v in enumerate(values))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        try:
            page=browser.new_page()
            page.set_content('<div id="grid" class="rMateH5__DataGridBaseContentHolder">'+''.join(cells)+'</div>')
            records=rows_on_page(page)
            selected=next(locator for record,locator in records if record.number==1)
            page.evaluate("""()=>{const g=document.querySelector('#grid');
                const cell=[...g.children].find(e=>e.textContent==='requested.xlsx');
                g.appendChild(cell);g.addEventListener('click',e=>window.clicked=e.target.style.top);} """)
            selected.click()
            assert page.evaluate('window.clicked')=='0px'
            print('PASS: selected file survives virtual-grid DOM reorder')
        finally:
            browser.close()


if __name__=='__main__':
    main()
