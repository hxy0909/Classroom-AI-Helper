import streamlit as st
import google.generativeai as genai
import tempfile
import os

# --- 1. 頁面設定 ---
st.set_page_config(page_title="AI 課堂速記助手", page_icon="🎓", layout="wide")

# --- 2. 側邊欄 ---
with st.sidebar:
    st.title("⚙️ 設定")
    api_key = st.text_input("🔑 Google API Key", type="password")
    
    # 顯示套件版本 (除錯用)
    st.divider()
    st.caption(f"目前 AI 套件版本: {genai.__version__}")
    if genai.__version__ < "0.8.3":
        st.error("⚠️ 套件版本過舊！請更新 requirements.txt")
    
    st.markdown("---")
    st.info("如果持續報錯，請嘗試在下方切換不同模型：")
    
    # 讓使用者手動選擇模型 (避免寫死導致錯誤)
    model_options = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
    selected_model_name = st.selectbox("選擇模型", model_options)

# --- 3. 主畫面 ---
st.title("🎓 AI 課堂速記助手 (除錯模式)")

uploaded_file = st.file_uploader("上傳錄音檔 (mp3, wav, m4a)", type=['mp3', 'wav', 'm4a', 'aac'])

if uploaded_file and api_key:
    if st.button("🚀 開始分析", use_container_width=True):
        
        # 設定 API
        try:
            genai.configure(api_key=api_key)
            
            # --- 測試連線與模型清單 ---
            # 這裡會列出你帳號真正能用的模型，方便除錯
            available_models = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
            
        except Exception as e:
            st.error(f"API Key 設定失敗: {e}")
            st.stop()

        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.info("處理中...")
            status = st.empty()
            
            try:
                # A. 處理檔案
                status.text("1/3 讀取音檔...")
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name

                # B. 上傳
                status.text("2/3 上傳檔案中...")
                myfile = genai.upload_file(tmp_path)
                
                # C. 生成
                status.text(f"3/3 使用 {selected_model_name} 分析中...")
                
                # 使用側邊欄選擇的模型
                model = genai.GenerativeModel(selected_model_name)

                prompt = "請針對這段錄音，製作一份詳細的 Markdown 學習筆記，包含摘要、關鍵字解釋與考題預測。"
                
                response = model.generate_content([myfile, prompt])
                result_text = response.text
                
                os.remove(tmp_path)
                status.success("完成！")
                
            except Exception as e:
                status.error("發生錯誤")
                st.error(f"詳細錯誤訊息: {e}")
                
                # 顯示可用的模型建議
                st.warning("👇 你的 API Key 目前僅支援以下模型，請嘗試在側邊欄切換：")
                st.code("\n".join(available_models))
                
                result_text = None

        with col2:
            if result_text:
                st.markdown(result_text)
                st.download_button("下載筆記", result_text, "notes.md")

elif not api_key:
    st.warning("請先輸入 API Key")
