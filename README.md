# 이마트24 주문 자동화

월~토 10:40부터 11:10까지 5분 간격으로 CJ대한통운 당일 주문 파일을 받아 재고관리 DB에 누적합니다. 성공 후에도 계속 조회하며 유효한 본 주문·추가 전송을 모두 확인합니다. 과거 날짜는 자동 소급하지 않습니다. 수정본으로 의심되는 자료는 확인 대상으로 남기며 자동 덮어쓰기는 하지 않습니다.

- 실행 규칙: [AGENTS.md](AGENTS.md)
- 설치·운영·복구: [docs/architecture.md](docs/architecture.md)
- 설정: [config.json](config.json)
- 확인한 결과와 남은 연결 작업: [docs/validation.md](docs/validation.md)

다른 PC에서는 설치 후 `configure-target.cmd`를 더블클릭해 대상 파일이 있는 폴더를 선택하세요. 파일명은 `재고관리_이마트24_26년(신제품 추가).xlsx`로 고정됩니다. 선택한 폴더는 이 PC의 `config.local.json`에 저장되며 모든 실행에서 공통으로 사용합니다. 이 설정 파일은 Git에 올라가지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m emart24 configure --target-dir 'D:\업무자료\이마트24'
.\.venv\Scripts\python.exe -m emart24 show-config
.\.venv\Scripts\python.exe -m emart24 credentials
.\.venv\Scripts\python.exe -m emart24 run --date 2026-10-06 --source '원본.xlsx' --dry-run
.\.venv\Scripts\python.exe -m emart24 verify-site --date 2026-10-06
.\.venv\Scripts\python.exe -m emart24 run --date 2026-10-06
.\scripts\register-task.ps1
```

사이트 로그인 이후 목록·다운로드 검증과 운영 파일 첫 처리 확인을 마친 뒤에만 예약 작업을 등록합니다. 비밀번호는 로컬 등록 창에서 입력합니다.
