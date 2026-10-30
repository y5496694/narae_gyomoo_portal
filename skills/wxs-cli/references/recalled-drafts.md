# 회수 기안의 서식 수정과 기존 결재선 재확인

사용자가 요청한 문서 수정·재상신의 절차다. 코드 작업이나 안내서 작성만 요청받았다면 실제 회수·상신을 수행하지 않는다. 실제 문서 제목·개인 ID·기록 경로는 매 작업에서 새로 확인하며 예시 값이나 과거 대화 값을 재사용하지 않는다.

## 웹과 WXS의 작업 경계

사용자가 기존 Chrome 또는 나래 브라우저를 요청하면 `narae-browser attach --session TASK`로 연결한다. 저장된 확장 토큰이 있으면 다시 요구하지 않는다. 확인창 처리와 별도 탭은 나래 브라우저의 `docs/dialogs-and-portal.md`를 따른다. 확인창 수락이 회수 완료를 뜻하지 않는다. `tabs`에 나타난 의견작성 창까지 처리하고 원래 목록의 **회수** 상태를 재조회한다. 이후 해당 행을 선택해 **재작성**한다. 제목 링크는 읽기 전용 열람으로 이어질 수 있다.

WXS가 열리면 `windows`와 브라우저 제목을 대조해 HWND를 선택하고 `draft-status`에서 `sancgian`, `processed:false`, `EditMode=2`를 확인한다. `sancview`·EditMode=0이면 읽기 전용이므로 본문 교체를 시도하지 않는다.

## 과제카드 후보가 비어 있는 경우

과제 선택창의 최초 목록이 비어 있어도 지원 불가나 사용자 수동 선택으로 단정하지 않는다. `draft-options --section task`가 반환한 실제 창을 사용해 검색한다.

```powershell
python $wxsCli draft-options --hwnd $hwnd --expected-title $title --section task --dialog-hwnd $taskDialog --task-query '확인할 과제명 일부'
python $wxsCli draft-options --hwnd $hwnd --expected-title $title --section task --dialog-hwnd $taskDialog
```

검색은 후보 조회만 하며 선택하지 않는다. 반환된 `rows`의 과제명·ID·보존기간을 대조한 뒤 정확한 후보 표시명으로 `--task-card $exactName --apply`한다. 공개 구분·첨부와 함께 주 화면의 실제 과제카드도 다시 확인한다.

## 결재 후보가 0명이고 부재 안내가 있는 경우

기존 경로를 열었는데 `participants`가 0명이면 아직 초기화 중이거나 네이티브 안내가 막고 있을 수 있다. 빈 경로로 확정하거나 창을 취소하고 사람을 다시 추가하지 않는다. 먼저 같은 프로세스의 안내를 읽는다.

```powershell
python $wxsCli native-notices --hwnd $hwnd --out $newNoticeJson
```

`native-notices`는 원문과 버튼만 읽으며 닫지 않는다. 실제 안내가 **기존 결재자가 부재중이며 대리결재자 지정 방법을 설명하는 정보성 메시지**인 경우:

```powershell
python $wxsCli route-notice --hwnd $hwnd --expected-title $title --expected-person $observedPerson --expected-message $observedMessage --out $newPreview
# 반환된 전체 문서·안내를 대조한 뒤 같은 인자에 추가
# --apply --expected-fingerprint $previewFingerprint
```

이 명령은 실제 기존 결재자 이름, 동일 기안, 정확한 원문, 같은 PID의 단일 안내창과 확인 버튼을 검증한다. 결재자 교체·삭제·대리결재 지정·상신을 하지 않는다. 안내를 닫은 뒤 **같은 결재경로 창**을 다시 조회하면 초기화된 원래 참여자 목록을 확인할 수 있다. 경로 추가 도중 별도의 **부재자 결재선** 창이 열린 경우와 혼동하지 않는다.

별도 부재자 결재선 창에서는 `absence-route --hwnd $absenceDialog --expected-person $person --expected-position $position`으로 미리보기를 읽는다. 사용자 요청이 원래 결재자를 유지하는 것이면 새 지문을 검토한 뒤 `--apply --expected-fingerprint ...`로 **부재자가 복귀 후 결재처리**만 선택할 수 있다. 이 명령은 대리결재자로 바꾸지 않는다. 이후 실제 주 화면의 이름·ID·순서·역할을 대조한다.

## 회수 후 순번이 대시로 표시되는 경로

재작성 직후 주 화면의 모든 현재 결재 행이 `-기안`, `-검토`, `-결재` 등으로 표시될 수 있다. 이는 확인 전의 예외 표현이다. 같은 인원의 이름·역할·행 수만 일치하는 경우에만 **재확인 전 비교**를 허용한다. 실제 열린 선택창의 모든 ID·이름·순서·역할이 route-only 설정과 일치해야 확인할 수 있다.

```powershell
python $wxsCli draft-options --hwnd $hwnd --expected-title $title --section approval --dialog-hwnd $routeDialog --confirm-route $reviewedRouteJson --apply
```

설정은 같은 제목의 `expected_title`, `title`, `approval_route`만 사용한다. 현재 후보에서 확인한 전체 ID를 넣어 동명이인을 구분한다. 기존 결재자를 추가·교체하지 않는다. 확인 후 실제 **연속된 현재 순번·역할·사람 순서**를 엄격하게 검증한다. 이력에 따라 현재 순번이 4부터 시작할 수도 있다. 숫자 순번이어도 사용자 ID 뒤 상태가 `-`인 비활성 이력은 현재 경로에 합치지 않는다. 번호 누락·중복·역할 변경은 거절한다.

## 서식과 재상신 완료 검증

[본문·붙임·줄 정렬 기준](draft-writing.md)에 따라 현재 기안을 내보내고 나래 한글 오피스로 본문 문단만 수정한다. 글꼴에 따른 `번호+공백` 폭을 확인한 내어쓰기를 사용한다. 전체 사본 적용은 `replace-document`의 문서 지문과 보호 필드 검사로 수행한다. 이후 실제 WXS 사본의 글꼴·문단 서식과 모든 쪽 캡처를 대조한다. 마지막 본문 값이 `끝.`으로 끝나야 하며 필드 경계 표시를 일반 문자로 입력하지 않는다.

상신은 [최종 실행 절차](../../../docs/final-actions.md)를 따른다. 이미 결재경로 확인을 마쳤어도 상신 직전 미리보기 지문은 새로 만든다. 실제 사전검사 거절이 입증된 경우 외에는 중복 시도하거나 receipt 잠금을 지우지 않는다.

정상 처리 안내를 닫은 뒤 웹의 같은 문서·기안자·새 기안 시각·현재 결재자를 재조회한다. 다시 연 서버 문서의 본문 끝·첨부·공개 사유와 경로도 대조한다. 읽기 전용 재열람 시 **“기안자에 의해 문서 내용이 변경되었습니다. 이력보기 버튼을 통해 확인하시기 바랍니다”** 안내가 표시될 수 있다. `native-notices`로 실제 원문을 먼저 읽고 `read-notice --hwnd ... --expected-title ... --expected-message ...`의 새 지문을 검토한 뒤 `--apply --expected-fingerprint ...`로 이 정보성 안내만 닫는다. 다른 메시지는 거절한다.

`capture`는 편집 가능 기안의 검수용이다. 읽기 전용 서버 사본은 `export-document`로 확보해 나래 한글 오피스의 inspect로 실제 문단 서식을 확인한다. 실제 공문·학생·개인정보·세션 URL·receipt는 로컬 비공개 작업 폴더에만 둔다.
