import streamlit as st
import google.generativeai as genai
import tempfile
import os
import time
import markdown
import pdfkit

# --- 1. 設定頁面基礎 ---
st.set_page_config(page_title="AI 課堂速記與教學系統", page_icon="📝", layout="centered")

# 美化介面 CSS
st.markdown("""
    <style>
    .stApp { background-color: #F5F7F9; }
    .stButton>button { color: white; background-color: #FF4B4B; border-radius: 20px; height: 3em; width: 100%; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #FFFFFF; border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px; padding-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 帳號登入系統 ---
USERS = {
    "student": {"password": "123", "role": "👩‍🎓 學生 (生成筆記)"},
    "teacher": {"password": "456", "role": "👨‍🏫 教師 (生成教材)"}
}

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None

if not st.session_state.logged_in:
    st.title("🔐 AI 課堂速記與教學系統")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.info("📝 測試帳號：\n* 學生請填：`student` / 密碼 `123`\n* 教師請填：`teacher` / 密碼 `456`")
        username = st.text_input("👤 帳號")
        password = st.text_input("🔑 密碼", type="password")
        if st.button("登入系統", type="primary", use_container_width=True):
            if username in USERS and USERS[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.user_role = USERS[username]["role"]
                st.rerun()
            else:
                st.error("❌ 帳號或密碼錯誤！")
    st.stop()

role = st.session_state.user_role

# --- 3. 側邊欄設定 ---
with st.sidebar:
    st.title("⚙️ 系統設定")
    st.success(f"目前身分：\n{role}")
    if st.button("🚪 登出系統", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_role = None
        st.rerun()
        
    st.divider()
    
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ 已載入自動金鑰")
    else:
        api_key = st.text_input("🔑 Google API Key", type="password")

    st.divider()
    st.info("👇 模型設定")
    model_options = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    model_name = st.selectbox("選擇模型", model_options)
    
    st.divider()
    st.info("🌐 輸出語言設定")
    output_language = st.selectbox(
        "選擇生成的筆記語言 (AI 會自動翻譯)",
        ["繁體中文", "English", "日本語", "한국어", "Español", "簡體中文", "自動偵測 (與錄音相同)"]
    )

# --- 4. 定義輔助函式 ---
def create_pdf(md_content):
    """將 Markdown 轉為 PDF"""
    html = markdown.markdown(md_content, extensions=['tables'])
    html_template = f"""
    <html>
      <head>
        <meta charset="UTF-8">
        <style>
          body {{ font-family: "Helvetica Neue", Helvetica, Arial, "Microsoft JhengHei", sans-serif; line-height: 1.6; padding: 2em; }}
          table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
          th, td {{ border: 1px solid #ccc; padding: 10px; text-align: left; }}
          th {{ background-color: #f8f9fa; font-weight: bold; }}
        </style>
      </head>
      <body>{html}</body>
    </html>
    """
    options = {'encoding': "UTF-8", 'enable-local-file-access': None}
    return pdfkit.from_string(html_template, False, options=options)

def analyze_audio_with_ai(model_name, file_path, prompt, status_box):
    """呼叫 AI 並處理重試機制"""
    model = genai.GenerativeModel(model_name)
    file = genai.upload_file(file_path)
    
    with st.spinner("上傳至 AI 大腦..."):
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
                status_box.write(f"⚠️ Google 伺服器忙碌中。冷卻 {wait_time} 秒後重試...")
                time.sleep(wait_time)
                continue
            elif "404" in str(e):
                raise Exception(f"模型 {model_name} 無法使用，請切換模型。")
            else:
                raise e
    raise Exception("系統忙碌中，請過幾分鐘再試。")

# --- 5. 主程式畫面 ---
lang_instruction = f"【重要指令】不論錄音檔原本是什麼語言，請務必將所有輸出的內容翻譯並撰寫為：「{output_language}」。" if "自動偵測" not in output_language else "【重要指令】請使用與錄音檔相同的語言來輸出內容。"

if "學生" in role:
    st.title("👩‍🎓 學生課堂速記助手")
    st.caption("將上課錄音自動轉換為「高品質複習筆記」與「考前猜題」")
    ai_prompt = f"""
    你是一位學霸助教。請仔細聆聽這段課堂錄音，幫學生整理出一份結構清晰的 Markdown 複習筆記。
    {lang_instruction}
    結構包含：1. 課程核心摘要 2. 關鍵名詞解釋(表格) 3. 重點觀念詳解 4. 考試重點預測。直接輸出 Markdown。
    """
    download_filename = "Student_Notes.md"
else:
    st.title("👨‍🏫 教師備課與教材生成器")
    st.caption("將授課錄音自動轉換為「課後大綱」與「隨堂測驗題」")
    ai_prompt = f"""
    你是一位專業教學助理。請仔細聆聽這段授課錄音，產出課後教材。
    {lang_instruction}
    結構包含：1. 課程內容大綱 2. 核心教學目標 3. 課後隨堂測驗(3題單選含解析) 4. 學生易錯點提醒。直接輸出 Markdown。
    """
    download_filename = "Teacher_Materials.md"

tab_upload, tab_record = st.tabs(["📂 上傳錄音檔", "🎙️ 網頁即時錄音"])
audio_data = None 

with tab_upload:
    uploaded = st.file_uploader("請上傳錄音檔", type=['mp3', 'wav', 'm4a', 'aac'])
    if uploaded:
        audio_data = uploaded
        st.audio(audio_data)

with tab_record:
    st.info("💡 允許麥克風後即可開始錄音。")
    recorded = st.audio_input("開始錄製語音")
    if recorded:
        audio_data = recorded

if audio_data and api_key:
    if st.button("🚀 開始全方位分析", type="primary", use_container_width=True):
        genai.configure(api_key=api_key)
        status_box = st.status("🚀 啟動 AI 引擎...", expanded=True)
        
        try:
            status_box.write("📂 讀取檔案中...")
            file_ext = f".{audio_data.name.split('.')[-1]}" if hasattr(audio_data, "name") and audio_data.name else ".wav"
                
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                tmp.write(audio_data.getvalue())
                tmp_path = tmp.name
            
            status_box.write(f"🧠 使用 {model_name} 進行深度分析...")
            final_content = analyze_audio_with_ai(model_name, tmp_path, ai_prompt, status_box)
            
            status_box.update(label="✅ 分析完成！", state="complete", expanded=False)
            st.markdown(final_content)
            
            # --- 下載按鈕區 ---
            col1, col2 = st.columns(2)
            with col1:
                st.download_button("📥 下載筆記 (.md)", data=final_content, file_name=download_filename, mime="text/markdown", use_container_width=True)
            with col2:
                try:
                    pdf_data = create_pdf(final_content)
                    st.download_button("📥 下載筆記 (.pdf)", data=pdf_data, file_name=download_filename.replace(".md", ".pdf"), mime="application/pdf", use_container_width=True)
                except Exception as pdf_err:
                    st.error("⚠️ PDF 生成失敗！")
                    st.code(f"詳細錯誤：\n{str(pdf_err)}")
                    st.info("👉 提示：如果您剛設定完 packages.txt，請務必執行右下角 Manage app -> Reboot 來重啟伺服器。")
                    
            os.remove(tmp_path)
            
        except Exception as e:
            status_box.update(label="❌ 發生錯誤", state="error")
            st.error(f"錯誤訊息: {e}")

elif not api_key:
    st.warning("請在左側輸入 API Key")
