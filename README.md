# 길드 랭킹 봇

KURO HELPER 인증 봇과 분리된 Discord 봇입니다. 이 폴더를 독립적인 GitHub 저장소와 Render 서비스로 배포하며 KURO HELPER의 `BOT/`, `render.yaml`, `requirements.txt`를 수정하거나 사용하지 않습니다.

## 동작

- `/인증 닉네임`으로 게임 닉네임을 즉시 등록합니다. `/회원등록`, `/회원수정`, `/회원삭제`의 관리 대상은 Discord ID, Discord 멘션 또는 등록된 게임 닉네임으로 지정할 수 있습니다. 닉네임 입력은 저장된 값과 대소문자 무시 완전 일치로 찾습니다.
- `/인증`을 완료한 사용자가 랭킹 채널에 숫자만 보내면 해당 값을 추뎀(조 단위)으로 저장합니다. 예: `2600`은 `2,600조`로 표시됩니다.
- 랭킹 채널에 `레벨 200` 형식으로 입력하면 본인 레벨을 변경하고 해당 입력 메시지는 삭제합니다. 기존 `/레벨` 명령도 사용할 수 있습니다.
- 관리자는 `/회원등록`, `/회원수정`, `/회원삭제`, `/랭킹갱신`으로 직접 관리할 수 있습니다. 서버 관리자/서버 관리 권한이 있거나 `RANKING_ADMIN_ROLE_ID`에 설정된 역할을 가진 사용자만 사용할 수 있습니다.
- `/인증`으로 처음 등록한 사용자는 레벨과 추뎀이 0으로 시작합니다. 재인증 시 기존 레벨과 추뎀은 유지되고 닉네임만 갱신됩니다.
- 랭킹은 추뎀 내림차순이며, 봇이 랭킹 채널의 이미지 메시지 하나를 계속 갱신합니다. 시작할 때 데이터는 비어 있습니다.
- Render가 시스템 패키지를 설치하지 않아도 되도록 Noto Sans KR 폰트와 OFL 라이선스를 저장소에 포함하고, `샘플.png`를 디자인 배경으로 사용합니다.

## 데이터베이스

새 Supabase 프로젝트의 SQL Editor에서 `supabase_schema.sql`을 실행하세요. 이 스키마는 `guild_ranking_*_v1` 테이블만 만들며, 기존 쿠로헬퍼 테이블은 읽거나 변경하지 않습니다. 앱의 service-role 키는 서버 환경변수로만 사용합니다.

## 별도 호스팅

기존 Render 서비스가 KURO HELPER 저장소의 변경을 자동 배포하므로, 기존 서비스에 배포 이벤트조차 발생하지 않게 하려면 랭킹 봇을 별도 GitHub 저장소로 분리해야 합니다.

1. 새 GitHub 저장소 최상위에 이 폴더의 파일들을 올립니다. 다른 KURO HELPER 파일은 복사하지 않습니다.
2. Render에서 새 Blueprint를 만들고 Blueprint 파일 경로로 최상위 `render.yaml`을 지정합니다. 서비스 이름은 `kuro-guild-ranking`으로 기존 인증 서비스와 구분됩니다.
3. 새 Discord 봇 토큰과 랭킹 전용 Supabase 프로젝트의 URL 및 service-role 키를 Render 환경변수로 등록합니다. 서버 ID와 채널 ID는 YAML에 입력되어 있습니다.

이렇게 하면 기존 KURO HELPER 저장소, Render 서비스, Supabase 테이블을 수정하거나 재사용하지 않습니다. 랭킹 봇 변경 사항을 배포할 때는 새 랭킹 봇 저장소에만 커밋하세요. 파일이 저장소 최상위에 있으므로 Root Directory는 `.`입니다.

Render 환경변수:

- `RANKING_DISCORD_BOT_TOKEN`: 새로 만든 랭킹 봇 토큰
- `RANKING_GUILD_ID`: Discord 서버 ID
- `RANKING_CHANNEL_ID`: 숫자 입력 및 랭킹 이미지 게시 채널 ID
- `RANKING_ADMIN_ROLE_ID`: 랭킹 관리 권한을 줄 Discord 역할 ID. 비워두면 서버 관리자/서버 관리 권한만 사용할 수 있습니다.
- `RANKING_SUPABASE_URL`: 랭킹 전용 Supabase 프로젝트 URL
- `RANKING_SUPABASE_SERVICE_ROLE_KEY`: 해당 프로젝트의 service-role 키

두 봇 모두 `discord.py`의 자동 재접속을 사용하고, 프로세스가 종료되면 Render가 재시작합니다. 랭킹 봇의 `/healthz`는 웹 프로세스 생존 상태, `/discordz`는 Discord 연결과 설정된 서버·랭킹 채널 접근 상태를 확인합니다. Render 무료 서비스는 유휴 상태에서 잠들 수 있으므로 UptimeRobot 등 외부 감시 서비스에서 `/healthz`를 5분 간격으로 호출해 깨워두고, `/discordz`도 별도 감시해 연결 끊김·서버 이탈·채널 접근 실패 알림을 받으세요. 일시적 재접속 중 알림을 줄이려면 `/discordz` 감시에서 연속 실패 알림을 설정합니다. 무료 플랜의 상시 가동이나 자동 복구는 보장되지 않으며, 봇이 서버에서 추방되거나 제거된 경우에는 다시 초대해야 합니다.

Discord Developer Portal의 Bot 설정에서 **Message Content Intent**를 켜세요. 봇에는 랭킹 채널 보기, 메시지 보내기, 메시지 관리(사용자 명령 메시지 삭제), 파일 첨부, 메시지 기록 보기, 반응 추가 권한과 `applications.commands` scope가 필요합니다. Discord의 `관리자` 권한은 필요하지 않습니다. 관리자는 서버 관리자/서버 관리 권한 또는 Render의 `RANKING_ADMIN_ROLE_ID`에 설정된 역할로 지정합니다. 역할 ID를 사용하면 해당 역할에 별도 Discord 권한을 줄 필요가 없습니다. 다만 `/인증`은 서버에 들어온 누구나 자기 게임 닉네임을 등록하므로, 게임 계정의 실제 소유 확인은 하지 않습니다. `NotoSansKR-Variable.ttf`, `NotoSansKR-OFL.txt`, `샘플.png`도 함께 GitHub에 올려야 합니다.

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