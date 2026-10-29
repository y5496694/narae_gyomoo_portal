# WXS (공문서 에디터) 설치와 명령

## 조건과 설치

Windows, Python 3.10 이상, pywin32와 정상 설치된 WXS Client·한글/첨부 컨트롤이 필요하다. 로그인된 사용자의 같은 Windows 데스크톱에 공문 창이 열려 있어야 한다. 관리자 권한은 필요하지 않으며 앱과 CLI의 사용자·권한 세션이 다르면 COM 접근이 실패할 수 있다.

자동화 전에는 [업무포털 → K-에듀파인 → WXS 최초 실행 3단계](../../narae-gyomu-work-portal/references/login.md#자동화-전-최초-실행-3단계)를 완료한다. 특히 WXS는 실제 공문 한 건을 열어 표시되는 초기 연동 승인을 사용자가 직접 처리해야 한다. 승인 대기 중에는 공문을 반복해서 열지 않는다. 이미 열린 초기 실행 공문을 읽을 때는 제목·hwnd를 대조한 뒤 `read-open`을 사용한다. `read-next`는 준비 이후 새로 열릴 창만 기다리므로 기존 창에는 사용하지 않는다.

나래교무 업무포털 팩 루트에서 실행한다. 팩의 install.ps1은 업무포털·나이스·에듀파인·WXS 스킬을 함께 설치한다.

```powershell
.\install.ps1
$wxsSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }
$wxsSkill = Join-Path $wxsSkills 'wxs-cli'
python -m pip install -r (Join-Path $wxsSkill 'scripts\requirements.txt')
$wxsCli = Join-Path $wxsSkill 'scripts\wxs_cli.py'
python $wxsCli doctor
python $wxsCli windows
```

기존 설치 갱신은 `install.ps1 -Update`로 백업 후 진행한다. 새 스킬이 현재 대화에서 발견되지 않으면 새 대화에서 `$wxs-cli`를 호출하거나 설치된 `SKILL.md`를 직접 읽는다.

## 명령

| 명령 | 용도 |
| --- | --- |
| `doctor` | 의존성 확인. 앱 실행·로그인 없음 |
| `windows` | 열린 WXS 창 hwnd·pid·제목 |
| `inspect --hwnd 값` | 프레임·컨트롤·편집 상태·함수 이름 조회 |
| `text --hwnd 값` | editor1 본문과 추출 전후 상태 |
| `attachments --hwnd 값` | DOM 첨부 표의 파일명·크기. 다운로드 없음 |
| `attachment-status --hwnd 값` | 현재 앱 첨부 목록의 이름·표시 크기 |
| `export-attachments --hwnd 값 --expected-title 제목 --directory 새폴더` | 현재 공문의 모든 첨부를 앱 저장 함수로 내려받고 파일·크기·해시 확인 |
| `read-next --expected-title 제목 --out 새JSON --background --attachments-dir 새폴더` | 새로 열리는 해당 제목의 읽기 전용 창 한 개를 기다려 본문·첨부 저장 후 닫기 |
| `read-open --hwnd 값 --expected-title 제목 --out 새JSON --background --attachments-dir 새폴더` | 이미 열린 작업 소유 문서의 명시적 hwnd를 읽고 닫기 |
| `close-readonly --hwnd 값 --expected-title 제목` | 제목·pid·읽기 전용·수정 없음 확인 후 한 창 닫기 |
| `draft-status --hwnd 값` | 표준 양식의 본문·제목·공개 제한·경로·수신자 등 |
| `draft --config 파일` | 오프라인 설정 검증과 변경 계획 |
| `draft --config 파일 --hwnd 값 --apply` | 실제 입력, save_name이 있으면 서버 임시저장 |
| `save-draft --name 이름 --expected-title 현재제목 --hwnd 값 --apply` | 이미 입력한 초안만 임시저장 |

쓰기 명령은 `--apply`가 없으면 계획만 출력한다. `--replace-existing`은 정확히 같은 임시저장 이름의 교체를 허용한다. 결재올림 명령은 없다. UTF-8 JSON, 성공 0·실패 1로 종료한다.

```powershell
# 123456을 windows 결과의 실제 hwnd로 치환
python $wxsCli inspect --hwnd 123456
python $wxsCli text --hwnd 123456 --out .\body.txt
python $wxsCli attachments --hwnd 123456 --out .\attachments.json
python $wxsCli draft-status --hwnd 123456
python $wxsCli draft --config .\draft.json
python $wxsCli draft --config .\draft.json --hwnd 123456 --apply
```

`--out`은 새 파일만 만든다. 기존 파일이 있으면 작업을 시작하지 않는다. `text --out`의 파일만 순수 텍스트이며 나머지는 JSON이다. Python 하위 프로세스는 인자 배열과 `encoding='utf-8'`을 사용한다. 제목·본문을 셸 문자열에 이어 붙이지 않는다.

## 공람을 한 건씩 읽고 닫기

1. 웹 목록에서 실제 문서 제목·번호를 얻는다. `read-next`를 시작하고 표준출력의 `ready:true`를 확인한다. 이 명령은 기존 창(숨은 창 포함)을 제외하므로 실행 전에 문서를 열어 버리지 않는다.
2. 웹에서 그 제목을 한 번 누른다. CLI는 새 창 중 **제목이 일치하는 유일한 창**만 읽는다. 웹의 공백 축약 차이를 위해 연속 공백·줄바꿈만 한 칸으로 정규화하며 문구·기호·접두어의 부분 일치는 허용하지 않는다. 여러 후보·시간 초과이면 다른 창을 임의로 고르지 않는다. 새 WXS의 인증서 창이 나타나면 `status:authentication_required`, 종료 코드 **2**로 기록하고 창을 보존한다. 사용자에게 보안문서의 추가 인증이 필요하다고 알린 뒤 다른 문서를 계속 확인한다. 인증창 자체를 세션 만료로 단정하거나 닫지 않는다. `--timeout`은 5~300초이며 기본값은 90초다.
3. 결과 파일에서 본문 `body.text`, 추출 전후 상태, 첨부 목록과 저장 결과를 확인한다. 비전자 문서는 `body.source:non_electronic_attachment`로 표시될 수 있다. 이때 편집기 본문을 읽은 것이 아니며 저장된 원문 PDF 등을 실제로 읽어야 한다.
4. `closed:true`를 확인하고 다음 문서를 연다. CLI는 본문과 첨부 저장 결과를 파일에 보존한 뒤 창 닫기를 요청한다. 닫기 실패 시 결과 파일에는 `closed:false`가 남고 실패한 창은 숨긴 상태로 방치하지 않도록 활성화 없이 복원한다. 실제 창을 다시 대조하고 `close-readonly`로 이어간다. 저장/종료 확인창은 자동 수락하지 않는다.
5. [첨부 읽기 도구](attachments.md)로 **저장한 모든 첨부 내용**을 확인하고 본문과 대조한 뒤 보고한다. 이 내용 검토는 WXS를 닫은 뒤에도 진행할 수 있다. `all_exported:false`, `exported:false`, 읽기 실패·OCR 실패·시각 확인 대기는 미확인으로 남긴다. 표시 크기와 실제 크기가 다르면 `size_matches:false`가 남는다. 파일 형식과 실제 내용으로 추가 확인하며 크기 일치만으로 읽기 완료를 판단하지 않는다.

`--background`는 **제목이 확인된 뒤** 해당 창을 숨기는 최선의 처리다. 창 생성 순간·인증서 로그인창의 최초 활성화는 WXS 자체 동작이며 이 옵션이 방지하지 못할 수 있다. 보안 설정을 바꾸거나 다른 앱 포커스를 강제로 되돌리지 않는다. 완전한 무인·비대화형 실행을 보장하지 않는다.

인증 대기 문서는 `body_read:false`, `closed:false`, `preserved:true`로 남고 자동 닫기 대상에서 제외된다. 이후 명령은 기존 대기 창을 제외한 새 문서만 선택한다. 사용자 인증 뒤 `windows --include-hidden`으로 숨겨진 창까지 실제 제목을 다시 확인하고 작업 소유 창에 `read-open --hwnd 실제값 ...`를 사용한다. 인증 대기 창에는 닫기 명령을 사용하지 않는다. 세션 유지는 [공통 30분 연장 절차](../../narae-gyomu-work-portal/references/login.md)를 따른다.

첨부 저장은 현재 앱의 `Attach.saveFilesAs`를 사용한다. 새 대상 폴더만 허용하고 중복·경로 이탈·Windows에서 안전하지 않은 이름을 거부한다. 파일이 실제로 생성됐는지 확인하고 실패한 항목을 기록한다. 서버 파일 URL을 CLI 밖에서 조립·재생하거나 인증 정보를 다른 다운로드 도구로 넘기지 않는다.

## 웹 단계와 CLI 단계

**업무포털 로그인 → 나이스/K-에듀파인 진입 → 에듀파인 문서 검색·양식 열기 → WXS CLI 조회/초안 작성 → 임시저장**으로 연결한다. WXS CLI는 WXS 창이 열린 이후를 담당한다. 나이스의 복무·학적·성적이나 에듀파인 웹 목록을 제어하지 않는다. 웹 단계에는 별도 브라우저 DOM/API 도구를 사용한다.

내부 선택창은 화면에 나타날 수 있으나 COM·데이터셋·Win32 메시지로 처리한다. 화면 좌표·이미지 인식·키 입력은 사용하지 않는다. 서비스로 실행하는 완전한 headless 운영은 검증하지 않았다.

## 오류와 제한

- `windows: []`: 웹에서 공문/양식을 연다. 자동 로그인·권한 우회·원본 열기 URL 재생은 하지 않는다.
- 창 여러 개: 제목·문서번호·inspect를 대조해 실제 hwnd를 지정한다.
- COM 접근 실패: 사용자 세션·권한·컨트롤 설치를 확인한다. 보안 기능을 해제하지 않는다.
- 이름 불일치/중복: 실제 후보와 사용자 요청을 대조한다. 유사한 이름을 대신 선택하지 않는다.
- 쓰기 실패: 일부 변경은 남는다. 완료 단계와 열린 선택창을 확인한 뒤 이어간다.
- 저장 성공 메시지 없음: 결과 불명이다. 웹 임시보관함에서 확인하고 자동 재시도하지 않는다.

본문 텍스트는 그림·도장·레이아웃을 재현하지 않는다. 첨부 파일 내용 읽기·다운로드는 별도 작업이다. 조회 전후 편집 상태가 같아도 서버 읽음 기록·감사로그까지 불변임을 뜻하지 않는다.
