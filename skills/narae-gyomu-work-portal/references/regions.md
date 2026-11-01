# 지역 설정

`scripts/regions.cjs`의 `regions`가 17개 시도교육청 주소의 공통 원본이다.
`portal-login.cjs.configure(home,{region:'경기'})`처럼 지역만 지정해도 해당 주소를 저장한다.
`config(home)`은 저장된 지역을 읽으며 미설정 시 충북이다. 나래오피스 설정 UI도 같은 파일을 사용한다.

주소 자료는 [비엘소프트 교육청 업무포털 고객지원표](https://www.blsoft.co.kr/menu7/index.html?pg=neis-address)를 2026-11-01에 대조했다. 충북은 [교육청 인증서 안내](https://www.cbe.go.kr/cbe/cm/cntnts/cntntsView.do?cntntsId=35660&mi=11772), 경기는 [정보기록원 나이스 사용자 연수물](https://goeia.go.kr/flexer/html/UPLOAD/BBS/B29/%28%EB%B0%B0%ED%8F%AC%EC%9A%A9%292024%20%ED%95%99%EB%85%84%EC%B4%88%20%EB%82%98%EC%9D%B4%EC%8A%A4%20%EC%82%AC%EC%9A%A9%EC%9E%90%20%EC%97%B0%EC%88%98%EB%AC%BC%2820240216%EC%88%98%EC%A0%95%29_hwp_files/Sections1.html)도 대조했다. 외부 네트워크의 직접 접속은 제한될 수 있다. 주소 등록과 실제 로그인·업무 호환성 검증은 다르며 현재 실검증 지역은 충북이다.

지역 변경은 진행 중인 업무를 끝낸 다음 한다. 열린 문서나 로그인 탭은 강제로 닫지 않는다. 다음 새 업무 세션에 변경을 적용하고 이전 지역 인증정보는 자동 복사하지 않는다. 인증서 암호는 계속 로컬 DPAPI 문서에만 둔다.
