import io
import re
import pandas as pd
import requests
import folium
import streamlit as st
from streamlit_folium import st_folium

# ==============================================================================
# 1. 페이지 기본 설정 및 디자인
# ==============================================================================
st.set_page_config(
    page_title="전국 폭염일수 현황 지도",
    page_icon="🔥",
    layout="wide"
)

st.title("🔥 전국 폭염일수 현황 및 기록 분석")
st.markdown("기상청 폭염 데이터를 바탕으로 연도별 폭염일수, 지속 기간 및 최장/최조 폭염을 분석합니다.")

# ==============================================================================
# 2. 기상청 관측지점 -> 행정구역(시군구) 매핑 딕셔너리
# ==============================================================================
# GeoJSON 파일의 '시군구' 속성과 기상청 지점명을 연결해주는 매핑 테이블입니다.
STATION_TO_SIGUNGU = {
    "서울": "종로구", "강릉": "강릉시", "대관령": "평창군", "춘천": "춘천시",
    "원주": "원주시", "속초": "속초시", "동해": "동해시", "태백": "태백시",
    "인제": "인제군", "홍천": "홍천군", "철원": "철원군", "수원": "수원시 권선구",
    "인천": "중구", "전주": "전주시 완산구", "광주": "동구", "대구": "중구",
    "부산": "중구", "울산": "중구", "대전": "중구", "청주": "청주시 상당구",
    "목포": "목포시", "여수": "여수시", "순천": "순천시", "포항": "포항시 남구",
    "안동": "안동시", "창원": "창원시 성산구", "진주": "진주시", "제주": "제주시",
    "서귀포": "서귀포시", "추풍령": "영동군", "울릉도": "울릉군", "관악산": "관악구",
    "백령도": "옹진군", "거제": "거제시", "통영": "통영시", "밀양": "밀양시",
    "산청": "산청군", "거창": "거창시", "합천": "합천군", "남해": "남해군",
    "구미": "구미시", "영주": "영주시", "상주": "상주시", "문경": "문경시",
    "영덕": "영덕군", "의성": "의성군", "청송": "청송군", "영천": "영천시",
    "경주시": "경주시", "군산": "군산시", "완주": "완주군", "진안": "진안군",
    "무주": "무주군", "장수": "장수군", "임실": "임실군", "순창": "순창군",
    "고창": "고창군", "부안": "부안군", "정읍": "정읍시", "남원": "남원시",
    "광양": "광양시", "보성": "보성군", "강진": "강진군", "해남": "해남군",
    "고흥": "고흥군", "완도": "완도군", "진도": "진도군", "흑산도": "신안군",
    "영광": "영광군", "함평": "함평군", "장성": "장성군", "나주": "나주시",
    "담양": "담양군", "화순": "화순군", "충주": "충주시", "제천": "제천시",
    "보은": "보은군", "옥천": "옥천군", "영동": "영동군", "천안": "천안시 동남구",
    "보령": "보령시", "부여": "부여군", "금산": "금산군", "서산": "서산시",
    "태안": "태안군", "홍성": "홍성군", "보령": "보령시", "양평": "양평군",
    "이천": "이천시", "파주": "파주시", " 강화": "강화군"
}

# ==============================================================================
# 3. 데이터 로드 및 전처리 함수 (캐싱 사용)
# ==============================================================================
@st.cache_data
def load_heatwave_data(file_path="heatwave.csv"):
    """하나의 CSV 파일 내에 표 3개가 나뉘어 들어있는 데이터를 파싱합니다."""
    # 1단계: 인코딩 예외 처리 (utf-8 실패 시 cp949 시도)
    raw_text = ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="cp949") as f:
            raw_text = f.read()

    # 2단계: 섹션 타이틀 기준으로 텍스트 분할
    # 섹션 구분 키워드: 가장 긴 폭염, 가장 빠른/가장 늦은 폭염, 전국 폭염일수
    sections = re.split(r'(?=가장 긴 폭염|가장 빠른/가장 늦은 폭염|전국 폭염일수)', raw_text)
    
    df_longest = pd.DataFrame()
    df_earliest_latest = pd.DataFrame()
    df_raw_days = pd.DataFrame()

    for sec in sections:
        if "가장 긴 폭염" in sec:
            lines = [l for l in sec.strip().split('\n') if l.strip()][1:] # 첫 줄(제목) 제외
            if lines:
                df_longest = pd.read_csv(io.StringIO('\n'.join(lines)))
        elif "가장 빠른/가장 늦은 폭염" in sec:
            lines = [l for l in sec.strip().split('\n') if l.strip()][1:]
            if lines:
                df_earliest_latest = pd.read_csv(io.StringIO('\n'.join(lines)))
        elif "전국 폭염일수" in sec:
            lines = [l for l in sec.strip().split('\n') if l.strip()][1:]
            if lines:
                df_raw_days = pd.read_csv(io.StringIO('\n'.join(lines)))

    return df_longest, df_earliest_latest, df_raw_days

@st.cache_data
def load_geojson():
    """대한민국 시군구 경계 GeoJSON 데이터 로드"""
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    response = requests.get(url)
    return response.json()

# 데이터 불러오기
try:
    df_longest, df_earliest_latest, df_raw_days = load_heatwave_data("heatwave.csv")
    geojson_data = load_geojson()
except Exception as e:
    st.error(f"데이터를 로드하는 중 오류가 발생했습니다: {e}")
    st.stop()

# ==============================================================================
# 4. 데이터 전처리 및 사이드바 설정
# ==============================================================================
# 연도 컬럼 탐색 및 정수형 변환
year_col = [col for col in df_raw_days.columns if '년' in col or 'year' in col.lower() or '연도' in col]
if not year_col:
    year_col = df_raw_days.columns[0]
else:
    year_col = year_col[0]

df_raw_days[year_col] = pd.to_numeric(df_raw_days[year_col], errors='coerce')
available_years = sorted(df_raw_days[year_col].dropna().unique().astype(int))

# 사이드바 연도 선택 슬라이더
st.sidebar.header("⚙️ 검색 조건")
selected_year = st.sidebar.slider(
    "연도를 선택하세요",
    min_value=int(min(available_years)),
    max_value=int(max(available_years)),
    value=int(max(available_years))
)

# 선택된 연도의 폭염 데이터 필터링
df_year = df_raw_days[df_raw_days[year_col] == selected_year]

# 지점별 폭염일수 집계
station_col = [c for c in df_year.columns if '지점' in c or '관측' in c]
station_col = station_col[0] if station_col else df_year.columns[2]

# 지점별 발생 건수(폭염일수) 집계
heatwave_counts = df_year.groupby(station_col).size().reset_index(name='폭염일수')

# 관측지점명을 행정구역(시군구) 이름으로 매핑
heatwave_counts['시군구'] = heatwave_counts[station_col].map(STATION_TO_SIGUNGU).fillna(heatwave_counts[station_col])

# ==============================================================================
# 5. 상단 지표 카드 (Metrics)
# ==============================================================================
col1, col2, col3 = st.columns(3)

avg_days = round(heatwave_counts['폭염일수'].mean(), 1) if not heatwave_counts.empty else 0
if not heatwave_counts.empty:
    max_row = heatwave_counts.loc[heatwave_counts['폭염일수'].idxmax()]
    max_station = f"{max_row[station_col]} ({max_row['폭염일수']}일)"
else:
    max_station = "-"
total_stations = len(heatwave_counts)

col1.metric("전국 평균 폭염일수", f"{avg_days} 일")
col2.metric("최다 폭염 관측지점", max_station)
col3.metric("총 관측지점 수", f"{total_stations} 곳")

st.markdown("---")

# ==============================================================================
# 6. 지도 시각화 (Folium Choropleth)
# ==============================================================================
st.subheader(f"🗺️ {selected_year}년 전국 시군구별 폭염일수 지도")

# 지도 초기화 (대한민국 중앙 좌표)
m = folium.Map(location=[35.907757, 127.766922], zoom_start=7, tiles="cartodbpositron")

# 단계구분도(Choropleth) 설정
folium.Choropleth(
    geo_data=geojson_data,
    data=heatwave_counts,
    columns=['시군구', '폭염일수'],
    key_on='feature.properties.시군구',
    fill_color='YlOrRd',
    fill_opacity=0.7,
    line_opacity=0.3,
    legend_name=f'{selected_year}년 폭염일수 (일)',
    nan_fill_color='white'
).add_to(m)

# 지도 출력
st_folium(m, width="100%", height=500)

st.markdown("---")

# ==============================================================================
# 7. 상위 / 하위 폭염일수 표
# ==============================================================================
col_top, col_bottom = st.columns(2)

with col_top:
    st.write(f"🔥 **{selected_year}년 폭염일수 상위 10곳**")
    top10 = heatwave_counts.sort_values(by='폭염일수', ascending=False).head(10)
    st.dataframe(top10[[station_col, '시군구', '폭염일수']], use_container_width=True)

with col_bottom:
    st.write(f"🧊 **{selected_year}년 폭염일수 하위 10곳**")
    bottom10 = heatwave_counts.sort_values(by='폭염일수', ascending=True).head(10)
    st.dataframe(bottom10[[station_col, '시군구', '폭염일수']], use_container_width=True)

st.markdown("---")

# ==============================================================================
# 8. 역대 주요 기록 표 (가장 긴 폭염 / 가장 빠른·늦은 폭염)
# ==============================================================================
st.subheader("📜 역대 폭염 주요 기록 데이터")

tab1, tab2 = st.tabs(["가장 긴 폭염 기록", "가장 빠른 / 가장 늦은 폭염 기록"])

with tab1:
    st.markdown("##### ⏳ 역대 가장 오래 지속된 폭염")
    if not df_longest.empty:
        st.dataframe(df_longest, use_container_width=True)
    else:
        st.info("데이터가 존재하지 않습니다.")

with tab2:
    st.markdown("##### 🗓️ 연도별 가장 이른 / 가장 늦은 폭염 관측일")
    if not df_earliest_latest.empty:
        st.dataframe(df_earliest_latest, use_container_width=True)
    else:
        st.info("데이터가 존재하지 않습니다.")
