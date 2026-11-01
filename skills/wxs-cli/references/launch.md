# 공용서식의 등록 기안기 연결

사용자가 새 기안을 열도록 맡겼는데 브라우저에서 로컬 WXS 실행 연결이 막힌 경우에만 사용한다. 브라우저의 실제 공용서식 클릭으로 발생한 `wxsclient` 요청을 로컬 실행기가 메모리에 보관한다. 이전 세션 URL 재생이나 임의 URI 입력 기능이 아니다.

나래오피스에서는 `gyomu_browser action=diagnostics`의 `externalApplication`에 요청 ID·서식명·출처만 표시한다. `gyomu_wxs_launch operation=preview, id=관찰한ID`로 등록 실행기의 지문을 확인하고 같은 ID·fingerprint로 `operation=apply`를 한 번 실행한다.

원본 CLI의 `launch-registered`는 비공개 stdin JSON만 받는다. 브라우저 실행기 내부에서만 `url`, `source_origin`, `format_title`을 전달한다. 실행 URI는 인증 연결값을 포함할 수 있으므로 명령 인자·임시 파일·모델·로그에 넣지 않는다. HTTPS 충북 에듀파인에서 관찰한 서식명, 해당 서비스의 WXS 진입 경로, Windows에 이미 등록된 `WXSClient.exe`와 유효한 HANDYSOFT 서명만 허용한다. 다른 출처·경로·서식명·등록 실행기로 바뀌면 거절한다. 보안프로그램 설치나 브라우저 전체 보호 해제는 수행하지 않는다.

미리보기와 적용 사이 URI·등록 명령·실행 파일 해시가 같아야 한다. 실행 시도 후 결과 불명은 반복하지 않는다. `windows`로 실제 새 창을 확인한 뒤 `draft-status`의 실제 제목·필드로 이어간다. 창이 열려도 임시저장·상신 완료는 별도 확인이다.
