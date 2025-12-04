import streamlit as st
import google.generativeai as genai
import tempfile
import os

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="AI 課堂速記助手 (除錯版)", 
    page_icon="🛠️", 
    layout="wide"
)

# --- 2. 側邊欄：除錯與設定 ---
with st.sidebar:
    st.title("⚙️ 設定控制台")
    api_key = st.text_input("🔑 輸入 Google API Key", type="password")
    
    st.divider()
    
    # [除錯功能 1] 顯示目前安裝的套件版本
    current_version = genai.__version__
    st.caption(f"目前 AI 套件版本: {current_version}")
    
    # 檢查版本是否過舊 (Flash 模型需要 0.8.3 以上)
    if current_version < "0.8.3":
        st.error("⚠️ 版本過舊！")
        st.warning("請更新 GitHub 上的 requirements.txt 為：google-generativeai>=0.8.3")
    else:
        st.success("✅ 版本正常")
    
    st.markdown("---")
    
    # [除錯功能 2] 讓使用者手動選擇模型
    # 這樣如果 flash 報錯，你可以馬上切換成 pro 試試看
    st.info("若發生 404 錯誤，請切換不同模型測試：")
    model_options = [
        "gemini-1.5-flash",       # 最新版別名
        "gemini-1.5-flash-001",   # 具體版本號 (較穩定)
        "gemini-1.5-pro",         # 強力版
        "gemini-1.5-flash-8b",    # 極速版
        "gemini-pro"              # 舊版穩定款
    ]
    selected_model_name = st.selectbox("選擇使用的模型", model_options)

# --- 3. 主畫面 ---
st.title("🛠️ AI 課堂速記助手 - 診斷模式")
st.info("此模式用於解決「404 Model not found」問題。")

uploaded_file = st.file_uploader("上傳錄音檔 (支援 mp3, wav, m4a)", type=['mp3', 'wav', 'm4a', 'aac'])

if uploaded_file and api_key:
    if st.button("🚀 開始測試與分析", use_container_width=True):
        
        # 設定 API
        try:
            genai.configure(api_key=api_key)
        except Exception as e:
            st.error(f"API Key 格式錯誤: {e}")
            st.stop()

        col1, col2 = st.columns([1, 2])
        
        with col1:
            status = st.empty()
            try:
                # A. 處理檔案
                status.info("1/3 讀取音檔中...")
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name

                # B. 上傳檔案
                status.info("2/3 上傳至 Google Server...")
                myfile = genai.upload_file(tmp_path)
                
                # C. 生成內容
                status.info(f"3/3 使用模型 [{selected_model_name}] 分析中...")
                
                model = genai.GenerativeModel(selected_model_name)
                
                prompt = """
                請針對這段錄音，製作一份 Markdown 格式的重點筆記。
                包含：摘要、關鍵詞解釋、考試重點。
                """
                
                response = model.generate_content([myfile, prompt])
                result_text = response.text
                
                # 清理
                os.remove(tmp_path)
                status.success("✅ 成功！模型運作正常。")
                
            except Exception as e:
                # [除錯功能 3] 如果出錯，列出帳號真正能用的模型
                status.error("❌ 發生錯誤")
                st.error(f"錯誤訊息: {e}")
                
                st.markdown("### 👇 診斷報告")
                st.warning("你的 API Key 目前可用的模型清單如下 (請嘗試切換到這些模型)：")
                
                try:
                    available_models = []
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            available_models.append(m.name)
                    st.code("\n".join(available_models))
                except:
                    st.error("無法取得模型清單，可能是 API Key 無效。")
                
                result_text = None

        # 顯示結果
        with col2:
            if result_text:
                st.markdown(result_text)
                st.download_button("下載筆記", result_text, "notes.md")

elif not api_key:
    st.warning("請在左側輸入 API Key")
