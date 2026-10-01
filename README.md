# Quota Glance · Windows AI 구독 한도 확인

Codex와 Claude의 남은 사용 한도를 한 창에서 확인하는 Windows 앱입니다. **1.4.0 시험 배포**이며 OpenAI·Anthropic의 공식 앱이 아닙니다.

## AI에게 설치 맡기기

아래 문장을 **내 Windows PC에서 파일과 명령을 실행할 수 있는 Codex 또는 Claude**에 그대로 전달하세요.

> https://github.com/firstmarch84/Quota-Glance 저장소의 README.md와 SETUP_FOR_AI.md를 읽고 내 Windows PC에 설치해줘. 기존 설치가 있으면 설정을 보존해 업데이트하고, 바탕화면 바로가기를 만들어줘. 내가 사용하는 서비스를 먼저 확인하고 Codex만, Claude만, 둘 다 중 맞게 설치해줘. 선택한 서비스의 실제 사용량 수신을 확인해줘. 로그인이나 Chrome 확장 설정처럼 내가 직접 해야 할 부분만 안내해줘. 아직 검증하지 못한 연결을 완료됐다고 보고하지 마.

AI가 PC를 조작할 수 없는 채팅 환경이면 설치 안내만 받을 수 있습니다.

## 준비할 것

| 항목 | 필요 조건 |
| --- | --- |
| PC | Windows 10/11, Python 3.11 이상(tkinter 포함) |
| Codex 선택 시 | Codex CLI 설치 및 본인 ChatGPT 구독 계정 로그인 |
| Claude 선택 시 | Chrome, 본인 Claude 계정, 이 저장소의 Chrome 확장 |
| 회사 PC | Python·CLI·개발자 모드 확장 설치가 허용되어야 함 |

**Codex만 선택하면 Chrome·Claude 확장·연결 코드가 필요하지 않습니다.** Claude를 선택한 경우에만 첫 설치 때 확장 로드와 연결 코드 붙여넣기, 로그인이 한 번 필요합니다. **현재 버전은 코드 입력 없는 설치나 Chrome 없는 Claude 조회를 지원하지 않습니다.** 회사에서 확장 설치를 제한하면 IT 담당자에게 문의하세요.

## 설치 후 사용

1. 바탕화면 **Quota Glance** 바로가기를 실행합니다.
2. Codex는 설치된 CLI를 통해 직접 조회합니다.
3. Claude는 연결된 Chrome 확장이 사용량 탭을 준비하고 값을 전달합니다. Chrome 백그라운드 실행과 사용량 탭이 필요합니다.
4. 창을 닫거나 트레이로 접으면 시계 옆 숨겨진 아이콘 영역에 남습니다. 바로가기를 다시 누르면 돌아옵니다. 완전 종료는 트레이 우클릭 → 종료입니다.

숫자와 막대가 회색이면 최신 수신에 실패한 상태입니다. 이름 옆 점은 서비스 색상이며 연결 표시가 아닙니다.

## 확인된 것과 남은 한계

- Codex 조회, Claude 수신, 바로가기 실행은 개발 PC에서 확인했습니다.
- 1.4.0은 탭 내부 타이머에만 의존하지 않고 확장 알람으로 약 30초마다 읽습니다. 숨겨진 정상 사용량 탭을 약 1분마다 새로고침합니다.
- 백그라운드 갱신 수정은 자동 테스트를 통과했으나, 다양한 회사 PC와 절전 환경에서 지속 동작은 추가 검증이 필요합니다. 따라서 시험 배포입니다.
- Claude 로그인 만료·사람 확인·사이트 변경·Chrome 절전은 자동 갱신을 중단시킬 수 있습니다. 보안 확인을 우회하지 않습니다.
- 표시하는 것은 구독 잔여 한도이며 토큰 수, API 결제 금액, 일반 ChatGPT 채팅 잔여량이 아닙니다.
- Windows 자동 시작은 선택 사항이며 로그인 시 창을 표시합니다. 실제 재부팅 검증은 각 PC에서 진행해야 합니다.

## 개인정보

각자의 PC에서 각자의 계정으로 연결합니다. 사용자 연결 코드·로그인 세션·설정은 저장소에 포함하지 않습니다. Claude 확장은 사용량 경로의 한도 숫자와 초기화 문구만 localhost 앱으로 보내며 쿠키·비밀번호·대화 내용을 앱으로 전달하지 않습니다. Codex는 로컬 CLI의 인증을 사용합니다.

`.runtime`, `.venv`, 로그, 인증 정보, 연결 코드를 다른 사람이나 GitHub 이슈에 업로드하지 마세요. 이 앱은 사용량을 별도 중앙 서버로 수집하지 않습니다.

## 직접 설치 / 상세 안내

저장소를 고정 폴더에 내려받은 후 PowerShell에서 실행합니다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

프로젝트 전용 Python 환경과 바탕화면 바로가기를 만듭니다. Python 자체와 Codex CLI, Chrome 확장은 자동 설치하지 않습니다. 상세 절차·업데이트·제거는 [SETUP_FOR_AI.md](SETUP_FOR_AI.md)를 참고하세요.

문제 제보에는 Windows/Chrome/확장 버전, 증상, 민감정보를 가린 화면만 포함해주세요.

## 필요한 서비스만 설치

AI에게 “Codex만 설치해줘” 또는 “Claude만 설치해줘”라고 덧붙이세요.

| 선택 | 설치 옵션 | 실행되는 기능 |
| --- | --- | --- |
| Codex만 | `-Providers codex` | Codex 카드만 표시. Claude 수신기와 Chrome 자동 실행 없음 |
| Claude만 | `-Providers claude` | Claude 카드만 표시. Codex CLI 불필요 |
| 둘 다 | `-Providers both` | 두 서비스 표시 |

예: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Providers codex`

다운로드한 소스에는 두 서비스 코드가 포함되어도, 선택하지 않은 서비스는 실행하지 않습니다. 나중에 변경하려면 앱을 트레이에서 종료한 뒤 다른 옵션으로 설치 스크립트를 다시 실행하세요. 옵션을 생략하면 기존 선택을 유지하고, 새 설치는 둘 다가 기본입니다.
