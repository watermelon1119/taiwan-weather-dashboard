import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import google.generativeai as genai
import urllib3

# ⚠ 忽略 SSL 警告 (CWA API 的憑證常會出錯)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =============================
# 🔧 Streamlit 頁面設定
# =============================
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
model = genai.GenerativeModel("gemini-pro")

# =============================
# 📡 抓取中央氣象署 36 小時預報資料
# =============================

API_URL = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={CWA_API_KEY}"

@st.cache_data(ttl=900)  # cache 15 分鐘
def fetch_cwa_weather():
    """ 從氣象局抓取天氣資料 """
    params = {
        "Authorization": GEMINI_API_KEY  # ❗ 你的 CWA Key 如果不同要改
    }
    r = requests.get(API_URL, params=params, timeout=10, verify=False)
    r.raise_for_status()
    return r.json()

# =============================
# 🔍 整理資料 (變成 DataFrame)
# =============================
def parse_cwa_data(data: dict) -> pd.DataFrame:
    locations = data["records"]["location"]
    rows = []

    for loc in locations:
        city = loc["locationName"]

        # 把 elementName 轉成 dictionary
        elements = {e["elementName"]: e["time"] for e in loc["weatherElement"]}

        # Wx, PoP, MinT, MaxT 都有 3 筆資料（未來 36 小時）
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

    # 加數值欄位為 float
    df["pop"] = pd.to_numeric(df["pop"], errors="coerce")
    df["minT"] = pd.to_numeric(df["minT"], errors="coerce")
    df["maxT"] = pd.to_numeric(df["maxT"], errors="coerce")

    return df

# =============================
# 🤖 Gemini AI 解讀天氣
# =============================
def gemini_explain_weather(text: str) -> str:
    prompt = f"以下是中央氣象署的未來天氣資料，請用自然口語、生活化、容易理解的中文進行解釋：\n{text}\n\n請統整出『天氣狀況、氣溫、降雨狀況、穿衣建議』。"

    response = model.generate_content(prompt)
    return response.text


# =============================
# 🚀 主程式流程
# =============================

# step1: 抓資料
try:
    raw = fetch_cwa_weather()
    df = parse_cwa_data(raw)
except Exception as e:
    st.error(f"無法取得氣象資料：{e}")
    st.stop()

# step2：城市選擇
cities = sorted(df["city"].unique().tolist())

sel_city = st.sidebar.selectbox("選擇縣市", cities)
st.sidebar.caption("左側選單可切換不同縣市")

city_df = df[df["city"] == sel_city].sort_values("startTime")

# step3：數據呈現
st.subheader(f"📊 {sel_city} 未來 36 小時天氣趨勢")

col1, col2 = st.columns(2)

with col1:
    fig_temp = px.line(
        city_df,
        x="startTime",
        y=["minT", "maxT"],
        title="溫度趨勢",
        markers=True
    )
    st.plotly_chart(fig_temp, use_container_width=True)

with col2:
    fig_pop = px.bar(
        city_df,
        x="startTime",
        y="pop",
        title="降雨機率 (%)"
    )
    st.plotly_chart(fig_pop, use_container_width=True)

# step4：表格呈現
st.subheader("📋 天氣數據表格")
st.dataframe(city_df, use_container_width=True)

# step5：Gemini AI 分析
st.subheader("🤖 Gemini AI 天氣說明")

if st.button("產生 AI 分析 ✨"):
    sample = city_df.iloc[0]  # 取第一筆進行分析

    text_block = (
        f"城市：{sample['city']}\n"
        f"時間：{sample['startTime']} ~ {sample['endTime']}\n"
        f"天氣：{sample['weather']}\n"
        f"最高溫：{sample['maxT']}°C\n"
        f"最低溫：{sample['minT']}°C\n"
        f"降雨機率：{sample['pop']}%\n"
    )

    try:
        ai_result = gemini_explain_weather(text_block)
        st.success("以下是 Gemini AI 的天氣解讀：")
        st.write(ai_result)
    except Exception as e:
        st.error(f"AI 分析失敗：{e}")


