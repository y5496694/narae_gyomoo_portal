# 나래교무 업무포털

업무포털을 통해 나이스와 K-에듀파인의 학교 업무를 처리하는 스킬 팩입니다. **웹은 브라우저 컨트롤, 열린 공문서 에디터는 WXS CLI**가 담당합니다. 업무포털의 여러 업무를 이 구조 안에서 계속 확장합니다.

저장소: [y5496694/narae_gyomoo_portal](https://github.com/y5496694/narae_gyomoo_portal)

```text
나래교무 업무포털
├─ 공통: 교육청 설정 · 로그인 · 개인 인증서
├─ 나이스
│  └─ 복무: 연가/조퇴 초안 · 결재경로 지정
└─ 에듀파인
   ├─ 문서등록대장: 검색 · 기안자 확인 · 목록 정리
   └─ WXS 공문서 에디터
      ├─ 공문 본문 · 첨부 목록 조회
      └─ 표준 기안 양식 입력 · 요청된 임시저장
```

## 현재 지원 범위

| 영역 | 현재 구현 | 검증 상태 |
| --- | --- | --- |
| 업무포털 | 충북 기본 접속, 로그인 절차, 개인별 로컬 인증서 도우미, 시스템 진입 | 로그인된 Chrome의 나이스/에듀파인 진입 실기 확인. 인증서 자동 입력은 미검증 |
| 나이스 | 복무 → 개인근무상황관리 → 연가/조퇴 입력 → 개인결재선 지정 → 최종 상신 전 정지 | 사용자 허가의 더미 입력으로 실기 확인 |
| 에듀파인 | 문서등록대장 기간·제목·기안(접수)자 검색, 기안자·문서번호·기안일시 확인 | 1페이지 전체와 개별 문서정보 실기 확인. 다수 페이지 이동은 미검증 |
| WXS | 본문·첨부 메타데이터 조회, 표준 양식 제목·본문·비공개 사유·과제·결재자·수신자·첨부·자동발송 설정·임시저장 | 실제 조회 확인. 범용 쓰기 배포본은 오프라인 모의 시험 확인 |

**상신·결재 승인·실제 발송은 현재 지원하지 않습니다.** WXS 자동발송은 나중에 결재 완료 후 발송하는 문서 속성입니다. 나이스의 이 신청 화면에서 `승인요청`은 결재경로 준비창을 여는 중간 단계이며, 그 창의 최종 `상신`을 누르지 않습니다.

WXS 초안은 기안자만 있는 경로에 결재자 1명, 빈 수신자 목록에 기관 1곳, 빈 첨부 목록에 파일 추가, 기본 관인 1개의 자동발송 설정을 지원합니다. 기존 경로·수신자·첨부 교체, 첨부 내용 읽기, 다른 양식과 다른 교육청의 동작은 추가 구현·검증 대상입니다. 전체 업무 지원은 개발 방향이며 현재 모든 메뉴를 구현했다는 의미가 아닙니다.

## 설치

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
```

내용이 같은 설치본은 건너뜁니다. 다른 내용의 기존 스킬은 `install.ps1 -Update`로 갱신합니다. 변경 전 원본은 **skills 폴더 밖** `skill-backups`에 복사합니다. 기존 파일을 삭제하지 않으며, 갱신 시 이 팩이 제공하는 파일만 덮어씁니다. 의존성 설치·로그인·업무 실행은 설치 스크립트가 자동으로 수행하지 않습니다.

사용자 지정 스킬 위치는 `-SkillsDirectory 'D:\사용자가 지정한 폴더\skills'`로 지정할 수 있습니다. 기존 `gyomunarae-neis-edufine`가 있으면 백업 후 새 업무포털로 연결하는 호환 안내를 적용합니다. 새 설치에는 이 구 이름을 추가하지 않습니다. 새 대화에서 스킬을 사용하거나 설치된 `SKILL.md`를 직접 읽습니다.

## 첫 사용 설정

기본 주소는 [충북 업무포털](https://cbe.eduptl.kr/bpm_lgn_lg00_001.do)입니다. **다른 지역은 설치된 `narae-gyomu-work-portal/references/portal.json`의 `region`과 `portal_url`을 해당 교육청의 확인된 주소로 갱신해야 합니다.** 나이스와 에듀파인은 업무포털을 통해 들어갑니다.

인증서 경로·이름·암호는 사용자의 보안 로컬 문서에 등록합니다. 새 등록 방법은 [인증서 설정](skills/narae-gyomu-work-portal/references/local-certificate.md)을 참고합니다. 암호는 로컬에서 가려진 입력으로 받고 Windows DPAPI로 보호합니다. 인증서 파일·개인 설정·암호를 이 저장소에 넣지 않습니다. 기존 로컬 인증서 문서 위치는 호환을 위해 유지합니다.

업무포털·나이스·에듀파인을 열 때 **‘이 기기의 다른 앱 및 서비스에 액세스’** 팝업이 나오면 최초 실행 시 **사용자가 직접 한 번 허용**해야 합니다. 에이전트가 대신 허용하거나 우회하지 않습니다. 이미 허용되어 있으면 반복해서 묻지 않습니다.

## 사용 예시

> `$narae-gyomu-work-portal`로 나이스에 들어가 지정한 날짜·시간의 연가 조퇴를 작성하고 결재경로를 확인해 줘. 상신 직전까지만 진행해.

> `$narae-gyomu-work-portal`로 에듀파인 문서등록대장에서 작년의 지정 주제와 기안자를 검색하고 문서번호·등록일·기안일시를 정리해 줘.

> `$narae-gyomu-work-portal`로 에듀파인에서 지정 공문을 열고 WXS 본문과 첨부 목록을 확인해 줘.

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
