import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import google.generativeai as genai
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Streamlit config
st.set_page_config(
    page_title="台灣氣象 + Gemini AI Dashboard",
    page_icon="⛅",
    layout="wide"
)

st.title("⛅ 台灣氣象資料 Dashboard（36 小時預報）")
st.caption("資料來源：中央氣象署 F-C0032-001 / Gemini AI 語意分析")

# =============================
# 🔑 讀取 Gemini API Key
# =============================
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")


# =============================
# 📡 氣象局 API（直接寫死）
# =============================
API_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization=CWA-44069CF5-90E6-4ABF-8319-A6461633FA16"

@st.cache_data(ttl=900)
def fetch_cwa_weather():
    r = requests.get(API_URL, timeout=10, verify=False)
    r.raise_for_status()
    return r.json()


# ====================================
# 解析成 DataFrame
# ====================================
def parse_cwa_data(data: dict) -> pd.DataFrame:
    locations = data["records"]["location"]
    rows = []

    for loc in locations:
        city = loc["locationName"]

        elements = {e["elementName"]: e["time"] for e in loc["weatherElement"]}

        for i in range(len(elements["Wx"])):
            row = {
                "city": city,
                "startTime": elements["Wx"][i]["startTime"],
                "endTime": elements["Wx"][i]["endTime"],
                "weather": elements["Wx"][i]["parameter"]["parameterName"],
                "pop": elements["PoP"][i]["parameter"]["parameterName"],
                "minT": elements["MinT"][i]["parameter"]["parameterName"],
                "maxT": elements["MaxT"][i]["parameter"]["parameterName"],
            }
            rows.append(row)

    df = pd.DataFrame(rows)
    df["pop"] = pd.to_numeric(df["pop"], errors="coerce")
    df["minT"] = pd.to_numeric(df["minT"], errors="coerce")
    df["maxT"] = pd.to_numeric(df["maxT"], errors="coerce")
    return df


# ====================================
# Gemini AI 解析天氣（自動生成）
# ====================================
def gemini_explain_weather(df_city: pd.DataFrame) -> str:

    # 只取接下來三筆預報來統整
    items = df_city.head(3)

    text_block = ""
    for _, row in items.iterrows():
        text_block += (
            f"時間：{row['startTime']} ~ {row['endTime']}\n"
            f"天氣：{row['weather']}\n"
            f"最高溫：{row['maxT']}°C\n"
            f"最低溫：{row['minT']}°C\n"
            f"降雨機率：{row['pop']}%\n\n"
        )

    prompt = f"""
你是一位溫和親切的氣象小幫手。

以下是中央氣象署提供的未來天氣預報資料，請用 5~7 句溫柔、自然、生活化、容易理解的中文來統整：
{text_block}

請包含：
- 整體天氣趨勢
- 氣溫變化特色
- 降雨機率的提醒
- 日常生活建議（穿著、攜帶物品）

請以溫暖、貼心、像朋友聊天的方式撰寫。
"""

    response = model.generate_content(prompt)
    return response.text


# ====================================
# 主流程
# ====================================
try:
    raw = fetch_cwa_weather()
    df = parse_cwa_data(raw)
except Exception as e:
    st.error(f"❌ 無法取得氣象資料：{e}")
    st.stop()

# 選縣市
cities = sorted(df["city"].unique().tolist())
sel_city = st.sidebar.selectbox("選擇縣市", cities)
st.sidebar.caption("左側選單可切換不同縣市")

city_df = df[df["city"] == sel_city].sort_values("startTime")

# 圖表
st.subheader(f"📊 {sel_city} 未來 36 小時天氣趨勢")

col1, col2 = st.columns(2)

with col1:
    fig_temp = px.line(city_df, x="startTime", y=["minT", "maxT"], 
                       title="溫度趨勢", markers=True)
    st.plotly_chart(fig_temp, use_container_width=True)

with col2:
    fig_pop = px.bar(city_df, x="startTime", y="pop", title="降雨機率 (%)")
    st.plotly_chart(fig_pop, use_container_width=True)

# 表格
st.subheader("📋 天氣數據表格")
st.dataframe(city_df, use_container_width=True)

# 自動 AI 說明
st.subheader("🤖 Gemini AI 天氣說明（自動生成）")

try:
    ai_result = gemini_explain_weather(city_df)
    st.success("以下為 AI 自動產生的溫和天氣說明：")
    st.write(ai_result)

except Exception as e:
    st.error(f"AI 分析失敗：{e}")





