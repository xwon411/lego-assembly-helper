# 머신 러닝을 이용한 레고 조립 순서 생성과 3D 조립 가이드

기말 프로젝트 · 지역시스템공학과 조이황 · 웹앱 https://xwon411.github.io/lego-assembly-helper/

레고 설계 파일(LDraw)을 3D로 한 단계씩 쌓아 보여 주는 웹앱이고, 조립 단계 정보가 없는 파일은 **실제 레고 설명서 65세트로 학습한 모델이 조립 순서를 정한다.**

## 코드 안내

| 위치 | 내용 |
| --- | --- |
| `index.html` | 웹앱 전체 (HTML·CSS·자바스크립트 한 파일). 3D 표시, 단계 이동, 세트 갤러리, 자동재생. AI 순서 계산은 `aiPrepare`·`aiOrder`·`aiGroup` 함수(1190행 부근), 학습된 모델은 `<script id="ai-model">` 안의 JSON |
| `ml/extract.py` | 학습 데이터 만들기: 각 세트를 앱으로 열어 부품의 3D 위치·크기·모양·색과 정답 단계를 뽑음 → `ml/feat/*.json` (65세트) |
| `ml/order.py` | 1차 시도: 부품 두 개 중 "누가 먼저"를 맞히는 모델 + 부품 사이 관계(닿음·받침) 계산 |
| `ml/next.py` | 최종 방식: "지금 상태에서 다음에 놓을 부품" 분류, 단서 23개(`state_features`), 5겹 교차검증 평가 |
| `ml/export.py` | 65세트 전체로 최종 모델 학습 → `ml/model.json`, 단계 묶기 방법 비교 |
| `ml/parity.py` | 파이썬 모델과 앱(자바스크립트)의 순서가 같은지 검증 |
| `ml/pack.py` | 수집한 모델 파일에 부품 데이터를 넣어 포장 |
| `ml/results_*.json` | 실험 결과 기록 |
| `tools/` | 세트 갤러리 데이터 만들기: 썸네일 렌더링(`make_thumbs.py`), 목록 정리(`build_catalog.py`) |
| `tests/` | 자동 테스트 (샘플 열기·단계 이동·갤러리) |
| `sets/` | 갤러리용 공식 세트 990개 (LDraw.org 공식 모델 저장소에서 수집, 각 제작자 저작물) |

### 결과 (65세트, 5겹 교차검증)

| 방법 | 다음 부품 적중률 | 전체 순서 정확도 |
| --- | --- | --- |
| 무작위 | 10.4% | 50% |
| 기존 규칙 (아래층부터·가까운 것끼리) | 6.9% | 58.3% |
| AI (그래디언트 부스팅) | 55.0% | 60.2% |

자세한 과정은 `ml/README.md` 참고.

### 다시 실행해 보기

```bash
pip install numpy scipy scikit-learn
python3 ml/next.py                    # 다음 부품 모델 평가 (FOLDS=5)
USE_RULE=1 python3 ml/export.py       # 최종 모델 학습·내보내기 + 전체 순서 평가
python3 -m http.server 8000           # 웹앱 실행 → http://localhost:8000
```

---

# 웹앱 상세

레고 디지털 설계 파일(LDraw `.ldr` / `.mpd`)을 올리면 **단계별로 3D로 쌓아 가며** 보여 주는 조립 가이드 웹앱.
서버 없이 브라우저에서만 동작하는 HTML 한 파일(`index.html`)이다.

## 기능

- **파일 열기 / 드래그 앤 드롭 / 샘플 3종** — 파일은 브라우저 안에서만 읽고 업로드하지 않음
- **단계 구분** — 파일 안의 `0 STEP` 기준. STEP이 없으면 아래층 → 위층으로 자동 분할. 한 층에 부품이 많으면 가까운 부품끼리 한 단계(최대 8개)로 묶고, 직전 단계 근처에서 이어 감
- **단계별 3D 렌더링** — 새 부품은 원래 색 그대로 + 주황 테두리로 강조, 이전 부품 반투명 토글
- **이동** — 이전/다음 버튼, 슬라이더, 키보드 `←` `→` `Home` `End`, 스페이스로 자동재생 (속도 4단계: 빠르게 1.2초 / 보통 2.2초 / 느리게 4초 / 아주 느리게 7초, 브라우저에 기억)
- **조립 방향 화살표 + 낙하 애니메이션** — 새 부품마다 끼우는 방향을 주황 화살표로 표시하고, 그 방향에서 날아와 끼워짐 (일반 브릭은 위→아래, 옆으로 붙는 부품은 옆에서). 부품의 스터드 축 기준이라 바퀴·핀처럼 축에 끼우는 부품은 실제와 다를 수 있음. "새 부품 강조"를 끄면 같이 꺼짐
- **이번 단계 부품 목록** — 부품 썸네일·이름·색(한글)·부품 번호·개수, 남은 부품 목록
- **부품 위치 찾기** — 이번 단계 목록에서 부품을 누르면 모델에서 그 부품이 깜빡임 (화면 밖이면 그쪽으로 이동)
- **완료율** — 상단에 `15 / 40단계 · 38%`, 옆 패널에 놓은 부품 수
- **소요시간 · 남은 예상 시간** — 실제로 만진 시간만 기록(5분 넘게 조작이 없으면 쉬는 중으로 보고 더 안 셈). 남은 예상 = 남은 부품 수 × 내 평균 속도 (부품당 15초에서 시작해 조립할수록 내 속도로 보정). 마지막 단계에 도착하면 "완성! 총 n분"
- **부품 준비** — 조립 전에 전체 부품을 색별/종류별로 보고, 꺼낸 부품은 눌러서 "있음" 표시 (파일별 저장, "처음부터"를 눌러도 유지)
- **조립 중 부품 체크** — "부품 체크"를 켜면(기본 꺼짐) 이번 단계 목록에 종류별 체크 버튼. 체크 안 해도 다음으로 넘어감
- **음성 "다음" / "이전"** — 🎤 음성을 켜고 말하면 넘어감 (Web Speech API: 크롬·엣지·안드로이드 크롬. 아이폰 사파리는 자주 끊길 수 있음, 마이크 권한 필요)
- **처음 방문자 안내** — 첫 방문 때 조작법 카드(마우스/터치에 맞춰 설명), 상단 `?`로 다시 보기
- **진행 저장** — 파일별로 보던 단계를 브라우저에 저장, 다시 열면 "지난번 n단계까지 봤어요 · 이어서 보기 / 처음부터"
- **카메라 자동 맞춤** — 지금까지 쌓인 모델이 화면의 3분의 2 정도를 차지하게 여유 있게, 아주 넓은 모델에서 새 부품이 너무 작을 때만 새 부품 쪽으로 확대 (끄기 가능, "전체 보기". 거리는 `AUTO_CAM_MARGIN`으로 조절)
- **모바일 대응** — 세로: 3D → 컨트롤 → 부품 목록 / 가로: 좌우 배치. 상단 옵션 버튼은 한 줄 가로 스크롤, 버튼 연타 시 화면 확대 방지. 조립 중 화면 꺼짐 방지(Wake Lock 지원 브라우저)

## 부품 모양 데이터

공식 LDraw 부품 라이브러리를 그때그때 필요한 부품만 받아서 실제 모양으로 그린다.

- 라이브러리: [gkjohnson/ldraw-parts-library](https://github.com/gkjohnson/ldraw-parts-library) (`raw.githubusercontent.com`, CORS 허용)
- 로더: three.js `LDrawLoader` (0.170.0, jsDelivr CDN)
- 부품이 내장된 "packed" `.mpd`는 추가 다운로드 없이 바로 열림. 일반 `.ldr`은 처음 열 때 부품 수에 따라 몇 초~수십 초 걸리고, 이후엔 브라우저 캐시로 빨라짐
- 라이브러리에 없는 부품(Studio 전용 부품 등)은 빠진 채로 그리고 상단에 경고 표시
- 받은 부품 파일과 썸네일은 브라우저 Cache Storage에 보관 → 두 번째 방문부터는 네트워크 없이 바로 열림 (`lah-parts-v1`, `lah-thumbs-v1`)
- 다운로드는 요청당 15초 제한, 실패(연결 끊김·5xx·429)하면 2번 더 시도. 그래도 못 받은 부품은 빠진 채로 열고 "다시 시도" 버튼 표시

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


## 출처 / 라이선스

- 샘플 모델 (`samples/`) — three.js 예제에 포함된 LDraw 모델 (부품 내장 형식)
- 세트 갤러리 모델 (`sets/`) — [LDraw.org 공식 모델 저장소(OMR)](https://library.ldraw.org/omr)의 파일, 각 파일 제작자의 저작물 (CCAL 2.0). 제작자는 `sets/catalog.json`과 앱 화면에 표시
  - `car.mpd` — James Jessiman (LDraw 기본 예제)
  - `mini-construction.mpd` — Ken Drew, 4915 Mini Construction · CCAL 2.0
  - `lighthouse.mpd` — Merlijn Wissink, 30023 Lighthouse · CCAL 2.0
- This software uses the [LDraw Parts Library](https://www.ldraw.org/). LDraw™ is a trademark owned and licensed by the Estate of James Jessiman.
- LEGO®는 LEGO Group의 상표이며, 이 프로젝트는 LEGO Group과 관련이 없다.
