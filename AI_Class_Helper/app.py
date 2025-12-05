import streamlit as st
import google.generativeai as genai
import tempfile
import os
import time
import re

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="AI 課堂速記助手 (結構化版)", 
    page_icon="🛡️", 
    layout="wide"
)

# --- 2. 獨立功能區 (將複雜邏輯隔離，避免縮排錯誤) ---

def generate_with_retry(model, content_file, prompt_text):
    """
    這是一個獨立的函式，專門負責跟 AI 溝通並處理重試。
    這樣主程式就不會有一堆複雜的縮排了。
    """
    max_retries = 3
    base_delay = 5
    last_error = None

    for i in range(max_retries):
        try:
            # 嘗試生成
            response = model.generate_content([content_file, prompt_text])
            return response.text # 成功就直接回傳結果
        except Exception as e:
            last_error = e
            error_msg = str(e)
            
            # 判斷是否為 429 (太多請求)
            if "429" in error_msg:
                wait_time = base_delay * (2 ** i) # 5秒, 10秒, 20秒
                st.toast(f"⏳ 伺服器忙碌，休息 {wait_time} 秒後重試...", icon="😴")
                time.sleep(wait_time)
            else:
                # 如果是其他嚴重錯誤 (如 404)，直接丟出異常，不重試
                raise e
    
    # 如果迴圈跑完還是沒結果，拋出最後一次的錯誤
    raise Exception(f"重試多次失敗。最後錯誤: {last_error}")

def parse_response(full_text):
    """
    這是一個獨立函式，專門負責切割 AI 回傳的筆記、心智圖和考題。
    """
    try:
        parts = full_text.split("---SEPARATOR---")
        note = parts[0]
        
        # 處理心智圖代碼
        raw_graph = parts[1] if len(parts) > 1 else ""
        match = re.search(r'digraph\s+.*\{.*\}', raw_graph, re.DOTALL)
        if match:
            graph_code = match.group(0)
        else:
            graph_code = raw_graph.replace("```dot", "").replace("```", "").strip()
            
        quiz = parts[2] if len(parts) > 2 else ""
        return note, graph_code, quiz
    except:
        return full_text, None, ""

# --- 3. 側邊欄設定 ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4712/4712035.png", width=80)
    st.title("⚙️ 設定")
    
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ 已載入內建金鑰")
    else:
        api_key = st.text_input("🔑 Google API Key", type="password")

    st.divider()
    
    # 模型清單：若 404 請嘗試切換不同模型
    model_options = [
        "gemini-1.5-flash",       # 首選推薦
        "gemini-2.0-flash-exp",   # 備用 (新版)
        "gemini-1.5-pro"          # 備用 (舊版)
    ]
    selected_model_name = st.selectbox("選擇模型", model_options)
    
    note_style = st.radio("風格", ["大眾", "學術", "考試"])

# --- 4. 主程式邏輯 ---
st.title("🎓 AI 課堂速記助手")

uploaded_file = st.file_uploader("上傳錄音檔", type=['mp3', 'wav', 'm4a', 'aac'])

if uploaded_file and api_key:
    if st.button("🚀 開始分析", use_container_width=True):
        
        # 設定 API
        try:
            genai.configure(api_key=api_key)
        except Exception as e:
            st.error(f"API Key 錯誤: {e}")
            st.stop()

        status = st.status("系統運作中...", expanded=True)
        
        try:
            # A. 讀取檔案
            status.write("📂 讀取錄音檔...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name

            # B. 上傳檔案
            status.write("☁️ 上傳至雲端...")
            myfile = genai.upload_file(tmp_path)
            
            # 等待處理
            check_count = 0
            while myfile.state.name == "PROCESSING":
                time.sleep(2)
                myfile = genai.get_file(myfile.name)
                check_count += 1
                if check_count > 30:
                    raise Exception("檔案處理超時")

            # C. AI 生成 (呼叫上面的獨立函式，避免縮排錯誤)
            status.write(f"🧠 AI ({selected_model_name}) 正在思考...")
            model = genai.GenerativeModel(selected_model_name)
            
            prompt = f"""
            你是一位助教。請依風格「{note_style}」製作內容。
            請用 "---SEPARATOR---" 分隔以下三部分：
            
            PART 1: Markdown 筆記 (摘要、名詞解釋、重點)
            PART 2: Graphviz 心智圖代碼 (需含 fontname="Microsoft JhengHei", 不要 ```)
            PART 3: 3題測驗題
            """
            
            # --- 關鍵：這裡呼叫函式，程式碼變簡單了 ---
            full_text = generate_with_retry(model, myfile, prompt)
            
            # D. 解析結果
            note_content, graphviz_code, quiz_content = parse_response(full_text)
            
            # 清理與顯示
            os.remove(tmp_path)
            status.update(label="✅ 完成！", state="complete", expanded=False)
            
            tab1, tab2, tab3 = st.tabs(["📝 筆記", "🌳 心智圖", "❓ 測驗"])
            
            with tab1:
                st.markdown(note_content)
                st.download_button("下載筆記", note_content, "notes.md")
            with tab2:
                if graphviz_code:
                    try:
                        st.graphviz_chart(graphviz_code)
                    except:
                        st.error("心智圖語法錯誤")
                        st.code(graphviz_code)
                else:
                    st.info("無心智圖")
            with tab3:
                st.markdown(quiz_content)

        except Exception as e:
            status.update(label="❌ 發生錯誤", state="error")
            st.error(f"錯誤訊息: {e}")
            
            if "404" in str(e):
                st.warning("⚠️ **404 錯誤**：代表「模型名稱」找不到，或是您的 AI 套件版本太舊。")
                st.info("💡 解法：請確認 GitHub 上的 `requirements.txt` 裡面有寫 `google-generativeai>=0.8.3`，並執行 Reboot App。")
            elif "429" in str(e):
                st.warning("⚠️ **429 錯誤**：代表「使用量已滿」。請稍後再試，或在側邊欄切換成 `gemini-1.5-flash`。")

elif not api_key:
    st.warning("請設定 API Key")
