# 이 컨테이너의 네트워크 제약 — 2026-08-31 실측

원격 세션 컨테이너의 **egress 정책**이 일부 호스트를 막고 있다. 키 문제가
아니라 조직 네트워크 정책이므로, 재시도해도 뚫리지 않는다. 아래는 추측이
아니라 이 컨테이너에서 실제로 찔러본 결과다.

확인 방법:

```bash
curl -sS "$HTTPS_PROXY/__agentproxy/status"   # 최근 차단 기록이 남는다
```

## 실측 결과

| 호스트 | 상태 | 영향 |
|---|---|---|
| `youtube.com`, `googlevideo.com` | **403 차단** | **yt-dlp로 설교 원본을 받을 수 없다** |
| `huggingface.co`, `cdn-lfs*` | **403 차단** | **whisper large-v3 가중치를 받을 수 없다** |
| `openaipublic.azureedge.net` | 403 차단 | OpenAI whisper 가중치도 불가 |
| `api.scrapecreators.com` | 403 차단 | Tier 2 리서치 스킬 전부 불가 |
| `api.apify.com` | 403 차단 | tiktok/instagram/x-research 불가 |
| `deb.debian.org`, `johnvansickle.com` | 403 차단 | apt / ffmpeg 정적 빌드 직접 다운로드 불가 |
| `generativelanguage.googleapis.com` | **열림** | Gemini 사용 가능 (키 검증 통과) |
| `pypi.org`, `files.pythonhosted.org` | 열림 | pip 사용 가능 |
| `registry.npmjs.org` | 열림 | npm 사용 가능 |
| `github.com`, `raw.githubusercontent.com` | 열림 | OpenMontage 설치 가능 |
| `archive.ubuntu.com` | 열리지만 일부 패키지 404 | `apt-get install ffmpeg` 실패 |

## 그래서 우회한 것

`scripts/setup_render_env.sh`가 아래를 자동으로 처리한다.

- **ffmpeg** — apt가 죽으므로 PyPI의 `imageio-ffmpeg` 휠에 들어 있는 정적
  빌드(johnvansickle 7.0.2와 동일물)를 꺼내 `/usr/local/bin/ffmpeg`에 링크.
- **한국어 폰트** — 컨테이너에 CJK 폰트가 하나도 없어서 자막이 두부(□□□)로
  탄다. Google Fonts는 막혔지만 npm은 열려 있어 `@fontsource/noto-sans-kr`의
  한국어 서브셋(woff2)을 받아 `fontTools`로 TTF로 변환한다. libass는 TTF만 읽는다.
- **자막 좌표계** — 이 ffmpeg 정적 빌드에는 libfreetype이 없어 `drawtext`를
  못 쓴다. `subtitles`(libass)를 쓰는데, SRT에는 해상도 정보가 없어 libass가
  384x288 기준으로 스타일 수치를 해석한 뒤 확대한다(= 자막이 화면 위로 뜬다).
  그래서 `PlayResX/Y`를 1080x1920으로 명시한 **ASS**를 생성해 실제 픽셀 단위로
  글자 크기와 여백을 지정한다.

## 아직 막혀 있는 것 — 사람이 풀어야 함

### 1. 설교 원본 확보 (필수 경로) — 허용목록으로도 안 풀림

**2026-08-31 갱신.** 사용자가 `youtube.com`·`*.googlevideo.com`을 허용목록에
추가했고, 호스트는 실제로 열렸다. 채널 조회와 영상 목록까지는 된다:

```bash
yt-dlp --js-runtimes node --flat-playlist \
  --print "%(id)s | %(duration)s | %(title)s" \
  "https://www.youtube.com/@yeshim1126/videos"      # 정상 동작
```

**그런데 미디어 본문(video/audio bytes)은 여전히 403이다.** 원인은 egress가
아니라 **서명 URL의 IP 불일치**다. 직접 확인한 내용:

- yt-dlp가 받아온 미디어 URL에는 `ip=fda3:e722:ac3:10:...` (컨테이너 내부
  IPv6 ULA)가 서명돼 박혀 있는데, 실제 요청은 프록시 egress
  `mip=160.79.106.128` 에서 나간다.
- 유튜브는 미디어 URL을 요청 IP에 묶어 서명하므로, 메타데이터를 받은 IP와
  본문을 받는 IP가 다르면 403을 준다.
- `--force-ipv4`, player_client 교체(`tv`/`ios`/`mweb`/`android_vr`/
  `tv_embedded`/`web_embedded`), `--downloader ffmpeg` 전부 실패.
  ffmpeg 경로는 403은 넘겼지만 정적 빌드가 SIGSEGV(-11)로 죽는다.
- 반복 시도 후에는 "Sign in to confirm you're not a bot" 봇 탐지까지 붙는다.

모든 트래픽이 프록시 IP 풀을 통해 나가는 한 컨테이너 안에서는 못 고친다.
**허용목록을 더 넓혀도 해결되지 않는다.**

- **(A) 로컬에서 실행** — 가정용/교회 회선은 IP가 하나로 고정이라 이 문제가
  없다. `scripts/sermon_shorts.py`가 그대로 돈다. **현재로선 이쪽이 유일하게
  확실한 길이다.**
- **(B) 원본 파일을 직접 넣기** — 이미 받아둔 mp4가 있으면
  `office/production/<idea-id>/source/sermon.mp4` 에 놓고 `fetch`를 건너뛰면
  된다. 나머지 단계는 컨테이너 안에서 전부 돈다.

### 2. 한국어 전사

`whisper large-v3` 가중치를 받을 수 없다. 대안:

- **로컬 실행 시** — whisper.cpp + `ggml-large-v3.bin`. 무료·무제한이고
  품질이 가장 좋다. **`medium.en` 같은 `.en` 모델은 영어 전용이라 쓸 수 없다.**
  (`sermon_shorts.py`가 `.en` 모델을 넘기면 거부한다.)
- **이 컨테이너에서** — `--backend gemini`. Gemini는 열려 있고 키도 유효하다.
  **유료 API이며 오디오 1건당 1콜**이 나간다. 설교 한 편(40분 내외)이면
  업로드 1콜 + 생성 1콜.

## 막히지 않은 것 — 렌더는 여기서 완전히 돈다

`bash scripts/smoke_test_render.sh` 가 원본 영상도 네트워크도 없이
9:16 크롭 + 한국어 자막 번인 + MP4 렌더를 끝까지 검증한다. 2026-08-31 기준 PASS.
