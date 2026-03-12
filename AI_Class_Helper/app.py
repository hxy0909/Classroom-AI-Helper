import streamlit as st
import google.generativeai as genai
import tempfile
import os
import time

# 1. 設定頁面基礎
st.set_page_config(
    page_title="AI 課堂速記助手", 
    page_icon="📝", 
    layout="centered" 
)

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

# 2. 側邊欄設定
with st.sidebar:
    st.title("⚙️ 設定")
    
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ 已載入金鑰")
    else:
        api_key = st.text_input("🔑 Google API Key", type="password")

    st.divider()
    
    st.info("👇 模型設定")
    model_options = [
        "gemini-2.5-flash",
        "gemini-2.0-flash", 
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash"
    ]
    model_name = st.selectbox("選擇模型", model_options)
    
    style = st.radio("筆記風格", ["一般大眾 (淺顯易懂)", "專業學術 (詳細嚴謹)", "考試衝刺 (只列考點)"])

# 3. 定義 AI 呼叫函式
def generate_note(model_name, file_path, prompt, status_box):
    model = genai.GenerativeModel(model_name)
    file = genai.upload_file(file_path)
    
    with st.spinner("正在將錄音檔上傳至 AI 大腦..."):
        while file.state.name == "PROCESSING":
            time.sleep(2)
            file = genai.get_file(file.name)
        if file.state.name == "FAILED":
            raise Exception("檔案處理失敗")

    max_retries = 5
    for i in range(max_retries):
        try:
            response = model.generate_content([file, prompt])
            return response.text
        except Exception as e:
            if "429" in str(e):
                wait_time = 10 * (i + 1)
                status_box.write(f"⚠️ Google 伺服器忙碌中。自動冷卻 {wait_time} 秒後進行第 {i+1} 次重試...")
                time.sleep(wait_time)
                continue
            elif "404" in str(e):
                raise Exception(f"模型 {model_name} 無法使用，請切換其他模型。")
            else:
                raise e
    raise Exception("系統忙碌中，已經盡力重試。請過幾分鐘再試。")

# 4. 主程式畫面
st.title("📝 AI 課堂速記助手")
st.caption("專注於將錄音轉換為高品質 Markdown 筆記")

# --- 【關鍵修改區】使用 Tabs 將輸入方式分為兩種 ---
tab_upload, tab_record = st.tabs(["📂 上傳錄音檔", "🎙️ 網頁即時錄音"])

# 建立一個變數來統一存放最終要分析的音檔資料
audio_data = None 

with tab_upload:
    uploaded = st.file_uploader("請上傳錄音檔 (mp3, wav, m4a)", type=['mp3', 'wav', 'm4a', 'aac'])
    if uploaded:
        audio_data = uploaded
        st.audio(audio_data)

with tab_record:
    st.info("💡 允許瀏覽器使用麥克風後，點擊下方按鈕即可開始錄音。")
    recorded = st.audio_input("開始錄製語音")
    if recorded:
        audio_data = recorded
# --- 修改結束 ---

if audio_data and api_key:
    if st.button("🚀 開始生成筆記", type="primary", use_container_width=True):
        genai.configure(api_key=api_key)
        
        status_box = st.status("🚀 AI 正在聆聽並整理重點...", expanded=True)
        
        try:
            status_box.write("📂 讀取檔案中...")
            
            # --- 【判斷檔案副檔名】確保即時錄音(wav)也能正確存檔 ---
            file_ext = ".wav" # 預設為 wav
            if hasattr(audio_data, "name") and audio_data.name:
                file_ext = f".{audio_data.name.split('.')[-1]}"
                
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                tmp.write(audio_data.getvalue())
                tmp_path = tmp.name
            
            status_box.write(f"🧠 使用 {model_name} 進行深度分析...")
            prompt = f"""
            你是一位專業的教授助教。請仔細聆聽這段錄音，並根據「{style}」風格，整理出一份結構清晰的 Markdown 筆記。
            
            筆記結構請包含：
            1. **課程標題與摘要** (200字內)
            2. **關鍵名詞解釋** (使用表格呈現：名詞 | 解釋 | 重要性)
            3. **核心觀念詳解** (請使用條列式，並適當使用粗體標示重點)
            4. **考試重點預測** (列出老師語氣加重或重複提及的地方)
            
            請直接輸出 Markdown 內容，不需其他開場白。
            """
            
            note_content = generate_note(model_name, tmp_path, prompt, status_box)
            
            status_box.update(label="✅ 筆記整理完成！", state="complete", expanded=False)
            
            st.divider()
            st.markdown(note_content)
            
            st.download_button(
                label="📥 下載筆記 (.md)",
                data=note_content,
                file_name="lecture_note.md",
                mime="text/markdown",
                use_container_width=True
            )
            
            os.remove(tmp_path)
            
        except Exception as e:
            status_box.update(label="❌ 發生錯誤", state="error")
            st.error(f"錯誤訊息: {e}")

elif not api_key:
    st.warning("請在左側輸入 API Key 以開始使用")
