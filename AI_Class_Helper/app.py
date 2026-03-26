import streamlit as st
import google.generativeai as genai
import tempfile
import os
import time
import markdown
import json

# --- 0. 初始化系統資料夾與資料庫 ---
# 改為儲存講義 (Markdown) 而不是笨重的音檔
SHARED_DIR = "shared_notes"
os.makedirs(SHARED_DIR, exist_ok=True)
COMMENTS_FILE = os.path.join(SHARED_DIR, "comments.json")

def load_comments():
    if os.path.exists(COMMENTS_FILE):
        with open(COMMENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_comments(comments_data):
    with open(COMMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(comments_data, f, ensure_ascii=False, indent=2)

# --- 1. 設定頁面基礎 ---
st.set_page_config(page_title="AI 課堂速記與教學系統", page_icon="📝", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #F5F7F9; }
    .stButton>button { color: white; background-color: #FF4B4B; border-radius: 20px; height: 3em; width: 100%; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #FFFFFF; border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px; padding-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 帳號登入與狀態管理 ---
USERS = {
    "student": {"password": "123", "role": "👩‍🎓 學生 (生成筆記)"},
    "teacher": {"password": "456", "role": "👨‍🏫 教師 (生成教材)"}
}

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_role' not in st.session_state: st.session_state.user_role = None
if 'generated_note' not in st.session_state: st.session_state.generated_note = None
if 'note_filename' not in st.session_state: st.session_state.note_filename = ""
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'current_shared_file' not in st.session_state: st.session_state.current_shared_file = None

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
        st.session_state.generated_note = None
        st.session_state.chat_history = []
        st.session_state.current_shared_file = None
        st.rerun()
        
    st.divider()
    
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ 已自動載入雲端保險箱金鑰")
    else:
        api_key = st.text_input("🔑 Google API Key", type="password")
        if not api_key:
            st.warning("⚠️ 尚未設定金鑰，請在 Streamlit 後台設定 Secrets")

    st.divider()
    st.info("👇 模型設定")
    model_options = ["gemini-2.5-flash", "gemini-2.0-flash"]
    model_name = st.selectbox("選擇模型", model_options)
    
    st.divider()
    st.info("🌐 輸出語言設定")
    output_language = st.selectbox(
        "選擇生成的筆記語言 (AI 會自動翻譯)",
        ["繁體中文", "English", "日本語", "한국어", "Español", "簡體中文", "自動偵測 (與錄音相同)"]
    )

# --- 4. 定義核心 AI 與處理函式 ---
def create_pdf(md_content):
    from weasyprint import HTML
    html = markdown.markdown(md_content, extensions=['tables'])
    html_template = f"""
    <html>
      <head>
        <meta charset="UTF-8">
        <style>
          body {{ font-family: "Noto Sans CJK TC", sans-serif; line-height: 1.6; padding: 2em; }}
          table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
          th, td {{ border: 1px solid #ccc; padding: 10px; text-align: left; }}
          th {{ background-color: #f8f9fa; font-weight: bold; }}
        </style>
      </head>
      <body>{html}</body>
    </html>
    """
    return HTML(string=html_template).write_pdf()

def analyze_audio_with_ai(model_name, file_path, prompt, status_box):
    model = genai.GenerativeModel(model_name)
    file = genai.upload_file(file_path)
    status_box.write("⏳ 正在上傳至 AI 雲端，請稍候...")
    while file.state.name == "PROCESSING":
        time.sleep(2)
        file = genai.get_file(file.name)
    if file.state.name == "FAILED":
        raise Exception("檔案處理失敗")

    max_retries = 5
    for i in range(max_retries):
        try:
            if i > 0: status_box.write(f"🔄 第 {i+1} 次嘗試呼叫 AI...")
            response = model.generate_content([file, prompt])
            return response.text
        except Exception as e:
            if "429" in str(e):
                wait_time = 10 * (i + 1)
                status_box.write(f"⚠️ 伺服器忙碌中。冷卻 {wait_time} 秒後重試...")
                time.sleep(wait_time)
                continue
            elif "404" in str(e):
                raise Exception(f"模型無法使用，請切換模型。")
            else:
                raise e
    raise Exception("系統忙碌中，請過幾分鐘再試。")

def generate_and_store_note(file_path_to_analyze, ai_prompt, download_filename):
    genai.configure(api_key=api_key)
    with st.status("🚀 啟動 AI 引擎...", expanded=True) as status_box:
        try:
            status_box.write("📂 讀取檔案中...")
            status_box.write(f"🧠 使用 {model_name} 進行深度分析...")
            final_content = analyze_audio_with_ai(model_name, file_path_to_analyze, ai_prompt, status_box)
            
            st.session_state.generated_note = final_content
            st.session_state.note_filename = download_filename
            st.session_state.chat_history = []
            st.session_state.current_shared_file = None # 自己生成的，非從共享載入
            
            status_box.update(label="✅ 講義生成完成！請至下方預覽並發布。", state="complete", expanded=False)
        except Exception as e:
            status_box.update(label="❌ 發生錯誤", state="error", expanded=True)
            st.error(f"錯誤訊息: {e}")

def analyze_from_buffer(audio_buffer, ai_prompt, download_filename):
    file_ext = f".{audio_buffer.name.split('.')[-1]}" if hasattr(audio_buffer, "name") and audio_buffer.name else ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
        tmp.write(audio_buffer.getvalue())
        tmp_path = tmp.name
    generate_and_store_note(tmp_path, ai_prompt, download_filename)
    try: os.remove(tmp_path)
    except: pass

lang_instruction = f"【重要指令】不論錄音檔原本是什麼語言，請務必將所有輸出的內容翻譯並撰寫為：「{output_language}」。" if "自動偵測" not in output_language else "【重要指令】請使用與錄音檔相同的語言來輸出內容。"

# ==========================================
# 👨‍🏫 教師專屬介面
# ==========================================
if "教師" in role:
    st.title("👨‍🏫 教師備課與教材發布中心")
    st.caption("管理您的授課錄音、生成大綱，發布講義並回覆學生的提問")
    
    ai_prompt = f"""
    你是一位專業教學助理。請仔細聆聽這段授課錄音，產出課後教材。
    {lang_instruction}
    請嚴格遵守以下結構，並務必在第2點和第3點之間插入「---TEACHER_ONLY---」作為系統分隔線：
    1. 課程內容大綱
    2. 核心教學目標
    ---TEACHER_ONLY---
    3. 課後隨堂測驗(3題單選含解析)
    4. 學生易錯點提醒
    
    請直接輸出 Markdown 內容。
    """
    
    tab_upload, tab_record, tab_comments = st.tabs(["📂 上傳錄音產製教材", "🎙️ 網頁錄音產製教材", "💬 學生提問留言板"])
    audio_data = None 

    with tab_upload:
        uploaded = st.file_uploader("請上傳您的授課錄音以生成講義", type=['mp3', 'wav', 'm4a', 'aac'])
        if uploaded: audio_data = uploaded; st.audio(audio_data)

    with tab_record:
        st.info("💡 允許麥克風後即可開始錄音。")
        recorded = st.audio_input("開始錄製授課內容")
        if recorded: audio_data = recorded

    if audio_data:
        st.divider()
        st.subheader("🤖 生成課後講義")
        if not api_key: st.warning("請在側邊欄輸入 API Key")
        elif st.button("🚀 開始生成教材", type="primary", use_container_width=True):
            analyze_from_buffer(audio_data, ai_prompt, "Teacher_Materials.md")

    # 教師端留言板管理 (讀取已發布的 Markdown)
    with tab_comments:
        st.subheader("💬 管理學生提問與留言")
        shared_md_files = [f for f in os.listdir(SHARED_DIR) if f.endswith('.md')]
        
        if shared_md_files:
            selected_file = st.selectbox("選擇要查看的講義", ["-- 請選擇 --"] + shared_md_files, key="teacher_select")
            if selected_file != "-- 請選擇 --":
                # 可選：預覽講義內容
                with st.expander("📖 展開預覽此份講義內容"):
                    with open(os.path.join(SHARED_DIR, selected_file), "r", encoding="utf-8") as f:
                        preview_content = f.read().replace("---TEACHER_ONLY---", "\n\n---\n**🔒 以下為教師專屬內容 (學生端不可見)：**\n\n")
                        st.markdown(preview_content)
                        
                all_comments = load_comments()
                course_comments = all_comments.get(selected_file, [])
                
                st.divider()
                if course_comments:
                    for c in course_comments:
                        avatar = "👨‍🎓" if c['role'] == "student" else "👨‍🏫"
                        with st.chat_message(c['role'], avatar=avatar):
                            st.write(c['content'])
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        reply_text = st.text_input("回覆學生...", key="teacher_reply", label_visibility="collapsed")
                    with col2:
                        if st.button("送出回覆", type="primary", use_container_width=True):
                            if reply_text:
                                course_comments.append({"role": "teacher", "content": reply_text})
                                all_comments[selected_file] = course_comments
                                save_comments(all_comments)
                                st.rerun()
                else:
                    st.info("這份講義目前還沒有學生提問喔！")
        else:
            st.warning("目前還沒有發布任何講義。請先在左側分頁生成並發布。")

# ==========================================
# 👩‍🎓 學生專屬介面
# ==========================================
else:
    st.title("👩‍🎓 學生課堂速記助手")
    st.caption("閱讀老師發布的講義，或自行上傳錄音生成複習筆記")
    
    ai_prompt = f"""
    你是一位學霸助教。請仔細聆聽這段課堂錄音，幫學生整理出一份結構清晰的 Markdown 複習筆記。
    {lang_instruction}
    結構包含：1. 課程核心摘要 2. 關鍵名詞解釋(表格) 3. 重點觀念詳解 4. 考試重點預測。直接輸出 Markdown。
    """
    
    # 學生端分頁：新增專屬的「💬 師生留言板」分頁
    tab_shared, tab_upload, tab_record, tab_comments = st.tabs(["📖 老師分享的講義", "📂 上傳自己的錄音", "🎙️ 網頁即時錄音", "💬 師生留言板"])
    
    shared_md_files = [f for f in os.listdir(SHARED_DIR) if f.endswith('.md')]

    with tab_shared:
        st.info("👇 選擇老師發布的講義直接閱讀，或呼叫 AI 助教為您解答。")
        if shared_md_files:
            selected_file = st.selectbox("請選擇要複習的講義", ["-- 請選擇 --"] + shared_md_files, key="student_select")
            if selected_file != "-- 請選擇 --":
                if st.button("📖 載入講義內容", type="primary", use_container_width=True):
                    file_path = os.path.join(SHARED_DIR, selected_file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        st.session_state.generated_note = f.read()
                    st.session_state.note_filename = selected_file
                    st.session_state.current_shared_file = selected_file
                    st.session_state.chat_history = []
                    st.rerun()
        else:
            st.warning("😴 目前老師還沒有發布任何講義喔！")

    audio_data = None 
    with tab_upload:
        uploaded = st.file_uploader("請上傳您自己錄的音檔", type=['mp3', 'wav', 'm4a', 'aac'])
        if uploaded: audio_data = uploaded; st.audio(audio_data)

    with tab_record:
        st.info("💡 允許麥克風後即可開始錄音。")
        recorded = st.audio_input("開始錄製語音")
        if recorded: audio_data = recorded

    if audio_data:
        st.divider()
        st.subheader("🤖 生成自己的筆記")
        if not api_key: st.warning("請在側邊欄輸入 API Key")
        elif st.button("🚀 分析上傳/錄製的語音", type="primary", use_container_width=True):
            analyze_from_buffer(audio_data, ai_prompt, "Student_Notes.md")

    # 學生端專屬的師生留言板分頁 (獨立出來)
    with tab_comments:
        st.subheader("💬 師生留言板")
        if shared_md_files:
            selected_comment_file = st.selectbox("請選擇要提問或查看回覆的講義", ["-- 請選擇 --"] + shared_md_files, key="student_comment_select")
            if selected_comment_file != "-- 請選擇 --":
                all_comments = load_comments()
                course_comments = all_comments.get(selected_comment_file, [])
                
                st.divider()
                if course_comments:
                    for c in course_comments:
                        avatar = "👨‍🎓" if c['role'] == "student" else "👨‍🏫"
                        with st.chat_message(c['role'], avatar=avatar):
                            st.write(c['content'])
                else:
                    st.info("還沒有留言，有不懂的地方可以直接發問，老師會親自回覆！")
                
                st.markdown("<br>", unsafe_allow_html=True)
                col1, col2 = st.columns([4, 1])
                with col1:
                    new_comment = st.text_input("留言給老師...", key="student_comment_input", label_visibility="collapsed", placeholder="輸入您想問老師的問題...")
                with col2:
                    if st.button("送出給老師", type="primary", use_container_width=True):
                        if new_comment:
                            course_comments.append({"role": "student", "content": new_comment})
                            all_comments[selected_comment_file] = course_comments
                            save_comments(all_comments)
                            st.rerun()
        else:
            st.warning("😴 目前老師還沒有發布任何講義喔！")

# ==========================================
# 🎯 分析結果、發布區與互動區 (全局置底顯示)
# ==========================================
if st.session_state.generated_note:
    st.divider()
    st.header("📝 講義與筆記內容")
    
    # --- 權限過濾機制：依據身分決定顯示範圍 ---
    raw_note = st.session_state.generated_note
    if "學生" in role:
        # 學生端：過濾掉 ---TEACHER_ONLY--- 之後的隱藏內容 (測驗與易錯點)
        display_note = raw_note.split("---TEACHER_ONLY---")[0].strip()
    else:
        # 教師端：顯示完整內容，並將標記轉換為視覺提示
        display_note = raw_note.replace("---TEACHER_ONLY---", "\n\n---\n**🔒 以下為教師專屬內容 (課後隨堂測驗 & 易錯提醒，學生端不可見)：**\n\n")
        
    st.markdown(display_note)
    
    # --- 下載按鈕 ---
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 下載 (.md)", data=display_note, file_name=st.session_state.note_filename, mime="text/markdown", use_container_width=True)
    with col2:
        try:
            pdf_data = create_pdf(display_note)
            st.download_button("📥 下載 (.pdf)", data=pdf_data, file_name=st.session_state.note_filename.replace(".md", ".pdf"), mime="application/pdf", use_container_width=True)
        except Exception as pdf_err:
            st.error("⚠️ PDF 生成失敗！")

    # ==========================
    # 教師區塊：將產生的講義發布
    # ==========================
    if "教師" in role:
        st.divider()
        st.subheader("📢 發布此講義給學生")
        st.info("💡 確認上方講義內容無誤後，請設定標題並「發布」，學生才能在系統中看到喔！")
        
        col_t1, col_t2 = st.columns([3, 1])
        with col_t1:
            share_title = st.text_input("輸入講義標題", key="teacher_share_title", label_visibility="collapsed", placeholder="例如：第一週_經濟學導論")
        with col_t2:
            if st.button("💾 正式發布", type="primary", use_container_width=True):
                if share_title:
                    safe_title = share_title.replace("/", "_").replace("\\", "_") + ".md"
                    save_path = os.path.join(SHARED_DIR, safe_title)
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(st.session_state.generated_note)
                    st.success(f"✅ 成功發布：「{safe_title}」！學生現在可以閱讀了。")
                else:
                    st.warning("⚠️ 請先輸入標題才能發布！")

    # ==========================
    # 學生區塊：AI 助教問答區
    # ==========================
    if "學生" in role:
        
        # 僅保留 AI 助教一對一問答 (永遠都在最底下陪伴)
        st.divider()
        st.subheader("🤖 AI 助教一對一問答")
        st.info("對這份筆記有不懂的地方嗎？直接在這裡問 AI 助教！（AI 將根據上方內容為您即時解答）")
        
        for msg in st.session_state.chat_history:
            avatar = "🤖" if msg["role"] == "assistant" else "👨‍🎓"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])
                
        if user_q := st.chat_input("請輸入您的問題，例如：請用更簡單的例子解釋第二點..."):
            st.session_state.chat_history.append({"role": "user", "content": user_q})
            with st.chat_message("user", avatar="👨‍🎓"):
                st.markdown(user_q)
            
            with st.chat_message("assistant", avatar="🤖"):
                message_placeholder = st.empty()
                message_placeholder.markdown("🧠 思考中...")
                
                try:
                    # 傳遞給 AI 的上下文必須使用過濾後的 display_note，防止 AI 不小心洩漏考題
                    chat_context = f"【課堂筆記內容】\n{display_note}\n\n【過去的對話紀錄】\n"
                    for msg in st.session_state.chat_history[:-1]:
                        role_name = "學生" if msg["role"] == "user" else "AI助教"
                        chat_context += f"{role_name}: {msg['content']}\n"
                        
                    chat_prompt = f"""
                    你是一位友善的 AI 助教。請根據【課堂筆記內容】來回答學生的問題。如果超出範圍，請溫柔提醒。
                    {chat_context}
                    學生最新問題: {user_q}
                    AI助教回答:
                    """
                    
                    chat_model = genai.GenerativeModel(model_name)
                    response = chat_model.generate_content(chat_prompt)
                    
                    message_placeholder.markdown(response.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    message_placeholder.error(f"抱歉，AI 助教遇到了一點問題：{e}")
