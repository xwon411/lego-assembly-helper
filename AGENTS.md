# AGENTS.md — 레고 조립 도우미 (Codex 등 코딩 에이전트용 인수인계)

이 파일은 이 저장소에서 작업하는 코딩 에이전트가 처음에 읽는 안내서다. 지금까지 Claude가 작업한 맥락·결정·주의점·테스트 방법·다음 할 일을 담았다.

## 1. 제품 한 줄
레고 디지털 설계 파일(LDraw `.ldr`/`.mpd`)을 열면 **단계별로 3D로 쌓아 가며** 보여 주는 조립 가이드 웹앱.
방향: 공식 LEGO Builder 앱이 지원하지 않는 MOC(커스텀 설계)를 설치 없이 폰 웹에서 3D로 따라 조립. 공모전 출품 예정.
**2026-11-22 결정: 레고에만 집중.** 건축 확장(평면도 → 3D, 사진 AI 분석)은 접었다. 건축 코드는 `main`에 없고, PR #6은 닫힘. 다시 꺼내자고 하기 전엔 건축 기능을 넣지 말 것.

## 2. 사용자와 일하는 방식 (꼭 지킬 것)
- 사용자: 조이황(서울대 학생). **한국어, 반말·편한 말투**로 대답.
- **요청 범위 밖의 변경은 먼저 물어볼 것.** 눈에 보이거나 동작이 달라지는 변경은 제안만 하고 허락받기. "고쳐줘"라고 한 것만 고치기.
- 선택지를 주고 고르게 하는 걸 선호. 구현 세부(코드·파일·포맷)는 알아서 처리.
- 계산·단위 실수를 잘 잡아냄 → 숫자는 검산하고 근거를 적기.
- **저장소 반영: 새 브랜치 + PR → 작업이 끝나고 테스트가 통과하면 바로 머지까지** (2026-11-22 사용자 요청). `main`에 직접 커밋하지 않기.
- PR 설명은 한국어: 요약 / 들어간 것 / 버그 수정 / 확인한 것(실제 테스트 결과 숫자) 순.
- 디자인 (2026-11-22 변경): **깔끔한 앱 스타일**(토스풍 시안 A + 배민식 카테고리 아이콘). 회색 바탕 `--paper` #f2f4f6, 흰 둥근 카드, 주 버튼·선택은 파랑 `--blue` #3182f6, 주황 `--accent`는 3D 새 부품 표시에만. 제목은 문장형 대신 카테고리 이름. (예전: 조립 설명서풍) 설명서 종이색 바탕(`--paper` #dce6ee), 먹색 글자·버튼(`--ink` #1b2430), 강조는 새 부품 주황(`--accent` #ff7a00)만. 화면의 주인공은 3D 화면 왼쪽 위 **큰 단계 번호**, 그 아래 **부품 상자**(설명서 콜아웃). 새 시각 요소를 넣을 땐 이 토큰만 쓰고, 큰 디자인 변경은 시안을 스크린샷으로 먼저 보여 주고 고르게 할 것.

## 3. 배포·구조
- 배포: GitHub Pages (`main` / root) → https://xwon411.github.io/lego-assembly-helper/
- **서버 없음. `index.html` 한 파일**(HTML+CSS+JS, ~2200줄)에 전부 들어 있음. 빌드 도구 없음.
- three.js `0.170.0`을 jsDelivr importmap으로 로드 (`three`, `three/addons/`).
- 부품 모양: 공식 LDraw 부품 라이브러리 미러 `https://raw.githubusercontent.com/gkjohnson/ldraw-parts-library/master/complete/ldraw/` (CORS 허용). 상수 `LIB`.
- `samples/`: `car.mpd`(8단계), `mini-construction.mpd`(40단계), `lighthouse.mpd`(STEP 없음 → 자동 분할). 부품 내장(packed)이라 라이브러리 요청 없이 열림.
- `?sample=samples/lighthouse.mpd` 처럼 첫 화면 샘플 지정 가능. 아무것도 없으면 **세트 갤러리**가 첫 화면.
- `sets/`: 세트 갤러리 데이터 (LDraw 공식 모델 저장소 OMR 1,472세트). `catalog.json`(세트·모델 목록, 부품·단계 수, 제작자), `m/<id>.mpd.gz`(모델, gzip — 앱이 `DecompressionStream`으로 풂), `t/<id>.webp`(썸네일). `?set=<모델 id>`로 바로 열기.
  - 만드는 법: 브라우저로 받은 묶음 → `python3 tools/build_catalog.py extract <묶음...>` → `python3 tools/make_thumbs.py /tmp/ml/gal/thumbs /tmp/ml/gal/src/*.mpd`(썸네일 + 앱과 같은 기준의 부품·단계 수) → `python3 tools/build_catalog.py assemble`
  - OMR 파일은 CCAL 2.0(CC BY 2.0). 제작자를 세트 열 때 모델 정보 줄에 표시함 — 지우지 말 것
- `ml/`: 조립 순서 학습 (STEP 없는 파일은 AI가 순서를 정함, `ml/README.md`)
- 글꼴: Pretendard(jsDelivr, 비동기 로드 — 안 와도 시스템 글꼴로 표시).
- 디버그용 전역: `window.__app` (state, goTo, userMove, scene, camera, …) — 테스트가 씀, 지우지 말 것.

### index.html 안의 구역 (`// ───── 이름 ─────` 주석으로 구분)
| 구역 | 핵심 함수/상수 |
|---|---|
| 다운로드 | `window.fetch` 래핑: LIB 요청만 Cache Storage(`lah-parts-v1`) 확인 → `fetchWithRetry`(요청당 15초, 연결 실패·5xx·429면 2번 재시도, **404는 재시도·실패 처리 안 함**) |
| 렌더러/씬 | `renderer`, `camera`, `controls`(OrbitControls), `ground` |
| 상태 | `state` (bricks, steps, stepOf, info(WeakMap), cur, timing, checks, prepHas …) |
| 렌더 루프 | `requestRender`/`frame` — **필요할 때만 그림**(계속 돌지 않음). 애니메이션 중이면 다시 요청 |
| 로딩 | `loadFromText(text, label)` — LDrawLoader. `hashText`로 진행 저장 키 |
| 모델 세팅 | `setModel(group, label, loader, missing, netFails)`, `collectBricks` |
| 진행 저장 | localStorage `lah:progress:<hash>` (step,total,elapsed,parts,done,checks), `lah:prep:<hash>` |
| 단계 | `buildSteps` (userData.buildingStep 기준, 없으면 `clusterLayer`로 층별·근접 묶음 자동 분할) |
| 단계 이동 | `goTo(index, {animate, camera})` — 화면 상태만 바꿈. **사람이 넘길 땐 `userMove`** (시간·완성 기록) |
| 시간 | `activity`, `IDLE_CAP`(5분), `DEFAULT_SEC_PER_PART`(15초), `PRIOR_PARTS`(12) |
| 위치 찾기 / 방향 화살표 | `findParts`(깜빡임), `insertDir`, `showArrows`, `dropIn`(끼우는 방향에서 날아옴) |
| 카메라 | `frameStep`(`AUTO_CAM_MARGIN`=1.5, 넓은 모델만 새 부품 쪽 확대), `fitAll` |
| UI | `updateUI`(큰 단계 번호 `#stepBadge`, 진행률), `renderCallout`(3D 화면 안 부품 상자, 최대 6칸), 보기 설정 메뉴 `setViewMenu`(`#viewMenu` 안에 강조·반투명·카메라·부품 체크·속도), 모델 선택 `#sampleSelect`(`__open` = 파일 열기) |
| 목록/썸네일 | `groupParts`, `renderList`, `drainThumbs`(Cache `lah-thumbs-v1`), `makeThumb`, `KO_COLORS` |
| 부품 준비 | `openPrep`, `renderPrep` (색별/종류별 "있음" 체크) |
| 음성 | Web Speech API `startVoice`/`stopVoice` ("다음"/"이전") |
| 안내 | `openGuide`/`closeGuide`, `lah:guideSeen` |

## 4. 알아 둘 함정 (실제로 겪은 것)
- **LDraw는 -Y가 위**: 모델 루트는 `rotation.x = Math.PI`.
- 레이아웃 그리드 열은 `minmax(0, 1fr)` — 그냥 `1fr`이면 긴 선택 상자 때문에 폰 화면이 가로로 넘침.
- 폰에서 `.tools` 아이콘 버튼 스타일은 `.tools > .chip, #bView`에만 — 메뉴 안 스위치까지 잡으면 메뉴가 깨짐.
- **`LDrawLoader.smoothNormals`를 켜면 48×48 베이스플레이트 하나에 50초+** → 꺼 두고 로드 후 `toCreasedNormals(35°)`.
- **로더는 부품 파일 하나만 못 받아도 모델 전체를 실패시킴** → `parseCache.fetchData`를 감싸서 실패 파일은 빈 Primitive로 채우고 `missing`에 기록(경고 표시).
- **로더가 색 이름 앞에 공백을 붙임** (`" Red"`) → `colorLabel`에서 trim. 안 하면 한글 색 이름 안 나옴.
- 진행 저장: 모델을 열 때 1단계를 그리면서 저장값을 덮어쓰지 않도록 `resumePending`으로 막음. 순서 바꾸지 말 것.
- 썸네일은 테스트 환경(GPU 없음)에서 수 초 걸림 — 버그 아님.
- 사용자 데이터(진행·준비·속도 등)는 전부 localStorage `lah:*`. 키 이름 바꾸면 기존 사용자 진행이 사라짐.

## 5. 테스트 방법
헤드리스 Chrome + Playwright. 실제 네트워크 대신 three.js는 로컬 npm 패키지로 가로챈다.
```bash
npm i --prefix /tmp/t3 three@0.170.0       # 한 번만
pip install playwright && python -m playwright install chromium   # 또는 시스템 Chrome 사용
python3 tests/smoke.py                      # 샘플 3종 × 데스크톱/폰 열기·단계 이동·콘솔 에러 확인
```
- `tests/smoke.py`를 참고해 기능별 테스트를 추가. 요령:
  - `ctx.add_init_script("localStorage.setItem('lah:guideSeen','1')")` — 첫 방문 안내가 클릭을 막음
  - 강조·반투명·카메라·부품 체크·속도는 `#bView`를 눌러 메뉴를 연 뒤에 클릭 가능
  - `page.route('https://cdn.jsdelivr.net/**', …)` → three.js는 `/tmp/t3/node_modules/three/` 파일로 응답, 글꼴 등 나머지는 abort
  - 준비 완료 대기: `window.__app && __app.state.steps.length>0 && !overlay.on`
  - 음성은 `window.SpeechRecognition`을 가짜 클래스로 주입해 `onresult` 직접 호출
  - 네트워크 실패는 `page.route`로 503/abort 흉내
- PR 전: 샘플 3종 + 바뀐 기능 테스트, 데스크톱(1280×800)과 폰(390×844) 스크린샷을 직접 보고 확인.

## 6. 지금 상태 (2026-11-22)
- `main`: 1단계(MVP) + 2단계(MOC 특화: 위치 찾기·진행 저장·완료율·속도·재시도·소요/예상 시간·부품 준비·부품 체크·음성·방향 화살표·모바일·안내·캐시) 전부 머지 (PR #1~#5).
- `design/manual-style` 브랜치: 조립 설명서풍 디자인 (이 파일과 `tests/smoke.py`가 함께 들어감).
- 건축 브랜치 `feat/stage3-architecture`, `feat/plan-image-ai`는 버리기로 함 (사용자가 GitHub에서 지울 예정).
- 진행 기록: claude.ai 프로젝트 문서 `claude/진행상황.md`, 발표 자료용 정리 `claude/발표용_고민정리.md`.

- PR #8: STEP 없는 파일 AI 조립 순서 (65세트 학습). 세트 갤러리(설명서 표지 카드, 사용자가 시안 B 선택)는 `feat/gallery`.
- **이 프로젝트는 기말 발표(11/27)용 일회성.** 폰 대응은 신경 쓰지 않아도 됨(사용자 결정). 우선순위: ① 교수님께 노력이 보이게 ② 학우들에게 "이런 것까지 되는구나".

## 7. 남은 일
- 실제 폰(안드로이드 크롬/아이폰 사파리)에서 음성·터치·새 디자인 확인
- 실제 MOC 파일로 조립해 보며 불편한 점 고치기
- 레고 기능 후보(사용자에게 먼저 물을 것): 하위 모델(서브어셈블리) 구분, 링크로 모델 공유, 부품 목록 내보내기
- 방향 화살표 한계: 바퀴·핀처럼 축에 끼우는 부품은 실제 방향과 다를 수 있음

## 8. 출처·라이선스 표기 유지
페이지 하단의 LDraw 라이브러리 표기와 LEGO 상표 고지를 지우지 말 것. 샘플 모델 저작자는 README에 있음.
