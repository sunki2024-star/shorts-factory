# YouTube Channel Context

## Channel Information
- **Channel Name:** 방배동 예심교회
- **Channel Handle:** @yeshim1126
- **Channel ID:** _미확인_ — `UC`로 시작하는 24자. 아래 "채널 ID 얻는 법" 참조.
  추측해서 채우지 말 것.

## Niche & Positioning
- **Primary Niche:** 설교 클립 / 한국 개신교 지역교회
- **Content Style:** 주일설교 발췌형 쇼츠 — 9:16, 한국어 자막 번인, 원본 음성 그대로
- **Target Audience:** 교인 · 지역 주민 · 비신자

## 쇼츠 소스 — 주일설교 (장선기 목사)

**주일예배는 "동영상" 탭이 아니라 "실시간 스트림" 탭에 있다.** 이걸 모르면
수요예배만 긁게 된다. 2026-08-31 확인:

```
https://www.youtube.com/@yeshim1126/streams
```

목록을 직접 열지 않아도 된다 — 아래가 streams 탭을 읽어 장선기 목사 주일예배만
추리고, 이미 만든 편은 숨긴다(메타데이터만 읽으므로 무료):

```bash
python3 scripts/sermon_shorts.py sermons          # 목록
python3 scripts/sermon_shorts.py sermons --pick   # 안 만든 것 중 무작위 1편
```

**제목의 날짜를 그대로 믿지 않는다.** 일요일이 아닌 날짜면 그 앞 주일로 맞추고
`⚠날짜` 를 붙인다 — 2026-07-14(화)로 올라온 편이 실제로는 07-12 주일예배였다.

- 매주 **일요일**, 전부 **장선기 목사**, **사무엘하 연속강해**
- 길이 60~85분 — 설교만이 아니라 **주일예배 실황 전체**다
- 최근: `l3LbSLU39jU` 2026-08-30 [삼하 22:1-8] 내가 피할 나의 반석의 하나님 (70분)

### 채널의 나머지 (쇼츠 소스 아님)

| 구분 | 위치 | 담당 | 비고 |
|---|---|---|---|
| 주일예배 | streams 탭 | 장선기 목사 | **← 쇼츠 소스** |
| 수요예배 | 동영상 탭 | 김지훈·김유미·배윤영·황성재 목사 | 요청 범위 밖 |
| 새벽기도 | 동영상 탭 | 장선기 목사 | 에스겔 연속, 매일 |
| 유치아동부 | 동영상 탭 | — | 미성년자 노출, 사용 금지 |

### ⚠️ 주일예배 실황은 설교가 아니다

streams 영상은 **예배 전체**라 찬양·기도·봉헌·광고가 함께 들어 있다.
설교는 그중 일부 구간이다. 그래서 이 채널에서는:

- **먼저 설교 시작·끝 타임코드를 잡고 그 안에서만 구간을 고른다.**
  찬양 구간에서 클립을 뽑으면 Content ID에 그대로 걸린다.
- 찬양·봉헌 구간은 예외 없이 `has_worship_music: true`
- 회중 기도·찬양 시간에는 회중석 카메라가 잡히는 경우가 많다 →
  `congregation_visible: true` 를 의심하고 확인한다

## Content Strategy
- **Typical Video Length:** 쇼츠 30~90초 / 원본 주일예배 실황 60~85분
- **Upload Frequency:** 주 1회 (주일)
- **Best Performing Topics:** _데이터 없음_ — 실제 발행 후 채운다

## Goals
- **Growth Targets:** _미정_
- **Content Goals:** 설교 한 편 → 쇼츠 3편. 렌더까지 자동, 업로드는 사람이 승인 후 수동.

## 원본 확보 — Apify, 480p 고정

이 컨테이너에서는 yt-dlp가 유튜브 미디어를 못 받는다(서명 URL의 IP 불일치,
`docs/environment-constraints.md`). **Apify 액터로 우회한다.**

```bash
curl -sS -X POST \
  "https://api.apify.com/v2/acts/epctex~youtube-video-downloader/runs" \
  -H "Authorization: Bearer $APIFY_TOKEN" -H "Content-Type: application/json" \
  -d '{"startUrls":["<URL>"],"quality":"480","storageType":"apify"}'
```

완료되면 dataset의 `output.url` 을 `Authorization` 헤더와 함께 받아
`office/production/<idea-id>/source/sermon.mp4` 로 저장한다.

- **화질은 무조건 `480`.** (사용자 지시, 2026-08-31) 초당 과금이라 화질이
  곧 비용이다: 480p $0.00025/s · 720p $0.00045/s · 1080p $0.00075/s.
  80분 예배 기준 480p ≈ **$1.20**, 720p ≈ $2.16, 1080p ≈ $3.60.
- **`quality: "480"` 은 실제로 640x360을 준다.** SUN-2026-04-26에서 확인.
  480p(854x480)가 아니라 360p가 오고, 과금은 480p 요율로 된다. 그래서
  9:16 크롭 후 1080x1920까지 **약 7배** 업스케일이 걸린다 — 720p 소스의
  3.5배와 눈에 띄게 차이 난다.
- 사용자는 이 화질 저하를 알고도 **360p로 진행하기로 했다**(2026-08-31).
  말과 자막이 핵심이라는 판단이다. 더 선명한 편이 필요하면 그때만 `720`을
  쓰고, 기본은 `480`을 유지한다.
- 이미 받아둔 파일이 있으면 다시 받지 않는다. 용량만 줄이려면 재다운로드가
  아니라 ffmpeg로 축소한다 — 재다운로드는 추가 과금이다.

## 이 채널의 제작 규칙

파이프라인: `scripts/weekly_run.sh` · 자세한 것은 `docs/session-handoff.md`.

- **업로드 자동화 없음.** `render`가 마지막 단계이고
  `office/production/<idea-id>/publish-package.md` 는 승인용 초안이다.
- **찬양 음원** — 예배 실황의 찬양 구간은 Content ID 위험이 있다. CCLI는 예배
  사용 범위이지 유튜브 배포 범위가 아니다. 설교 발췌를 우선하고, 찬양이 깔린
  구간은 `has_worship_music: true` 로 표시해 승인 패키지에 경고가 따라가게 한다.
- **회중석 초상권** — 성도 얼굴이 잡히면 `congregation_visible: true`.
  크롭(`crop: left|right`)으로 피하거나 그 구간을 버린다.
- **음성 합성 금지.** 목사님 음성을 클로닝하거나 안 하신 말씀을 만들지 않는다.
  실제 하신 말씀을 자르는 것만 한다.
- **구간 선별은 사람(또는 전사본을 읽은 Claude)이 한다.** 자동 휴리스틱을 쓰지
  않으며, `clips.json` 의 `reason` 이 비어 있거나 템플릿 문구 그대로면
  렌더가 거부된다.

## 채널 ID 얻는 법

egress 정책상 이 컨테이너에서 youtube.com에 접근할 수 없어 핸들로부터
자동 조회가 불가능하다. 셋 중 아무거나:

1. YouTube Studio → 설정 → 채널 → 고급 설정 → "채널 ID" 복사
2. <https://www.youtube.com/@yeshim1126> 접속 → 페이지 소스에서
   `"channelId":"UC...` 검색
3. 브라우저 콘솔: `ytInitialData.metadata.channelMetadataRenderer.externalId`

채널 ID는 Tier 2~3 리서치 스킬에서만 쓰인다. **Tier 0 파이프라인은 설교 영상
URL만 있으면 채널 ID 없이 그대로 돈다.**

## 벤치마킹 대상

아직 없음. `.claude/context/instagram-accounts.md` 와 함께 채운다.
단, ScrapeCreators / Apify 호스트도 현재 egress에서 막혀 있어 리서치 스킬은
허용목록 확장 전까지 실행 불가다 — 키가 아니라 네트워크 문제다.
