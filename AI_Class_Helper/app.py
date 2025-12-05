import streamlit as st
import google.generativeai as genai
import tempfile
import os

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="AI 課堂速記助手 (2.0版)", 
    page_icon="🚀", 
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
    st.info("👇 請在此選擇您的帳號支援的模型：")
    
    # 【關鍵修改】根據您的截圖，新增了 2.0 和 2.5 的模型選項
    model_options = [
        "gemini-2.0-flash",       # 根據您的截圖新增 (推薦)
        "gemini-2.5-flash",       # 根據您的截圖新增 (最新)
        "gemini-2.0-flash-exp",   # 實驗版
        "gemini-1.5-flash",       # 舊版 (備用)
        "gemini-1.5-pro"          # 舊版 (備用)
    ]
    
    # 預設選第一個 (2.0-flash)
    selected_model_name = st.selectbox("選擇模型", model_options, index=0)

# --- 3. 主畫面 ---
st.title("🎓 AI 課堂速記助手")
st.caption(f"目前使用模型：{selected_model_name}")

uploaded_file = st.file_uploader("上傳錄音檔 (mp3, wav, m4a)", type=['mp3', 'wav', 'm4a', 'aac'])

if uploaded_file and api_key:
    if st.button("🚀 開始分析", use_container_width=True):
        
        # 設定 API
        try:
            genai.configure(api_key=api_key)
        except Exception as e:
            st.error(f"API Key 錯誤: {e}")
            st.stop()

        col1, col2 = st.columns([1, 2])
        
        with col1:
            status = st.empty()
            try:
                # A. 處理檔案
                status.info("1/3 讀取音檔...")
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name

                # B. 上傳
                status.info("2/3 上傳檔案中...")
                myfile = genai.upload_file(tmp_path)
                
                # C. 生成
                status.info(f"3/3 使用 {selected_model_name} 分析中 (速度極快)...")
                
                model = genai.GenerativeModel(selected_model_name)
                
                prompt = """
                你是一位專業的助教。請聆聽這段錄音，並用 Markdown 格式整理出一份詳細的學習筆記。
                
                格式要求：
                1. 課程摘要 (200字內)
                2. 關鍵名詞解釋 (條列式)
                3. 考試猜題 (預測老師可能考的地方)
                
                請用繁體中文回答。
                """
                
                response = model.generate_content([myfile, prompt])
                result_text = response.text
                
                os.remove(tmp_path)
                status.success("✅ 完成！")
                
            except Exception as e:
                status.error("❌ 錯誤")
                st.error(f"錯誤訊息: {e}")
                # 再次顯示可用模型清單，以防萬一
                try:
                    models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    st.warning(f"您的 Key 實際可用模型: {models}")
                except:
                    pass
                result_text = None

        with col2:
            if result_text:
                st.markdown(result_text)
                st.download_button("下載筆記", result_text, "notes.md")

elif not api_key:
    st.warning("請在左側輸入 API Key")
