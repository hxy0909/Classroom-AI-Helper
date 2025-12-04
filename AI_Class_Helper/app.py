import streamlit as st
import google.generativeai as genai
import tempfile
import os

# --- 1. 頁面基礎設定 ---
st.set_page_config(
    page_title="AI 課堂速記助手",
    page_icon="🎓",
    layout="wide"
)

# --- 2. 側邊欄：設定與說明區 ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4712/4712035.png", width=100)
    st.title("⚙️ 設定控制台")
    
    # API Key 輸入區
    api_key = st.text_input("🔑 輸入 Google API Key", type="password")
    st.caption("本系統使用 Google Gemini 1.5 Flash 模型 (免費且快速)。")
    st.markdown("[👉 點此取得免費 API Key](https://aistudio.google.com/app/apikey)")
    
    st.divider()
    
    st.subheader("關於本專案")
    st.info(
        """
        這是一個解決「學生來不及記筆記」痛點的 AI 應用。
        
        **核心功能：**
        - 🎙️ **聽**：支援長錄音辨識
        - 📝 **寫**：自動生成結構化筆記
        - 🧠 **想**：抓出考試重點與猜題
        """
    )
    st.markdown("---")
    st.caption("Designed for AI Competition")

# --- 3. 主畫面設計 ---
st.title("🎓 AI 課堂速記助手")
st.subheader("讓 AI 幫你上課做筆記，你專心聽講！")

# 檔案上傳區
uploaded_file = st.file_uploader(
    "請拖曳或上傳錄音檔 (支援 mp3, wav, m4a, aac)", 
    type=['mp3', 'wav', 'm4a', 'aac']
)

# --- 4. 核心運作邏輯 ---
if uploaded_file and api_key:
    # 顯示一個醒目的開始按鈕
    if st.button("🚀 開始 AI 分析", use_container_width=True):
        
        # 設定 Google API
        try:
            genai.configure(api_key=api_key)
        except Exception as e:
            st.error(f"API Key 設定失敗，請檢查格式。錯誤：{e}")
            st.stop()
        
        # 使用兩欄排版
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.info("系統處理中...")
            status_text = st.empty() # 建立一個空位來顯示動態文字
            
            try:
                # 步驟 A: 處理檔案
                status_text.text("1/3 正在讀取音檔...")
                
                # 建立暫存檔
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file_path = tmp_file.name

                # 步驟 B: 上傳給 Google
                status_text.text("2/3 正在上傳至 AI 大腦 (Gemini)...")
                myfile = genai.upload_file(tmp_file_path)
                
                # 步驟 C: AI 生成內容
                status_text.text("3/3 AI 正在聆聽並撰寫筆記 (請稍候)...")
                
                # --- 關鍵修正：使用具體版本號 'gemini-1.5-flash-001' 以避免找不到模型 ---
                model = genai.GenerativeModel("gemini-1.5-flash-001")

                # 給 AI 的指令 (Prompt)
                prompt = """
                你是一位教學經驗豐富的教授助教。請仔細聆聽這段課堂錄音，並為學生製作一份高品質的學習筆記。
                
                請依照以下 Markdown 格式輸出，繁體中文呈現：
                
                # 📝 [課程主題自動生成] 學習筆記
                
                ## 📌 課程核心摘要
                (請用 200 字以內，精簡說明這堂課在講什麼)
                
                ## 🔑 關鍵名詞與概念
                * **[名詞 1]**：[解釋]
                * **[名詞 2]**：[解釋]
                * **[名詞 3]**：[解釋]
                
                ## 💡 考試重點預測
                > 這裡列出老師語氣加重、或反覆提及的觀念，極有可能是考題。
                1. ...
                2. ...
                
                ---
                *筆記生成時間：剛剛*
                """

                response = model.generate_content([myfile, prompt])
                result_text = response.text
                
                # 清理暫存檔
                os.remove(tmp_file_path)
                status_text.success("✅ 處理完成！")
                
            except Exception as e:
                status_text.error(f"發生錯誤：{e}")
                st.error("若出現 404 錯誤，請確認 GitHub 上的 requirements.txt 是否已包含 google-generativeai>=0.8.3")
                result_text = None

        # 在右邊欄位顯示結果
        with col2:
            if result_text:
                st.markdown(result_text)
                
                st.divider()
                # 下載按鈕
                st.download_button(
                    label="📥 下載筆記 (.md)",
                    data=result_text,
                    file_name="Lecture_Notes.md",
                    mime="text/markdown",
                    use_container_width=True
                )

elif not uploaded_file:
    st.info("👈 請先在左側輸入 API Key，並在上方上傳錄音檔以開始使用。")

elif not api_key:
    st.warning("⚠️ 請記得在左側側邊欄輸入 API Key 才能運作喔！")
