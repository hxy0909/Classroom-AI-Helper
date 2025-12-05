import streamlit as st
import google.generativeai as genai
import tempfile
import os
import time

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="AI 課堂速記助手 (Pro版)", 
    page_icon="🎓", 
    layout="wide"
)

# --- 2. 側邊欄：設定 ---
with st.sidebar:
    st.title("⚙️ 設定控制台")
    api_key = st.text_input("🔑 輸入 Google API Key", type="password")
    
    st.divider()
    
    # 顯示版本供參考
    st.caption(f"AI 套件版本: {genai.__version__}")
    
    st.markdown("---")
    st.info("👇 模型選擇：")
    
    # 模型選項
    model_options = [
        "gemini-2.0-flash",       
        "gemini-2.5-flash",       
        "gemini-1.5-flash",       
        "gemini-1.5-pro"          
    ]
    selected_model_name = st.selectbox("選擇模型", model_options, index=0)
    
    st.divider()
    st.markdown("### 🎨 筆記風格設定")
    note_style = st.radio(
        "你希望筆記寫給誰看？",
        ["一般大眾 (淺顯易懂)", "大學生 (學術專業)", "考試衝刺 (只列考點)"]
    )

# --- 3. 主畫面 ---
st.title("🎓 AI 課堂速記助手 Pro")
st.caption(f"目前使用模型：{selected_model_name} | 風格：{note_style}")

uploaded_file = st.file_uploader("上傳錄音檔 (mp3, wav, m4a)", type=['mp3', 'wav', 'm4a', 'aac'])

# 如果有上傳檔案，顯示播放器
if uploaded_file:
    st.audio(uploaded_file, format='audio/mp3')

if uploaded_file and api_key:
    if st.button("🚀 開始全方位分析", use_container_width=True):
        
        # 設定 API
        try:
            genai.configure(api_key=api_key)
        except Exception as e:
            st.error(f"API Key 錯誤: {e}")
            st.stop()

        # 建立處理狀態區
        status = st.status("正在進行 AI 分析...", expanded=True)
        
        try:
            # A. 處理檔案
            status.write("📂 讀取與處理音檔中...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name

            # B. 上傳
            status.write("☁️ 上傳至 Google Gemini 大腦...")
            myfile = genai.upload_file(tmp_path)
            
            # 等待檔案處理完成 (雖然 flash 很快，但加上這段更保險)
            while myfile.state.name == "PROCESSING":
                time.sleep(1)
                myfile = genai.get_file(myfile.name)

            # C. 生成內容 (一次生成所有需要的內容)
            status.write("🧠 AI 正在理解內容、繪製心智圖與出題...")
            model = genai.GenerativeModel(selected_model_name)
            
            # --- 複合式 Prompt (這就是強大的關鍵) ---
            prompt = f"""
            你是一位全能的教授助教。請聆聽這段錄音，並根據使用者要求的風格「{note_style}」，完成以下三項任務。
            請務必使用特定的分隔線來區分這三部分，以便我程式切割。

            ### PART 1: 筆記
            請用 Markdown 整理詳細筆記：
            1. 課程摘要 (200字內)
            2. 關鍵名詞解釋 (表格呈現)
            3. 深入概念解析
            4. 考試猜題

            ### PART 2: 心智圖
            請根據內容，生成一段 "Graphviz DOT" 語言的程式碼。
            - 只要給我程式碼內容，不要用 markdown code block 包裹。
            - 結構要清晰，從核心主題發散。
            - 請確保是有效的 DOT 語法。

            ### PART 3: 測驗題
            請出 3 題單選題，格式如下：
            Q1: 題目...
            (A) 選項...
            (B) 選項...
            (C) 選項...
            (D) 選項...
            ✅ 正解：(選項) 解析...

            請用 "---SEPARATOR---" 這串文字來分隔這三個部分。
            """
            
            response = model.generate_content([myfile, prompt])
            full_text = response.text
            
            # 清理暫存檔
            os.remove(tmp_path)
            status.update(label="✅ 分析完成！", state="complete", expanded=False)
            
            # --- 解析 AI 回傳的內容 ---
            # 透過分隔線切割內容
            try:
                parts = full_text.split("---SEPARATOR---")
                note_content = parts[0]
                graphviz_code = parts[1].replace("```dot", "").replace("```", "").strip() # 清理可能的多餘符號
                quiz_content = parts[2] if len(parts) > 2 else "生成測驗題時發生錯誤"
            except:
                note_content = full_text
                graphviz_code = None
                quiz_content = "解析格式錯誤，請重試"

            # --- 顯示結果 (使用 Tabs 分頁) ---
            tab1, tab2, tab3 = st.tabs(["📝 重點筆記", "🌳 知識心智圖", "❓ 自我測驗"])
            
            with tab1:
                st.markdown(note_content)
                st.download_button("📥 下載筆記", note_content, "lecture_notes.md")
                
            with tab2:
                st.info("這是 AI 根據錄音內容自動繪製的結構圖：")
                if graphviz_code:
                    try:
                        st.graphviz_chart(graphviz_code)
                    except Exception as e:
                        st.error("心智圖生成失敗 (語法錯誤)，請再試一次。")
                        st.code(graphviz_code)
                else:
                    st.warning("AI 未能生成有效的心智圖代碼。")

            with tab3:
                st.markdown("### 🎯 隨堂小測驗")
                st.markdown(quiz_content)
                with st.expander("查看測驗詳解"):
                    st.write("答案已包含在上方內容中。")

        except Exception as e:
            status.update(label="❌ 發生錯誤", state="error")
            st.error(f"詳細錯誤: {e}")

elif not api_key:
    st.warning("請在左側輸入 API Key")
