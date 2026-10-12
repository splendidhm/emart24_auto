# 이마트24 자동화 인수인계

## 최신 운영 정책 — 2026-10-13부터 적용

- 사용자의 최종 요청에 따라 **과거 날짜 자동 소급 수집은 하지 않는다.** 예약 실행은 당일 자료만 처리한다.
- 월~토 10:40, 10:45, 10:50, 10:55, 11:00, 11:05, 11:10 한국시간에 실행한다. 일요일 제외, 공휴일 포함이다. 성공 후에도 다음 시각에 다시 조회한다.
- 당일 입력 > 0, 오류 = 0인 모든 전송을 등록일시·전송번호 순서로 처리한다. 본 주문과 추가 주문을 모두 확인하며 이미 존재하는 데이터는 다시 넣지 않는다.
- 기존 주문과 식별 후보 항목이 같으나 값이 다른 자료는 확인 대상으로 남긴다. 수정 주문 식별 기준이 확정되지 않았으므로 **자동 덮어쓰기 수정은 미구현**이다. 모호한 전송 외의 독립적인 전송은 처리한다.
- 2026-10-12 실제 Windows 작업 `Emart24-CJ-DailyImport` 갱신 완료. `Ready`, 다음 실행 `2026-10-13 10:40:00`, 월~토 주간 트리거 7개와 로그인 트리거를 확인했다. 오늘 운영 Excel 적재는 하지 않았다.
- 실행 중이면 다음 인스턴스를 무시한다. 사이트 조회가 5분을 초과하면 해당 시각 실행이 생략될 수 있다. 11:10은 마지막 실행 시작 시각이며 진행 중 작업은 이후 완료될 수 있다.
- 단위 테스트 41개, PowerShell 구문 및 Git 공백 검사 통과. 실제 10월 10일 원본 73행+추가 2행은 읽기 전용 미리보기에서 모두 `already_present`였다. 새 다중 전송 경로의 실제 사이트 전체 실행과 첫 예약 운영 결과는 아직 확인 대상이다.
- 사용자가 수정한 최신 DB의 마지막 행은 40,217이다. 8일 53행, 9일 78행, 10일 73+2행, 12일 80행을 대조했으며 누락이 없었다. 아래 수동 처리 당시 행 번호는 과거 기록이다.
- 배포 커밋 메시지: `주문 추가 및 데이터 취합시간 변경`. 코드·설정·테스트·운영 문서를 함께 반영하며, PC별 설정·예약 작업·자격 증명은 Git으로 이전되지 않는다.

## 2026-10-12 수동 처리 및 다운로드 수정

**운영 반영 완료:** 10월 9일 78행(39,932~40,009), 10일 2행(40,010~40,011), 12일 80행(40,012~40,091), 총 160행. 날짜별 복사본 검증 후 백업·적재·최종 해시 대조를 완료했다. 기존 26개 시트 보존과 P~T 계산 및 중복 방지를 확인했다.

사용자가 10월 9일·10일·12일 운영 반영을 요청했다. 가상 그리드의 DOM 순번 locator가 다른 파일을 클릭하는 문제를 확인해, 파일명+행 위치로 선택하고 다운로드 파일명을 대조하도록 수정했다. 최초 잘못된 9일 기적재 확인 이력은 `aborted`로 보존 정정했으며 그 과정에서 운영 파일에 추가한 행은 없다. 정확한 선택 결과는 9일 78행, 10일 2행, 12일 80행이다. 최종 반영 결과와 백업 경로는 `runtime/manual-three-final.json`, 상세 검증은 `docs/validation.md`를 확인한다. 단위 테스트 33개와 오프라인 Edge 셀 재배치 시험이 통과했다. 이번 수정의 Git 커밋·푸시는 아직 수행하지 않았다.

갱신: 2026-10-07. 다른 PC 적용 예정일: 2026-10-08.

최신 운영 상태: 한글 인코딩 수정 후 사용자가 현재 PC의 예약 작업 `Ready` 상태를 확인했다. 아래의 정기 작업 미등록 기록은 복사본 테스트 당시의 상태다. 첫 예약 실행 성공은 아직 확인하지 않았다. 타 PC로 운영을 이전할 때는 현재 PC 작업을 사용 안 함으로 전환한다. 프로젝트 밖에서 등록할 때는 `register-task.ps1`의 전체 경로를 지정한다.

## 현재 상태

- 저장소: https://github.com/splendidhm/emart24_auto.git / 배포 브랜치: `main`.
- 실제 CJ 로그인, rMate 목록 157페이지·4,709건 대조, 최신 유효 전송번호 `2819177` 선택 및 다운로드를 확인했다. 제목은 상세 화면을 열며 **파일명 셀**을 클릭해야 다운로드된다.
- 10월 7일 원본 70행을 **운영 파일 복사본** DB 39,932~40,001행에 적재했다. A~O 값, P~T 수식 참조·계산, 기존 26개 시트의 값·수식·숫자 표시 형식, 재실행 중복 방지가 통과했다. 운영 파일 해시는 동일했다.
- 최종 `verify-site`는 다운로드·양식 검증·미리보기까지 성공했다(`would_append`, 70행). 단위 테스트 30개 통과. 상세 결과는 `docs/validation.md`.
- 자격 증명 저장 시 bytes 전달 오류를 Unicode 문자열 전달로 수정했다. 실제 Windows 임시 시험값의 저장·읽기·삭제를 확인했다. 과거 10:30 점검의 인증 미등록 상태는 이후 해결됐다.
- 10월 6일 73행은 운영 DB에 이미 존재해 이 PC에 `existing` 이력을 기록했다. **10월 7일 테스트는 운영 파일에 쓰지 않았으며, 현재 PC의 정기 작업도 등록하지 않았다.**
- `.xls` 실파일 호환성, 다른 PC 설치 및 첫 예약 실행은 아직 별도 검증 대상이다.

## 1. 새 PC 설치

Windows 사용자 로그인 환경에 Python 3.12(64비트), 데스크톱 Microsoft Excel, Microsoft Edge, Git을 준비한다. Excel은 직접 한 번 실행해 초기 설정을 마친다. Windows 시간대는 한국 표준시로 설정한다. 설치·자격 증명·예약 등록은 실제 운영할 동일한 Windows 계정에서 진행한다. Codex 설치나 상시 실행은 필요 없다.

PowerShell에서 아래를 순서대로 실행한다. 사용자 문서 폴더에 새로 설치하는 예이며 같은 폴더가 이미 있으면 기존 설치 여부부터 확인한다. 명령 실패 시 다음 단계로 넘어가지 않는다.

```powershell
Set-Location -LiteralPath ([Environment]::GetFolderPath('MyDocuments'))
git clone --branch main https://github.com/splendidhm/emart24_auto.git emart24_auto
Set-Location -LiteralPath '.\emart24_auto'
$pythonPath = py -3.12 -c "import sys; print(sys.executable)"
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 설치를 확인하세요.' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\scripts\setup.ps1' -Python $pythonPath
```

`py`가 없으면 Python 3.12의 실제 `python.exe` 경로를 `-Python`에 지정한다. 기존 PC의 `.venv`는 복사하지 않는다. `ExecutionPolicy Bypass`는 해당 PowerShell 실행에만 적용된다.

## 2. 대상 파일·로그인 설정

최신 운영 통합문서를 새 PC의 업무 폴더에 준비한다. Excel 파일은 Git에 포함되지 않는다. 기존 PC에서 아직 반영하지 않은 주문이 있는지 확인한다. 고정 파일명은 `재고관리_이마트24_26년(신제품 추가).xlsx`, 시트는 `DB`다.

```powershell
.\configure-target.cmd
.\.venv\Scripts\python.exe -m emart24 show-config
.\register-credentials.cmd
```

첫 창에서 대상 파일이 있는 **폴더**를 선택하고 `show-config`의 최종 경로를 확인한다. 로그인 창에는 CJ 사이트 ID/비밀번호를 입력한다. Windows 자격 증명 이름은 `Emart24/CJLogistics`다. 비밀번호를 채팅·명령 인수·설정에 넣지 않는다.

로컬 설정, 자격 증명, 사이트 검증, 예약 작업은 새 PC에서 다시 구성한다. 기존 PC의 검증 파일을 복사해 준비 검사를 우회하지 않는다. 기존 백업·이력은 기존 PC에 보존한다. 새 PC의 이력은 비어 있으므로 기존 DB 중복 검사를 반드시 거친다. 동일 업무의 예약은 **운영 PC 한 대에서만** 활성화한다.

## 3. 사이트·복사본 검증과 운영 준비

대상 Excel을 닫고 진행한다. 아래 날짜는 실제 자료가 있는 검증 예시다. 10월 8일 설치 시 당일 자료가 아직 없으면 10월 7일 자료로 설치 검증할 수 있다. 과거 주문의 실제 적재 필요 여부는 담당자가 확인한다.

```powershell
$checkDate = '2026-10-07'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m emart24 verify-site --date $checkDate
Get-ChildItem -LiteralPath (Join-Path 'runtime\downloads' $checkDate) -Recurse -File
```

성공한 `verify-site` 실행에서 다운로드한 파일의 전체 경로를 다음 명령에 입력한다. 같은 날짜의 실행 폴더가 여러 개면 해당 성공 실행의 파일인지 확인한다.

```powershell
$sourcePath = Read-Host '방금 검증에서 다운로드한 Excel 전체 경로'
.\.venv\Scripts\python.exe -m tests.validate_download $sourcePath --date $checkDate
```

이 테스트는 `runtime/validation`에 운영 파일과 원본을 복사해 검사한다. 보고서의 `passed: true`를 확인한다. 이미 반영된 자료는 `append_exercised: false`이며 신규 적재를 시험한 것으로 간주하지 않는다.

다음 명령은 **실제 운영 파일 처리**다. 복사본 검증 통과 후 해당 날짜·파일이 적재 대상임을 확인하고 실행한다. 전체가 이미 반영됐으면 `already_present`로 건너뛰며 일부 중복이나 수정본이면 중단한다. 중단을 우회하거나 이력을 삭제하지 않는다.

```powershell
.\.venv\Scripts\python.exe -m emart24 run --date $checkDate --source $sourcePath --dry-run
.\.venv\Scripts\python.exe -m emart24 run --date $checkDate --source $sourcePath
.\.venv\Scripts\python.exe -m emart24 check-ready
```

`--source`는 지정 파일을 사용하므로 날짜와 원본의 대응은 실행자가 확인한다. `check-ready`는 이 PC의 사이트 검증과 운영 처리 또는 기적재 이력이 있어야 통과한다. 폴더 설정 변경 후에는 사이트 검증부터 다시 진행한다.

## 4. Windows 작업 스케줄러 등록

한글 경로에서 `ConvertFrom-Json` 이스케이프 오류가 발생한 문제를 수정했다. 등록 스크립트가 `show-config --ascii`를 사용하므로 콘솔 인코딩을 수동 변경할 필요가 없다. 이전 코드를 사용하는 PC는 수정본으로 갱신한 뒤 아래 등록 명령을 다시 실행한다. JSON 변환에서 중단됐다면 이번 시도로 새 작업은 등록되지 않은 상태다(기존 작업이 있었다면 그대로 유지).

프로젝트 폴더의 PowerShell에서 현재 사용자 계정으로 일반 실행한다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\scripts\register-task.ps1'
Get-ScheduledTask -TaskName 'Emart24-CJ-DailyImport' | Select-Object TaskName,State
Get-ScheduledTaskInfo -TaskName 'Emart24-CJ-DailyImport' | Select-Object LastRunTime,LastTaskResult,NextRunTime
```

오류가 있으면 해결한 뒤 다시 등록한다. 같은 이름의 기존 작업은 새 설정으로 갱신된다. 등록 후 예약 실행은 운영 파일에 실제로 적재한다.

| 항목 | 등록 내용 |
|---|---|
| 이름 | `Emart24-CJ-DailyImport` |
| 정기 실행 | 월~토 한국시간 10:40~11:10, 5분 간격 총 7회, 공휴일 포함 |
| 추가 트리거 | 해당 사용자 로그인 시 놓친 실행 확인 |
| 실행 사용자 | 현재 Windows 사용자, 로그인 상태에서만 실행 |
| 동작 | 프로젝트 `.venv\Scripts\python.exe`로 `run --scheduled` |
| 시간 | 당일 자료만 처리하며 성공·자료 없음 이후에도 다음 예약 시각에 재조회 |
| 중복 | 실행 중이면 새 인스턴스 무시 |
| 실행 시간 제한 | 작업 스케줄러 설정상 최대 45분 |

Windows 키+R → `taskschd.msc` → **작업 스케줄러 라이브러리** → 해당 작업 더블클릭. 일반 탭에서 사용자·로그온 조건, 트리거에서 월~토 10:40~11:10의 7개 시각·로그인 시, 동작에서 Python·프로젝트 경로, 조건에서 전원 설정을 확인한다. 특정 날짜부터 시작하려면 등록 명령 끝에 `-StartDate '2026-10-13'`처럼 시작 날짜를 지정한다.

PC 전원·인터넷을 유지하고 로그인해 둔다. 화면 잠금은 로그아웃과 다르다. 등록 스크립트는 절전 깨우기를 설정하지 않으므로 실행 시간에는 절전 상태를 피한다. 노트북은 AC 전원 조건을 확인하고 전원을 연결한다. 대상 Excel은 닫아둔다. Codex·PowerShell 창은 닫아도 된다. 프로그램 폴더를 이동하면 가상환경과 예약 경로를 다시 구성한다.

10:40~11:10 실행 구간 밖에 로그인하면 적재하지 않는다. 과거 날짜는 자동 소급하지 않는다. 작업의 **실행** 버튼도 시간 제한을 적용하므로 시간 밖에는 적재 없이 정상 종료할 수 있다. `LastTaskResult=0`만으로 적재 성공을 판단하지 않는다.

## 5. 결과 확인·중지·복구

```powershell
Get-Content -LiteralPath '.\runtime\events.log' -Tail 40
```

- `committed`: 운영 파일 적재 완료. `already_present`: 기적재라 추가 없음.
- `would_append`: 미리보기만 수행, 저장하지 않음. `ERROR`/`stopped`: 원인 확인 필요.
- 첫 예약 실행 후 실행 시각·로그·DB 행·P~T 계산을 확인하고 `docs/validation.md`와 이 문서를 갱신한다.

예약을 중지할 때:

```powershell
Disable-ScheduledTask -TaskName 'Emart24-CJ-DailyImport'
```

다시 자동 실행할 때:

```powershell
Enable-ScheduledTask -TaskName 'Emart24-CJ-DailyImport'
```

작업 우클릭 → 사용 안 함/사용으로도 전환한다. 사용 안 함은 미래 실행을 막으며 이미 실행 중인 작업을 취소하는 명령은 아니다. 시간 경과 후 수동 복구는 `run --date YYYY-MM-DD --dry-run`으로 확인한 뒤 `run --date YYYY-MM-DD`를 사용한다.

복구는 예약 중지 → Excel 닫기 → 현재 파일 별도 보관 → 백업·SQLite 이력 대조 순서다. 백업·이력을 임의 삭제하거나 Excel 프로세스를 일괄 종료하지 않는다. `prepared` 이력은 파일 해시와 함께 검토한다.

## 유지보수 기준

업무 규칙은 `AGENTS.md`, 구조는 `docs/architecture.md`를 따른다. A~O 위치 그대로 복사하며 F/H를 교환하지 않는다. P~T 수식을 확장하고 U열·기존 행·다른 시트를 보존한다. 매크로·외부 링크 자동 갱신을 차단한다.

백업 → 작업 사본 편집·검증 → `prepared` → `ReplaceFileW` 교체 → `committed` 순서다. 보호 핸들과 충돌하는 단순 `os.replace`로 변경하지 않는다.

`runtime`에는 다운로드·로그·백업·SQLite·시험 파일이 있다. Git에 올리지 않는다. `.venv`, `config.local.json`, Excel 파일, 자격 증명도 제외한다. 70행 시험 보고서는 기존 PC의 `runtime/validation/2026-10-07-0bac0e39b2a748edb4f7cf751b8ade91/report.json`에 있다.

완료 기준은 **새 PC에서 검증 → 운영 처리/기적재 확인 → 예약 등록 → 첫 평일 예약 실행 확인**이다. 기존 PC의 시험 성공을 새 PC의 운영 완료로 간주하지 않는다.
