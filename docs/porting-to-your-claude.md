# 내 계정·내 키로 옮기기

이 파이프라인을 다른 사람의 Claude / 다른 컴퓨터로 그대로 이식하는 방법.

## 0. 먼저 알아야 할 것 — 지금 드는 돈은 대부분 이 컨테이너 탓이다

한 편(설교 1개 → 쇼츠 3개)에 지금까지 약 **$1.7** 이 들었다. 그런데 그 돈은
작업 자체가 아니라 **이 원격 컨테이너의 제약** 때문에 나갔다.

| 항목 | 여기(클라우드) | 내 컴퓨터 |
|---|---|---|
| 원본 다운로드 | Apify **$1.2~1.4** — yt-dlp가 막힘 | `yt-dlp` **무료** |
| 한국어 전사 | Gemini **약 $0.3** — whisper 못 받음 | `whisper.cpp large-v3` **무료** |
| 자막 싱크 보정 | `--retime` 클립당 1콜 (**유료**) | 불필요 — whisper는 시간이 안 밀림 |
| 화질 | 480 요청에 640×360 | 원본 1080p까지 그대로 |
| **합계** | **약 $1.7 / 편** | **$0 / 편** |

**내 컴퓨터에서 돌리면 키가 하나도 필요 없고, 화질과 자막 품질이 오히려 낫다.**
그래서 아래 A안을 권한다.

---

## A안 (권장) — 내 컴퓨터의 Claude Code

> **새 컴퓨터에 처음부터 까는 거라면 이 문서 말고 OS별 안내를 보라** —
> **`docs/설치-맥.md`** 또는 **`docs/설치-윈도우.md`**. 아무것도 없는 상태에서
> 시작해 쇼츠 3편이 나오고 자막을 고치는 데까지 전부 들어 있다.
> 이미 깔린 기계에서 만들기만 하면 **`docs/쇼츠-만들기.md`**.

교회 PC나 개인 PC에 Claude Code를 설치하고 거기서 돌린다.

### 1. 코드 가져오기

```bash
git clone -b claude/shorts-creation-automation-0xaii8 \
  https://github.com/sunki2024-star/shorts-factory
cd shorts-factory
```

> 저장소가 내 계정이 아니면 GitHub에서 **Fork** 한 뒤 내 주소로 clone 한다.
> 앞으로의 커밋이 내 저장소에 쌓여야 기록이 남는다.

### 2. 도구 설치

```bash
bash scripts/setup_render_env.sh --with-whisper
```

ffmpeg · yt-dlp · 한국어 폰트(Noto Sans KR) · whisper.cpp + large-v3 모델을
한 번에 깐다. 마지막에 출력되는 두 줄을 셸 프로필(`~/.zshrc` 등)에 붙인다:

```bash
export PATH="$HOME/whisper.cpp/build/bin:$PATH"
export WHISPER_MODEL="$HOME/whisper.cpp/models/ggml-large-v3.bin"
```

**모델은 반드시 `large-v3`.** `medium.en` 같은 `.en` 모델은 영어 전용이라
한국어 설교에 못 쓴다(스크립트가 넘기면 거부한다).

### 3. 확인

```bash
python3 scripts/sermon_shorts.py doctor    # 도구가 다 잡히는지
bash scripts/smoke_test_render.sh          # 렌더 계층 전체 검증, 네트워크 불필요
```

### 4. 돌리기

```bash
bash scripts/weekly_run.sh "https://www.youtube.com/watch?v=..."
```

전사까지 자동으로 가고 **구간 선별에서 멈춘다.** 거기서 Claude에게
"전사본 읽고 쇼츠감 3구간 골라줘"라고 하면 된다. 그다음 같은 명령을 다시
실행하면 렌더까지 이어진다.

멈추지 않고 **끝까지 자동으로** 가려면:

```bash
bash scripts/weekly_run.sh --auto "https://www.youtube.com/watch?v=..."
```

URL조차 없으면 생략해도 된다. 채널 streams 탭에서 **아직 안 만든 주일예배를
무작위로 하나** 뽑아 그대로 돌린다:

```bash
bash scripts/weekly_run.sh --auto
```

어떤 편이 남았는지 먼저 보고 싶으면:

```bash
python3 scripts/sermon_shorts.py sermons          # 목록 (무료, 메타데이터만)
python3 scripts/sermon_shorts.py sermons --pick   # 무작위 1편의 URL + idea-id
```

idea-id 는 **예배 날짜**에서 나온다. 오늘 날짜가 아니다 — 화요일에 돌려도
`SUN-2025-05-11` 처럼 그 예배의 주일이 붙는다.

구간 선별까지 모델이 한다. 로컬에 설치된 Claude Code를 `claude -p` 로 불러
쓰므로 구독으로 돌아가고 **추가 비용이 없다**(claude 명령이 없으면 Gemini로
넘어간다). 크롭 좌표도 영상 크기에서 자동 계산된다.

선별이 자동이어도 **강제되는 것은 그대로다** — 설교 구간 밖은 잘리고,
15초 미만은 버려지고, 근거가 없으면 렌더가 거부된다. 저작권 방어선은
모델의 판단이 아니라 파이프라인 구조에 있다.

> 결과물을 보고 마음에 안 드는 편이 있으면 `clips.json` 의 숫자만 고쳐서
> 다시 렌더하면 된다. 전부 다시 돌릴 필요 없다.

### 필요한 키

**없다.** Gemini도 whisper가 있으면 안 쓴다.

---

## B안 — 내 Claude Code(웹)에서 그대로

컨테이너 제약이 똑같이 따라오므로 **키 2개가 필요하다.**

### 1. 발급

| 키 | 발급처 | 용도 | 비용 |
|---|---|---|---|
| `GEMINI_API_KEY` | <https://aistudio.google.com/apikey> | 예배 구조 분석 · 전사 · 자막 재타이밍 | 무료 티어 있음, 초과분 종량 |
| `APIFY_TOKEN` | <https://console.apify.com> → Settings → Integrations | 원본 다운로드 (yt-dlp가 막히므로) | 액터가 **초당 과금**. 아래 참조 |

**Apify는 계정만 있으면 되고 구독은 사용량에 따라 다르다.** 이 세션에서 쓴
액터는 `epctex/youtube-video-downloader` 이고 요율은:

| 화질 | 초당 | 80분 예배 |
|---|---|---|
| 360p | $0.00015 | $0.72 |
| 480p | $0.00025 | $1.20 |
| 720p | $0.00045 | $2.16 |
| 1080p | $0.00075 | $3.60 |

> ⚠️ `quality: "480"` 을 요청해도 실제로는 **640×360** 이 오고 과금은 480p
> 요율로 된다. 확인된 동작이다. 선명한 결과가 필요하면 `720`을 써야 한다.

### 2. 환경변수로 넣기

**`.env` 파일을 만들지 말 것.** 클라우드 세션에서는 environment 설정에
환경변수로 등록한다 — 컨테이너가 새로 떠도 유지되고 디스크에 안 남는다.

claude.ai/code → 해당 environment 설정 → 환경변수에 위 두 개를 등록.
→ <https://code.claude.com/docs/en/claude-code-on-the-web>

`.claude/settings.json` 에는 **절대 키를 넣지 말 것.** 이 파일은 저장소에
커밋되므로 GitHub에 그대로 올라간다.

### 3. 네트워크 허용목록

이 환경은 기본적으로 유튜브가 막혀 있다. environment 설정의 허용목록에
아래를 넣어야 채널 조회·메타데이터가 된다:

```
youtube.com
*.youtube.com
*.googlevideo.com
*.ytimg.com
```

> 허용해도 **미디어 본문 다운로드는 여전히 403** 이다. 유튜브가 미디어 URL을
> 요청 IP에 묶어 서명하는데 프록시 egress IP가 달라서 그렇다. 그래서 Apify가
> 필요한 것이다. 자세한 실측은 `docs/environment-constraints.md`.

### 4. 확인

```bash
python3 scripts/check_keys.py    # 무료 조회 엔드포인트만 호출, 크레딧 안 씀
```

### 5. 돌리기

```bash
bash scripts/setup_render_env.sh                      # 매 세션 (컨테이너가 새로 뜸)
python3 scripts/sermon_shorts.py fetch SUN-2026-09-06 \
    --url "https://www.youtube.com/watch?v=..." --via apify --quality 480
python3 scripts/sermon_shorts.py transcribe SUN-2026-09-06 --backend gemini
python3 scripts/sermon_shorts.py clips      SUN-2026-09-06     # 여기서 사람이 판단
python3 scripts/sermon_shorts.py render     SUN-2026-09-06 --retime
```

`--retime` 은 클라우드에서 **반드시 붙인다.** Gemini 타임스탬프가 긴 청크에서
4~5초씩 밀리므로 그냥 렌더하면 자막이 어긋난다. 클립당 1콜이 더 나간다.

---

## 새 Claude에게 줄 첫 메시지

아래를 그대로 붙여넣으면 된다. `{{ }}` 두 곳만 채운다.

````text
방배동 예심교회(@yeshim1126) 유튜브 주일설교를 쇼츠로 만드는 파이프라인을
이어받았다. 저장소는 shorts-factory, 브랜치는
claude/shorts-creation-automation-0xaii8 이다.

먼저 이 셋을 읽어라. 이미 내려진 판단이 들어 있으니 뒤집을 이유가 없으면 따른다:
  docs/porting-to-your-claude.md      ← 어디서 돌릴지, 키가 뭐가 필요한지
  .claude/context/youtube-channel.md  ← 채널 구조와 제작 규칙
  docs/environment-constraints.md     ← 이 환경에서 뭐가 막히는지 실측 기록

환경: {{ 내 컴퓨터 / Claude Code 웹 }}

할 일:
1. bash scripts/setup_render_env.sh (로컬이면 --with-whisper 붙여서)
2. python3 scripts/sermon_shorts.py doctor 로 도구 확인
3. bash scripts/smoke_test_render.sh 로 렌더 계층 회귀 확인
4. 대상 설교: {{ 유튜브 URL — 없으면 streams 탭에서 골라달라고 할 것 }}
   원본 확보 → 설교 구간 탐지 → 한국어 전사 → 쇼츠감 3구간 선별
   → 제목/훅/설명 → 9:16 크롭 + 자막 번인 + 엔드카드 → MP4

지켜야 할 것:
- 업로드는 절대 자동으로 하지 않는다. 렌더까지만 하고 사람 승인을 받는다.
- 주일예배 영상은 예배 실황 전체다. 설교 구간을 먼저 잡고 그 안에서만
  자른다. 찬양 구간에서 뽑으면 Content ID에 걸린다.
- 회중석에 성도 얼굴이 잡힌 프레임은 크롭하거나 문제 구간으로 보고한다.
- 목사님 음성 합성/클로닝은 하지 않는다. 실제 하신 말씀만 자른다.
- 구간 선별은 전사본을 직접 읽고 판단하고, 왜 그 구간인지 근거를 붙인다.
- 유료 API를 쓰기 전에 대략 얼마가 나갈지 먼저 말한다.

이미 만든 편(주제 중복 피할 것):
- SUN-2026-07-12 [삼하 16:9-14] 상처의 말에 마음을 빼앗기지 말라 — 4편
- SUN-2026-04-26 [삼하 2:24-32] 이기는데 집착하지 말라. 잃는다. — 3편
````

## 옮길 때 같이 가져가야 하는 것

코드 말고 **판단이 쌓인 파일들**이 있다. 이게 없으면 다음 사람이 같은 실수를
반복한다.

| 파일 | 왜 필요한가 |
|---|---|
| `.claude/context/youtube-channel.md` | 주일설교가 "동영상" 탭이 아니라 **streams 탭**에 있다는 것, 찬양·회중석 규칙, 화질 방침 |
| `docs/environment-constraints.md` | 어떤 호스트가 막혔는지 실측 기록. 다시 삽질하지 않게 |
| `docs/key-setup.md` | 이 채널에 실제로 필요한 키의 티어 판단 |
| `office/production/*/qc.md` | 편별로 확인해야 할 것과 알려진 문제 |
| `office/production/*/clips.json` | 구간 선정 근거. 다음 편의 기준이 된다 |

전부 저장소에 커밋돼 있으므로 clone 하면 따라온다.

## 계정을 옮길 때 주의

- **지금 쓰는 Apify 계정(`bracing_linear`)과 Gemini 키는 이 세션 소유다.**
  내 것으로 바꾸면 그 키들은 더 이상 안 쓰이게 된다. 남겨둘 이유가 없으면
  각 콘솔에서 폐기하는 편이 안전하다.
- GitHub 저장소가 다른 사람 소유면 fork 하고 remote를 내 것으로 바꾼다:
  ```bash
  git remote set-url origin https://github.com/<내계정>/shorts-factory
  ```
- 업로드 자동화는 어느 안에서도 없다. 렌더까지가 끝이고 발행은 사람이 한다.
