# donotreadagain (dnr)

> **Read once, never again.** 비싸게 한 번 전사하고, 그 결과를 파일 자신에게 박아 — AI가 같은 파일을 다시 파싱하지 않게 하는 자기설명 파일 규격 + 얇은 툴.

이 문서는 dnr의 **vision/design 문서**다. 정식 스펙(`spec/dnr-0.1.md`)과 구현은 여기서 파생된다.

---

## 0. TL;DR

비싸게 읽는 파일(PDF·오디오·영상·이미지·office)을 **한 번 충실히 전사**해서, 그 전사 + 메타데이터를 **파일 자신의 네이티브 메타 슬롯에 통일 규격(서명된 JSON)으로 임베드**한다. 그러면 파일이 "자기설명적"이 되어, 어떤 AI든 파일을 열면 재파싱 없이 전사를 바로 쓴다. 폴더 단위 **재생성 가능한 인덱스**(`.dnr.db`)가 크로스파일 쿼리를 받친다.

- **파일 = canonical 진실** (위치 무관, 서명됨)
- **인덱스 = 파생 캐시** (언제든 재생성)
- **무설치 소비**: AI가 `sqlite3`/`exiftool`로 그냥 읽음. 생산(전사·임베드)만 `uvx` 즉석 실행.

---

## 1. 문제 (Why)

AI 하네스가 같은 PDF/오디오를 읽을 때마다 OCR·전사를 다시 돌린다. 시간·토큰·비용 낭비이고, 전사는 결정론적 작업이라 **한 번만 하고 캐시**하면 된다. 기존 캐시들은 결과를 외부 저장소에만 두지만, dnr은 **결과를 파일 자신에 실어** 파일이 어디로 가든 자기를 설명하게 만든다.

---

## 2. 핵심 아이디어 — 자기설명 파일

1. 파일을 한 번 전사한다 (verbatim, 아래 §8).
2. 전사 + 출처(provenance) + 쿼리용 필드 + 서명을 **하나의 JSON 레코드**로 만든다.
3. 그 레코드를 **파일의 네이티브 메타 슬롯**에 박는다 (PDF→XMP, mp3→ID3 …).
4. 소비자(AI)는 파일을 열 때 레코드를 먼저 보고, **검증되면 전사를 그대로 쓰고 재파싱을 건너뛴다.**
5. 폴더를 인덱싱하면 레코드들이 쿼리 가능한 테이블로 모인다.

---

## 3. 아키텍처 — 2층

```
파일 (canonical 진실, 위치무관)            인덱스 .dnr.db (파생, 재생성가능)
┌────────────────────────────┐           ┌──────────────────────────────┐
│ dnr 레코드 (XMP/ID3 슬롯)    │  harvest  │ 코어컬럼 + fields/extras       │
│  content_hash, transcript,  │ ────────▶ │ + path, whole_hash, mtime      │
│  provenance, fields, sig    │           │ + FTS5(본문검색)               │
└────────────────────────────┘           └──────────────────────────────┘
   ▲ 비싸게 1회 전사·임베드·서명                ▲ 싸게 언제든 재생성
   생산자(uvx, 1회)                          소비자 = AI (sqlite3, 무설치)
```

**분담 규칙 — 파일엔 "콘텐츠 사실"만, 인덱스엔 "위치·카탈로그 사실"만.**

| 정보 | 어디에 | 이유 |
|---|---|---|
| content_hash, transcript, provenance, fields, sig | **파일 + 인덱스** | 어디 있든 참인 사실 (위치 무관) |
| path | **인덱스 전용** | 이사 가면 바뀜 (파일이 자기 위치를 들면 이동마다 자기를 고쳐 써야 함) |
| whole_hash | **인덱스 전용** | 파일 전체 바이트 해시 — 자기 안에 자기 해시 못 넣음 (닭-달걀) |
| mtime, indexed_at | **인덱스 전용** | 파일시스템/카탈로그 기록 |

판단 기준: *"이 파일을 인덱스 없이 이메일로 보냈을 때 따라가야 하나?"* → 그렇다면 파일, 아니면 인덱스.

---

## 4. 레코드 스키마 (파일에 박는 것)

```jsonc
{
  "dnr": "0.1",                          // 버전 = "이 파일엔 dnr 레코드 있음" 마커
  "content_hash": "sha256:…",            // 디코딩 콘텐츠 해시 (정체성 + 무효화 키, §6)
  "source": {
    "mime": "application/pdf",
    "bytes": 184213,
    "pages": 42
  },
  "transcript": {                        // ← verbatim·완전. 요약 아님 (§8)
    "format": "text/markdown",
    "lang": "ko",
    "text": "# 판결…\n…전체 본문 그대로…",
    "segments": [ { "t": 0.0, "text": "…" } ]   // AV용 시간코딩, 선택
  },
  "provenance": {                        // "어떻게 전사했나" (§8)
    "method": "vision",                  // text-extract | vision | ocr | asr | none
    "transcriber": "claude-opus-4-vision",
    "version": "…",
    "instruction_id": "dnr-verbatim-1",  // 어떤 전사 계약을 따랐나
    "prompt_hash": "sha256:…",           // 실제 프롬프트의 해시
    "params_hash": "sha256:…",
    "confidence": 0.94,
    "created_at": "2026-06-20T08:00:00Z"
  },
  "fields": {                            // 쿼리용 컬럼 (도메인 자유 추가)
    "title": "…",
    "summary": "…",                      // 명시적 손실 요약 (≠ transcript)
    "start_date": "2024-04-01",
    "tags": ["계약", "손해배상"]
  },
  "extras": { },                         // 포맷별 부산물 (duration, 시트수 등)
  "sig": {                               // 서명 (§9)
    "alg": "ed25519",
    "key_id": "…",
    "value": "base64…"                   // sign(JCS(record − sig))
  }
}
```

- `path`·`whole_hash`는 **여기 없음** (인덱스 전용, §3).
- `transcript`(축자·완전)와 `fields.summary`(손실 요약)는 **절대 안 섞는다** (§8).
- **이미-텍스트 파일**(txt/csv/json/md)은 `transcript` 생략 + `method: "none"`(전사 안 함). `fields`만 채워 사이드카로 인덱스에 합류하고, 본문은 인덱스가 원본에서 직접 읽는다 (§15).

---

## 5. 캐리어 매핑 — 한 JSON, N 슬롯

같은 JSON 레코드를 각 포맷의 **전용 제3자 슬롯**에 문자열로 박는다. 고유 키(`dnr`)를 써서 네이티브 태그와 충돌하지 않는다.

| 포맷 | canonical 슬롯 |
|---|---|
| PDF · JPEG · PNG · TIFF · MP4/MOV | XMP, 네임스페이스 `dnr`, 프로퍼티 `dnr:record` |
| MP3 | ID3v2 `TXXX:dnr` |
| FLAC · OGG | Vorbis comment `DNR=` |
| M4A | MP4 atom |
| docx · xlsx · pptx | OOXML 커스텀 XML 파트 |
| 슬롯 없음 · 쓰기불가 · 대용량 · 위험 | **사이드카** `<file>.dnr.json` |

인덱서는 레코드를 *어디서 뽑았든 같은 JSON*으로 동일하게 파싱한다.

---

## 6. content_hash — 결정론적, 포맷별 canonical

**가장 중요한 단일 원시값.** 캐시 유효성·재전사 판단·이동 매칭이 전부 여기 걸린다.

### 왜 raw 바이트가 아니라 디코딩 콘텐츠인가
"파일 바이트에서 메타 영역만 뺀다"는 PDF·OOXML에서 **결정론적이지 않다** — 라이브러리가 저장 때 컨테이너 전체를 재직렬화(객체 재번호·재정렬·Flate 재압축, ZIP 재압축)하기 때문. 그래서 **디코딩된 콘텐츠**를 해시한다.

### 포맷별 정의
- **PDF** = `sha256( 페이지 순서대로: 압축 푼 content-stream 바이트 ++ 이미지 XObject 바이트 )`
  - 객체 재정렬·Flate 재압축·메타 쓰기에 **불변**, 실제 내용 편집엔 민감.
  - 조건: 임베드가 content/image 스트림을 **재인코딩하면 안 됨**(컨포먼스 게이트, §16).
- **mp3 · FLAC** = `sha256( ID3/Vorbis 태그 제외한 오디오 프레임 바이트 )`
- **이미지(JPEG/PNG)** = `sha256( 디코딩 픽셀 + 치수 )`
- **OOXML** = `sha256( dnr 파트 제외, 정렬된 (멤버경로, 압축푼 멤버 해시) 매니페스트 )`

### 정규화 고정 (스펙 v0.1)
- 해시 알고리즘: **SHA-256**
- 레코드 JSON: **RFC 8785 JCS** (canonical 직렬화)
- 모든 텍스트: **NFC** 정규화
- 추출 **프로파일 id** 명시 (`dnr-pdf-content-1` …) — 동일 프로파일끼리만 해시 일치 보장
- **골든 테스트 벡터** 공개 (구현 간 자기검증)

---

## 7. 캐시 무효화 — 해시 3트리거

저렴→비싼 순서로 레이어드:

| 무엇이 바뀜 | 신호 | 결과 |
|---|---|---|
| 아무것도 | stat(size, mtime) 동일 | **스킵** (파일 안 엶) |
| 메타만 (태그 등) | whole_hash만 변경 | **재인덱스만** (재전사 X) |
| 본문(내용) | **content_hash 변경** | **재전사** + 재인덱스 |
| 더 좋은 모델 출시 | transcriber/version 비교 | **의도적 재전사** |

핵심: **재전사 트리거는 `content_hash` 변경 OR 모델 업그레이드뿐.** 파일 바이트가 달라져도(메타만 바뀜) 비싼 전사는 안 돈다. `method`별로 정밀 제어 가능 — 새 ASR 나오면 `asr`로 뜬 것만 재전사하고 `text-extract`는 건너뜀.

이동(`mv`)은 바이트 불변 → 해시 불변 → 인덱스 `path` 컬럼만 갱신, 재전사 0.

---

## 8. 전사 계약 (Transcription Contract)

**"재파싱 스킵"이 정당하려면 transcript를 읽는 게 원본을 읽는 것과 같아야 한다.** transcript가 요약이면 정보가 날아가 전제가 무너진다. 그래서:

### 원칙: transcript = 축자(verbatim)·완전(complete)
- 전체 내용을 빠짐없이 — 절단·"…"·"이하 생략" 금지
- **요약·의역·논평 금지**, 원문 순서·구조 보존(제목/목록/표/페이지구분/화자/타임스탬프)
- 표는 prose 요약이 아니라 구조 그대로(마크다운 표)
- 불확실·판독불가는 추측·생략하지 말고 명시 (`[illegible]`, `[unclear: …]`)
- 언어 보존(번역 시 표시)
- `transcript`(축자) ≠ `fields.summary`(명시적 손실 요약) — **절대 안 섞음**

### 방법 위계 (text-extract > vision > ~~ocr~~)

| method | 오타 | 환각 | 신뢰 | 언제 |
|---|---|---|---|---|
| **text-extract** | 없음 | 없음 | **최고** | 깨끗한 텍스트 레이어 있을 때 (무손실·공짜) |
| **vision (모델)** | 적음 | 드묾(검증으로 차단) | 높음 | 스캔·이미지·표/서식 중요할 때 |
| ~~ocr (전통)~~ | **많음** | 없음 | 낮음 | 오프라인·극단 비용절약 최후수단만 |
| `none` | — | — | — | 이미-텍스트 파일(txt/csv/json/md) — 전사 안 함, fields만 |

**전통 OCR은 오타가 많아 verbatim 목표엔 부적격** → 권장 경로에서 강등. 기본은 *"텍스트 레이어 있으면 추출, 없으면 비전 모델"*. 비전 모델의 드문 약점(환각·누락)은 verbatim 계약 + (법률 등 고위험은) **교차검증/2회 diff**로 잡는다. 2026년 기준 비전 LLM이 OCR을 사실상 대체.

### 기록 (provenance)
`method` + `transcriber` + `version` + `instruction_id` + `prompt_hash`를 박아, **"무슨 방법·모델·지시로 만든 verbatim인가"** 가 검증·재현 가능. `method`만 보면 신뢰도가 바로 읽힘.

> 한계 정직: verbatim은 *설계상 손실(요약)*을 0으로 만드는 것. *추출 오류*(모델 환각 등)는 `method`+`confidence`로 노출하고 고위험은 verify 모드로 보강.

---

## 9. 서명 & 신뢰

unsigned 레코드는 위조·prompt-injection·오염에 무방비. 그래서 **레코드를 서명한다.**

- `record_hash = sha256(JCS(record − sig))`, **Ed25519** 서명(서명 64B·공개키 32B — 메타에 가뿐).
- 레코드가 둘을 묶음: `content_hash`(레코드 ↔ 콘텐츠) + `sig`(레코드 ↔ 생산자).
- **소비자 신뢰 등급:**

| 상태 | 행동 |
|---|---|
| 신뢰키 서명 ✓ **AND** content_hash 재계산 일치 ✓ | **skip-reparse 허용** (전사 그대로 사용) |
| 미서명 · 미신뢰키 · 해시 불일치 | **검색/인덱스용만**, 원본은 평소대로 읽기, transcript는 "untrusted 데이터"로 감싸 **절대 지시문으로 안 먹임** |

단일 사용자: 로컬 키페어 1개 + 내 공개키만 신뢰목록 → 남이 만든 파일 위조 즉시 차단. **no-install과 양립**(검증은 pubkey 파일 하나).

---

## 10. 소비자 계약 (Consumer Contract)

- **읽기:** 레코드 있고 (서명 신뢰 + content_hash 일치) → 전사 사용, 재파싱 X. 아니면 → 평소대로 읽음 (**에러 아님, 폴백**).
- **자가 채움 (lazy):** 어떤 파일을 *실제로 읽을 때* 미전사면 그 한 파일만 전사·레코드화(어차피 읽을 비용). **단, 쿼리에 답하려 여러 파일을 선제 전사해야 하면 → 사용자에게 물어 승인분만**(비용 폭탄 방지). 폴더 통째는 명시적 `dnr ingest`.
- **이동 내성:** 정체성은 content_hash → 옮겨도 인덱스 path만 갱신.
- **보안 자세:** 임베드 레코드는 **기본 untrusted**. 서명·해시로만 신뢰 승격. transcript는 절대 지시문 취급 안 함.
- **additive:** 레코드 없는 파일은 오늘과 똑같이 동작(무회귀). 단, "zero-risk"는 *채택자가 악성 파일을 만나는* 경우엔 성립 안 함 → 그래서 서명이 필수.

---

## 11. 인덱스

폴더당 숨김 파일 하나 **`.dnr.db`** (SQLite + FTS5, 나중에 sqlite-vec). 폴더 따라 이동, **재생성 가능** — 진실은 파일에.

> **index ≠ ingest.** 인덱싱은 *이미 박힌 레코드를 수확*하는 싼 작업(전사 안 함). 전사+임베드(ingest)는 별개. 인덱싱·쿼리는 **CLI로 강제**(`dnr index`/`dnr query`) — 프로즈 지시는 모델이 잘 안 따름.

### 기본 테이블 = 고정 계약 (이름·컬럼·타입 모두 스펙이 박음)

에이전트는 이 스키마를 **스킬로 미리 주입**받으므로, 아무 `.dnr.db`나 만나면 introspection 없이 **즉시 쿼리**한다. 이게 "쿼리 portable"의 정체.

```sql
CREATE TABLE dnr (                 -- 테이블 이름 'dnr' 고정
  content_hash TEXT PRIMARY KEY,   -- 정체성 / 조인키
  path         TEXT NOT NULL,      -- 현재 위치
  mime         TEXT,
  bytes        INTEGER,
  mtime        INTEGER,
  indexed_at   TEXT,
  method       TEXT,               -- text-extract|vision|ocr|asr|none
  transcriber  TEXT,
  version      TEXT,
  lang         TEXT,
  title        TEXT,
  summary      TEXT,
  tags         TEXT,               -- JSON array
  transcript   TEXT,               -- 본문 (FTS 소스)
  fields       TEXT,               -- JSON: 도메인 추가필드 (start_date, court…)
  extras       TEXT                -- JSON: 포맷별 (duration…)
);
CREATE VIRTUAL TABLE dnr_fts USING fts5(title, summary, transcript, content='dnr');
CREATE TABLE _dnr_readme(...);     -- 자기설명 (스킬 없는 에이전트용 in-band 백업)
```

**블라인드 쿼리가 안 깨지려면 스펙이 강제하는 2가지:**
1. **이름 고정** — 테이블은 항상 `dnr`, 풀텍스트는 `dnr_fts`.
2. **타입(affinity) 고정** — SQLite는 동적 타입이라 폴더마다 affinity가 다르면 쿼리가 어긋남 → 위 타입을 normative하게 박는다.

예시 쿼리 (어느 dnr 폴더에서나 그대로):
```sql
SELECT path FROM dnr WHERE method='vision' AND lang='ko';
SELECT path FROM dnr_fts WHERE dnr_fts MATCH '손해배상';
SELECT path FROM dnr WHERE json_extract(fields,'$.start_date') > '2024-01-01';
```

### 그 너머는 자유
- 서브 테이블·뷰·벡터 인덱스, 인덱스를 *어떻게* 빌드하는지 = 구현 자유.
- **DuckDB** = 선택적 크로스폴더 쿼리 렌즈(여러 `.dnr.db` ATTACH), 스토어 아님.
- **도메인 필드**: 기본은 `fields` JSON + `json_extract`(블라인드 가능). 자주 쓰면 **프로파일**로 진짜 컬럼 승격(예: `legal` → court·case_no·start_date) — 승격분은 `_dnr_readme`에 적혀 에이전트가 인지.

**스킬이 들고 다니는 것 = ① 위 고정 스키마 + ② 예시 쿼리.** 그래서 첫 만남에 바로 쿼리. 스킬 없는 에이전트는 `_dnr_readme` 한 번 읽고 부트스트랩.

### 런타임 동작 (빌드 · 쿼리 · 동시성)

- **index ≠ ingest** (재강조): 인덱싱은 *수확만*(싸다), 전사는 별개.
- **cold 폴더**: 한 번도 인제스트 안 된 폴더 → 있는 레코드만 수확 + 텍스트 본문, **미디어는 전사 없이 "pending" 행**(path·hash, transcript 비움). 전사는 명시적 `dnr ingest` 또는 query-driven(§10: 에이전트가 물어보고 승인분만).
- **쿼리 전 증분 스캔**: `dnr query`가 쿼리 직전 가벼운 stat 스캔으로 인덱스 최신화 — 안 바뀐 99%는 stat-스킵이라 거의 공짜. `--no-scan`으로 끔.
- **동시성** (plain SQLite 유지, *Turso 아님*): `.dnr.db` = **WAL 모드** + 쓰기락 · 같은 파일 중복 전사 = **content_hash별 락**(claim) · 임베드 = **temp+rename 원자적** · 크로스머신 = *인덱스를 동기화하지 말고 파일을 동기화한 뒤 각자 재생성*(인덱스는 재생성 가능), 파일-레코드 split-brain은 서명+last-writer.

---

## 12. 배포 — 무설치

**"AI가 런타임, 지시사항이 프로그램."**

- **소비(읽기/쿼리)** = `sqlite3`/`exiftool` 등 이미 있는 도구. dnr 설치 0.
- **생산(전사/임베드)** = `uvx donotreadagain ingest <file>` 즉석 실행, 파일당 1회. 상주 데몬·MCP 강제 없음.
- 진짜 무거운 코드는 **전사**뿐. 임베드/인덱스/읽기는 ubiquitous 도구 위 얇은 glue.
- 발견성: 복붙용 `AGENTS.md` 스탠자 + `_dnr_readme` + 공개 spec URL.

---

## 13. 비협상 안전 3종 (임베드를 택한 이상 필수)

1. **서명** — unsigned는 skip-reparse 못 함 (§9).
2. **원자적 쓰기** — 원본 직접수정 금지. 복사본에 쓰고 → content_hash 불변·네이티브 태그 보존 검증 → temp+fsync+rename으로 교체.
3. **사이드카 폴백** — 대용량(transcript 큼)·서명/read-only·기밀/증거·소셜 재인코딩 경로 파일은 임베드 대신 `.dnr.json`.

---

## 14. 알려진 리스크 (8-에이전트 점검 결과, 정직하게)

| 리스크 | 대응 |
|---|---|
| content_hash가 PDF/OOXML에서 raw-바이트론 비결정 | **디코딩 콘텐츠 해시 + 컨포먼스 게이트**(§6, §16) |
| unsigned 레코드 = prompt-injection·위조·TOFU 오염 | **Ed25519 서명 + untrusted-default**(§9) |
| 임베드 vs 단순 캐시: n=1엔 한계가치 낮음 | 임베드는 *자기설명·휴대성·표준* 야망을 위한 선택. 즉시 효용은 인덱스/캐시가, 차별점은 in-file이 — 둘 다 안고 감 |
| 공유 시 AI 요약·엔티티 유출 / 법률 원본 변형 | **사이드카 기본(위험 파일) + 기밀 플래그 + strip 명령** |
| 채택 cold-start, OKF가 유사 framing 선출시 | **단일 사용자 툴 먼저**, OKF 사이드카도 함께 emit해 공존 |
| write(전사) 비용 + transcriber_version 재전사 세금 | one-time·캐시됨 + `method`별 정밀 재전사(text-extract는 재전사 면제) |
| verbatim transcript = 큰 페이로드 | 사이드카 폴백이 받음(§13) |

> 점검은 "캐시부터, 임베드는 보류"를 권했지만, **자기설명 파일 표준**이라는 비전을 위해 임베드-퍼스트를 택하되 — 점검이 건 전제(canonical 해시 + 서명)를 **먼저** 푼다.

---

## 15. 범위

dnr은 분리된 **두 가치**를 준다 — 파일마다 적용 범위가 다르다:
1. **전사 캐시** (비싸게 읽는 걸 한 번만) — 미디어 전용.
2. **파생 필드 + 통합 인덱스** (title/summary/tags/날짜로 검색·라우팅) — 모든 파일에 유용.

| 파일 종류 | 전사 | 인덱스 합류 | 캐리어 |
|---|---|---|---|
| PDF·오디오·영상·이미지 | ✅ verbatim | ✅ | in-file (또는 사이드카) |
| txt·csv·json·md (작음) | ❌ `method:"none"` | ✅ fields-only | **사이드카만** (본문은 원본에서 직접 읽음) |
| 대용량 CSV/JSON/로그 | ❌ | ✅ **요약+스키마만** | 사이드카 (본문은 코드/pandas로) |

**안 하는 것:**
- **본문 복사 금지** — 이미-텍스트 파일 본문을 사이드카에 베끼지 않음(중복·동기화 위험). 인덱스가 원본에서 직접 읽음.
- **서명/read-only 파일** — 변형 금지 → 사이드카 또는 제외.
- **소셜/이메일 재인코딩 전송** — 메타 stripping → in-file 신뢰 못 함. dnr은 blob 보존 전송(git/rsync/S3/NAS)에서 신뢰.

> 텍스트 파일 지원은 *통일성 보너스*지 코어(미디어 재파싱)가 아니다 → **옵트인·후순위**. 미디어 경로부터 세운 뒤 붙인다.

---

## 16. 로드맵 — v0.1 "코어" 먼저

점검 결론: 아래가 얼기 전엔 나머지가 다 불안정. **이게 진짜 conformance 표면.**

**기둥 1 — Canonicalization 코어**: 포맷별 content_hash(디코딩) + SHA-256/JCS/NFC/프로파일/골든벡터.
**기둥 2 — Signing 코어**: Ed25519 over JCS(record−sig) + 신뢰 등급.
**컨포먼스 게이트** (캐리어별 테스트):
1. `embed(record)` 후 **content_hash 불변** (라운드트립)
2. `embed` 후 **네이티브 태그 보존**
3. `embed`는 **원자적**

대상: **PDF + mp3** 둘부터. 통과하면 임베드-퍼스트가 기술적으로 구제됨.

### 🔬 make-or-break 실험 (첫 코드)
```
real.pdf → content_hash(h0) → XMP 임베드 → 재계산 == h0 ?
        → 다른 설정 재저장 → 재계산 == h0 ?
mp3도 동일 (ID3 TXXX)
```
점검 1순위 의심(PDF 비결정성)을 직접 검증. 성립 → 기둥1 증명. 깨짐 → 거기가 진짜 제약.

### 이후
인덱스/FTS 쿼리 → `dnr read` 강제 CLI(프로토콜을 프로즈→코드) → 포맷 확장 → 선택적 MCP/OKF emit.

---

## 17. 이름

**donotreadagain**, CLI 별칭 **dnr**. 가치가 이름에 박힘("again" = 캐싱). 태그라인: *Read once, never again.*

---

## 부록: 포지셔닝 (선행기술 대비)

- **digiKam** — 임베드+로컬 SQLite 인덱스+증분. 단 사진만, AI 전사 없음. dnr = "digiKam을 전 미디어 + AI 전사 페이로드로 일반화".
- **C2PA** — 크로스포맷 in-file 구조화 어서션. 단 진위/서명용, 쿼리 무관, hard-bound(편집에 깨짐). dnr = edit-tolerant·query-first.
- **Google OKF** (2026-06) — 에이전트 지식 사이드카(md+YAML). 단 in-file 아님, 미디어 전사 없음. dnr = in-file + 미디어 전사.
- **Framedex** — 영상 사이드카 + 인덱스. 단 사이드카만, 영상/사진만.
