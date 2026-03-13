import streamlit as st
import google.generativeai as genai
import tempfile
import os
import time
import markdown
import pdfkit

# --- 1. 設定頁面基礎 ---
st.set_page_config(
    page_title="AI 課堂速記與教學助手", 
    page_icon="🎓", 
    layout="centered" 
)

# 美化介面 CSS
st.markdown("""
    <style>
    .stApp { background-color: #F5F7F9; }
    .stButton>button {
        color: white;
        background-color: #FF4B4B;
        border-radius: 20px;
        height: 3em;
        width: 100%;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #FFFFFF;
        border-radius: 4px 4px 0px 0px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 帳號登入系統 (新增) ---
# 預設的測試帳號密碼 (您可以自行新增或修改)
USERS = {
    "student": {"password": "123", "role": "👩‍🎓 學生 (生成筆記)"},
    "teacher": {"password": "456", "role": "👨‍🏫 教師 (生成教材)"}
}

# 初始化 Session State 來記住登入狀態
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None

# 如果未登入，顯示登入畫面並阻擋後續程式執行
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
                st.rerun() # 驗證成功，重新整理網頁進入主系統
            else:
                st.error("❌ 帳號或密碼錯誤！")
    st.stop() # 關鍵：停止執行後續的 UI，直到登入成功

# 取得目前登入者的身分
role = st.session_state.user_role

# --- 3. 側邊欄設定 (登入後才會顯示) ---
with st.sidebar:
    st.title("⚙️ 系統設定")
    
    # 顯示當前登入身分與登出按鈕
    st.success(f"目前身分：\n{role}")
    if st.button("🚪 登出系統", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_role = None
        st.rerun()
        
    st.divider()
    
    # API Key 設定
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ 已自動載入系統金鑰")
    else:
        api_key = st.text_input("🔑 輸入 Google API Key", type="password")

    st.divider()
    
    # 模型設定
    st.info("👇 模型設定")
    model_options = [
        "gemini-2.5-flash",
        "gemini-2.0-flash", 
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash"
    ]
    model_name = st.selectbox("選擇模型", model_options)

    st.divider()
    
    # 語言設定 (新增多國語言支援)
    st.info("🌐 輸出語言設定")
    output_language = st.selectbox(
        "請選擇生成的筆記語言 (AI 會自動翻譯)",
        ["繁體中文", "English", "日本語", "한국어", "Español", "Français", "Deutsch", "簡體中文", "自動偵測 (與錄音相同)"]
    )

# --- 3. 定義 AI 呼叫函式 (含防當機機制) ---
def create_pdf(md_content):
    """將 Markdown 內容轉換為 PDF 格式"""
    # 1. 先將 Markdown 轉成 HTML (支援表格解析)
    html = markdown.markdown(md_content, extensions=['tables'])
    
    # 2. 加上 CSS 樣式與 UTF-8 編碼，防止中文亂碼並美化表格
    html_template = f"""
    <html>
      <head>
        <meta charset="UTF-8">
        <style>
          body {{ font-family: "Helvetica Neue", Helvetica, Arial, "Microsoft JhengHei", "PingFang TC", sans-serif; line-height: 1.6; padding: 2em; }}
          h1, h2, h3 {{ color: #333; }}
          table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
          th, td {{ border: 1px solid #ccc; padding: 10px; text-align: left; }}
          th {{ background-color: #f8f9fa; font-weight: bold; }}
          blockquote {{ border-left: 4px solid #ccc; margin: 0; padding-left: 10px; color: #666; }}
        </style>
      </head>
      <body>
        {html}
      </body>
    </html>
    """
    
    # 3. 轉譯為 PDF 位元組資料
    options = {
        'encoding': "UTF-8",
        'enable-local-file-access': None
    }
    return pdfkit.from_string(html_template, False, options=options)

def analyze_audio_with_ai(model_name, file_path, prompt, status_box):
    model = genai.GenerativeModel(model_name)
    file = genai.upload_file(file_path)
    
    with st.spinner("正在將音檔上傳至 AI 大腦..."):
        while file.state.name == "PROCESSING":
            time.sleep(2)
            file = genai.get_file(file.name)
        if file.state.name == "FAILED":
            raise Exception("檔案處理失敗，請確認檔案格式是否正確。")

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
    raise Exception("系統忙碌中，已經盡力重試。請稍後再試。")

# --- 4. 主程式畫面 (根據身分變換 UI) ---
# 新增語種控制指令
lang_instruction = f"【重要指令】不論錄音檔原本是什麼語言，請務必將所有輸出的內容翻譯並撰寫為：「{output_language}」。" if "自動偵測" not in output_language else "【重要指令】請使用與錄音檔相同的語言來輸出內容。"

if role == "👩‍🎓 學生 (生成筆記)":
    st.title("👩‍🎓 學生課堂速記助手")
    st.caption("將上課錄音自動轉換為「高品質複習筆記」與「考前猜題」")
    
    # 學生專屬 Prompt (加入語言指令)
    ai_prompt = f"""
    你是一位學霸助教。請仔細聆聽這段課堂錄音，幫學生整理出一份結構清晰的 Markdown 複習筆記。
    
    {lang_instruction}
    
    請包含以下結構：
    1. **📖 課程核心摘要** (200字內精華)
    2. **🔑 關鍵名詞解釋** (請用表格呈現：名詞 | 解釋 | 重要度星號)
    3. **💡 重點觀念詳解** (請使用條列式，並適當使用粗體標示重點)
    4. **🎯 考試重點預測** (列出老師語氣加重、重複提及、或暗示會考的地方)
    請直接輸出 Markdown 內容。
    """
    download_filename = "Student_Notes.md"

else:
    st.title("👨‍🏫 教師備課與教材生成器")
    st.caption("將您的授課錄音自動轉換為「課後大綱」與「隨堂測驗題」")
    
    # 教師專屬 Prompt (加入語言指令)
    ai_prompt = f"""
    你是一位專業的教學助理。請仔細聆聽這段授課錄音，協助教授產出課後教材。
    
    {lang_instruction}
    
    請包含以下結構：
    1. **📝 課程內容大綱** (適合放在教學平台給學生看的總結)
    2. **🎯 核心教學目標** (這堂課傳達了哪些重要概念)
    3. **❓ 課後隨堂測驗** (請根據錄音內容，出 3 題單選題，並在最後附上解答與解析)
    4. **💬 學生易錯點提醒** (根據教學經驗，總結這段內容學生最容易聽不懂的地方)
    請直接輸出 Markdown 內容。
    """
    download_filename = "Teacher_Materials.md"

# --- 5. 檔案輸入區 (雙重輸入模式) ---
tab_upload, tab_record = st.tabs(["📂 上傳錄音檔", "🎙️ 網頁即時錄音"])

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

# --- 6. 執行 AI 分析 ---
if audio_data and api_key:
    # 按鈕文字也會跟著身分改變
    btn_text = "🚀 開始生成筆記 (學生版)" if role == "👩‍🎓 學生 (生成筆記)" else "🚀 開始生成教材 (教師版)"
    
    if st.button(btn_text, type="primary", use_container_width=True):
        genai.configure(api_key=api_key)
        status_box = st.status("🚀 AI 正在處理中...", expanded=True)
        
        try:
            status_box.write("📂 讀取音訊檔案中...")
            
            # 判斷副檔名 (錄音通常是 wav，上傳可能是 mp3)
            file_ext = ".wav" 
            if hasattr(audio_data, "name") and audio_data.name:
                file_ext = f".{audio_data.name.split('.')[-1]}"
                
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                tmp.write(audio_data.getvalue())
                tmp_path = tmp.name
            
            status_box.write(f"🧠 使用 {model_name} 進行深度分析...")
            
            # 呼叫 AI (將上面定義好的 prompt 傳進去)
            final_content = analyze_audio_with_ai(model_name, tmp_path, ai_prompt, status_box)
            
            status_box.update(label="✅ 處理完成！", state="complete", expanded=False)
            
            # 顯示結果
            st.divider()
            st.markdown(final_content)
            
            # --- 雙格式下載按鈕區 ---
            col1, col2 = st.columns(2)
            
            with col1:
                # 下載 Markdown 按鈕
                st.download_button(
                    label="📥 下載檔案 (.md)",
                    data=final_content,
                    file_name=download_filename,
                    mime="text/markdown",
                    use_container_width=True
                )
            
            with col2:
                # 生成並下載 PDF 按鈕
                try:
                    pdf_data = create_pdf(final_content)
                    pdf_filename = download_filename.replace(".md", ".pdf")
                    st.download_button(
                        label="📥 下載檔案 (.pdf)",
                        data=pdf_data,
                        file_name=pdf_filename,
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as pdf_err:
                    # 捕捉未安裝系統套件的錯誤，避免網頁當機
                    st.error(f"⚠️ PDF 生成失敗 (請確認 GitHub 專案中已設定 packages.txt)。")
                    
            # 清理暫存檔
            os.remove(tmp_path)
            
        except Exception as e:
            status_box.update(label="❌ 發生錯誤", state="error")
            st.error(f"錯誤訊息: {e}")

elif not api_key:
    st.warning("⚠️ 請在左側輸入 API Key 以開始使用")
