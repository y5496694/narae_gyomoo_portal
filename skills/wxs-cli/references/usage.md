# WXS (공문서 에디터) 설치와 명령

## 조건과 설치

Windows, Python 3.10 이상, pywin32와 정상 설치된 WXS Client·한글/첨부 컨트롤이 필요하다. 로그인된 사용자의 같은 Windows 데스크톱에 공문 창이 열려 있어야 한다. 관리자 권한은 필요하지 않으며 앱과 CLI의 사용자·권한 세션이 다르면 COM 접근이 실패할 수 있다.

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
