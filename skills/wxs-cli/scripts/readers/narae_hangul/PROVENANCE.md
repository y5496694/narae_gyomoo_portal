# 포함된 나래한글

HWP/HWPX를 다른 도구로 대체하지 않고 같은 패키지에서 읽을 수 있도록 나래한글 CLI·소스 엔진을 포함했다. 바이너리·사용자 글꼴·개인 설정·인증 정보는 포함하지 않는다.

- 원본: [y5496694/narae_hangul](https://github.com/y5496694/narae_hangul), `1_나래엔진/narae-hangul/scripts`의 엔진 0.6.0과 읽기 전용 뷰어.
- 가져온 출처: 만승 교무팩의 `narae_hangul` 소스 사본, 교무팩 커밋 `3956f0f13fe8971d0549f24f19dcd0378c4491f6`.
- 나래한글 소스 라이선스: [MIT LICENSE](LICENSE).
- 의존성 라이선스: [THIRD_PARTY_NOTICES](scripts/engine/THIRD_PARTY_NOTICES.txt)와 함께 포함된 `scripts/engine/licenses/`.
- `attachment_reader.py`는 포함된 `scripts/narae.py run` inspect와 `export`를 실제로 실행한다. 엔진의 독립 렌더링 한계와 문서 보호를 유지한다.

엔진을 갱신할 때 소스·라이선스·의존성을 함께 대조하고 HWP/HWPX 읽기·원본 불변·그림 포함 문서의 미리보기를 다시 검증한다. 외부 폴더에 우연히 설치된 한글 파서로 자동 전환하지 않는다.
