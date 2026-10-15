# 에듀파인 → WXS 공문서 에디터

에듀파인 웹에서 공문 제목이나 확인된 열기 동작으로 공문/양식을 연다. 이후 같은 팩의 [WXS 스킬](../../wxs-cli/SKILL.md)을 읽어 CLI로 이어간다. WXS는 개념상 에듀파인의 하위 도구이며 설치 폴더는 다른 스킬과 나란히 둔다. **컴퓨터 유즈는 사용하지 않는다.**

```powershell
$naraeSkillsRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }
$naraeWxsSkill = Join-Path $naraeSkillsRoot 'wxs-cli'
$naraeWxsCli = Join-Path $naraeWxsSkill 'scripts\wxs_cli.py'
if (-not (Test-Path -LiteralPath $naraeWxsCli)) { throw '업무포털 팩의 wxs-cli 스킬을 먼저 설치하세요.' }
Get-Content -LiteralPath (Join-Path $naraeWxsSkill 'SKILL.md') -Encoding UTF8
python $naraeWxsCli doctor
python $naraeWxsCli windows
```

1. 웹에서 문서를 열기 전후의 창을 대조한다. 창 재사용도 가능하므로 브라우저의 제목·문서번호와 `windows`·`inspect`의 현재 값으로 대상을 식별한다. 첫 창이나 과거 hwnd를 임의로 선택하지 않는다.
2. 조회는 `text`, `attachments`를 사용하고 본문 추출 전후 편집 상태를 확인한다. 첨부 메타데이터만으로 첨부를 읽었다고 보고하지 않는다.
3. 작성 요청이면 WXS의 `references/draft.md`를 읽고 `draft-status` → 실제 요청 항목의 UTF-8 JSON → 변경 계획 → 실제 hwnd와 `--apply` 순서로 처리한다. `save_name`이 있을 때만 마지막에 서버 임시저장을 한다.
4. 기존 경로·수신자·첨부 교체 등 지원 밖 변경을 임의 COM 코드나 업무 API로 확장하지 않는다. 대상 불일치·후보 중복·세션 만료·알 수 없는 창이면 완료 지점과 원인을 보고한다.
5. 부분 실패는 `completed_steps`, `attempted_step`과 현재 값을 대조해 남은 항목으로 이어간다. 저장 결과가 불명확하면 웹 임시보관함의 실제 상태를 확인하며 전체 명령을 반복하지 않는다. 임시보관함 조회 경로 자체는 현재 팩에서 실기 검증하지 않았으므로 현재 웹 화면으로 확인한다.

조회·초안 입력·임시저장을 구분해 보고하며 최종 상신은 수행하지 않는다. WXS가 지원하는 상세 범위와 검증 상태는 해당 스킬의 문서를 기준으로 한다. 구 교무나래에 있던 조회 전용 `wxs_cli.py`는 이 팩에 중복 포함하지 않는다.
