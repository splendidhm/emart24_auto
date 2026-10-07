# 이마트24 발주데이터 자동화 인수인계

작성일: 2026-10-07 (한국시간)

## 현재 상태

추가 변경: 다른 Windows PC를 위한 전역 대상 경로 설정을 구현했다. `configure-target.cmd`로 폴더만 선택하며 파일명은 `core.TARGET_FILENAME`에 고정된다. PC별 `config.local.json`은 Git 제외이며 수동·미리보기·예약 실행 모두 같은 경로 해석기를 사용한다. 경로 변경 시 사이트 검증을 다시 수행해야 한다. 현재 PC는 기존 대상 폴더로 설정을 이관한다.

**프로토타입 코드·운영 문서 구현 및 로컬 Excel 파일 처리 검증 완료. 실제 사이트 로그인 이후 연동 검증과 정기 실행 활성화는 미완료.**

- 저장소: https://github.com/splendidhm/emart24_auto.git
- 전달 브랜치: `main`
- 요청 커밋 메시지: `발주데이터 자동화 프로토`
- 실행 환경: Windows 사용자 로그인 상태, Microsoft Excel 및 Edge 설치 필요.
- 작업 폴더: `C:\Users\케이지에프앤비\Documents\ChatGPT\이마트24 매출 데이터 엑셀 자동화`

## 확정된 업무 규칙

1. 평일 월~금 한국시간 10:30 시작. 공휴일도 실행하며, 자료 미등록·파일 사용 중 등 일시적 실패는 5분 간격으로 11:00까지 재시도한다.
2. CJ대한통운 사이트 로그인 → 정보관리 → TASA 전송리스트로 이동한다.
3. 제목의 월·일과 등록일이 처리 날짜에 해당하는 `OO월 OO일 7F 주문정보(7F 이마트24) 전송`을 찾는다. 입력 > 0, 오류 = 0 중 최신 등록 항목 한 건을 선택한다. 동시각이면 큰 전송번호가 우선이다.
4. 다운로드 파일의 첫 표시 시트(샘플: `붙여넣기`)에서 A~O 2행부터 마지막 실제 데이터 행까지 읽는다.
5. **열 위치 그대로 A→A … O→O 값만 적재한다. F/H를 교환하지 않는다.** 사용자가 위치 그대로 붙여넣기를 명시했다. 현재 첨부 파일 헤더는 F=분류명, H=상품명이며 설정도 해당 첨부 파일을 기준으로 한다. 향후 수정본 헤더를 받으면 기준 헤더만 검토한다.
6. 대상 `DB`의 A~O 마지막 데이터 아래에 추가하고, 이전 행 서식을 유지하며 P~T 수식을 새 행까지 확장한다. U열과 기존 시트는 보존한다.
7. 중복 전체 일치 시 건너뛰고 일부 중복·당일 수정본·처리 이력 불일치는 중단한다. 정상 원본의 반복 행은 삭제하지 않는다.

정확한 대상 경로와 상세 규칙은 `config.json` 및 `AGENTS.md`에 있다. 대상 확장자는 `.xlsx`다.

## 구현된 구성

| 경로 | 역할 |
|---|---|
| `emart24/__main__.py` | CLI, 예약 시간 제한, 재시도, 로그, 등록 전 준비 검사 |
| `emart24/site.py` | Playwright 로그인, HTML 전송목록·페이지 탐색, 다운로드 |
| `emart24/core.py` | 날짜·제목 선택, 값 정규화, 지문, 중복 판단 |
| `emart24/workbooks.py` | 원본 읽기·양식 검증, Excel COM 편집, 수식 검증 |
| `emart24/importer.py`, `emart24/ledger.py` | 백업·저장·교체·SQLite 이력과 중단 복구 |
| `emart24/windows.py` | 실행/파일 잠금, Windows 자격 증명, 파일 교체, PC 알림 |
| `scripts/`, `register-credentials.cmd` | 환경 설치, 작업 스케줄러 등록, 알림, 로컬 로그인 정보 입력 |
| `tests/` | 업무 규칙 단위 테스트, 실제 Excel 복사본 통합 테스트 |
| `docs/architecture.md`, `docs/validation.md` | 설치·운영·복구 절차와 검증 결과 |

Python 3.12 환경에 Playwright 1.63.0, pywin32 312, openpyxl 3.1.5를 사용했다. openpyxl은 읽기 전용이며 실제 저장은 Excel COM을 사용한다. 현재 `.venv`는 번들 Python의 패키지를 참조해 만들어졌으므로 다른 PC에는 복사하지 말고 `scripts/setup.ps1`로 다시 설치한다.

## 검증 결과와 운영 파일 상태

- 단위 테스트 **12개 통과**: 선택 규칙, 시간 경계, 반복 행, 코드 문자열, 목록 파싱, 수정본, 저장 전후 중단 복구, 미리보기 이력 무변경.
- 실제 Excel 복사본에 시험용 **2행 적재 성공**. P~T 수식·계산, 문자열 앞자리 0과 수식 모양 문자열, 파일 잠금, 백업, 교체 실패 후 복구, 재실행 중복 방지 확인.
- 기존 **26개 시트**의 기존 셀 값·수식·숫자 표시 형식 보존 확인. 모든 개체의 외관·외부 링크 갱신까지 검증한 것은 아니다.
- 통합 테스트 중 운영 파일의 SHA-256이 그대로 유지됨을 확인했다.
- 첨부 `7F_자동전환양식_ver_4_20261006 (2).xlsx`의 **73행은 이미 운영 DB에 존재**했다. 미리보기 및 실제 로컬 원본 실행이 `already_present`로 끝났다. 운영 파일에 추가/저장하지 않고 로컬 SQLite에 `existing` 이력만 기록했다.
- 보고서: `runtime/validation/70b2f6cb87034082992c1930ebb0acd1/report.json` (로컬 전용, Git 제외).
- Python 컴파일, PowerShell 구문 검사, Git 공백 오류 검사 통과.

## 다음 담당자가 이어서 할 일

1. `AGENTS.md`, 본 문서, `docs/architecture.md`를 읽는다. 새 PC에서는 설치 후 `configure-target.cmd`로 대상 폴더를 먼저 선택한다. 로그인 정보 등록 여부는 현재 사용자 Windows 세션에서 확인한다. 이전 작업 시 미등록이었으며 이후 등록됐다고 가정하지 않는다.
2. 사용자에게 `register-credentials.cmd`를 실행해 로컬 창에 ID/비밀번호를 입력하도록 안내한다. 자격 증명 이름은 `Emart24/CJLogistics`다. 채팅·커맨드 인수·설정 파일에 비밀번호를 넣지 않는다.
3. 실제 존재하는 날짜로 `verify-site`를 실행한다. 현재 로그인 프레임 `topFrame`, 입력 필드 `#userId`, `#passwd`, Login 버튼까지만 실제 화면 확인을 마쳤다.
4. 인증 이후 목록 DOM과 페이지 탐색, 제목 클릭 다운로드를 검증하고 필요하면 `site.py`를 조정한다. 현재 어댑터는 첨부 화면의 9개 열 순서(등록일 index 8)와 HTML 테이블을 가정한다. ActiveX 전용 화면이면 별도 대응이 필요하다.
5. `verify-site` 성공 후 필요 날짜를 미리보기하고 운영 실행한다. 이미 들어간 10월 6일 자료를 다시 추가하지 않는다. 다른 PC에서는 로컬 `runtime` 이력이 없으므로 기존 DB 중복 확인을 반드시 거친다.
6. `check-ready` 통과 후 `scripts/register-task.ps1`로 `Emart24-CJ-DailyImport`를 등록한다. 등록 결과·다음 실행 시각·사용자 로그인 조건을 확인한다. 현재는 등록되지 않았다.
7. 첫 예약 실행 결과를 확인하고 `docs/validation.md`와 본 문서를 갱신한다. 기능 변경 시 `AGENTS.md`, 아키텍처 문서, 관련 테스트도 같이 갱신한다.

```powershell
# 프로젝트 폴더에서 실행
.\.venv\Scripts\python.exe -m emart24 configure
.\.venv\Scripts\python.exe -m emart24 show-config
.\.venv\Scripts\python.exe -m emart24 credentials
.\.venv\Scripts\python.exe -m emart24 verify-site --date 2026-10-06
.\.venv\Scripts\python.exe -m emart24 run --date 2026-10-06 --dry-run
.\.venv\Scripts\python.exe -m emart24 run --date 2026-10-06
.\.venv\Scripts\python.exe -m emart24 check-ready
.\scripts\register-task.ps1

# 테스트
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m tests.integration_excel '원본 파일 절대 경로'
```

위 날짜는 검증에 사용한 예시다. 과거 날짜 재실행은 명시적으로 선택하고 실제 일일 실행은 해당 일자를 사용한다. Excel 통합 테스트는 원본 샘플이 운영 DB에 이미 존재하는 상태를 전제로 한다.

## 발견한 제약과 주의점

- 일반 `os.replace`는 사용 중인 Windows 보호 핸들과 충돌했다. **`ReplaceFileW`를 사용하는 구현을 유지**한다. 테스트에서 보호 핸들을 유지한 교체를 확인했다.
- Excel COM은 격리된 실행 환경에서 서버 시작 오류가 발생했다. 사용자 세션에서 실행한 복사본 테스트는 통과했다. 사용자의 기존 Excel 프로세스를 일괄 종료하지 않는다.
- 첨부 원본에 잘못된 숨김 시트 관계가 있어 openpyxl 경고가 나타난다. 표시 시트 읽기는 통과했고 원본을 복구 저장하지 않았다.
- `.xls` 읽기 경로는 구현됐지만 실제 `.xls` 샘플로 검증하지 않았다.
- 로그인 이후 사이트 연동과 정기 운영이 완료됐다고 보고하지 않는다. PC 로그아웃/종료 상태의 무인 Office 실행은 지원하지 않는다.
- `runtime/`에는 백업, 다운로드, SQLite, 로그, 시험 파일이 있다. 자동 삭제하지 않으며, 중단 이력은 파일 해시와 함께 검토한다.
- Git에는 소스·설정·문서·테스트만 포함한다. `.venv`, `runtime`, Excel 파일, `config.local.json`, 비밀번호는 포함하지 않는다.

## 인수인계 완료 기준

실제 계정으로 다운로드 검증 → 운영 DB에 정확히 한 번 반영 또는 기적재 확인 → 예약 작업 등록 확인 → 첫 평일 예약 실행 확인까지 마쳐야 운영 활성화가 완료된다.
