# 이마트24 주문 자동화

평일 10:30 CJ대한통운 주문 파일을 받아 재고관리 DB에 누적합니다. 자료 미등록·파일 사용 중이면 11:00까지 재시도합니다.

- 실행 규칙: [AGENTS.md](AGENTS.md)
- 설치·운영·복구: [docs/architecture.md](docs/architecture.md)
- 설정: [config.json](config.json)
- 확인한 결과와 남은 연결 작업: [docs/validation.md](docs/validation.md)

```powershell
.\.venv\Scripts\python.exe -m emart24 credentials
.\.venv\Scripts\python.exe -m emart24 run --date 2026-10-06 --source '원본.xlsx' --dry-run
.\.venv\Scripts\python.exe -m emart24 verify-site --date 2026-10-06
.\.venv\Scripts\python.exe -m emart24 run --date 2026-10-06
.\scripts\register-task.ps1
```

사이트 로그인 이후 목록·다운로드 검증과 운영 파일 첫 처리 확인을 마친 뒤에만 예약 작업을 등록합니다. 비밀번호는 로컬 등록 창에서 입력합니다.
