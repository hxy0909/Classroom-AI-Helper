
薪雅 <kew923894@gmail.com>
11:42 (3分钟前)
发送至 我

import streamlit as st
import google.generativeai as genai
import tempfile
import os
import time
import re

# 1. 設定頁面
st.set_page_config(page_title="AI 課堂速記助手", page_icon="🎓", layout="wide")
# 美化介面 CSS
st.markdown("""
    <style>
    .stApp {
        background-color: #F5F7F9;
    }
    .stButton>button {
        color: white;
        background-color: #FF4B4B;
        border-radius: 20px;
        height: 3em;
        width: 100%;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #FFFFFF;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)
# 2. 設定側邊欄
with st.sidebar:
    st.title("⚙️ 設定")
   
    # 嘗試讀取 Secrets
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ 已載入金鑰")
    else:
        api_key = st.text_input("🔑 Google API Key", type="password")

    st.divider()
   
    st.info("👇 請注意：您的帳號需使用 2.0 系列")
    # 【關鍵修正】根據您的截圖，您的 Key 只能用這些模型
    # 我們把 2.0-flash 放在第一個
    model_options = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash"  # 保留備用
    ]
    model_name = st.selectbox("選擇模型", model_options)
    style = st.radio("風格", ["大眾", "學術", "考試"])

# 3. 定義 AI 呼叫函式 (含強力重試機制)
def call_ai(model_name, file_path, prompt):
    model = genai.GenerativeModel(model_name)
    file = genai.upload_file(file_path)
   
    # 等待檔案處理
    with st.spinner("檔案上傳處理中..."):
        while file.state.name == "PROCESSING":
            time.sleep(2)
            file = genai.get_file(file.name)
        if file.state.name == "FAILED":
            raise Exception("檔案處理失敗，請檢查格式")

    # 嘗試生成 (針對 429 錯誤進行指數退避重試)
    max_retries = 5
    for i in range(max_retries):
        try:
            response = model.generate_content([file, prompt])
            return response.text
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg:
                # 如果是 429 (忙碌)，等待時間隨次數增加 (5s, 10s, 20s...)
                wait_time = 5 * (2 ** i)
                st.toast(f"⏳ 伺服器忙碌 (429)，正在冷卻 {wait_time} 秒後重試 ({i+1}/{max_retries})...", icon="🧊")
                time.sleep(wait_time)
                continue
            elif "404" in error_msg:
                # 如果是 404，直接告訴使用者換模型
                raise Exception(f"模型 {model_name} 不存在或無權限。請在左側切換其他模型 (例如 gemini-2.0-flash)。")
            else:
                raise e
               
    raise Exception("伺服器過於繁忙，重試多次失敗。請稍後再試。")

# 4. 主程式介面
st.title("🎓 AI 課堂速記助手")
uploaded = st.file_uploader("上傳錄音檔", type=['mp3', 'wav', 'm4a', 'aac'])

if uploaded and api_key:
    if st.button("🚀 開始分析"):
        genai.configure(api_key=api_key)
        status = st.status("🚀 啟動 AI 引擎...", expanded=True)
       
        try:
            status.write("📂 讀取暫存檔...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name
           
            status.write(f"🧠 AI ({model_name}) 正在分析內容...")
            prompt = f"""
            你是一位專業助教。請依風格「{style}」將錄音內容整理成Markdown筆記。
            包含：1.摘要 2.名詞解釋(表格) 3.考前猜題。
            請直接輸出 Markdown，不要包含其他無關文字。
            """
           
            result = call_ai(model_name, tmp_path, prompt)
           
            status.update(label="✅ 分析完成！", state="complete", expanded=False)
            st.markdown(result)
            st.download_button("下載筆記", result, "notes.md")
           
            os.remove(tmp_path)
           
        except Exception as e:
            status.update(label="❌ 發生錯誤", state="error")
            st.error(f"錯誤詳細訊息: {e}")
           
            # 給出具體建議
            if "429" in str(e):
                st.warning("💡 建議：現在伺服器很擠，請等待幾分鐘後再按一次開始。")
            if "404" in str(e):
                st.warning("💡 建議：您的 Key 不支援目前的模型，請在側邊欄換一個模型試試看。")

elif not api_key:
    st.warning("請輸入 API Key")
