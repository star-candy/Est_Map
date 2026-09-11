# 피해가!(街) MVP

경로가 생성되는 전체 과정과 강화학습의 상태·행동·보상·fallback은
[`docs/route-generation.md`](docs/route-generation.md)에서 설명합니다.
weighted A* 비용식과 Q-learning 학습·추론을 단계별로 이해하려면
[`docs/routing-algorithms.md`](docs/routing-algorithms.md)를 참고하세요.
개인정보 처리, AI 오류·편향과 복구 안내 점검 결과는
[`docs/responsible-ai-checklist.md`](docs/responsible-ai-checklist.md)에 기록했습니다.
AI 적용 기능, 사용 모델, 외부 서비스와 구현 도구는
[`docs/ai-external-services-tools.md`](docs/ai-external-services-tools.md)에 정리했습니다.

서울 안에서 일반 최단 보행 경로와 계절·안심 지표를 반영한 맞춤 경로를 비교하는
Streamlit MVP입니다. OpenStreetMap 부분 그래프에서 tabular Q-learning 정책을 학습해
우선 사용하고, 적용할 수 없으면 weighted A*로 전환합니다. 전처리된 서울 공공데이터를
보행 edge에 결합하며 사용자 화면에서는 합성 샘플 경로를 제공하지 않습니다.

> 안심 및 겨울 지표는 참고용이며 공식 안전 경로가 아닙니다. 첨부 자료에는 결빙 위험과
> 열선 좌표·실시간 가동 상태가 없어 해당 정보를 임의로 생성하지 않습니다.

## 화면과 사용자 흐름

1. 출발지·도착지와 여름/가을/겨울/안심 모드를 선택하고 `경로 검색`을 누릅니다.
3. 지도에서 회색 일반 경로, 모드 색상의 맞춤 경로, 공간 지표 layer를
   함께 확인합니다. LayerControl에서 지표를 켜고 끌 수 있습니다.
4. 거리, 예상 시간, 쾌적 점수, 우회율, 생성 알고리즘과 fallback 이유를 비교합니다.
5. 장거리이면 인근 따릉이 대여·반납 후보와 개략 복합 이동 시간을 확인합니다.
6. 실제 이동한 경로와 택시 대체 여부를 확인한 뒤 `이동 완료`를 누릅니다.
7. 로그인 없이 로컬에 누적된 월간 거리·탄소·비용 통계를 확인합니다.

## 핵심 기능 상세

| 기능명 | 사용자 행동 | 앱·AI가 하는 일 |
|---|---|---|
| 경로 검색 | 장소와 모드 선택 | 거리 최단 경로와 모드 지표 기반 후보를 계산한다. |
| 맞춤 경로 | 여름·가을·겨울·안심 선택 | 저장된 Q-learning 정책을 적용하고 불가하면 weighted A*로 전환한다. |
| 지도 비교 | 지도와 layer 선택 | 두 경로, 출도착 marker, 공간 지표와 범례를 표시한다. |
| 맛집 쿠폰 안내 | 맞춤 경로 주변 맛집 검색 | 검색 결과의 맛집마다 닫기 전까지 유지되는 혜택 안내 토스트를 표시한다. 실제 쿠폰은 제휴 연동 후 제공한다. |
| 따릉이 추천 | 1.2km/15분 이상 경로 검색 | 실제 정적 대여소 자료에서 복합 이동 후보를 찾는다. |
| 이동 완료 | 실제 경로·택시 대체 여부 확인 | TMAP 예상 택시요금 또는 로컬 가정식과 탄소량을 계산해 월별 집계한다. |
| 출석·걷기 포인트 | 출석체크 또는 이동 완료 | 하루 한 번 출석 50P와 거리·탄소 기반 걷기 포인트를 로컬 원장에 기록한다. |
| 포인트 비교 | 리더보드 확인 | 현재 사용자는 실시간 값, 다른 사용자는 고정 데모 값으로 순위를 표시한다. |
| 월간 이동 코치 | 리포트 월 선택 후 질문 | LangChain Gemini가 월간·전월 통계와 대화 이력에 근거해 답한다. |

거리·비용·탄소와 경로 가중치는 생성형 AI가 계산하지 않습니다. Gemini는 키가 있을
때 이미 계산된 집계와 최근 대화를 바탕으로 비교·패턴·다음 행동을 설명합니다.

## 요구 환경

- Python 3.11 또는 3.12 권장
- 인터넷 연결: 실제 모드의 Nominatim 지오코딩·Overpass 보행 그래프와 지도 타일에 필요
- API 키: 경로 검색에는 필요 없으며 맛집·택시요금·Gemini 기능에 선택적으로 사용

## 설치 및 실행

PowerShell 기준:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 안내된 로컬 주소를 열고 출발지, 도착지와 모드를 선택합니다. 앱은 로컬
OSM 보행망을 우선 사용하고 필요하면 온라인 OSM을 조회합니다. 둘 다 실패하면 합성
경로를 만들지 않고 오류를 표시합니다.

### 실제 로컬 데이터 준비

첨부 원본 다섯 파일을 Downloads 폴더에 둔 상태에서 실행합니다.

```powershell
python -m scripts.prepare_real_data
python -m scripts.prepare_osm_network
```

다른 위치라면 `--source-dir`을 지정합니다. `data/processed/*.csv.gz`에는 가로수
287,635건, 은행나무 암나무 15,316건, 그늘막 4,941건, 가로등 19,316건,
안심귀갓길 연계 시설 347건, 열선
993건, 불법주정차 단속 CCTV 4,470건, 정적 따릉이 대여소 2,789건이 저장됩니다.
PBF 전처리는 서울 보행망을 `data/processed/seoul_walk.sqlite3.gz`로 저장합니다. 앱 최초
실행 시 이를 `cache/`에 해제하므로 이후 Downloads 원본은 필요하지 않습니다.

불법주정차 단속 CCTV 자료만 최신 API 값으로 갱신하려면 다음 명령을 실행합니다.

```powershell
python -m scripts.fetch_cctv_data
```

앱은 저장된 `data/processed/cctv.csv.gz`를 사용하므로 평상시 실행에는 API 호출이
필요하지 않습니다. 갱신 명령에만 `SEOUL_OPEN_API_KEY`가 필요합니다.

## 환경 변수

외부 공급자를 연결할 때만 `.env.example`을 `.env`로 복사하고 필요한 키를
입력합니다. 빈 키는 무시됩니다.

| 변수 | 용도 | 샘플 실행 필수 |
|---|---|---:|
| `LOCAL_REPORT_DB_PATH` | 로컬 SQLite 집계 파일 | 아니요 |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | 선택적 LangChain 월간 이동 코치 | 아니요 |
| `SEOUL_OPEN_API_KEY` | 서울 열린데이터광장 API | 아니요 |
| `SEOUL_BIKE_API_SERVICE` | 명세로 확인한 따릉이 서비스명 | 아니요 |
| `KMA_DATA_API_KEY` | 기상청 공공데이터포털 API | 아니요 |
| `SEOUL_TREE_DATA_PATH` | 검증된 가로수 CSV/GeoJSON | 아니요 |
| `SEOUL_SHADE_DATA_PATH` | 검증·지오코딩한 그늘막 자료 | 아니요 |
| `SEOUL_HEATING_DATA_PATH` | 검수된 열선 자료 | 아니요 |
| `SEOUL_STREETLIGHT_DATA_PATH` | 검증된 가로등 자료 | 아니요 |
| `VWORLD_API_KEY`, `KAKAO_REST_API_KEY`, `TMAP_APP_KEY`, `OPENAI_API_KEY` | 향후 adapter 후보이며 현재 미사용 | 아니요 |

## 개발 검사

```powershell
python -c "import app"
ruff check .
pytest
streamlit run app.py --server.headless true
```

## 현재 구조

- `app.py`: Streamlit 화면과 사용자 흐름
- `config/settings.py`: 지도 중심점, 화면 설정, 선택적 환경 변수
- `src/domain.py`: UI와 독립적인 입력 및 결과 모델
- `src/geocoding.py`: 샘플 및 OSM 지오코딩 adapter, 서울 범위 검증과 캐시
- `src/routing/`: 합성·OSM 그래프 로딩과 NetworkX 거리 최단 경로
- `src/routing/weighted.py`: 모드별 edge 비용과 weighted A* 경로
- `src/routing/rl_agent.py`: Q-learning 환경, 학습, 평가, 저장·로딩 및 추론
- `src/places/restaurants.py`: TMAP·Google Places 기반 맞춤 경로 주변 음식점 검색
- `src/indicators/`: 합성/실제 지표 로딩, edge 공간 결합과 쾌적 점수
- `src/services/routing.py`: 지오코딩과 그래프 및 fallback을 조율하는 서비스
- `src/map_view.py`: 두 경로, 모드별 합성 지표 layer와 범례
- `src/mobility/bike.py`: 대여소 provider와 따릉이 복합 이동 추천
- `src/reporting/`: 비용·탄소 계산, SQLite 월간 집계와 LangChain 챗봇 adapter
- `config/accounting.py`: 택시비와 탄소 계산 가정
- `src/ui/components.py`: 결과 빈 상태 등 UI 구성 요소

## 현재 제한사항

- 주소와 OSM 그래프 조회는 공용 서비스 상태와 사용 정책의 영향을 받습니다.
- 지도 경로는 현재 graph node를 연결한 선으로 표시하므로 실제 도로 곡선이 단순화됩니다.
- 첨부 공공데이터를 사용하지만 공간 근접도 점수 자체는 MVP용 proxy입니다.
- 맞춤 경로의 우회율은 비교 정보로 표시하며, 우회율만을 이유로 일반 경로로 교체하지 않습니다.
- 쾌적 점수는 선택 모드 지표의 길이 가중 평균으로, 경로 안전성을 보장하지 않습니다.
- RL 정책은 검색 구간 주변의 제한된 부분 그래프에서만 학습됩니다.
- 브라우저별 화면·모바일 레이아웃은 실제 기기에서 추가 수동 검수가 필요합니다.

## 데이터 출처와 라이선스

첨부된 서울시 가로수, 그늘막, 도로 열선, 가로등, 안심귀갓길 연계 시설,
공공자전거 대여소 파일을 사용합니다. 보행 그래프와 배경
지도는 OpenStreetMap을 사용하므로 실제 배포에서는 OpenStreetMap
저작자 표시와 타일 사용 정책을 준수해야 합니다. 연결 준비 중인 서울 자료에는 공공누리
제1유형과 제4유형이 섞여 있습니다. 데이터별 공식 URL, 갱신일, 확인된 필드, 좌표계,
전처리 및 표시 의무는 [`data/README.md`](data/README.md)에 기록했습니다.

## 일반 경로와 weighted A*

일반 경로는 NetworkX 기반 보행 우선 경로입니다. 실제 모드에서는 OSM 보행 그래프의
전용 보행로를 우선하고 보도 여부가 불명확한 간선도로에는 추가 비용을 적용합니다.
weighted A*는 직선거리 heuristic과 아래 모드별 edge 비용을 사용합니다.
맞춤 후보는 우회율과 관계없이 선택 모드의 지표가 실제로 개선되면 유지합니다. 주변에
활용할 맞춤 지표가 없어 개선되지 않으면 일반 보행 경로를 반환합니다.

## 현재 위치 기반 경로 안내

경로 검색 후 일반 보행 경로 또는 맞춤 경로를 선택하고 `경로 안내 시작`을 누릅니다.
브라우저 위치 버튼으로 현재 좌표를 갱신하거나 안내 지도상의 위치를 클릭해 테스트할 수
있습니다. 안내 엔진은 현재 위치를 선택 경로에 투영하여 다음 회전까지 거리, 남은 거리,
진행률, 35m 이상 경로 이탈과 목적지 도착을 텍스트로 안내합니다.

브라우저 위치는 사용자 권한과 HTTPS 또는 localhost 환경이 필요합니다. 위치는 로컬
Streamlit 세션에서만 사용하며 이동 기록에 저장하지 않습니다. `GEMINI_API_KEY`가 있으면
`gemini-3.1-flash-tts-preview`를 이용해 출발 시, 회전 지점 60m 전, 경로 이탈 및 도착
시점에 현재 안내를 자동으로 음성 재생할 수 있습니다. 동일한 행동 지점은 한 번만 생성해
반복 안내와 API 호출을 줄입니다.

## 출석·걷기 포인트

로그인 없는 MVP이므로 현재 사용자를 로컬 사용자 한 명으로 취급하고 월간 리포트와 같은
SQLite 파일에 포인트 이벤트를 저장합니다. 출석은 서울 날짜 기준 하루 한 번 50P입니다.

```text
걷기 포인트 = floor(이동 거리 / 100m) + floor(탄소 감축량 / 20gCO₂e)
```

같은 날짜의 출석과 같은 `trip_id` 이동은 중복 지급하지 않습니다. 리더보드의 다른 사용자
이름과 점수는 MVP 화면용 고정 샘플이며 현재 로컬 사용자의 점수만 실제로 변경됩니다. 이동
완료 후에는 이동 거리와 탄소 감축량에 따라 펭귄·빙하 형식의 환경 응원 토스트를 표시합니다.
맛집 혜택과 환경 응원 토스트는 사용자가 닫을 때까지 화면에 유지됩니다.

## 맞춤 경로 비용

각 edge의 비용은 `길이(m) × 모드별 비용 계수`이며 계수는 최소 0.2로 제한됩니다.

- 여름: 그늘 점수가 높을수록 비용 감소
- 가을: 은행나무 위험이 높을수록 비용 증가
- 겨울: 결빙 위험은 비용 증가, 열선 점수는 비용 감소
- 안심: 불법주정차 단속 CCTV 근접도 50%, 안심귀갓길 시설 35%, 가로등 밀도 15%를 결합

합성 지표의 출처와 필드는 `data/README.md`에 기록되어 있습니다.

## 강화학습 정책

기본 모델은 `서울시청 → 광화문`, `여름` 모드의 제한된 합성 부분 그래프에서 seed
42로 4,000 episode를 학습한 tabular Q-learning Q-table입니다.

실제 로컬 데이터 모드는 출도착 기준 경로 주변 200m corridor만 부분 그래프로 만들고,
각 모드별로 seed 42의 Q-learning을 1,500 episode 학습합니다. 상태와 행동은 아래와
같고 진행 거리 기반 reward shaping도 학습 보상에 포함됩니다. 학습 Q-table과 metadata는
`models/runtime/`에 캐시되어 같은 그래프·구간·모드 검색에서 재사용됩니다. 학습 정책이
루프, 미도달 또는 RL 내부 탐색 한도를 넘으면 weighted A*로 fallback합니다.

- 상태: 현재 노드, 목적지까지의 거리 구간, 현재 노드의 모드 지표 구간
- 행동: 현재 노드에서 연결된 인접 edge의 다음 노드 선택
- 보상: 목적지 도착, edge 거리 비용, 모드 쾌적성, 재방문 및 최대 우회 패널티
- 안전장치: graph fingerprint, 모드와 출도착 검증, 미학습 상태·반복·최대 step
  RL episode 내부 과도 탐색 검사

저장된 metadata의 평가 결과:

| 지표 | 학습 전 무작위 정책 | 학습 후 greedy 정책 |
|---|---:|---:|
| 평균 보상 | -8.19 | 89.28 |
| 목적지 도달률 | 30.0% | 100.0% |
| 평균 우회율 | 0.0% | 0.0% |
| 평균 여름 쾌적 점수 | 0.0점 | 0.0점 |

학습 평가의 평균 우회율과 쾌적 점수는 목적지에 성공한 episode만 집계합니다. RL과
weighted A* 맞춤 경로 모두 고정 우회율 제한을 적용하지 않습니다.
이 평가에서는 도달률과 보상은 개선됐지만 쾌적 점수 개선은 검증되지 않았습니다.
따라서 RL이 weighted A*보다 더 쾌적한 경로를 만든다고 주장하지 않습니다.

학습 및 metadata 재생성:

```powershell
python -m scripts.train_rl
```

모델은 `models/`에 Q-table과 graph fingerprint, 모드, 출도착, seed, 학습 설정,
평가 통계를 함께 저장합니다. 학습 전후 평가는 고정 seed의 무작위 정책과 greedy
정책을 비교하며, 특정 실행에서 검증되지 않은 성능 개선은 문서화하지 않습니다.

앱에서 `서울시청 → 광화문`, `여름`을 선택하면 결과 생성 방식에 `RL 정책`이
표시됩니다. 다른 구간·모드, 모델 누락, graph 변경 또는 추론 실패 시 fallback 사유와
함께 `weighted A* fallback`이 표시됩니다.

## 따릉이 복합 이동

일반 최단 보행 경로가 1.2km 이상이거나 예상 도보 시간이 15분 이상이면 출발지와
도착지 각각 700m 안에서 대여·반납 후보를 찾습니다. 샘플 provider는
`data/sample/bike_stations.csv`를 사용합니다. 실제 모드는 2026년 6월 기준 정적
대여소 위치를 사용하지만 현재 자전거와 빈 거치대 수는 제공하지 않습니다.

표시되는 복합 이동 수치는 다음 가정으로 계산한 개략값입니다.

- 출발지→대여소 및 반납소→도착지: 직선거리, 도보 4.5km/h
- 대여소→반납소: 직선거리의 1.15배, 자전거 15km/h
- 대여·반납 처리: 3분

대여 가능한 자전거 또는 반납 가능한 빈 거치대가 검색 반경 안에 없으면 추천하지 않고
화면에 이유를 표시합니다. `BikeStationProvider` 인터페이스를 구현하면 이후 서울시
실시간 따릉이 API로 교체할 수 있습니다.

## 이동 완료와 월간 리포트

경로 검색 후 실제로 이동한 일반 또는 맞춤 경로를 선택하고 `이동 완료`를 누르면 로그인
없이 `data/local/monthly_report.sqlite3`에 집계됩니다. 저장 항목은 임시 이동 ID, 완료
시각과 월, 경로 종류, 거리, 탄소 및 비용 집계값뿐입니다. 주소, 출도착 좌표와 전체 경로는
저장하지 않습니다. 이동 ID는 SQLite 기본키이므로 같은 검색 결과를 여러 번 눌러도 한 번만
기록됩니다.

MVP 계산 가정은 `config/accounting.py`에서 관리합니다.

- 택시 기본요금: 1.6km까지 4,800원
- 거리요금: 이후 131m마다 100원
- 승용차 배출계수: 192gCO₂e/km
- 도보 운행 배출량: 0gCO₂e로 단순화

탄소 절감량은 동일 거리의 승용차 이동을 대체했다고 가정한 추정값입니다. 택시비 절감액은
사용자가 `택시를 타는 대신 이 경로를 걸었습니다`를 확인한 이동에만 계산·집계합니다.

기본 템플릿은 API 키 없이 월간 통계를 설명합니다. 추정 비용 절감액은 선택 월의
직전 달과 비교한 증감도 함께 표시합니다. `GEMINI_API_KEY`가 있으면 LangChain의
`ChatGoogleGenerativeAI` 기반 월간 이동 코치가 활성화됩니다. 선택 월·전월의 계산된
집계와 최근 대화 8개만 전달하며 좌표와 전체 경로는 보내지 않습니다. 모델은 통계를
재계산하지 않고 사용자의 질문에 맞춰 비교, 관찰 가능한 패턴과 다음 행동을 설명합니다.
- OpenStreetMap 타일은 인터넷 연결이 없으면 나타나지 않을 수 있지만 앱 시작과 입력
  UI에는 영향을 주지 않습니다.

## 사용된 모델·데이터·외부 서비스·구현 도구

- AI 모델: 자체 학습 tabular Q-learning 정책; 선택적 LangChain Google Gemini 챗봇
- 데이터: 합성 데모 자료, 첨부 서울 공공데이터, 선택적 OSM 보행 그래프
- 외부 서비스: OpenStreetMap/Nominatim/Overpass, 선택적 Gemini REST API;
  서울 열린데이터광장 실시간 API와 기상청 adapter는 연결 준비 상태
- 구현 도구: Python, Streamlit, Folium/streamlit-folium, OSMnx, NetworkX,
  GeoPandas/Shapely(간접 공간 처리), pandas, joblib, SQLite, pytest, Ruff

## 실제 서비스 전환 시 필요한 작업

1. `data/README.md`의 공식 자료를 내려받고 라이선스·표시·변환·재배포 조건을 확정합니다.
2. 원본 버전과 schema를 고정하고 CRS 검사, 주소 지오코딩, 구간 map-matching 및
   데이터 품질 리포트를 구현합니다. 암수 정보가 없으면 은행나무 전체 회피로 제한합니다.
3. 따릉이 실제 JSON 필드와 반납 가능 거치대 의미를 검증하고 pagination·TTL 캐시를
   적용합니다. 기상 API의 격자 변환과 발표시각 처리를 구현합니다.
4. 서울의 작은 실제 구역별 부분 그래프에서 정책을 다시 학습·평가하고 모델 버전,
   실패율과 fallback 관측을 운영합니다. 안전 경로라는 표현은 사용하지 않습니다.
5. OSM 타일·Nominatim·Overpass의 운영 정책에 맞는 자체 캐시/서버 또는 계약 서비스를
   선택하고, 개인정보·보존기간·로컬 저장 정책을 제품 환경에 맞게 재검토합니다.
6. 접근성, 모바일, 여러 브라우저, 장애·부하·데이터 갱신 회귀 테스트를 추가합니다.
