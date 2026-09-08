# 키 세팅 — 방배동 예심교회 쇼츠 자동화

이 저장소의 `.env.example`은 **경쟁사 리서치용**으로 설계돼 있다. 교회 채널의
쇼츠 자동화는 그와 파이프라인이 다르므로, 필요한 키도 다르다. 이 문서는
예심교회 채널 기준으로 "무엇을 실제로 발급해야 하는가"를 정리한다.

## 0. 결론

| | 키 |
|---|---|
| 설교 클립 → 쇼츠 자동화 (핵심 워크플로) | **0개** |
| 영상 화면까지 AI가 보고 판단 | `GEMINI_API_KEY` 1개 |
| 다른 교회·기독교 채널 벤치마킹 | `SCRAPECREATORS_API_KEY` 추가 |
| 쇼츠 아웃라이어 탐지 / 릴스·틱톡 확장 | `TUBELAB_API_KEY`, `APIFY_TOKEN` 추가 |

**먼저 키 없이 Tier 0으로 한 편을 끝까지 만들어 보고, 막히는 지점이 생겼을 때
그 지점에 해당하는 키만 발급하는 것을 권한다.** 아래 키는 전부 사용량 과금이다.

---

## 1. 왜 키가 필요 없는가

예심교회 채널의 소스는 **이미 우리가 가진 주일 설교 영상**이다. 남의 콘텐츠를
긁어올 일이 없으므로 스크래핑 키가 파이프라인의 필수 경로에 없다.

| 단계 | 하는 일 | 필요한 것 | 키 |
|---|---|---|---|
| A | 원본 설교 영상 확보 | 파일 업로드 또는 `yt-dlp` | 없음 |
| B | 한국어 전사 (타임코드 포함) | `whisper.cpp` (로컬·무료) | **없음** |
| C | 쇼츠감 구간 30~90초 선별 | Claude가 전사본을 직접 읽음 | **없음** |
| D | 후킹 문장 / 제목 / 설명 작성 | `viral-youtube-shorts`, `viral-hooks` 스킬 | 없음 |
| E | 9:16 크롭 + 자막 번인 + 렌더 | FFmpeg / Remotion | 없음 |
| F | 업로드 | 사람이 직접 (승인 필수) | 없음 |

핵심은 C단계다. 설교는 토킹헤드이므로 **신호의 90% 이상이 말(전사본)에 있다.**
전사본만 있으면 Claude가 직접 읽고 클립 구간을 고를 수 있고, 여기에 별도의
영상분석 API는 필요 없다.

### Tier 0에서 대신 설치해야 하는 것 (키 아님, 무료)

이 컨테이너에는 지금 `ffmpeg`, `yt-dlp`, `whisper`가 **없다.** 렌더 계층을
설치하면 FFmpeg까지 같이 들어온다:

```bash
bash .claude/skills/openmontage/scripts/install.sh   # OpenMontage + FFmpeg + Piper
pip3 install yt-dlp                                   # 원본 영상 내려받기
npx remotion add @remotion/install-whisper-cpp        # 한국어 전사 (모델은 large-v3)
```

전사 모델은 `medium.en`이 아니라 **`large-v3`** 를 써야 한다. `.en` 모델은
영어 전용이라 한국어 설교에서 쓸 수 없다.

---

## 2. Tier 1 — `GEMINI_API_KEY` (권장, 무료 티어 있음)

발급: <https://aistudio.google.com/apikey>

이걸 넣으면 달라지는 것:

- `video-content-analyzer` 스킬이 **영상 자체를 본다.** 전사본에 안 잡히는
  표정·제스처·화면전환·자막 스타일을 읽는다.
- `tiktok-research` / `instagram-research`가 상위 영상을 자동 분석한다.

교회 채널에서 이게 값을 하는 경우는 두 가지다. 찬양·간증·행사 영상처럼 **말보다
그림이 중요한 콘텐츠**를 다룰 때, 그리고 잘 되는 기독교 쇼츠의 **편집 문법**을
분석할 때. 순수 설교 클립만 뽑을 거면 없어도 무방하다.

무료 티어가 있으나 한도와 정책은 바뀐다. 발급 전 요금 페이지를 확인할 것.

---

## 3. Tier 2 — `SCRAPECREATORS_API_KEY` (유료, 요청당 과금)

발급: <https://scrapecreators.com> · 문서: <https://docs.scrapecreators.com>

**키 하나로 가장 많은 스킬이 열린다 (13개).** 교회 채널에서 실제로 쓸 것:

| 스킬 | 예심교회에서의 용도 |
|---|---|
| `creator-profile-teardown` | 잘 되는 교회 채널 하나를 통째로 분해 |
| `outlier-post-finder` | 그 채널의 평균 대비 터진 영상만 골라냄 |
| `comment-mining` | 성도·비신자가 댓글에서 실제로 쓰는 말 수집 |
| `transcript-intelligence` | 남의 영상 전사 (우리 영상은 whisper로 무료) |
| `trend-discovery` | 기독교 니치의 뜨는 주제·해시태그 |

**주의: 요청 1건당 과금된다.** "구경"으로 돌리지 말고, 실제 리서치를 돌릴
때만 쓴다. 실행 전 대략 몇 콜이 나가는지 먼저 밝히는 것이 이 저장소의 규칙이다.

---

## 4. Tier 3 — 확장할 때만

| 키 | 열리는 것 | 발급 |
|---|---|---|
| `TUBELAB_API_KEY` | `youtube-research` — 유튜브 아웃라이어 탐지 | <https://tubelab.net/settings/api> |
| `APIFY_TOKEN` | `tiktok-research`, `instagram-research`, `x-research` | <https://console.apify.com/account/integrations> |

예심교회가 유튜브 쇼츠에만 집중한다면 `APIFY_TOKEN`은 미뤄도 된다. 릴스로
확장할 때 발급하면 된다. (Apify의 X/Twitter 액터는 유료 플랜이 필요하다.)

---

## 5. 넣지 않아도 되는 키

- `ELEVENLABS_API_KEY`, `REPLICATE_API_TOKEN`, `MINIMAX_API_KEY` — TTS·생성형
  미디어. **설교 원본 음성이 이미 있으므로 내레이션 합성이 필요 없다.**
- `PEXELS_API_KEY`, `PIXABAY_API_KEY`, `UNSPLASH_ACCESS_KEY`, `FREESOUND_API_KEY`
  — B롤·효과음 소스. 설교 클립은 원본 화면을 쓰므로 당장은 불필요.
- `ANTHROPIC_API_KEY` — MCP 서버 채점용. 이 워크플로와 무관.

### 목소리에 대한 판단

목사님 음성을 클로닝해 없던 설교를 합성하는 것은 **하지 않기를 권한다.** 기술로는
가능하지만 교회 콘텐츠에서 신뢰 문제가 크고, 실제로 하신 말씀을 자르는 것과
안 하신 말씀을 만드는 것은 성격이 완전히 다르다. 합성 음성은 자막 낭독이나
공지 영상처럼 화자가 사람이 아님이 명백한 곳에만 쓴다.

---

## 6. 키를 어디에 넣는가

이 세션은 **일회성 원격 컨테이너**에서 돈다. 세션이 끝나면 컨테이너가 회수되므로
`.env`에 넣은 키는 사라진다. 목적에 따라 위치가 다르다.

### (1) 웹/원격 세션에서 계속 쓸 키 — 환경 설정에 등록 (권장)

Claude Code 웹의 **environment 설정**에 환경변수로 등록하면 매 세션 자동 주입된다.
컨테이너가 새로 떠도 유지되는 유일한 방법이다.
→ <https://code.claude.com/docs/en/claude-code-on-the-web>

### (2) 로컬에서 돌릴 때 — `.env`

```bash
cd /home/user/shorts-factory
cp .env.example .env
# .env를 열어 필요한 키만 채운다. 안 쓰는 줄은 빈 값으로 둔다.
```

`.env`는 `.gitignore`에 있어 커밋되지 않는다.

### (3) `.claude/settings.json` — 실제 키는 절대 금지

이 파일은 **저장소에 커밋된다.** 현재 들어 있는 `LAST30DAYS_PYTHON`처럼 비밀이
아닌 경로 값만 둔다. API 키를 여기에 넣으면 GitHub에 그대로 올라간다.

---

## 7. 검증

```bash
python3 scripts/check_keys.py            # 존재 확인 + 실제 유효성 검사
python3 scripts/check_keys.py --offline  # 네트워크 없이 존재만 확인
```

이 스크립트는 무료 계정 조회 엔드포인트만 호출하며 크레딧을 쓰지 않는다.
TubeLab은 무료 확인 엔드포인트가 문서화돼 있지 않아 존재 여부만 본다.

렌더 계층 상태는 따로 본다:

```bash
python3 .claude/skills/studio-setup/scripts/doctor.py
```

---

## 8. 키와 별개로 채워야 할 것 — 채널 컨텍스트

키를 다 넣어도 `.claude/context/`가 예시 상태면 리서치 스킬이 붙잡을 대상이 없다.
이 파일들은 **사용자 소유 설정**이라 사람이 직접 채운다.

- `.claude/context/youtube-channel.md` — 예심교회 채널명·핸들·채널 ID,
  주 시청자(교인 / 지역 주민 / 비신자), 업로드 주기, 목표
- `.claude/context/instagram-accounts.md` — 벤치마킹할 교회·기독교 계정
- `.claude/context/tiktok-accounts.md`, `x-accounts.md` — 확장 시에만

채널 ID는 채널 페이지 소스에서 `UC`로 시작하는 24자 문자열이다.

---

## 9. 저작권 주의 (키보다 먼저 걸리는 문제)

- **찬양 음원.** 예배 실황의 찬양 부분을 그대로 쇼츠에 넣으면 유튜브 Content ID에
  걸릴 수 있다. CCLI 라이선스는 예배 사용 범위이지 유튜브 배포 범위가 아니다.
  설교 발췌를 우선하고, 찬양은 저작권 상태를 개별 확인한 것만 쓴다.
- **성도 얼굴.** 회중석이 잡힌 프레임은 크롭하거나 초상권 동의를 받는다.
- 배경음이 필요하면 유튜브 오디오 보관함이나 CC0 음원을 쓴다.

---

## 10. 첫 실행 순서

```bash
# 1. 키 없이 시작 — 렌더 계층부터 설치
bash .claude/skills/openmontage/scripts/install.sh

# 2. 현재 상태 확인
python3 scripts/check_keys.py --offline

# 3. .claude/context/youtube-channel.md 를 예심교회 정보로 채운다

# 4. 설교 영상 한 편으로 Tier 0 파이프라인을 끝까지 돌려본다
#    → 여기서 막히는 지점이 곧 발급해야 할 키다
```
