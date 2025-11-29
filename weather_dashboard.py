import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import google.generativeai as genai
import urllib3

# 忽略 SSL 警告（中央氣象局 API 常有問題）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =============================
# Streamlit 頁面設定
# =============================
st.set_page_config(
    page_title="台灣氣象 + Gemini AI Dashboard",
    page_icon="⛅",
    layout="wide"
)

st.title("⛅ 台灣氣象資料 Dashboard（36 小時預報）")
st.caption("資料來源：中央氣象署 F-C0032-001 / Gemini AI 語意分析")

# =============================
# 讀取 Secrets（Gemini + CWA）
# =============================
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
CWA_API_KEY = st.secrets["CWA_API_KEY"]  # ⭐ 你漏掉的部分！

# 初始化 Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-pro")

# =============================
# 抓取中央氣象署資料
# =============================

API_URL = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={CWA_API_KEY}"

@st.cache_data(ttl=900)
def fetch_cwa_weather():
    """ 從氣象局抓取天氣資料 """
    r = requests.get(API_URL, timeout=10, verify=False)
    r.raise_for_status()
    return r.json()

# =============================
# 整理資料成 DataFrame
# =============================
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


# =============================
# Gemini AI 天氣說明
# =============================
def gemini_explain_weather(text: str) -> str:
    prompt = (
        "以下是中央氣象署未來天氣資料，請用自然口語、生活化、容易理解的中文進行解釋：\n"
        f"{text}\n\n"
        "請統整：天氣狀況、氣溫、降雨狀況、穿衣建議。"
    )
    response = model.generate_content(prompt)
    return response.text

# =============================
# 主流程
# =============================
try:
    raw = fetch_cwa_weather()
    df = parse_cwa_data(raw)
except Exception as e:
