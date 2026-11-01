# 길드 랭킹 봇

KURO HELPER 인증 봇과 분리된 Discord 봇입니다. 이 폴더를 독립적인 GitHub 저장소와 Render 서비스로 배포하며 KURO HELPER의 `BOT/`, `render.yaml`, `requirements.txt`를 수정하거나 사용하지 않습니다.

## 동작

- `/인증 닉네임`으로 게임 닉네임 등록을 요청합니다. `/대기목록`으로 요청을 확인하고 `/승인 사용자` 또는 `/거절 사용자`로 처리합니다.
- 승인된 사용자가 랭킹 채널에 숫자만 보내면 해당 값을 추딜(조 단위)로 저장합니다. 예: `2600`은 `2,600조`로 표시됩니다. 숫자가 아닌 메시지는 무시합니다.
- `/레벨 레벨`은 본인 레벨을 변경합니다.
- 관리자는 `/회원등록`, `/회원수정`, `/회원삭제`, `/랭킹갱신`으로 직접 관리할 수 있습니다. 서버 관리자 또는 서버 관리 권한이 있는 사용자만 사용할 수 있습니다.
- 랭킹은 추딜 내림차순이며, 봇이 랭킹 채널의 이미지 메시지 하나를 계속 갱신합니다. 시작할 때 데이터는 비어 있습니다.

## 데이터베이스

새 Supabase 프로젝트의 SQL Editor에서 `supabase_schema.sql`을 실행하세요. 이 스키마는 `guild_ranking_*_v1` 테이블만 만들며, 기존 쿠로헬퍼 테이블은 읽거나 변경하지 않습니다. 앱의 service-role 키는 서버 환경변수로만 사용합니다.

## 별도 호스팅

기존 Render 서비스가 이 저장소의 변경을 자동 배포하므로, 기존 서비스에 배포 이벤트조차 발생하지 않게 하려면 랭킹 봇을 별도 GitHub 저장소로 분리해야 합니다.

1. 새 GitHub 저장소를 만들고 이 폴더의 파일들을 저장소 루트에 올립니다. 다른 KURO HELPER 파일과 기존 루트 `render.yaml`은 복사하지 않습니다.
2. Render에서 새 Blueprint를 만들고 Blueprint 파일 경로로 `render.yaml`을 지정합니다. 서비스 이름은 `kuro-guild-ranking`으로 기존 인증 서비스와 구분됩니다.
3. 새 Discord 봇 토큰과 랭킹 전용 Supabase 프로젝트의 URL 및 service-role 키를 Render 환경변수로 등록합니다. 서버 ID와 채널 ID는 YAML에 입력되어 있습니다.

이렇게 하면 기존 KURO HELPER 저장소, Render 서비스, Supabase 테이블을 수정하거나 재사용하지 않습니다. 랭킹 봇 변경 사항을 배포할 때는 새 랭킹 봇 저장소에만 커밋하세요. Render 서비스의 Root Directory는 `.`으로 둡니다.

Render 환경변수:

- `RANKING_DISCORD_BOT_TOKEN`: 새로 만든 랭킹 봇 토큰
- `RANKING_GUILD_ID`: Discord 서버 ID
- `RANKING_CHANNEL_ID`: 숫자 입력 및 랭킹 이미지 게시 채널 ID
- `RANKING_SUPABASE_URL`: 랭킹 전용 Supabase 프로젝트 URL
- `RANKING_SUPABASE_SERVICE_ROLE_KEY`: 해당 프로젝트의 service-role 키

무료 Render 서비스는 유휴 상태에서 잠들 수 있습니다. UptimeRobot에서 `https://<Render 주소>/healthz`를 5분 간격으로 확인하도록 설정하면 기존에 사용하던 무료 모니터링 흐름으로 서비스가 다시 깨어나는 것을 줄일 수 있습니다. 무료 플랜의 상시 가동은 보장되지 않습니다.

Discord Developer Portal의 Bot 설정에서 **Message Content Intent**를 켜세요. 봇에는 랭킹 채널 보기, 메시지 보내기, 파일 첨부, 메시지 기록 보기, 반응 추가 권한과 `applications.commands` scope가 필요합니다.

## 로컬 테스트

프로젝트 루트에서 다음 명령으로 순수 랭킹 규칙 테스트를 실행합니다.

```powershell
py -m unittest test_board
```

봇을 로컬에서 실행할 때는 위의 `RANKING_*` 환경변수를 설정하고 다음 명령을 사용합니다.

```powershell
py -m pip install -r requirements.txt
py main.py
```