import os
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="台灣天氣 Dashboard", page_icon="☁️", layout="wide")
st.title("☁️ 台灣氣象資料 Dashboard（36 小時預報）")

API_KEY = os.getenv("CWA_API_KEY")  # 從環境變數讀取
if not API_KEY:
    st.error("找不到 API Key，請設定環境變數 CWA_API_KEY。")
    st.stop()

# CWA 36 小時天氣預報（一般天氣）
# 資料集：F-C0032-001（免加 locationName 參數，先抓全部縣市以免中英名稱不對）
URL = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={API_KEY}"

@st.cache_data(ttl=900)  # 15 分鐘快取
def fetch_weather():
    r = requests.get(URL, timeout=20, verify=False)
    r.raise_for_status()
    return r.json()

def parse_dataset(data: dict) -> pd.DataFrame:
    """
    回傳欄位：
    city, startTime, endTime, weather, pop(降雨機率%), minT(°C), maxT(°C), rh(相對濕度%)
    注意：F-C0032-001 的要素英文代碼：
      - PoP: 降雨機率 (%)
      - MinT: 最低溫 (°C)
      - MaxT: 最高溫 (°C)
      - Wx: 天氣現象 (文字)
      - CI: 舒適度 (文字)
    有些縣市「濕度」需改用別的資料集；這裡以 PoP/MinT/MaxT 為主，並示範計算「平均溫度」近似溫度。
    """
    recs = data["records"]["location"]
    rows = []
    for loc in recs:
        city = loc["locationName"]  # 例如：臺北市、臺中市
        # 轉成字典方便取值
        elements = {e["elementName"]: e["time"] for e in loc["weatherElement"]}
        # 每個要素 time 皆有 3 筆（未來 36 小時，每 12 小時一筆）
        for i in range(len(elements["Wx"])):
            start = elements["Wx"][i]["startTime"]
            end = elements["Wx"][i]["endTime"]
            wx = elements["Wx"][i]["parameter"]["parameterName"]          # 天氣現象
            pop = elements["PoP"][i]["parameter"]["parameterName"]         # 降雨機率 %
            minT = elements["MinT"][i]["parameter"]["parameterName"]       # 最低溫 °C
            maxT = elements["MaxT"][i]["parameter"]["parameterName"]       # 最高溫 °C

            # 以 (MinT+MaxT)/2 略估展示用溫度（若要精準可換用其他資料集）
            try:
                temp = (float(minT) + float(maxT)) / 2
            except:
                temp = None

            rows.append({
                "city": city,
                "startTime": start,
                "endTime": end,
                "weather": wx,
                "pop": pd.to_numeric(pop, errors="coerce"),
                "minT": pd.to_numeric(minT, errors="coerce"),
                "maxT": pd.to_numeric(maxT, errors="coerce"),
                "temp": temp
            })
    df = pd.DataFrame(rows)
    return df

try:
    raw = fetch_weather()
    df = parse_dataset(raw)
except Exception as e:
    st.error(f"取得或解析資料時發生錯誤：{e}")
    st.stop()

# 側邊選單
cities = sorted(df["city"].unique().tolist())
with st.sidebar:
    st.header("篩選條件")
    sel_city = st.selectbox("選擇縣市", cities, index=cities.index("臺北市") if "臺北市" in cities else 0)
    st.caption("資料來源：中央氣象署開放資料 F-C0032-001")

cdf = df[df["city"] == sel_city].sort_values("startTime")

# 指標卡
col1, col2, col3, col4 = st.columns(4)
now_row = cdf.iloc[0]
col1.metric("當期天氣", now_row["weather"])
col2.metric("最低溫 (°C)", f"{now_row['minT']:.1f}" if pd.notna(now_row["minT"]) else "—")
col3.metric("最高溫 (°C)", f"{now_row['maxT']:.1f}" if pd.notna(now_row["maxT"]) else "—")
col4.metric("降雨機率 (%)", f"{now_row['pop']:.0f}" if pd.notna(now_row["pop"]) else "—")

# 折線與柱狀圖
lcol, rcol = st.columns(2)
with lcol:
    fig_t = px.line(cdf, x="startTime", y="temp", title=f"{sel_city} 未來 36 小時溫度（近似）", markers=True)
    st.plotly_chart(fig_t, use_container_width=True)
with rcol:
    fig_p = px.bar(cdf, x="startTime", y="pop", title=f"{sel_city} 未來 36 小時降雨機率", text="pop")
    st.plotly_chart(fig_p, use_container_width=True)

# 明細表
st.subheader(f"{sel_city} 預報明細")
st.dataframe(
    cdf[["startTime", "endTime", "weather", "minT", "maxT", "pop"]]
    .rename(columns={"startTime":"開始時間", "endTime":"結束時間", "weather":"天氣", "minT":"最低溫", "maxT":"最高溫", "pop":"降雨機率(%)"}),
    use_container_width=True
)


