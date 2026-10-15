# 개인별 인증서 보안 로컬 문서

인증서 경로·인증서 이름·암호는 각 사용자의 학교 PC에 등록한다. 스킬·에이두 옵시디언에는 등록 양식과 절차만 두며 실제 값은 저장하지 않는다. 이미 지정한 보안 로컬 문서가 있으면 재등록을 강제하지 않는다.

새 Windows 등록의 기본 위치는 `%LOCALAPPDATA%\Aiedue\GyomuNarae\neis-edufine.credentials.clixml`이다. 문서 위치를 바꾸려면 도우미의 `-Path`를 사용한다. 사용자 지정 문서 위치는 개인 환경에서 보관하고 공개 스킬의 설정으로 복사하지 않는다.

## 등록 항목

| 문서 필드 | 등록 값 |
| --- | --- |
| `region` | 교육청 지역. 충북 기본 설정에서는 `충북` |
| `storage_type` | `HardDisk` 또는 `Removable` |
| `certificate_path` | 해당 사용자의 실제 인증서 절대 경로 |
| `certificate_name` | 인증서 목록에 표시되는 정확한 이름 |
| `storage_name` | 화면에서 저장소 구분이 필요한 경우의 이름. 단일 저장소면 생략 가능 |
| `disk_label` | USB 등의 실제 볼륨 이름. 하드디스크는 생략 가능 |
| `disk_drive` | USB 등의 현재 드라이브. 이동식은 이름 또는 드라이브 하나 이상 등록 |
| `password` | 로컬에서 입력한 인증서 암호를 Windows DPAPI로 암호화한 SecureString |

아래 예시 값은 가상이다. 개인별 경로·이름·저장소·USB 정보를 실제 화면에 맞춰 바꾼다. `NPKI`라는 경로를 실제 인증서 위치로 가정하지 않는다.

## 로컬 등록

스킬의 실제 설치 폴더를 기준으로 `scripts/certificate-profile.ps1`을 찾는다. 기본 개인 스킬 폴더의 예:

```powershell
$naraeSkillsRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }
$naraeProfileScript = Join-Path $naraeSkillsRoot 'narae-gyomu-work-portal\scripts\certificate-profile.ps1'

# 사용자가 로컬 터미널에서 실행한다. 암호는 마지막의 가려진 입력 프롬프트에서 입력한다.
& $naraeProfileScript -Action Register -Region '충북' -StorageType HardDisk -CertificatePath 'C:\Example\Certificate' -CertificateName '화면에 표시된 본인 인증서 이름' -StorageName '화면에 표시된 저장소 이름'

# USB 사용자의 대체 예. 위 하드디스크 예와 둘 다 실행하지 않는다.
& $naraeProfileScript -Action Register -Region '충북' -StorageType Removable -CertificatePath 'E:\Example\Certificate' -CertificateName '화면에 표시된 본인 인증서 이름' -StorageName '화면에 표시된 저장소 이름' -DiskLabel 'MY-USB' -DiskDrive 'E:'

# 암호·인증서 이름·경로를 출력하지 않는 점검
& $naraeProfileScript -Action Status
```

실제 암호를 명령 인자, 채팅, 평문 JSON 또는 환경변수에 넣지 않는다. 도우미는 기존 문서를 자동으로 덮어쓰지 않는다. 변경 등록을 명시적으로 요청받았을 때만 `-Replace`를 붙인다. `-Password`는 로컬 코드 안에서 SecureString을 전달하는 용도로만 제공된다.

CLIXML의 암호는 Windows DPAPI의 현재 사용자 방식으로 보호되며, 파일 접근 권한은 해당 Windows 사용자와 SYSTEM으로 제한된다. 경로·이름 등 메타데이터는 파일 권한으로 보호되며 파일 내부에서 암호화되는 것은 암호 값이다. 같은 Windows 사용자로 실행되는 프로그램까지 차단하는 저장소는 아니다. 다른 PC·Windows 사용자로 옮겨 복호화가 안 되면 해당 PC에서 다시 등록한다. 암호화가 실패했다고 평문 저장으로 대체하지 않는다. 이 도우미는 인증서 파일을 복사·변경하지 않는다.

## 자동 로그인에서 읽기

`Status`는 비밀값을 표시하지 않는다. `ReadForBrowser`는 자동 입력을 위한 **로컬 프로세스 간 전달 전용**이다. 이를 일반 셸 도구에서 직접 실행하거나 stdout을 채팅으로 반환하지 않는다.

브라우저 제어 런타임이 허용하는 로컬 Node.js 파일·프로세스 API가 있을 때, PowerShell 출력을 그 런타임의 메모리로 직접 받아 암호 입력에 전달한다. 브라우저 작업은 해당 브라우저 도구의 API로만 수행한다. 다음은 로컬 문서 읽기 예시이며, 경로는 설치된 스킬의 실제 경로로 바꾼다.

```javascript
// 브라우저 컨트롤 세션 안에서 실행한다. profile 또는 raw를 출력하지 않는다.
const { execFileSync } = await import('node:child_process');
let raw = execFileSync('powershell.exe', [
  '-NoProfile', '-NonInteractive', '-File', profileScriptPath,
  '-Action', 'ReadForBrowser'
], { encoding: 'utf8', windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
let profile = JSON.parse(raw.replace(/^\uFEFF/, ''));
raw = null;
// 최신 화면에서 인증서 선택과 로그인 주소를 확인한 뒤:
// await observedPasswordLocator.fill(profile.password);
// 위 locator는 현재 화면에서 확인한 실제 암호 입력란이어야 한다.
profile.password = null;
profile = null;
```

사용자 지정 문서 경로에는 인자 배열로 `-Path`, 해당 경로를 추가한다. 쉘 명령 문자열에 개인 값을 이어 붙이지 않는다. 실패 시 프로세스 오류 객체의 stdout·stderr 전체를 출력하지 말고 실패 원인만 비밀값 없이 보고한다. 암호 입력의 성공·실패와 관계없이 `finally`에서 메모리 변수 참조를 정리한다. 암호를 출력해 모델이 다시 입력하는 방식을 사용하지 않는다. 실행 환경이 이러한 비밀값 전달을 지원하지 않으면 가능한 매체·인증서 선택까지 수행하고 암호 입력 단계만 사용자가 직접 처리하도록 안내한다. 도구 제한을 자동 로그인 성공으로 설명하지 않는다.
