import streamlit as st
import google.generativeai as genai
import tempfile
import os
import time
import re

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="AI 課堂速記助手", 
    page_icon="🛡️", 
    layout="wide"
)

# --- 2. 側邊欄：設定 ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4712/4712035.png", width=80)
    st.title("⚙️ 設定控制台")
    
    # 自動判定是否需要輸入 Key
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ 已載入內建金鑰")
    else:
        api_key = st.text_input("🔑 輸入 Google API Key", type="password")

    st.divider()
    
    st.info("👇 遇到 429 錯誤請切換模型：")
    # 將 1.5-flash 設為預設第一個，因為最穩定
    model_options = [
        "gemini-1.5-flash",       # 推薦：最穩定
        "gemini-2.0-flash",       # 最新：容易 429
        "gemini-1.5-pro"          
    ]
    selected_model_name = st.selectbox("選擇模型", model_options, index=0)
    
    st.divider()
    note_style = st.radio("筆記風格：", ["一般大眾", "專業學術", "考試衝刺"])

# --- 3. 主畫面 ---
st.title("🎓 AI 課堂速記助手")

uploaded_file = st.file_uploader("請上傳課堂錄音", type=['mp3', 'wav', 'm4a', 'aac'])

if uploaded_file:
    st.audio(uploaded_file, format='audio/mp3')

if uploaded_file and api_key:
    if st.button("🚀 開始分析", use_container_width=True):
        
        try:
            genai.configure(api_key=api_key)
        except Exception as e:
            st.error(f"API Key 設定失敗: {e}")
            st.stop()

        status = st.status("正在啟動...", expanded=True)
        
        try:
            # A. 處理檔案
            status.write("📂 讀取錄音檔...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name

            # B. 上傳
            status.write("☁️ 上傳至雲端 (若卡住請稍候)...")
            myfile = genai.upload_file(tmp_path)
            
            # 等待檔案處理 (加入超時機制避免無限迴圈)
            check_count = 0
            while myfile.state.name == "PROCESSING":
                time.sleep(2)
                myfile = genai.get_file(myfile.name)
                check_count += 1
                if check_count > 30: # 等待超過 60秒
                    raise Exception("檔案處理過久，請重新上傳或壓縮檔案。")

            # C. 生成 (加入超強自動重試機制)
            status.write(f"🧠 AI ({selected_model_name}) 正在思考中...")
            model = genai.GenerativeModel(selected_model_name)
            
            prompt = f"""
            你是一位專業助教。請聆聽錄音並依風格「{note_style}」製作內容。
            請用 "---SEPARATOR---" 分隔以下三部分：

            ### PART 1: 筆記 (Markdown)
            1. 摘要
            2. 名詞解釋表格
            3. 重點詳解
            4. 考前猜題

            ### PART 2: 心智圖代碼 (Graphviz)
            - 必須包含 `fontname="Microsoft JhengHei"`
            - 只要代碼，不要 Markdown 標記 ` ``` `
            
            ### PART 3: 測驗題 (3題)
            請用 "---SEPARATOR---" 分隔。
            """
            
            # --- [關鍵修改] 指數退避重試機制 (Exponential Backoff) ---
            max_retries = 5
            base_delay = 5  # 基礎等待秒數
            full_text = None
            
            for i in range(max_retries):
                try:
                    response = model.generate_content([myfile, prompt])
                    full_text = response.text
                    break  # 成功就跳出
                except Exception as e:
                    if "429" in str(e):
                        wait_time = base_delay * (2 ** i) # 5s, 10s, 20s, 40s...
                        status.write(f"⚠️ 伺服器忙碌 (429)，正在冷卻 {wait_time} 秒後重試 ({i+1}/{max_retries})...")
                        time.sleep(wait_time)
                    else:
                        raise e # 其他錯誤直接拋出

            if not full_text:
                raise Exception("伺服器過於繁忙，已重試多次無效。請稍後再試，或切換至 gemini-1.5-flash 模型。")
            
            # --- 完成後的清理與顯示 ---
            os.remove(tmp_path)
            status.update(label="✅ 分析完成！", state="complete", expanded=False)
            
            try:
                parts = full_text.split("---SEPARATOR---")
                note_content = parts[0]
                raw_graph = parts[1] if len(parts) > 1 else ""
                match = re.search(r'digraph\s+.*\{.*\}', raw_graph, re.DOTALL)
                graphviz_code = match.group(0) if match else raw_graph.replace("```", "").strip()
                quiz_content = parts[2] if len(parts) > 2 else ""
            except:
                note_content = full_text
                graph

