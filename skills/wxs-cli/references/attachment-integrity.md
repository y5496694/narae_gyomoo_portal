# 첨부 업로드와 서버 사본 검증

이름·용량·파일 ID가 표시돼도 서버에 원본 바이트가 저장됐다는 뜻은 아니다. 원본을 형식별 읽기 도구로 검사하고 크기·SHA-256을 기록한다. 저장·상신 뒤 실제 서버 문서를 다시 열어 **모든 첨부를 내려받아 원본과 비교**한다. PDF 열기 오류를 수정한 건은 네이티브 열기도 확인한다. 실제 파일과 진단은 비공개 로컬 폴더에 둔다.

## 새 파일 추가

기존 `draft`의 `attachments`와 네이티브 `Attach.addFiles`를 사용하며 사이트의 확장자·크기 검사를 유지한다. 확인된 표준 기안 `2020` 앱은 네이티브 `syncNew`가 로컬 파일의 ID를 할당한 뒤 누락된 바이트 등록을 CLI가 보완한다. 원래 검증·HOX 변경·ID 할당을 그대로 실행하고 반환된 실제 ID에 `hsattach.AddFlashFile`을 연결한다. 이미 바이트를 등록하는 임시저장 등 확인된 앱에는 중복 적용하지 않는다. 알 수 없는 앱이나 변경된 함수는 거절한다.

이 보완은 합성 회귀시험으로 검증했다. 모든 기관·버전의 실제 신규 상신까지 확인한 것으로 확대하지 않는다. 서버 검증은 생략하지 않는다.

## 내려받기와 열기

```powershell
python $wxsCli export-attachments --hwnd $hwnd --expected-title $title --directory $newDirectory --out $newManifest
# 임시저장 사본이 편집 가능 기안으로 열린 경우에만 추가: --editable-draft
python $wxsCli open-attachment --hwnd $readonlyHwnd --expected-title $title --name $exactPdfName --apply --out $newResult
```

다운로드 폴더는 새 경로여야 한다. 모든 파일의 `exported`, `size_matches`, `sha256`을 원본과 대조한다. `all_exported`는 파일 확보 결과이며 원본 일치·내용 검토를 대신하지 않는다. 편집 가능 사본은 추출 전후 전체 상태가 같아야 한다. `open-attachment`는 변경되지 않은 읽기 전용 서버 문서에서 정확히 한 개로 확인된 PDF의 네이티브 `Attach.open`만 호출한다. 반환은 스크립트 예외 없이 핸들러가 돌아왔다는 근거이며 결재 완료를 뜻하지 않는다.

## 이름만 남거나 서버 파일이 없는 기존 첨부

```powershell
python $wxsCli attachment-diagnostics --hwnd $hwnd --expected-title $title --out $privateDiagnostics
```

진단은 파일 정보와 확인된 네이티브 처리 분기를 읽으며 파일을 열거나 수정하지 않는다. 사용자가 복구를 맡기고 원본을 확보한 경우 기존 파일 전체와 같은 ID·이름·순서로 아래 설정을 준비한다. ID는 현재 진단에서 확인한 값이다.

```json
{"expected_title":"현재 확인한 제목","files":[{"id":"현재 첨부 ID","name":"합성 첨부.pdf","path":"D:/Example/합성 첨부.pdf"}]}
```

```powershell
python $wxsCli stage-attachments --hwnd $hwnd --config $sourceConfig --out $newPreview
# 미리보기의 전체 문서·첨부·원본 지문을 대조한 뒤:
python $wxsCli stage-attachments --hwnd $hwnd --config $sourceConfig --apply --expected-fingerprint $fingerprint --out $newStaging
```

이 명령은 같은 이름의 원본을 확인된 네이티브 첨부 편집 맵에 등록한다. 크기·해시, 현재 기안, 첨부 ID·순서, 네이티브 수정 파일 업로드 분기를 검증한다. **`server_uploaded:false`**이며 실제 업로드는 이후 네이티브 저장·상신에서 수행된다. 부분 적용이나 이미 등록된 상태를 재실행하지 않는다. 삭제·개수 변경·이름 변경은 이 복구 명령의 범위가 아니다.

복구본 임시저장 후 웹의 실제 **임시저장** 메뉴에서 저장 사본을 연다. 사본의 첨부를 전부 내려받아 원본과 비교하고 본문·공개 구분·과제카드·현재 결재선을 재검수한다. 정확한 전환 안내 `열려있는 기안/결재기를 닫습니다.`만 취소할 때는 `cancel-editor-switch --hwnd ... --expected-title ... --apply`를 사용한다. 이 명령은 기존 편집기를 보존하며 저장·상신하지 않는다. 이후 `windows`로 창을 다시 구분한다.

기존 서버 파일이 없는 회수본은 수정 후에도 원래 레코드의 상신이 거절될 수 있다. 같은 시도를 반복하지 않는다. `final-failure-ack --receipt ... --expected-message '에러가 발생했습니다.'`는 정확한 단일 실패 안내만 닫고 기존 잠금과 `retry_allowed:false`를 보존한다. 웹에서 원본이 회수 상태이고 새 진행 문서가 없음을 확인한 뒤에만, 사용자가 맡긴 재기안 범위에서 검증된 임시저장 사본을 별도 기안으로 처리한다. 결과 불명 시 새 receipt로 원래 문서를 재시도하지 않는다.

상신 후 새 기안 시각·현재 결재자를 조회하고 새 서버 사본의 첨부 해시와 PDF 열기를 재확인한다. 대체 기안 검증 전에 원래 회수본을 삭제하지 않는다. 사용자가 정리까지 맡겼으면 [회수본 정리](../../narae-gyomu-edufine/references/recalled-cleanup.md)를 이어간다.
