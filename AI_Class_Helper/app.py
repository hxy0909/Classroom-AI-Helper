import streamlit as st
import google.generativeai as genai
import tempfile
import os
import time

# 1. 設定頁面基礎
st.set_page_config(
    page_title="AI 課堂速記助手", 
    page_icon="📝", 
    layout="centered" # 改回置中，閱讀筆記比較舒服
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
    
    # 自動讀取金鑰
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ 已載入金鑰")
    else:
        api_key = st.text_input("🔑 Google API Key", type="password")

    st.divider()
    
    st.info("👇 模型設定")
    # 保留您的帳號能用的 2.0 模型
    model_options = [
        "gemini-2.0-flash", 
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash"
    ]
    model_name = st.selectbox("選擇模型", model_options)
    
    # 風格設定
    style = st.radio("筆記風格", ["一般大眾 (淺顯易懂)", "專業學術 (詳細嚴謹)", "考試衝刺 (只列考點)"])

# 3. 定義 AI 呼叫函式 (保留防當機重試機制)
def generate_note(model_name, file_path, prompt):
    model = genai.GenerativeModel(model_name)
    file = genai.upload_file(file_path)
    
    # 等待檔案處理
    with st.spinner("正在將錄音檔上傳至 AI 大腦..."):
        while file.state.name == "PROCESSING":
            time.sleep(2)
            file = genai.get_file(file.name)
        if file.state.name == "FAILED":
            raise Exception("檔案處理失敗")

    # 重試機制 (解決 429 Resource Exhausted)
    max_retries = 5
    for i in range(max_retries):
        try:
            response = model.generate_content([file, prompt])
            return response.text
        except Exception as e:
            if "429" in str(e):
                wait_time = 5 * (2 ** i)
                st.toast(f"⏳ 伺服器忙碌，休息 {wait_time} 秒後繼續...", icon="💤")
                time.sleep(wait_time)
                continue
            elif "404" in str(e):
                raise Exception(f"模型 {model_name} 無法使用，請切換其他模型。")
            else:
                raise e
    raise Exception("系統忙碌中，請稍後再試。")

# 4. 主程式畫面
st.title("📝 AI 課堂速記助手")
st.caption("專注於將錄音轉換為高品質 Markdown 筆記")

uploaded = st.file_uploader("請上傳錄音檔 (mp3, wav, m4a)", type=['mp3', 'wav', 'm4a', 'aac'])

if uploaded:
    st.audio(uploaded, format='audio/mp3')

if uploaded and api_key:
    if st.button("🚀 開始生成筆記", type="primary", use_container_width=True):
        genai.configure(api_key=api_key)
        
        # 建立狀態容器
        status_box = st.status("🚀 AI 正在聆聽並整理重點...", expanded=True)
        
        try:
            # 儲存暫存檔
            status_box.write("📂 讀取檔案中...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name
            
            # 設定 Prompt (只專注於筆記，不畫圖、不出題)
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
            
            # 執行生成
            note_content = generate_note(model_name, tmp_path, prompt)
            
            # 完成
            status_box.update(label="✅ 筆記整理完成！", state="complete", expanded=False)
            
            # 顯示結果
            st.divider()
            st.markdown(note_content)
            
            # 下載按鈕
            st.download_button(
                label="📥 下載筆記 (.md)",
                data=note_content,
                file_name="lecture_note.md",
                mime="text/markdown",
                use_container_width=True
            )
            
            # 清理檔案
            os.remove(tmp_path)
            
        except Exception as e:
            status_box.update(label="❌ 發生錯誤", state="error")
            st.error(f"錯誤訊息: {e}")

elif not api_key:
    st.warning("請在左側輸入 API Key 以開始使用")
