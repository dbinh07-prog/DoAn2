import streamlit as st
import pandas as pd
import sqlite3
import google.generativeai as genai
import json
import time
import re
import io
import zipfile
import xml.etree.ElementTree as ET
import os
import shutil
from datetime import datetime

# Thư viện biểu đồ
import plotly.express as px
import plotly.graph_objects as go

# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from google.generativeai.types import HarmCategory, HarmBlockThreshold, GenerationConfig

# ==============================================================================
# 1. CẤU HÌNH & CSS (DARK MODE - UI CHUẨN)
# ==============================================================================
st.set_page_config(page_title="AI Insight Universal", page_icon="💎", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: white; }
    .hero-title { font-family: 'Segoe UI', sans-serif; font-size: 3rem; font-weight: 700; color: #4CAF50; margin-bottom: 5px; text-align: left; }
    .hero-subtitle { font-size: 1rem; color: #888; margin-bottom: 40px; font-style: italic; text-align: left;}
    .feature-card { background-color: #161B22; border: 1px solid #30363D; padding: 20px; border-radius: 10px; text-align: center; height: 100%; }
    .stButton > button { background-color: #FF4B4B; color: white; border: none; border-radius: 6px; font-weight: bold; height: 45px; width: 100%; font-size: 16px; }
    .stButton > button:hover { background-color: #D32F2F; }
    [data-testid="stSidebar"] { background-color: #161B22; border-right: 1px solid #30363D; }
    div.stButton > button.history-btn { background-color: #21262D; border: 1px solid #30363D; color: #ddd; text-align: left; padding: 10px; height: auto; font-size: 14px; margin-bottom: 5px; width: 100%; }
    div.stButton > button.history-btn:hover { border-color: #4CAF50; color: #4CAF50; }
    .metric-box { background-color: #21262D; border: 1px solid #30363D; padding: 15px; border-radius: 8px; text-align: center; }
    .metric-num { font-size: 24px; font-weight: bold; color: #4CAF50; }
    .metric-lbl { font-size: 12px; color: #8B949E; text-transform: uppercase; margin-top: 5px; }
    [data-testid="stFileUploader"] section { background-color: #161B22; border: 1px dashed #4CAF50; }
</style>
""", unsafe_allow_html=True)

MY_API_KEY = "AIzaSyCngLZhTY4tm3uIFZyMozhf71xOCBBj2E4"
DB_NAME = 'universal_v56_debug.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS analyses 
                 (id INTEGER PRIMARY KEY, product_name TEXT, url TEXT, result_json TEXT, time TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ==============================================================================
# 2. HÀM ĐỌC FILE
# ==============================================================================
def read_docx(file):
    try:
        with zipfile.ZipFile(file) as z: xml_content = z.read('word/document.xml')
        tree = ET.fromstring(xml_content)
        text = []
        for elem in tree.iter():
            if elem.tag.endswith('t') and elem.text: text.append(elem.text)
        return '\n'.join(text)
    except: return ""

def process_uploaded_file(uploaded_file):
    try:
        if uploaded_file.name.endswith('.csv'): return pd.read_csv(uploaded_file).to_string()
        elif uploaded_file.name.endswith(('.xls', '.xlsx')): return pd.read_excel(uploaded_file).to_string()
        elif uploaded_file.name.endswith('.txt'): return uploaded_file.read().decode("utf-8")
        elif uploaded_file.name.endswith('.docx'): return read_docx(uploaded_file)
        return None
    except Exception as e: return f"Lỗi: {str(e)}"

# ==============================================================================
# 3. CÀO WEB (CẤU HÌNH CLOUD + HIỂN THỊ LỖI CHI TIẾT)
# ==============================================================================
def get_web_content_selenium(url, max_pages=15):
    driver = None
    collected_data = []
    error_log = ""
    
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # --- LOGIC CHỌN DRIVER (ƯU TIÊN CLOUD) ---
        service = None
        
        # Kiểm tra xem có phải đang chạy trên Cloud (Linux có Chromium) không
        if os.path.exists("/usr/bin/chromium"):
            chrome_options.binary_location = "/usr/bin/chromium"
            service = Service("/usr/bin/chromedriver")
        else:
            # Nếu không tìm thấy Chromium hệ thống, dùng Webdriver Manager (cho máy cá nhân)
            try:
                service = Service(ChromeDriverManager().install())
            except:
                pass

        if service:
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # Fallback cuối cùng
            driver = webdriver.Chrome(options=chrome_options)
        
        st.toast(f"🌐 Đang truy cập: {url}")
        driver.get(url)
        time.sleep(5)
        
        # --- CHIẾN THUẬT: CUỘN TỪ TỪ ---
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        # --- BƯỚC 1: MỞ RỘNG ---
        try:
            see_all = driver.find_elements(By.XPATH, """
                //a[contains(text(), 'Xem') and contains(text(), 'đánh giá')] |
                //button[contains(text(), 'Xem') and contains(text(), 'đánh giá')] |
                //div[contains(text(), 'Xem') and contains(text(), 'đánh giá')]//a |
                //a[contains(@class, 'btn-view-all')]
            """)
            for btn in see_all:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", btn)
                    st.toast("⚡ Đã bấm nút mở rộng...")
                    time.sleep(4)
                    break
        except: pass

        # --- BƯỚC 2: LẬT TRANG (SVG + SỐ) ---
        page = 1
        while page <= max_pages:
            try:
                try:
                    content = driver.find_element(By.CSS_SELECTOR, "div.f-cm-list, div.card-body, div.re-list").text
                except:
                    content = driver.find_element(By.TAG_NAME, "body").text
                collected_data.append(f"\n--- PAGE {page} ---\n{content}")
            except: pass

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 600);")
            time.sleep(1.5)

            try:
                clicked = False
                next_page = page + 1
                
                # SVG (Priority 1)
                svg_icons = driver.find_elements(By.XPATH, "//*[name()='svg' and contains(@class, 'Pagination')]")
                visible_svgs = [icon for icon in svg_icons if icon.is_displayed()]
                if visible_svgs:
                    next_svg = visible_svgs[-1]
                    try:
                        driver.execute_script("arguments[0].click();", next_svg)
                        st.toast(f"⚡ Bấm SVG Next (Trang {next_page})...")
                        time.sleep(4)
                        clicked = True
                        page += 1
                    except: pass

                # Số trang (Priority 2)
                if not clicked:
                    next_num_btns = driver.find_elements(By.XPATH, f"//ul//li//a[text()='{next_page}'] | //div//a[text()='{next_page}']")
                    for btn in next_num_btns:
                        if btn.is_displayed():
                            driver.execute_script("arguments[0].click();", btn)
                            st.toast(f"⚡ Sang trang số {next_page}...")
                            time.sleep(4)
                            clicked = True
                            page += 1
                            break
                
                if not clicked: break
            except: break
        
        return "\n".join(collected_data)[:600000], None

    except Exception as e: 
        return None, str(e) # Trả về lỗi chi tiết
    finally:
        if driver: driver.quit()

# ==============================================================================
# 4. AI PHÂN TÍCH
# ==============================================================================
def analyze_content(text):
    genai.configure(api_key=MY_API_KEY)
    
    models_to_try = [
        "models/gemini-2.5-flash-lite",      # Ưu tiên 1
        "models/gemini-2.5-flash",           # Dự phòng 1
        "models/gemma-3-27b",                # Dự phòng 2
        "models/gemini-1.5-flash"            # Fallback an toàn
    ]

    
    prompt = f"""
    Dữ liệu thô từ nguồn (Web hoặc File):
    ---
    {text}
    ---
    
    NHIỆM VỤ:
    !!!! PHẢI QUÉT ĐỦ BÌNH LUẬN/ FEEDBACK
    !!! BẮT BUỘC CHỈ ĐƯỢC LẤY VÀ PHÂN TÍCH BÌNH LUẬN CỦA NGƯỜI DÙNG, KHÔNG PHẢI LẤY HẾT THÔNG TIN KĨ THUẬT, HIỂU CHƯA ?
    !! KHÔNG ĐƯỢC BỊA ĐẶT THÊM BẤT CỨ 1 THỨ GÌ VÀ CHỈ LẤY BÌNH LUẬN CỦA NGƯỜI DÙNG, KHÔNG PHẢI THÔNG TIN SẢN PHẨM
    1. Trích xuất TOÀN BỘ ý kiến/bình luận/ đánh giá/ góp ý CỦA NGƯỜI DÙNG (User Reviews).
    1*. Nếu dữ liệu là từ file Excel/CSV, hãy đọc từng dòng và phân tích.
    2. Gộp nội dung trùng lặp.
    3. Phân tích câu từ rồi Phân loại ra 4 nhóm: Tích cực, Tiêu cực, Trung lập, Thắc mắc.
    4. Đếm Topic (Chủ đề được người dùng nhắc tới).
    5. Đưa ra giải pháp cho cửa hàng để khắc phục các vấn đề gặp phải.


    Output JSON strict:
    {{
        "product_name": "Tên SP",
        "has_reviews": true,
        "positive_reviews": ["Review 1..."],
        "negative_reviews": ["Review 1..."],
        "neutral_reviews": ["Review 1..."],
        "inquiry_reviews": ["Hỏi 1..."],
        "topic_counts": {{ "Pin": 10, "Màn hình": 5 }},
        "solution": "Lời khuyên..."
    }}
    """
    
    safety = {HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}
    config = GenerationConfig(temperature=0.3, response_mime_type="application/json")
    
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name, safety_settings=safety, generation_config=config)
            response = model.generate_content(prompt)
            return json.loads(response.text)
        except Exception: continue
            
    return {"error": "Hệ thống bận. Vui lòng thử lại sau."}

def generate_excel(result, url):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        summary_data = {"Thông tin": ["Tên SP", "Nguồn", "Thời gian"], "Giá trị": [result.get('product_name'), url, datetime.now().strftime("%H:%M %d/%m")]}
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Dashboard', index=False)
        rows = []
        for r in result.get('positive_reviews', []): rows.append({"Loại": "Tích cực", "Nội dung": r})
        for r in result.get('negative_reviews', []): rows.append({"Loại": "Tiêu cực", "Nội dung": r})
        for r in result.get('neutral_reviews', []): rows.append({"Loại": "Trung lập", "Nội dung": r})
        for r in result.get('inquiry_reviews', []): rows.append({"Loại": "Thắc mắc", "Nội dung": r})
        pd.DataFrame(rows).to_excel(writer, sheet_name='Chi Tiết', index=False)
    return output.getvalue()

# ==============================================================================
# 5. GIAO DIỆN CHÍNH
# ==============================================================================

with st.sidebar:
    st.markdown("### ⚙️ Cấu Hình")
    with st.expander("🛠️ Cài đặt nâng cao"):
        page_limit = st.slider("Số trang quét:", 1, 50, 15)
        st.info(f"Bot sẽ quét tối đa {page_limit} trang.")
    
    st.markdown("---")
    st.markdown("### 📂 Lịch Sử")
    
    conn = sqlite3.connect(DB_NAME)
    try:
        df_hist = pd.read_sql('SELECT id, time, product_name, result_json, url FROM analyses ORDER BY id DESC LIMIT 10', conn)
        if not df_hist.empty:
            for index, row in df_hist.iterrows():
                btn_label = f"{row['time']} - {row['product_name'][:15]}..."
                if st.button(btn_label, key=f"hist_{row['id']}", use_container_width=True):
                    try:
                        st.session_state['analysis_result'] = json.loads(row['result_json'])
                        st.session_state['source_url'] = row['url']
                        st.rerun()
                    except: st.error("Lỗi tải lịch sử")
        else:
            st.info("Chưa có lịch sử.")
    except Exception as e: st.error(f"Lỗi DB: {e}")
    conn.close()
    
    st.markdown("---")
    if st.button("🗑️ Xóa Lịch Sử", type="primary"):
        conn = sqlite3.connect(DB_NAME)
        conn.execute("DELETE FROM analyses")
        conn.commit()
        conn.close()
        st.rerun()

if 'analysis_result' not in st.session_state: st.session_state['analysis_result'] = None
if 'source_url' not in st.session_state: st.session_state['source_url'] = ""

if st.session_state['analysis_result'] is None:
    st.markdown('<div class="hero-title">AI Insight Universal</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hero-subtitle">Model: Gemini 2.5 Flash Lite • Quét đa năng mọi nền tảng</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1: st.markdown('<div class="feature-card">🕷️ <b>Quét Đa Năng</b><br><span style="font-size:12px;color:#888">Tự động bấm nút Xem thêm trên mọi web.</span></div>', unsafe_allow_html=True)
    with c2: st.markdown('<div class="feature-card">⚡ <b>Gemini 2.5 Lite</b><br><span style="font-size:12px;color:#888">Model mới nhất, tốc độ cao, chính xác.</span></div>', unsafe_allow_html=True)
    with c3: st.markdown('<div class="feature-card">📊 <b>Báo Cáo Sâu</b><br><span style="font-size:12px;color:#888">Phân loại 4 nhóm & Xuất Excel.</span></div>', unsafe_allow_html=True)
    
    st.write("")
    tab_link, tab_file = st.tabs(["🔗 NHẬP LINK", "📁 NẠP FILE DỮ LIỆU"])
    
    with tab_link:
        url_input = st.text_input("Link SP:", label_visibility="collapsed", placeholder="Dán link Foody, Shopee, FPT Shop...")
        if st.button("🚀 BẮT ĐẦU PHÂN TÍCH", use_container_width=True):
            if url_input:
                with st.status(f"🕷️ Đang quét dữ liệu ({page_limit} trang)...", expanded=True) as status:
                    # GỌI HÀM CÀO DỮ LIỆU
                    fetched, error_msg = get_web_content_selenium(url_input, max_pages=page_limit)
                    
                    if fetched and len(fetched) > 1000:
                        status.write(f"✅ Đã tải xong! Tổng dung lượng: {len(fetched)} ký tự. Đang gửi AI...")
                        res = analyze_content(fetched)
                        st.session_state['analysis_result'] = res
                        st.session_state['source_url'] = url_input
                        
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO analyses (product_name, url, result_json, time) VALUES (?,?,?,?)",
                                     (res.get('product_name'), url_input, json.dumps(res), datetime.now().strftime("%H:%M %d/%m")))
                        conn.commit()
                        conn.close()
                        
                        st.rerun()
                    else:
                        status.update(label="❌ Thất bại", state="error")
                        # HIỂN THỊ LỖI CHI TIẾT
                        if error_msg:
                            st.error(f"Lỗi hệ thống: {error_msg}")
                            st.info("💡 Mẹo: Hãy chắc chắn bạn đã tạo file packages.txt trên GitHub.")
                        else:
                            st.error("Không lấy được dữ liệu. Trang web có thể đang chặn hoặc trống.")
            else: st.warning("Vui lòng nhập Link!")
    
    with tab_file:
        uploaded_file = st.file_uploader("Kéo thả file Excel, CSV, Word, TXT vào đây:", type=['csv', 'xlsx', 'xls', 'txt', 'docx'])
        if uploaded_file is not None:
            if st.button("PHÂN TÍCH FILE", type="primary", use_container_width=True):
                with st.spinner("📂 Đang đọc và phân tích file..."):
                    file_text = process_uploaded_file(uploaded_file)
                    if file_text and len(file_text.strip()) > 0:
                        res = analyze_content(file_text)
                        st.session_state['analysis_result'] = res
                        st.session_state['source_url'] = f"File: {uploaded_file.name}"
                        
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO analyses (product_name, url, result_json, time) VALUES (?,?,?,?)",
                                     (res.get('product_name'), f"File: {uploaded_file.name}", json.dumps(res), datetime.now().strftime("%H:%M %d/%m")))
                        conn.commit()
                        conn.close()

                        st.rerun()
                    else:
                        st.error("File rỗng!")

else:
    res = st.session_state['analysis_result']
    c_back, c_space, c_excel = st.columns([1, 3, 2])
    with c_back:
        if st.button("⬅️ Quay lại"):
            st.session_state['analysis_result'] = None
            st.rerun()
    with c_excel:
        excel_data = generate_excel(res, st.session_state['source_url'])
        st.download_button("📥 TẢI BÁO CÁO EXCEL", excel_data, f"Report_{datetime.now().strftime('%d%m')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    if "error" in res: st.error(f"Lỗi AI: {res['error']}")
    else:
        st.divider()
        st.markdown(f"### 📦 {res.get('product_name', 'Kết quả phân tích')}")
        
        pos = res.get('positive_reviews', [])
        neg = res.get('negative_reviews', [])
        neu = res.get('neutral_reviews', [])
        inq = res.get('inquiry_reviews', [])
        
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f'<div class="metric-box"><div class="metric-num" style="color:#00C853">{len(pos)}</div><div class="metric-lbl">Tích cực</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-box"><div class="metric-num" style="color:#FF4B4B">{len(neg)}</div><div class="metric-lbl">Tiêu cực</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-box"><div class="metric-num" style="color:#FFAB00">{len(neu)}</div><div class="metric-lbl">Trung lập</div></div>', unsafe_allow_html=True)
        c4.markdown(f'<div class="metric-box"><div class="metric-num" style="color:#2962FF">{len(inq)}</div><div class="metric-lbl">Thắc mắc</div></div>', unsafe_allow_html=True)
        
        st.write("---")
        
        if len(pos)+len(neg)+len(neu)+len(inq) == 0:
            st.warning("⚠️ Không tìm thấy bình luận nào.")
        
        c_chart1, c_chart2 = st.columns(2)
        with c_chart1:
            st.subheader("Tỷ lệ Cảm Xúc")
            fig = go.Figure(data=[go.Pie(labels=["Tích cực", "Tiêu cực", "Trung lập", "Thắc mắc"], values=[len(pos), len(neg), len(neu), len(inq)], hole=.5, marker_colors=['#00C853', '#FF4B4B', '#FFAB00', '#2962FF'])])
            fig.update_layout(height=300, margin=dict(t=0,b=0,l=0,r=0), paper_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))
            st.plotly_chart(fig, use_container_width=True)
        
        with c_chart2:
            st.subheader("Chủ đề Nổi bật")
            clean_topics = {k:v for k,v in res.get('topic_counts', {}).items() if v > 0}
            if clean_topics:
                df_t = pd.DataFrame(list(clean_topics.items()), columns=['Topic', 'Count']).sort_values('Count')
                fig2 = px.bar(df_t, x='Count', y='Topic', orientation='h', text='Count')
                fig2.update_traces(marker_color='#4CAF50', textposition='outside')
                fig2.update_layout(height=300, margin=dict(t=0,b=0,l=0,r=0), paper_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))
                st.plotly_chart(fig2, use_container_width=True)
            else: st.info("Chưa có dữ liệu chủ đề.")

        st.write("---")
        t1, t2, t3, t4 = st.tabs(["🟢 Khen", "🔴 Chê", "🟡 Trung lập", "🔵 Hỏi đáp"])
        with t1: 
            for r in pos: st.success(f"👍 {r}")
        with t2: 
            for r in neg: st.error(f"👎 {r}")
        with t3: 
            for r in neu: st.warning(f"😐 {r}")
        with t4: 
            for r in inq: st.info(f"❓ {r}")

        if res.get('solution'):
            st.write("---")
            st.subheader("💡 Giải Pháp")
            st.info(res['solution'])