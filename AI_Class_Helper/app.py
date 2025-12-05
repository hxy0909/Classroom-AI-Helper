import streamlit as st
import google.generativeai as genai
import tempfile
import os
import time
import re

# 1. 設定頁面
st.set_page_config(page_title="AI 課堂速記助手", page_icon="🎓", layout="wide")

# 2. 設定側邊欄
with st.sidebar:
    st.title("⚙️ 設定")
    
    # 嘗試讀取 Secrets，沒有的話就顯示輸入框
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ 已載入金鑰")
    else:
        api_key = st.text_input("🔑 Google API Key", type="password")

    st.divider()
    # 選擇模型 (只留最穩定的選項)
    model_name = st.selectbox("模型", ["gemini-1.5-flash", "gemini-1.5-pro"])
    style = st.radio("風格", ["大眾", "學術", "考試"])

# 3. 定義一個簡單的函式來呼叫 AI (避免主程式太亂)
def call_ai(model_name, file_path, prompt):
    model = genai.GenerativeModel(model_name)
    file = genai.upload_file(file_path)
    
    # 等待檔案處理
    while file.state.name == "PROCESSING":
        time.sleep(2)
        file = genai.get_file(file.name)
        
    # 嘗試生成 (簡單的重試邏輯)
    for i in range(3):
        try:
            response = model.generate_content([file, prompt])
            return response.text
        except Exception as e:
            if "429" in str(e): # 如果太忙碌，休息一下再試
                time.sleep(5)
                continue
            else:
                raise e # 其他錯誤直接丟出
    raise Exception("系統忙碌中，請稍後再試")

# 4. 主程式介面
st.title("🎓 AI 課堂速記助手")
uploaded = st.file_uploader("上傳錄音檔", type=['mp3', 'wav', 'm4a', 'aac'])

if uploaded and api_key:
    if st.button("🚀 開始分析"):
        # 設定 API
        genai.configure(api_key=api_key)
        
        status = st.status("處理中...", expanded=True)
        
        try:
            # 儲存暫存檔
            status.write("📂 讀取檔案...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name
            
            # 呼叫 AI
            status.write(f"🧠 AI ({model_name}) 正在分析...")
            prompt = f"請用Markdown格式整理筆記，包含：摘要、名詞解釋、考題。風格：{style}"
            
            result = call_ai(model_name, tmp_path, prompt)
            
            # 完成
            status.update(label="✅ 完成！", state="complete", expanded=False)
            st.markdown(result)
            st.download_button("下載筆記", result, "notes.md")
            
            # 清理
            os.remove(tmp_path)
            
        except Exception as e:
            status.update(label="❌ 出錯了", state="error")
            st.error(f"錯誤訊息: {e}")
            if "404" in str(e):
                st.warning("請檢查 requirements.txt 是否已更新並重啟 App。")

elif not api_key:
    st.warning("請輸入 API Key")
