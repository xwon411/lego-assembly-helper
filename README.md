# 레고 조립 도우미 (lego-assembly-helper)

레고 디지털 설계 파일(LDraw `.ldr` / `.mpd`)을 올리면 **단계별로 3D로 쌓아 가며** 보여 주는 조립 가이드 웹앱.
서버 없이 브라우저에서만 동작하는 HTML 한 파일(`index.html`)이다.

## 기능 (MVP)

- **파일 열기 / 드래그 앤 드롭 / 샘플 3종** — 파일은 브라우저 안에서만 읽고 업로드하지 않음
- **단계 구분** — 파일 안의 `0 STEP` 기준. STEP이 없으면 아래층 → 위층으로 자동 분할. 한 층에 부품이 많으면 가까운 부품끼리 한 단계(최대 8개)로 묶고, 직전 단계 근처에서 이어 감
- **단계별 3D 렌더링** — 새 부품은 원래 색 그대로 + 주황 테두리로 강조, 이전 부품 반투명 토글
- **이동** — 이전/다음 버튼, 슬라이더, 키보드 `←` `→` `Home` `End`, 스페이스로 자동재생
- **낙하 애니메이션** — 새 부품이 위에서 내려와 끼워짐
- **이번 단계 부품 목록** — 부품 썸네일·이름·색(한글)·부품 번호·개수, 남은 부품 목록, 진행률
- **카메라 자동 맞춤** — 작은 모델은 지금까지 쌓인 전체가 보이게, 넓은 모델은 새 부품 쪽으로 확대 (끄기 가능, "전체 보기")
- **모바일 대응** — 세로: 3D → 컨트롤 → 부품 목록 / 가로: 좌우 배치. 조립 중 화면 꺼짐 방지(Wake Lock 지원 브라우저)

## 부품 모양 데이터

공식 LDraw 부품 라이브러리를 그때그때 필요한 부품만 받아서 실제 모양으로 그린다.

- 라이브러리: [gkjohnson/ldraw-parts-library](https://github.com/gkjohnson/ldraw-parts-library) (`raw.githubusercontent.com`, CORS 허용)
- 로더: three.js `LDrawLoader` (0.170.0, jsDelivr CDN)
- 부품이 내장된 "packed" `.mpd`는 추가 다운로드 없이 바로 열림. 일반 `.ldr`은 처음 열 때 부품 수에 따라 몇 초~수십 초 걸리고, 이후엔 브라우저 캐시로 빨라짐
- 라이브러리에 없는 부품(Studio 전용 부품 등)은 빠진 채로 그리고 상단에 경고 표시

## 실행

`index.html`을 웹 서버로 열면 된다 (파일을 더블클릭해서 `file://`로 열면 샘플 불러오기가 막힘).

```bash
python3 -m http.server 8000
# → http://localhost:8000
```

`?sample=samples/lighthouse.mpd` 처럼 첫 화면 샘플을 지정할 수 있다.

### GitHub Pages 배포

Settings → Pages → Source: `Deploy from a branch` → `main` / `(root)` 저장 → `https://xwon411.github.io/lego-assembly-helper/`

## BrickLink Studio에서 내보내기

Studio에서 `File → Export As → LDraw (.ldr / .mpd)` 로 저장한 뒤 열기. (`.io` 파일은 바로 못 엶)

## 다음에 할 것 (2차 아이디어)

- 부품 위치 찾기 (목록에서 누르면 모델에서 깜빡)
- 음성 "다음"
- 진행 상황 저장 (새로고침해도 이어서)
- 완료율 · 소요 시간 기록

## 출처 / 라이선스

- 샘플 모델 (`samples/`) — three.js 예제에 포함된 LDraw 모델 (부품 내장 형식)
  - `car.mpd` — James Jessiman (LDraw 기본 예제)
  - `mini-construction.mpd` — Ken Drew, 4915 Mini Construction · CCAL 2.0
  - `lighthouse.mpd` — Merlijn Wissink, 30023 Lighthouse · CCAL 2.0
- This software uses the [LDraw Parts Library](https://www.ldraw.org/). LDraw™ is a trademark owned and licensed by the Estate of James Jessiman.
- LEGO®는 LEGO Group의 상표이며, 이 프로젝트는 LEGO Group과 관련이 없다.
