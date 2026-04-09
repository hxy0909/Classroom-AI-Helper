import streamlit as st
import google.generativeai as genai
import tempfile
import os
import time
import markdown
import json
import re

# --- 0. 初始化系統資料夾與資料庫 ---
SHARED_DIR = "shared_notes"
QUIZ_DIR = "shared_quizzes" # 新增：存放測驗題庫的資料夾
os.makedirs(SHARED_DIR, exist_ok=True)
os.makedirs(QUIZ_DIR, exist_ok=True)
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
    
    /* 針對「水平排列」的選項 (導覽列) 隱藏圓圈並轉換為按鈕/分頁外觀 */
    div[role="radiogroup"][aria-orientation="horizontal"] > label > div:first-child { 
        display: none; 
    }
    div[role="radiogroup"][aria-orientation="horizontal"] { 
        gap: 12px; 
    }
    div[role="radiogroup"][aria-orientation="horizontal"] > label { 
        padding: 10px 16px; 
        background-color: #FFFFFF; 
        border: 1px solid #E0E0E0; 
        border-radius: 8px; 
        margin: 0;
        cursor: pointer;
        transition: all 0.2s;
    }
    div[role="radiogroup"][aria-orientation="horizontal"] > label:hover {
        background-color: #F8F9FA;
    }
    div[role="radiogroup"][aria-orientation="horizontal"] > label[data-checked="true"] { 
        background-color: #FF4B4B; 
        border-color: #FF4B4B; 
    }
    div[role="radiogroup"][aria-orientation="horizontal"] > label[data-checked="true"] p { 
        color: #FFFFFF !important; 
        font-weight: 600;
    }
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
            st.session_state.current_shared_file = None 
            
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

def generate_interactive_quiz(note_content, title):
    """叫 AI 生成 10 題選擇題的 JSON 題庫"""
    model = genai.GenerativeModel(model_name)
    quiz_prompt = f"""
    請根據以下講義內容，設計 10 題適合學生的「單選題」測驗。
    這是一個類似 Kahoot 的互動遊戲，請確保題目有趣、難易適中，且涵蓋核心觀念。
    
    【講義內容】：
    {note_content}
    
    【輸出格式要求】：
    請嚴格只輸出 JSON 格式的陣列（Array），不要加上任何其他文字或 Markdown 標記（如 ```json）。
    JSON 格式範例：
    [
      {{
        "question": "題目內容",
        "options": ["選項A", "選項B", "選項C", "選項D"],
        "answer": "正確的選項內容 (必須與 options 裡的字完全一模一樣)",
        "explanation": "解析說明"
      }}
    ]
    """
    response = model.generate_content(quiz_prompt)
    text = response.text
    # 嘗試清理可能的 markdown 標記
    match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
    if match:
        text = match.group(0)
    
    return json.loads(text)

lang_instruction = f"【重要指令】不論錄音檔原本是什麼語言，請務必將所有輸出的內容翻譯並撰寫為：「{output_language}」。" if "自動偵測" not in output_language else "【重要指令】請使用與錄音檔相同的語言來輸出內容。"

# ==========================================
# 👨‍🏫 教師專屬介面
# ==========================================
if "教師" in role:
    st.title("👨‍🏫 教師備課與教材發布中心")
    st.caption("管理您的授課錄音、發布講義、生成隨堂測驗，並回覆學生的提問")
    
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
    
    # 使用 radio 按鈕取代 tabs，達成完美的防作弊與介面切換
    teacher_mode = st.radio("功能導覽", ["📂 上傳錄音產製教材", "🎙️ 網頁錄音產製教材", "💬 學生提問留言板"], horizontal=True, label_visibility="collapsed")
    audio_data = None 

    if teacher_mode == "📂 上傳錄音產製教材":
        uploaded = st.file_uploader("請上傳您的授課錄音以生成講義", type=['mp3', 'wav', 'm4a', 'aac'])
        if uploaded: audio_data = uploaded; st.audio(audio_data)

    elif teacher_mode == "🎙️ 網頁錄音產製教材":
        st.info("💡 允許麥克風後即可開始錄音。")
        recorded = st.audio_input("開始錄製授課內容")
        if recorded: audio_data = recorded

    if audio_data:
        st.divider()
        st.subheader("🤖 生成課後講義")
        if not api_key: st.warning("請在側邊欄輸入 API Key")
        elif st.button("🚀 開始生成教材", type="primary", use_container_width=True):
            analyze_from_buffer(audio_data, ai_prompt, "Teacher_Materials.md")

    # 教師端留言板管理
    elif teacher_mode == "💬 學生提問留言板":
        st.subheader("💬 管理學生提問與留言")
        shared_md_files = [f for f in os.listdir(SHARED_DIR) if f.endswith('.md')]
        
        if shared_md_files:
            selected_file = st.selectbox("選擇要查看的講義", ["-- 請選擇 --"] + shared_md_files, key="teacher_select")
            if selected_file != "-- 請選擇 --":
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
    st.caption("閱讀講義、向老師提問，或是參加隨堂 Kahoot 挑戰！")
    
    ai_prompt = f"""
    你是一位學霸助教。請仔細聆聽這段課堂錄音，幫學生整理出一份結構清晰的 Markdown 複習筆記。
    {lang_instruction}
    結構包含：1. 課程核心摘要 2. 關鍵名詞解釋(表格) 3. 重點觀念詳解 4. 考試重點預測。直接輸出 Markdown。
    """
    
    # 使用 radio 按鈕取代 tabs，達成完美的防作弊與介面切換
    student_mode = st.radio("功能導覽", ["📖 老師分享的講義", "🎮 互動測驗", "📂 上傳自己的錄音", "🎙️ 網頁錄音", "💬 師生留言板"], horizontal=True, label_visibility="collapsed")
    
    shared_md_files = [f for f in os.listdir(SHARED_DIR) if f.endswith('.md')]
    audio_data = None 

    if student_mode == "📖 老師分享的講義":
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

    # --- 🎓 學生端：Kahoot 互動測驗區塊 ---
    elif student_mode == "🎮 互動測驗":
        st.subheader("🎮 隨堂互動測驗 (Kahoot 模式)")
        quiz_files = [f for f in os.listdir(QUIZ_DIR) if f.endswith('.json')]
        if quiz_files:
            selected_quiz = st.selectbox("選擇要挑戰的測驗", ["-- 請選擇 --"] + quiz_files)
            if selected_quiz != "-- 請選擇 --":
                quiz_path = os.path.join(QUIZ_DIR, selected_quiz)
                with open(quiz_path, "r", encoding="utf-8") as f:
                    quiz_data = json.load(f)
                
                st.info(f"🎯 本次測驗共有 {len(quiz_data)} 題，開始作答！")
                st.markdown("---")
                
                with st.form("quiz_form"):
                    user_answers = {}
                    for i, q in enumerate(quiz_data):
                        st.markdown(f"**Q{i+1}: {q['question']}**")
                        user_answers[i] = st.radio("請選擇：", q['options'], key=f"q_{i}", index=None)
                        st.markdown("<br>", unsafe_allow_html=True)
                    
                    submitted = st.form_submit_button("🚀 交卷看成績！", type="primary", use_container_width=True)
                    
                    if submitted:
                        st.divider()
                        st.subheader("📊 測驗結果")
                        score = 0
                        total = len(quiz_data)
                        
                        for i, q in enumerate(quiz_data):
                            ans = user_answers[i]
                            if ans == q['answer']:
                                score += 1
                                st.success(f"**Q{i+1}: 答對了！✅** (您的答案: {ans})")
                            else:
                                st.error(f"**Q{i+1}: 答錯了 ❌** (您的答案: {ans}，正確答案: **{q['answer']}**)")
                            st.caption(f"💡 解析：{q['explanation']}")
                            st.markdown("---")
                        
                        final_score = int((score / total) * 100)
                        st.header(f"🏆 您的總分：{final_score} / 100")
                        
                        if final_score >= 80:
                            st.balloons()
                            st.success("太棒了！您已經完全掌握了這堂課的精華！🎉")
                        elif final_score >= 60:
                            st.info("表現不錯！再複習一下會更好喔！💪")
                        else:
                            st.warning("要加油囉！建議多聽幾次老師的錄音或再看一次講義！📚")
        else:
            st.info("老師還沒有開放任何測驗題喔！")

    elif student_mode == "📂 上傳自己的錄音":
        uploaded = st.file_uploader("請上傳您自己錄的音檔", type=['mp3', 'wav', 'm4a', 'aac'])
        if uploaded: audio_data = uploaded; st.audio(audio_data)

    elif student_mode == "🎙️ 網頁錄音":
        st.info("💡 允許麥克風後即可開始錄音。")
        recorded = st.audio_input("開始錄製語音")
        if recorded: audio_data = recorded

    if audio_data:
        st.divider()
        st.subheader("🤖 生成自己的筆記")
        if not api_key: st.warning("請在側邊欄輸入 API Key")
        elif st.button("🚀 分析上傳/錄製的語音", type="primary", use_container_width=True):
            analyze_from_buffer(audio_data, ai_prompt, "Student_Notes.md")

    elif student_mode == "💬 師生留言板":
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
                    new_comment = st.text_input("留言給老師...", key="student_comment_input", label_visibility="collapsed")
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
# 嚴格防作弊機制：動態判斷是否要顯示講義
show_global_notes = False
if st.session_state.generated_note:
    if "教師" in role:
        show_global_notes = True
    elif "學生" in role:
        # 關鍵：只要學生切換到「互動測驗」，這裡的條件就不成立，整個講義區塊都會直接消失！
        if student_mode != "🎮 互動測驗":
            show_global_notes = True

if show_global_notes:
    st.divider()
    st.header("📝 講義與筆記內容")
    
    raw_note = st.session_state.generated_note
    if "學生" in role:
        display_note = raw_note.split("---TEACHER_ONLY---")[0].strip()
    else:
        display_note = raw_note.replace("---TEACHER_ONLY---", "\n\n---\n**🔒 以下為教師專屬內容 (課後隨堂測驗 & 易錯提醒，學生端不可見)：**\n\n")
        
    st.markdown(display_note)
    
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
    # 👨‍🏫 教師區塊：發布講義 & 一鍵生成題庫
    # ==========================
    if "教師" in role:
        st.divider()
        st.subheader("📢 發布設定")
        st.info("💡 您可以選擇只發布這份講義，或者點擊「發布並生成互動測驗」，讓 AI 幫您出 10 題選擇題給學生考！")
        
        share_title = st.text_input("輸入講義標題", key="teacher_share_title", placeholder="例如：第一週_經濟學導論")
        
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            if st.button("💾 單純發布講義", type="primary", use_container_width=True):
                if share_title:
                    safe_title = share_title.replace("/", "_").replace("\\", "_") + ".md"
                    save_path = os.path.join(SHARED_DIR, safe_title)
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(st.session_state.generated_note)
                    st.success(f"✅ 成功發布講義：「{safe_title}」！")
                else:
                    st.warning("⚠️ 請先輸入標題才能發布！")
        
        with col_t2:
            if st.button("🎲 發布講義 + 一鍵生成互動測驗", type="primary", use_container_width=True):
                if share_title:
                    safe_title = share_title.replace("/", "_").replace("\\", "_")
                    md_save_path = os.path.join(SHARED_DIR, f"{safe_title}.md")
                    with open(md_save_path, "w", encoding="utf-8") as f:
                        f.write(st.session_state.generated_note)
                    
                    with st.status("🎲 正在叫 AI 自動出題 (10題)...", expanded=True) as status_box:
                        try:
                            quiz_json = generate_interactive_quiz(display_note, safe_title)
                            quiz_save_path = os.path.join(QUIZ_DIR, f"{safe_title}.json")
                            with open(quiz_save_path, "w", encoding="utf-8") as f:
                                json.dump(quiz_json, f, ensure_ascii=False, indent=2)
                                
                            status_box.update(label="✅ 講義與測驗皆已發布成功！", state="complete", expanded=False)
                            st.balloons()
                        except Exception as e:
                            status_box.update(label="❌ 出題失敗", state="error", expanded=True)
                            st.error(f"詳細錯誤：{e}\n\n可能是 AI 回傳格式不符，請重新點擊一次按鈕。")
                else:
                    st.warning("⚠️ 請先輸入標題才能發布！")

    # ==========================
    # 👩‍🎓 學生區塊：AI 助教問答
    # ==========================
    if "學生" in role:
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
