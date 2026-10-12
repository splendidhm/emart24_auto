"""Import every successful transfer; ambiguous changes require review."""
from .core import StopRun
from .importer import import_file
from .workbooks import read_source, read_xlsx


def process_batches(cfg, batches, day, dry_run=False):
    results=[]
    errors=[]
    for item, source in batches:
        try:
            _,rows=read_source(source,cfg['source_headers'])
            if len(rows)!=item.count:
                raise StopRun('전송 입력 수량과 원본 행 수가 다릅니다.')
            _,_,existing=read_xlsx(cfg['target'],cfg['sheet'])
            # This is a conservative collision alarm, not an approved update key.
            # Never infer permission to overwrite a quantity from a matching key.
            def key(row):
                return tuple(row[i] for i in (0,1,3,4,6,14))
            by_key={}
            for row in existing:
                by_key.setdefault(key(row),set()).add(tuple(row))
            for row in rows:
                if key(row) in by_key and tuple(row) not in by_key[key(row)]:
                    raise StopRun('기존 주문과 식별 항목은 같지만 내용이 다릅니다. 수정 판별 기준 확인 필요')
            result=import_file(cfg,source,day,item.number,dry_run=dry_run)
            results.append(dict(transfer=item.number,**result))
        except StopRun as exc:
            errors.append({'transfer':item.number,'reason':str(exc)})
    return {'date':str(day),'dry_run':dry_run,'results':results,'errors':errors}
