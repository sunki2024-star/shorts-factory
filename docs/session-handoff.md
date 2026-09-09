# 이어받기 — 방배동 예심교회 쇼츠 자동화

갱신: 2026-09-04 · 브랜치 `claude/shorts-creation-automation-0xaii8`

이 문서 하나면 대화 기록 없이도 이어서 일할 수 있다. **대화는 계정 사이로
옮겨지지 않지만, 대화에서 내린 판단은 전부 여기와 저장소에 글로 남아 있다.**

## 지금 상태

**돌아간다.** 맥 두 대(Mac mini M1 · iMac)에서 설교 한 편 → 쇼츠 3편이
끝까지 나온다. 클라우드 컨테이너에서 시작했지만 지금은 **로컬이 본선**이다.

| | |
|---|---|
| 실행 환경 | 사용자의 맥. `~/shorts-factory` |
| 비용 | **0원.** yt-dlp로 받고 whisper.cpp large-v3로 전사한다 |
| API 키 | **필요 없다.** `.env` 를 만들 일이 없다 |
| 만든 편 | `office/produced.json` — 폴더를 지워도 남는다 |
| 저장소 | 사용자가 자기 GitHub으로 fork 했다. 원본은 `Kairose-master/shorts-factory` |

두 진입점이 전부다.

```bash
bash scripts/shorts-auto.sh              # 채널에서 안 만든 편을 무작위로
bash scripts/shorts-url.sh "<유튜브주소>"  # 이 설교로
```

## 이 세션에서 내린 판단 — 뒤집기 전에 읽을 것

전부 실제로 실패를 겪고 고친 것들이다. 이유 없이 되돌리면 같은 실패가 다시 난다.

**설교자를 화면에서 찾아 가운데 놓는다.** 고정 좌표를 쓰지 않는다. 예심교회
방송은 해마다 배치가 바뀌었고 강단 위치도 주일마다 다르다. 1초 간격 프레임을
설교 구간 여덟 지점에서 비교해 움직이는 사람을 찾는다(`motion_box`). 상수는
측정값이다 — 간격 0.4초로는 세 편 다 검출 문턱 아래였고 1.0초에서 잡혔다.
정지 이미지(새벽기도)는 점수가 정확히 0이라 `fit` 으로 갈라진다.

**가장 밝은 열이 아니라 가장 넓은 구간을 고른다.** 깜빡이는 LIVE 배지가 한
열에서 설교자보다 높은 점수를 낸다. `_span()` 이 연속 구간의 총합으로 고르는
이유다.

**굽기 전에 `preview` 로 확인한다.** 렌더는 10분, 확인은 1분이다. 노란 네모가
잘라낼 구간을 원본 위에 그려 준다.

**`captions/` 가 전사본보다 우선한다.** 손으로 고친 낱말이 재전사에 지워지면
안 되기 때문이다. 그런데 구간을 옮기면 그 파일의 시간이 안 맞게 되므로,
자막마다 어느 구간에서 나온 것인지 도장을 찍어 두고(`captions/.window.json`)
구간이 바뀌면 렌더가 굽기 전에 새로 만든다. 고쳐 둔 파일은 `.이전` 으로 남긴다.
도장이 없는 옛 폴더는 `captions <id> --show` 가 전사본과 대조해 몇 초
어긋났는지 말해 준다.

**ffmpeg는 libass가 있어야 한다.** Homebrew의 기본 `ffmpeg` 는 libass 없이
온다 — 다른 건 다 정상인데 마지막 렌더에서만 `No such filter: 'subtitles'` 로
죽는다. 맥은 **`brew install ffmpeg-full`** 이 답이고 `brew reinstall ffmpeg` 는
소용없다. `doctor` 가 `subtitles` 줄로 보여 주고, `render` 는 시작 전에 막는다.

**필터에 절대 경로를 넣지 않는다.** libavfilter는 `:` 와 `,` 로 쪼개고 한 번 더
언이스케이프한다. 홑따옴표가 든 경로(`/Users/장선기's Mac/`)는 **어떤 표기법
으로도 통과시킬 수 없다** — 문서에 나온 형태를 전부 시험해 확인했다. 그래서
경로를 저장소 기준 상대경로로 만들고 ffmpeg를 저장소에서 실행한다. 윈도우의
`C:` 도 같은 이유로 해결됐다.

**필터 옵션 이름을 다 적는다.** 최신 ffmpeg는 첫 옵션을 생략하는 축약형
(`subtitles=<파일>`)을 거부한다.

**정리 명령을 만들지 않았다.** 사용자가 직접 `source/` 만 지운다. 폴더 이름이
있어야 무엇을 만들었는지 기억하고, 기록은 폴더 밖 `office/produced.json` 에도
남아서 폴더째 지워도 다시 뽑히지 않는다.

## 절대 바뀌지 않는 규칙

- **업로드는 사람이 한다.** 어느 단계에도 자동 업로드가 없다. `render` 가
  끝이고 `publish-package.md` 는 승인용 초안이다.
- **찬양 구간은 피한다.** CCLI는 예배 사용 범위지 유튜브 배포 범위가 아니다.
  `has_worship_music` 플래그가 승인 패키지까지 따라간다.
- **회중석 노출은 확인한다.** `congregation_visible` 플래그도 마찬가지다.
- **음성 합성·클로닝 없음.** 실제 하신 말씀을 자르기만 한다.
- **유료 API는 콜 수를 먼저 밝히고 쓴다.** 로컬에서는 쓸 일이 없다.
- **키를 지어내지 않는다.** 없으면 어느 변수가 없는지 말하고 멈춘다.
- 설교 구간 밖은 잘리고, 15초 미만은 버려지고, `reason` 이 템플릿 문구 그대로면
  렌더가 거부한다. 저작권 방어선은 모델의 판단이 아니라 파이프라인 구조에 있다.
- `.claude/context/*.md` 는 사용자 소유 설정이다. 읽되 고쳐 쓰지 않는다.

## 사람이 보는 문서

| 문서 | 웹판 |
|---|---|
| `docs/설치-맥.md` | <https://claude.ai/code/artifact/2a914a51-9b2d-43f9-963e-288547acb3cf> |
| `docs/설치-윈도우.md` | <https://claude.ai/code/artifact/af691eb5-c4aa-48e4-8764-1454f56688cc> |
| `docs/설치-다른교회.md` | <https://claude.ai/code/artifact/6ff620d1-367f-400f-9b2f-2079319b845f> |
| `docs/내-클로드로-옮기기.md` | <https://claude.ai/code/artifact/e4ad1f98-12bf-4fb7-8a2f-5bbeb6bce93f> |
| `docs/두-번째-컴퓨터.md` | <https://claude.ai/code/artifact/8de5219b-79ff-4118-9abb-82e595f1657d> |

인쇄본은 `docs/pdf/`. 웹판을 고치려면 HTML을 다시 만들어 `docs/_build/` 에 넣고
`python3 scripts/make_guide_pdf.py` 로 PDF를 다시 뽑은 뒤 같은 URL로 재발행한다.

## 첫 명령

```bash
cd ~/shorts-factory
git pull
bash scripts/shorts doctor            # subtitles 줄이 OK 여야 한다
bash scripts/smoke_test_render.sh     # 마지막 줄 PASS
```

`smoke_test_render.sh` 는 네트워크 없이 30초에 렌더 계층 전체를 검증한다.
크롭·자막·엔드카드·자막 어긋남 검출까지 12가지를 확인하므로, **코드를 고쳤으면
이것부터 돌린다.**

## 클라우드에서 돌려야 한다면

이 컨테이너에서는 유튜브가 막혀 있어 Apify와 Gemini가 필요했다. 편당 약 $1.7이
들었고 화질과 자막 품질은 로컬보다 나빴다. 실측 기록은
`docs/environment-constraints.md`, 키 판단은 `docs/key-setup.md`,
비용 비교는 `docs/porting-to-your-claude.md` 맨 위 표에 있다.
**로컬에서 돌 수 있으면 그쪽이 낫다.**
