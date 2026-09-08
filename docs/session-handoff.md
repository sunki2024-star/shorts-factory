# 다음 세션 인계 — 방배동 예심교회 쇼츠 자동화

갱신: 2026-08-31 (2세션차) · 브랜치: `claude/shorts-creation-automation-0xaii8`

## 지금까지 된 것

| | 상태 |
|---|---|
| 키 4종 주입 | **완료** — 전부 set. Gemini만 유효성까지 확인됨 |
| 렌더 계층 (ffmpeg · yt-dlp · 한국어 폰트 · OpenMontage) | **완료**, 단 매 세션 재설치 필요 |
| Tier 0 파이프라인 코드 | **완료** — `scripts/sermon_shorts.py` |
| 9:16 크롭 + 한국어 자막 번인 | **완료·검증됨** — `scripts/smoke_test_render.sh` PASS |
| 주간 반복 스크립트 | **완료** — `scripts/weekly_run.sh` |
| 설교 한 편 실제 처리 | **미완** — 아래 차단 사유 |
| `.claude/context/youtube-channel.md` | **미완** — 채널 정보 미확보 |

## 막힌 지점 — egress 정책

`youtube.com` / `googlevideo.com` / `huggingface.co` 가 이 컨테이너의 네트워크
정책에서 403으로 막힌다. 키 문제가 아니다. 실측 결과는
`docs/environment-constraints.md` 에 있다. 그래서:

- 설교 원본을 `yt-dlp`로 받을 수 없다 → `fetch` 단계 불가
- whisper `large-v3` 가중치를 받을 수 없다 → 로컬 전사 불가

**사용자가 택한 해법: egress 허용목록에 추가.** Claude Code 웹의 environment
설정에서 아래를 허용하고 **새 세션**을 띄우면 파이프라인이 그대로 돈다.

```
youtube.com
*.youtube.com
*.googlevideo.com
*.ytimg.com
huggingface.co          # whisper large-v3 가중치용
*.hf.co
cdn-lfs.huggingface.co
```

→ <https://code.claude.com/docs/en/claude-code-on-the-web>

허용목록 반영은 컨테이너 재생성이 필요하다. 이 세션에서 다시 찔러본 결과는
여전히 403이었다.

## 다음 세션 첫 명령

```bash
bash scripts/setup_render_env.sh        # 컨테이너가 새로 떴으므로 매번
python3 scripts/check_keys.py
python3 scripts/sermon_shorts.py doctor
bash scripts/smoke_test_render.sh       # 렌더 계층 회귀 확인
```

그다음, 허용목록이 반영됐는지 확인:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://www.youtube.com
```

`200`이면 진행, `000`/`403`이면 아직 반영 안 된 것이다.

## 한 편 돌리기

```bash
bash scripts/weekly_run.sh "<설교-유튜브-URL>"
```

3단계(구간 선별)에서 **일부러 멈춘다.** 전사본이 출력되면 그것을 읽고
`office/production/<idea-id>/clips.json` 을 채운 뒤 같은 명령을 다시 실행하면
렌더까지 이어진다. 구간 선별은 자동화하지 않았다 — 키워드 휴리스틱은
목사님의 지나가는 말과 설교가 꺾이는 문장을 구분하지 못한다.

`reason` 필드가 템플릿 문구 그대로면 렌더가 거부된다. 근거 없는 클립이
조용히 나가지 않게 하려는 장치다.

### 전사 백엔드

- `--backend whisper` — `WHISPER_MODEL` 이 `ggml-large-v3.bin` 을 가리켜야 한다.
  `.en` 모델을 넘기면 스크립트가 거부한다(영어 전용).
- `--backend gemini` — 이 컨테이너에서 유일하게 동작하는 경로. **유료.**
  설교 1편당 약 2콜(업로드 1 + 생성 1).
- `--backend auto` (기본) — whisper 먼저, 실패하면 gemini.

## 아직 필요한 정보

`.claude/context/youtube-channel.md` 가 예시 템플릿 그대로다. 채우려면:

- 채널 핸들 (`@...`)
- 채널 ID (`UC`로 시작하는 24자 — 채널 페이지 소스에서)
- 대상 설교 영상 URL

이 파일은 사용자 소유 설정이므로 내용을 보여주고 확인받은 뒤에 쓴다.

## 지켜지고 있는 규칙

- 파이프라인 어느 단계도 업로드하지 않는다. `render` 가 끝이고,
  `publish-package.md` 는 승인용 초안이다.
- 찬양 음원(`has_worship_music`)과 회중석 노출(`congregation_visible`) 플래그가
  승인 패키지까지 따라간다. CCLI는 예배 사용 범위지 유튜브 배포 범위가 아니다.
- 음성 합성·클로닝 없음. 실제 하신 말씀을 자르기만 한다.
- 유료 API는 콜 수를 먼저 밝히고 쓴다.

## 리서치까지 하고 싶을 때

`SCRAPECREATORS_API_KEY` / `APIFY_TOKEN` 은 주입돼 있지만 **해당 API 호스트도
egress에서 막혀 있다**(`api.scrapecreators.com`, `api.apify.com`). 벤치마킹
리서치를 하려면 이 두 호스트도 허용목록에 넣어야 한다. 넣기 전에는 Tier 2~3
스킬이 전부 실패한다 — 키가 아니라 네트워크 때문이다.
