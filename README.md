# 나래교무 업무포털

업무포털을 통해 나이스와 K-에듀파인의 학교 업무를 처리하는 스킬 팩입니다. **웹은 브라우저 컨트롤, 열린 공문서 에디터는 이 팩에 포함된 WXS CLI만** 사용합니다. 업무포털 로그인은 사용자 직접 로그인을 우선하고, 요청받은 자동 로그인은 차단 가능성을 안내한 뒤 1회만 시도합니다.

저장소: [y5496694/narae_gyomoo_portal](https://github.com/y5496694/narae_gyomoo_portal)

```text
나래교무 업무포털
├─ 공통: 교육청 설정 · 로그인 · 개인 인증서
├─ 나이스
│  └─ 복무: 연가/조퇴 초안 · 결재경로 지정
└─ 에듀파인
   ├─ 문서등록대장 · 문서진행 · 공람대기/완료 조회
   └─ WXS 공문서 에디터
      ├─ 공문을 한 건씩 열어 본문 · 모든 첨부 저장 후 닫고 내용 대조
      ├─ 첨부 읽기: 나래한글 · PDF · 엑셀 · 워드 · PPT · 이미지/OCR
      └─ 표준 기안 양식 입력 · 요청된 임시저장
```

## 현재 지원 범위

| 영역 | 현재 구현 | 검증 상태 |
| --- | --- | --- |
| 업무포털 | 충북 기본 접속, 직접 로그인 우선·자동 1회, 개인별 로컬 인증서 도우미, 시스템 진입 | 로그인된 Chrome의 시스템 진입 확인. 자동 로그인의 서버 차단 가능성과 실패 후 직접 로그인 원칙 명시 |
| 나이스 | 복무 → 개인근무상황관리 → 연가/조퇴 입력 → 개인결재선 지정 → 최종 상신 전 정지 | 사용자 허가의 더미 입력으로 실기 확인 |
| 에듀파인 | 등록대장 검색, 문서진행·업무담당확인·공람대기/완료 조회 | 현재 메뉴와 iframe 경로 확인. 공람 기본값 최근 한 달, 모든 페이지와 실제 날짜 대조 |
| WXS | 본문·첨부 저장, 한 건씩 읽고 닫기·제목 확인 후 숨기기, 기존 표준 양식·임시저장 | 실제 읽기 전용 공문과 첨부 저장·창 닫기 확인. 최초 창 활성화 방지는 보장하지 않음. 쓰기는 기존 오프라인 검증 범위 유지 |

공람은 [진행 문서와 공람 절차](skills/narae-gyomu-edufine/references/circulation.md)를 따릅니다. 본문 확인을 중심으로 **모든 첨부 내용까지** 읽고, 실패·암호화·보호·시각 확인 대기를 구분합니다. [첨부 도구 안내](skills/wxs-cli/references/attachments.md)에 형식별 코드·설치 도우미·명령이 있습니다. HWP/HWPX용 나래 한글 오피스 CLI 연결기를 포함합니다. 한컴오피스 한글을 먼저 설치한 뒤 [나래 한글 오피스](https://github.com/y5496694/Narae_hangul_office)의 설치.cmd를 한 번 실행하세요.

**상신·결재 승인·실제 발송은 현재 지원하지 않습니다.** WXS 자동발송은 나중에 결재 완료 후 발송하는 문서 속성입니다. 나이스의 이 신청 화면에서 `승인요청`은 결재경로 준비창을 여는 중간 단계이며, 그 창의 최종 `상신`을 누르지 않습니다.

WXS 초안은 기안자만 있는 경로에 결재자 1명, 빈 수신자 목록에 기관 1곳, 빈 첨부 목록에 파일 추가, 기본 관인 1개의 자동발송 설정을 지원합니다. 기존 경로·수신자·첨부 교체, 지원하지 않는 첨부 형식, 다른 양식과 다른 교육청의 동작은 추가 구현·검증 대상입니다. 전체 업무 지원은 개발 방향이며 현재 모든 메뉴를 구현했다는 의미가 아닙니다.

## 설치

WXS CLI 0.4.0은 나래한글로 준비한 표 포함 본문 HWP를 빈 표준 본문에 삽입하고, 실제 WXS 본문 페이지를 PNG로 캡처합니다. 본문 전체와 표준 필드 보존을 대조하고 캡처 전후 수정 상태를 확인합니다. [본문 삽입·캡처 설정](skills/wxs-cli/references/draft.md)을 따르세요. 기존 본문 교체와 HWPX 직접 삽입은 지원하지 않습니다.

Windows, Python 3.10 이상, 정상 설치된 업무 시스템·WXS Client, 브라우저 컨트롤이 연결된 브라우저가 필요합니다. WXS는 로그인한 사용자와 같은 Windows 데스크톱에서 실행해야 합니다. Node.js는 개발 시험에만 사용합니다.

Git으로 내려받는 경우 PowerShell에서 실행합니다.

```powershell
git clone https://github.com/y5496694/narae_gyomoo_portal.git
Set-Location narae_gyomoo_portal
```

ZIP으로 받은 경우 압축을 푼 폴더에서, Git으로 받은 경우 이어서 실행합니다.

```powershell
.\install.ps1
$naraeSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }
$naraeWxs = Join-Path $naraeSkills 'wxs-cli\scripts\wxs_cli.py'
python -m pip install -r (Join-Path $naraeSkills 'wxs-cli\scripts\requirements.txt')
python $naraeWxs doctor
# 공문 첨부도 읽을 때: 전용 가상환경에 형식별 의존성을 설치합니다.
& (Join-Path $naraeSkills 'wxs-cli\scripts\readers\setup-readers.ps1')
```

내용이 같은 설치본은 건너뜁니다. 다른 내용의 기존 스킬은 `install.ps1 -Update`로 갱신합니다. 변경 전 원본은 **skills 폴더 밖** `skill-backups`에 복사합니다. 기존 파일을 삭제하지 않으며, 갱신 시 이 팩이 제공하는 파일만 덮어씁니다. 의존성 설치·로그인·업무 실행은 설치 스크립트가 자동으로 수행하지 않습니다.

사용자 지정 스킬 위치는 `-SkillsDirectory 'D:\사용자가 지정한 폴더\skills'`로 지정할 수 있습니다. 기존 `gyomunarae-neis-edufine`가 있으면 백업 후 새 업무포털로 연결하는 호환 안내를 적용합니다. 새 설치에는 이 구 이름을 추가하지 않습니다. 새 대화에서 스킬을 사용하거나 설치된 `SKILL.md`를 직접 읽습니다.

## 첫 사용 설정

기본 주소는 [충북 업무포털](https://cbe.eduptl.kr/bpm_lgn_lg00_001.do)입니다. **다른 지역은 설치된 `narae-gyomu-work-portal/references/portal.json`의 `region`과 `portal_url`을 해당 교육청의 확인된 주소로 갱신해야 합니다.** 나이스와 에듀파인은 업무포털을 통해 들어갑니다.

인증서 경로·이름·암호는 사용자의 보안 로컬 문서에 등록합니다. 새 등록 방법은 [인증서 설정](skills/narae-gyomu-work-portal/references/local-certificate.md)을 참고합니다. 암호는 로컬에서 가려진 입력으로 받고 Windows DPAPI로 보호합니다. 인증서 파일·개인 설정·암호를 이 저장소에 넣지 않습니다. 기존 로컬 인증서 문서 위치는 호환을 위해 유지합니다.

공문 자동화 전에 **업무포털 → K-에듀파인 → 공문서 에디터(WXS)**를 각각 최초 1회 실행하고, 표시되는 초기 연동 승인을 사용자가 직접 완료해야 합니다. **WXS는 에듀파인에서 실제 공문 한 건을 열어 에디터 실행·승인까지 확인하세요.** 에듀파인 목록 조회만으로는 WXS 준비가 끝나지 않습니다. [최초 실행 3단계](skills/narae-gyomu-work-portal/references/login.md#자동화-전-최초-실행-3단계)를 참고하세요.

업무포털·나이스·에듀파인에서 **‘이 기기의 다른 앱 및 서비스에 액세스’** 팝업이 나오면 사용자가 직접 허용합니다. 이미 승인된 단계는 반복하지 않고, 승인 대기 중 공문·진입 메뉴를 계속 열지 않습니다. 에이전트의 **‘모두 허용’** 설정과는 별도이며, 개별 보안문서의 인증서 로그인도 별도입니다.

## 사용 예시

> `$narae-gyomu-work-portal`로 나이스에 들어가 지정한 날짜·시간의 연가 조퇴를 작성하고 결재경로를 확인해 줘. 상신 직전까지만 진행해.

> `$narae-gyomu-work-portal`로 에듀파인 문서등록대장에서 작년의 지정 주제와 기안자를 검색하고 문서번호·등록일·기안일시를 정리해 줘.

> `$narae-gyomu-work-portal`로 에듀파인에서 최근 한 달 공람대기와 공람완료의 본문·모든 첨부 내용을 읽고 정리해 줘. 보안문서는 인증창을 남겨 두고 다음 문서를 확인해 줘.

> `$wxs-cli`로 열린 표준 기안 양식에 내가 지정한 항목을 입력하고 임시저장해 줘. 결재올림은 하지 마.

단계별 스킬을 직접 사용할 수도 있습니다: [업무포털](skills/narae-gyomu-work-portal/SKILL.md), [나이스](skills/narae-gyomu-neis/SKILL.md), [에듀파인](skills/narae-gyomu-edufine/SKILL.md), [WXS](skills/wxs-cli/SKILL.md). 나이스·에듀파인 스킬은 팩에 포함된 업무포털 공통 절차를 함께 사용합니다.

## 저장소 구성과 개발

```text
skills/
├─ narae-gyomu-work-portal/   # 공통 진입·지역·인증서와 업무 분기
├─ narae-gyomu-neis/         # 나이스 웹 업무
├─ narae-gyomu-edufine/      # 에듀파인 웹 업무 → WXS 연결
└─ wxs-cli/                 # 열린 WXS 에디터 전용 로컬 어댑터
compat/                     # 구 스킬 이름의 호환 안내
docs/                       # 구조·확장 방법·검증 구분
examples/                   # 개인정보 없는 WXS 설정 예시
tests/                      # 오프라인 시험
install.ps1
validate.ps1
```

개념상 WXS는 에듀파인 하위 기능입니다. 설치 폴더는 스킬별로 나란히 두어 각각 발견·호출되도록 하며, 에듀파인 절차에서 WXS 스킬로 연결합니다. 공통 로그인은 한 곳에서 관리하고, 구 조회 전용 WXS 스크립트는 새 팩에 중복 동봉하지 않습니다.

개발 시험은 `python -X utf8 -m unittest discover -s tests -p 'test_*.py' -v`, `node tests/test_actions.cjs` 또는 `./validate.ps1`로 실행합니다. 앱·서버·인증서를 사용하는 실제 업무 시험은 별도로 요청받은 범위에서 진행합니다. 새 업무 추가 방법은 [확장 안내](docs/architecture.md), 확인한 범위는 [검증 기록](docs/validation.md), WXS 원본 팩 출처는 [출처 기록](docs/provenance.md)을 참고합니다.

공개 배포본은 절차·소스·가상 예시만 포함합니다. 실제 공문·화면·학생 정보·인증서·세션 URL·실행 출력은 포함하지 않습니다. 개인 실행 자료는 저장소 밖 또는 git에서 제외하는 `local/`에 둡니다. `.gitignore`만으로 이미 추적된 파일이 제거되지는 않습니다.

교육행정 시스템 및 WXS 제조사의 공식 배포물이 아닙니다. WXS 실행 파일과 제3자 프로그램은 동봉하지 않습니다. 이 팩의 코드 이용허락 라이선스는 현재 지정하지 않았습니다.
