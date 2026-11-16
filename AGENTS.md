# AGENTS.md — 레고 조립 도우미 (Codex 등 코딩 에이전트용 인수인계)

이 파일은 이 저장소에서 작업하는 코딩 에이전트가 처음에 읽는 안내서다. 지금까지 Claude가 작업한 맥락·결정·주의점·테스트 방법·다음 할 일을 담았다.

## 1. 제품 한 줄
레고 디지털 설계 파일(LDraw `.ldr`/`.mpd`)이나 건축 평면도(JSON)를 열면 **단계별로 3D로 쌓아 가며** 보여 주는 조립·시공 가이드 웹앱.
방향: "레고부터 건축까지, 설계도를 단계별 3D로". 공식 LEGO Builder 앱이 지원하지 않는 MOC(커스텀 설계)용 + 건축 시공 순서 시각화. 공모전 출품 예정(1~2단계 완성 + 3단계 건축 예시 1개로 비전 제시).

## 2. 사용자와 일하는 방식 (꼭 지킬 것)
- 사용자: 조이황(서울대 학생). **한국어, 반말·편한 말투**로 대답.
- **요청 범위 밖의 변경은 먼저 물어볼 것.** 눈에 보이거나 동작이 달라지는 변경은 제안만 하고 허락받기. "고쳐줘"라고 한 것만 고치기.
- 선택지를 주고 고르게 하는 걸 선호. 구현 세부(코드·파일·포맷)는 알아서 처리.
- 계산·단위 실수를 잘 잡아냄 → 숫자는 검산하고 근거를 적기.
- **저장소 반영: 새 브랜치 + PR**, 사용자가 확인하면 머지. `main`에 직접 커밋하지 않기.
- PR 설명은 한국어: 요약 / 들어간 것 / 버그 수정 / 확인한 것(실제 테스트 결과 숫자) 순.
- 디자인(시각적 스타일)은 "나중에 따로 손보기"로 미뤄 둔 상태 — 기능 작업 중엔 스타일 대공사 금지.

## 3. 배포·구조
- 배포: GitHub Pages (`main` / root) → https://xwon411.github.io/lego-assembly-helper/
- **서버 없음. `index.html` 한 파일**(HTML+CSS+JS, ~2200줄)에 전부 들어 있음. 빌드 도구 없음.
- three.js `0.170.0`을 jsDelivr importmap으로 로드 (`three`, `three/addons/`).
- 부품 모양: 공식 LDraw 부품 라이브러리 미러 `https://raw.githubusercontent.com/gkjohnson/ldraw-parts-library/master/complete/ldraw/` (CORS 허용). 상수 `LIB`.
- `samples/`: `car.mpd`(8단계), `mini-construction.mpd`(40단계), `lighthouse.mpd`(STEP 없음 → 자동 분할), `house.json`(건축 7단계). `.mpd`는 부품 내장(packed)이라 라이브러리 요청 없이 열림.
- `?sample=samples/house.json` 처럼 첫 화면 샘플 지정 가능.
- 디버그용 전역: `window.__app` (state, goTo, userMove, parsePlan, buildHouse, …) — 테스트가 씀, 지우지 말 것.

### index.html 안의 구역 (`// ───── 이름 ─────` 주석으로 구분)
| 구역 | 핵심 함수/상수 |
|---|---|
| 다운로드 | `window.fetch` 래핑: LIB 요청만 Cache Storage(`lah-parts-v1`) 확인 → `fetchWithRetry`(요청당 15초, 연결 실패·5xx·429면 2번 재시도, **404는 재시도·실패 처리 안 함**) |
| 렌더러/씬 | `renderer`, `labelRenderer`(CSS2D, 건축 라벨), `camera`, `controls`(OrbitControls), `ground` |
| 상태 | `state` (bricks, steps, stepOf, info(WeakMap), cur, mode `'lego'|'house'`, timing, checks, prepHas, plan …) |
| 렌더 루프 | `requestRender`/`frame` — **필요할 때만 그림**(계속 돌지 않음). 애니메이션 중이면 다시 요청 |
| 로딩 | `loadFromText(text, label)` — JSON이면 건축 모드, 아니면 LDrawLoader. `hashText`로 진행 저장 키 |
| 모델 세팅 | `setModel(group, label, loader, missing, netFails, opts)` — `opts.house`면 건축. `collectBricks`(레고) / `collectElements`(건축) |
| 진행 저장 | localStorage `lah:progress:<hash>` (step,total,elapsed,parts,done,checks), `lah:prep:<hash>` |
| 단계 | `buildSteps` (userData.buildingStep 기준, 없으면 `clusterLayer`로 층별·근접 묶음 자동 분할) |
| 단계 이동 | `goTo(index, {animate, camera})` — 화면 상태만 바꿈. **사람이 넘길 땐 `userMove`** (시간·완성 기록) |
| 시간 | `activity`, `IDLE_CAP`(5분), `DEFAULT_SEC_PER_PART`(15초), `PRIOR_PARTS`(12) |
| 위치 찾기 / 방향 화살표 | `findParts`(깜빡임), `insertDir`, `showArrows`, `dropIn`(끼우는 방향에서 날아옴) |
| 카메라 | `frameStep`(`AUTO_CAM_MARGIN`=1.5, 넓은 모델만 새 부품 쪽 확대), `fitAll` |
| 목록/썸네일 | `groupParts`, `renderList`, `drainThumbs`(Cache `lah-thumbs-v1`), `makeThumb`, `KO_COLORS` |
| 부품 준비 | `openPrep`, `renderPrep` (색별/종류별 "있음" 체크) |
| 건축 모드 | `parsePlan`, `buildHouse`, `houseElement`, `HOUSE_STEPS`, `HOUSE_MATS`, `setMode`, `applyDims` |
| 음성 | Web Speech API `startVoice`/`stopVoice` ("다음"/"이전") |
| 안내 | `openGuide`/`closeGuide`, `lah:guideSeen` |

## 4. 알아 둘 함정 (실제로 겪은 것)
- **LDraw는 -Y가 위**: 레고 모델 루트는 `rotation.x = Math.PI`. 건축 모델은 회전 없음.
- **`LDrawLoader.smoothNormals`를 켜면 48×48 베이스플레이트 하나에 50초+** → 꺼 두고 로드 후 `toCreasedNormals(35°)`.
- **로더는 부품 파일 하나만 못 받아도 모델 전체를 실패시킴** → `parseCache.fetchData`를 감싸서 실패 파일은 빈 Primitive로 채우고 `missing`에 기록(경고 표시).
- **로더가 색 이름 앞에 공백을 붙임** (`" Red"`) → `colorLabel`에서 trim. 안 하면 한글 색 이름 안 나옴.
- 진행 저장: 모델을 열 때 1단계를 그리면서 저장값을 덮어쓰지 않도록 `resumePending`으로 막음. 순서 바꾸지 말 것.
- 썸네일은 테스트 환경(GPU 없음)에서 수 초 걸림 — 버그 아님.
- 사용자 데이터(진행·준비·속도 등)는 전부 localStorage `lah:*`. 키 이름 바꾸면 기존 사용자 진행이 사라짐.

## 5. 평면도 형식 (`lah-floorplan/1`, 단위 m) — AI 출력 목표 형식
```json
{
  "format": "lah-floorplan/1", "name": "집 이름", "unit": "m",
  "wallHeight": 2.6, "wallThickness": 0.2,
  "walls":    [{ "id": "front", "from": [0,0], "to": [10,0], "exterior": true, "thickness": 0.2 }],
  "openings": [{ "type": "door|window", "wall": "front", "offset": 2.2, "width": 1.0, "height": 2.1, "sill": 0.9 }],
  "rooms":    [{ "name": "거실", "polygon": [[0,0],[6,0],[6,5],[0,5]] }],
  "roof":     { "type": "gable|flat|none", "pitch": 28, "overhang": 0.4 }
}
```
- `offset` = 벽 시작점(`from`)에서 **개구부 중심**까지 거리. `sill` = 창턱 높이(문은 0).
- 좌표: 평면도 x → 3D X, 평면도 y → 3D Z. 1 m = 40 화면 단위(`M`).
- `parsePlan`이 고칠 수 있는 오류는 고치고 경고: 길이 0 벽, 없는 벽 참조, 벽 밖 개구부(안으로 이동), 겹치는 개구부(뒤의 것 삭제), 벽보다 높은 창(줄임), 꼭짓점 부족한 방. `exterior`가 하나도 없으면 바깥 테두리 벽을 외벽으로 추정.
- 시공 단계(`HOUSE_STEPS`): 기초·바닥 → 기둥 → 보 → 외벽 → 내벽 → 창호 → 지붕. 박공지붕 용마루는 긴 쪽을 따라감.
- 면적: 신발끈 공식, 1평 = 3.305785㎡. 샘플: 30+20+15+15 = 80㎡ = 24.2평.

## 6. 테스트 방법
헤드리스 Chrome + Playwright. 실제 네트워크 대신 three.js는 로컬 npm 패키지로 가로챈다.
```bash
npm i --prefix /tmp/t3 three@0.170.0       # 한 번만
pip install playwright && python -m playwright install chromium   # 또는 시스템 Chrome 사용
python3 tests/smoke.py                      # 샘플 4종 열기·단계 이동·콘솔 에러 확인
```
- `tests/smoke.py`를 참고해 기능별 테스트를 추가. 요령:
  - `ctx.add_init_script("localStorage.setItem('lah:guideSeen','1')")` — 첫 방문 안내가 클릭을 막음
  - `page.route('https://cdn.jsdelivr.net/**', …)` → `/tmp/t3/node_modules/three/` 파일로 응답
  - 준비 완료 대기: `window.__app && __app.state.steps.length>0 && !overlay.on`
  - 음성은 `window.SpeechRecognition`을 가짜 클래스로 주입해 `onresult` 직접 호출
  - 네트워크 실패는 `page.route`로 503/abort 흉내
- PR 전: 샘플 4종 + 바뀐 기능 테스트, 데스크톱(1280×800)과 폰(390×844) 스크린샷을 직접 보고 확인.

## 7. 지금 상태 (2026-11-16)
- `main`: 1단계(MVP) + 2단계(MOC 특화) + 품질 항목 전부 머지됨 (PR #1~#5).
- **`feat/stage3-architecture` 브랜치 (푸시됨, PR 아직 없음)**: 3단계 건축 뼈대 완료 — 평면도 형식, `samples/house.json`, 3D 생성, 시공 7단계, 치수·면적 라벨(지붕 단계에선 숨김), 망가진 평면도 처리. 테스트 통과.
- 진행 기록: claude.ai 프로젝트 문서 `claude/진행상황.md`(사용자가 볼 수 있음)에 날짜별로 정리돼 있음.

## 8. 다음 할 일
### 8-1. 평면도 사진 → AI → 평면도 JSON (3단계 첫 묶음의 나머지) — **호출 방식 미정, 사용자에게 먼저 물을 것**
선택지(사용자에게 보여 준 것):
1. **Claude 아티팩트로도 배포**: 같은 앱을 claude.ai 아티팩트로 올리면 페이지에서 `claude.use("sample")`(이미지 가능)로 키 없이 Claude 호출. GitHub Pages 버전에선 버튼 숨김. (Claude 쪽에서 해야 하는 작업)
2. **사용자 API 키 입력**: 브라우저에서 Anthropic API 직접 호출(`anthropic-dangerous-direct-browser-access: true` 헤더 필요). 키는 localStorage에만, 화면에 경고 문구.
3. **둘 다**.
4. **중계 서버**(Cloudflare Workers 등): 키 숨김, 계정·배포 필요.
구현 제안: 호출 방식과 무관하게 `analyzePlanImage(file) → JSON 문자열` 하나로 감싸고, 결과는 `parsePlan`에 그대로 넣기(검사·자동 수정이 이미 있음). 프롬프트에는 위 5번 형식과 규칙(단위 m, offset 정의, 외벽 표시, 방 polygon)을 넣고 **JSON만 출력**하게. 실패 시 원문을 보여 주고 수정해서 다시 열 수 있게.
### 8-2. 이후 묶음 (사용자가 고른 순서: AI 먼저 → 나머지)
- 1인칭 둘러보기 (완성된 집 안 걷기)
- 햇빛 시뮬레이션 (시간대·계절별 그림자, 채광)
- 건축 → 레고 변환 (평면도를 레고 브릭 모델(.ldr)로 바꿔 같은 앱에서 조립 설명서로) — 공모전 스토리 핵심
### 8-3. 기타
- 실제 폰(안드로이드 크롬/아이폰 사파리)에서 음성·터치 확인 안 됨
- 디자인 정리 (미뤄 둠)
- 방향 화살표 한계: 바퀴·핀처럼 축에 끼우는 부품은 실제 방향과 다를 수 있음

## 9. 출처·라이선스 표기 유지
페이지 하단의 LDraw 라이브러리 표기와 LEGO 상표 고지를 지우지 말 것. 샘플 모델 저작자는 README에 있음.
