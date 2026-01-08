import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import io
import ast
import os
import base64
import json

# ==========================================
# 0. ตรวจสอบการติดตั้ง Library ที่จำเป็น
# ==========================================
try:
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
except ImportError:
    st.error("⚠️ Cloud environment detected: Missing Google Auth libraries. Please add 'google-auth-oauthlib' and 'google-api-python-client' to requirements.txt")
    st.stop()

# ==========================================
# 1. ตั้งค่าหน้าเว็บ & Design System
# ==========================================
st.set_page_config(
    page_title="TOR Smart Auditor",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ลิ้งก์ Gemini Gem ของคุณ
GEMINI_LINK = "https://gemini.google.com/gem/104gb9EOFpjtI6H3prcO76jchjc4DZE72?usp=sharing"

# --- ตั้งค่า Google OAuth ---
CLIENT_SECRETS_FILE = "client_secret.json" 
SCOPES = [
    'openid', 
    'https://www.googleapis.com/auth/userinfo.email', 
    'https://www.googleapis.com/auth/userinfo.profile'
]

def get_google_config():
    """ดึงข้อมูล Config สำหรับ OAuth จาก Secrets (Cloud) หรือ JSON (Local)"""
    if "web" in st.secrets:
        return dict(st.secrets["web"])
    if os.path.exists(CLIENT_SECRETS_FILE):
        with open(CLIENT_SECRETS_FILE, "r") as f:
            data = json.load(f)
            return data.get("web", data.get("installed"))
    return None

config_data = get_google_config()
if os.getenv('STREAMLIT_SERVER_ADDRESS') == 'localhost' or os.getenv('STREAMLIT_SERVER_ADDRESS') is None:
    REDIRECT_URI = "http://localhost:8501"
else:
    if "web" in st.secrets and "redirect_url" in st.secrets["web"]:
        REDIRECT_URI = st.secrets["web"]["redirect_url"]
    else:
        REDIRECT_URI = "https://chinavut-marketing-tor-auditor.streamlit.app"

# --- Custom CSS (ปรับปรุงเพื่อให้เสถียรขึ้น) ---
st.markdown("""
<style>
    .stApp { 
        background-color: #f8f9fa; 
        font-family: 'Sarabun', -apple-system, BlinkMacSystemFont, sans-serif; 
    }
    .hero-header {
        background: linear-gradient(135deg, #1565c0 0%, #1e88e5 100%);
        padding: 2rem; border-radius: 12px; color: white; 
        text-align: center; margin-bottom: 2rem; box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .hero-title { font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem; }
    .hero-subtitle { font-size: 1.1rem; opacity: 0.9; font-weight: 300; }

    .stButton > button[data-testid="baseButton-primary"] {
        border-radius: 30px; font-weight: bold; height: 50px;
        background: linear-gradient(90deg, #1e88e5 0%, #1565c0 100%); 
        color: white; border: none; transition: all 0.3s ease; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.1); width: 100%;
    }
    .stButton > button[data-testid="baseButton-secondary"] {
        border-radius: 30px; font-weight: bold; height: 45px;
        border: 1px solid #d32f2f; color: #d32f2f; background-color: white;
    }

    .login-container-box {
        text-align: center; padding: 50px 40px; background: white; 
        border-radius: 24px; box-shadow: 0 15px 35px rgba(0,0,0,0.1); 
        margin: 20px auto; border: 1px solid #f0f0f0; max-width: 500px;
    }
    .login-logo-img { max-width: 220px; margin-bottom: 30px; }

    .google-btn {
        display: inline-flex; align-items: center; justify-content: center;
        background-color: white; color: #3c4043; border: 1px solid #dadce0;
        border-radius: 8px; padding: 12px 24px; font-weight: 600; 
        cursor: pointer; text-decoration: none !important; font-size: 16px; 
        transition: all 0.2s; width: 100%; max-width: 350px;
    }
    .google-btn:hover { background-color: #f8f9fa; border-color: #d2e3fc; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
    .google-icon { width: 20px; height: 20px; margin-right: 12px; }
    
    .success-box {
        padding: 1.5rem; background-color: #e8f5e9; border-radius: 10px;
        border-left: 6px solid #4caf50; color: #2e7d32; margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔐 2. ส่วนจัดการระบบ Login
# ==========================================
def check_login():
    config = get_google_config()
    if config is None:
        st.error("❌ Configuration Error: ไม่พบการตั้งค่า OAuth")
        st.stop()

    if 'credentials' not in st.session_state:
        st.session_state.credentials = None

    # Handle Google Callback
    if 'code' in st.query_params:
        try:
            flow = Flow.from_client_config({"web": config}, scopes=SCOPES, redirect_uri=REDIRECT_URI)
            flow.fetch_token(code=st.query_params['code'])
            st.session_state.credentials = flow.credentials
            st.query_params.clear()
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดระหว่างกระบวนการ Login: {e}")

    # แสดงหน้า Login
    if not st.session_state.credentials:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<br><br>", unsafe_allow_html=True)
            
            # เตรียมข้อมูล Logo และ Auth URL
            logo_html = ""
            if os.path.exists("logo.png"):
                with open("logo.png", "rb") as f:
                    encoded_img = base64.b64encode(f.read()).decode("utf-8")
                logo_html = f'<img src="data:image/png;base64,{encoded_img}" class="login-logo-img">'
            
            try:
                flow = Flow.from_client_config({"web": config}, scopes=SCOPES, redirect_uri=REDIRECT_URI)
                auth_url, _ = flow.authorization_url(prompt='consent')
                
                # Render HTML ชุดเดียวเพื่อป้องกันปัญหา Indentation และ String break
                login_ui_html = f"""
                <div class="login-container-box">
                    {logo_html}
                    <h2 style="color: #0d47a1; margin-bottom: 8px;">🔐 Login System</h2>
                    <p style="color: #5f6368; margin-bottom: 32px;">กรุณาเข้าสู่ระบบด้วยบัญชี Google ของบริษัทเพื่อดำเนินการต่อ</p>
                    <a href="{auth_url}" target="_self" class="google-btn">
                        <img src="https://fonts.gstatic.com/s/i/productlogos/googleg/v6/24px.svg" class="google-icon">
                        Sign in with Google (@chinavut.com)
                    </a>
                </div>
                """
                st.markdown(login_ui_html, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"การตั้งค่าความปลอดภัยผิดพลาด: {e}")
        st.stop()

    # ตรวจสอบสิทธิ์หลัง Login
    if st.session_state.credentials:
        try:
            service = build('oauth2', 'v2', credentials=st.session_state.credentials)
            user_info = service.userinfo().get().execute()
            user_email = user_info.get('email', '')
            
            if not user_email.endswith('@chinavut.com'):
                st.warning(f"🔒 เข้าถึงไม่ได้: บัญชี {user_email} ไม่มีสิทธิ์ใช้งาน")
                st.error("ระบบนี้จำกัดการเข้าถึงเฉพาะบุคลากรของ Chinavut Marketing เท่านั้น")
                if st.button("🔙 กลับไปหน้า Login"):
                    st.session_state.credentials = None
                    st.rerun()
                st.stop()
            
            st.session_state.user_email = user_email
            st.session_state.user_name = user_info.get('name', 'User')
            st.session_state.user_picture = user_info.get('picture', 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png')
            
        except Exception as e:
            st.session_state.credentials = None
            st.rerun()

check_login()

# ==========================================
# 3. ส่วนการประมวลผล PDF & Logic (ฟังก์ชันเดิมทั้งหมด)
# ==========================================
def highlight_pdf_content(pdf_file, data_list):
    pdf_file.seek(0)
    document = fitz.open(stream=pdf_file.read(), filetype="pdf")
    match_count = 0
    
    for entry in data_list:
        try:
            page_index = int(entry.get("page", 0))
            search_text = entry.get("text", entry.get("evidence", ""))
            label = str(entry.get("tor_no", ""))
            
            if 0 <= page_index < len(document):
                current_page = document[page_index]
                hits = current_page.search_for(search_text)
                if not hits: hits = current_page.search_for(search_text.strip())
                
                if hits:
                    for rect in hits:
                        highlight = current_page.add_highlight_annot(rect)
                        highlight.update()
                        target_x = rect.x0 - 45 if rect.x0 > 50 else rect.x1 + 10
                        current_page.insert_text(fitz.Point(target_x, rect.y0 + 8), label, fontsize=9, color=(1, 0, 0))
                    match_count += 1
        except: continue
            
    pdf_output = io.BytesIO()
    document.save(pdf_output)
    pdf_output.seek(0)
    return pdf_output, match_count

# ==========================================
# 4. หน้าจอการทำงานหลัก (UI เดิมทั้งหมด)
# ==========================================
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    st.markdown("---")
    st.image(st.session_state.user_picture, width=80)
    st.markdown(f"👤 **{st.session_state.user_name}**")
    st.caption(f"📧 {st.session_state.user_email}")
    if st.button("🚪 Sign out (ออกจากระบบ)", type="secondary", use_container_width=True):
        st.session_state.credentials = None
        st.query_params.clear()
        st.rerun()
    st.markdown("---")
    st.link_button("🧠 เปิด Gemini (Start AI Analysis)", GEMINI_LINK, type="primary", use_container_width=True)
    st.info("**ขั้นตอนการใช้งาน:**\n1. วิเคราะห์ด้วย AI\n2. วางโค้ดข้อมูล\n3. อัปโหลด PDF\n4. กดปุ่มสร้างรายงาน")

st.markdown(f"""
    <div class="hero-header">
        <div class="hero-title">📋 TOR Smart Auditor</div>
        <div class="hero-subtitle">ระบบตรวจสอบสเปกสินค้า ทำไฮไลท์เอกสาร และสรุปผลอัตโนมัติ</div>
    </div>
""", unsafe_allow_html=True)

main_col1, main_col2 = st.columns([1, 1], gap="large")
with main_col1:
    st.markdown("### 1️⃣ เตรียมข้อมูลตรวจสอบ")
    input_text = st.text_area("Input Area", height=350, placeholder="highlight_data = [...]", label_visibility="collapsed")
with main_col2:
    st.markdown("### 2️⃣ อัปโหลดเอกสารต้นฉบับ")
    pdf_file_upload = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")
    if not pdf_file_upload:
        st.markdown('<div style="border: 2px dashed #ccc; padding: 60px; text-align: center; border-radius: 15px; color: #999;">📂<br>ลากไฟล์ PDF มาวางที่นี่</div>', unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)
if st.button("✨ เริ่มประมวลผลและสร้างรายงาน (Generate) ✨", type="primary", use_container_width=True):
    if not input_text or not pdf_file_upload:
        st.warning("⚠️ กรุณาวางโค้ด AI และอัปโหลดไฟล์ PDF ให้เรียบร้อยก่อนครับ")
    else:
        with st.spinner("🔄 กำลังวิเคราะห์ข้อมูล..."):
            try:
                clean_str = input_text.strip()
                if "=" in clean_str: clean_str = clean_str.split("=", 1)[1].strip()
                final_data_list = ast.literal_eval(clean_str)
                
                if isinstance(final_data_list, list):
                    # สร้าง Excel Report
                    report_df = pd.DataFrame(final_data_list)
                    if 'page' in report_df.columns:
                        report_df['page'] = pd.to_numeric(report_df['page'], errors='coerce').fillna(0).astype(int) + 1
                    
                    mapping = {"tor_no": "ข้อที่ (TOR)", "desc": "รายละเอียดเกณฑ์ TOR", "text": "ข้อความที่พบ", "evidence": "ข้อความที่พบ", "page": "หน้า", "status": "ผลการตรวจสอบ"}
                    report_df.rename(columns=mapping, inplace=True)
                    
                    excel_out = io.BytesIO()
                    with pd.ExcelWriter(excel_out, engine='openpyxl') as writer:
                        report_df.to_excel(writer, index=False)
                    
                    # ไฮไลท์ PDF
                    pdf_result, total_highlights = highlight_pdf_content(pdf_file_upload, final_data_list)
                    
                    st.balloons()
                    st.markdown(f'<div class="success-box">🎉 การประมวลผลสำเร็จ! ไฮไลท์ได้ทั้งหมด {total_highlights} จุด</div>', unsafe_allow_html=True)
                    
                    d1, d2 = st.columns(2)
                    with d1: st.download_button("📊 ดาวน์โหลด Excel", excel_out.getvalue(), "Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                    with d2: st.download_button("📕 ดาวน์โหลด PDF ไฮไลท์", pdf_result.getvalue(), "Highlighted.pdf", mime="application/pdf", use_container_width=True)
                    with st.expander("🔍 ดูตัวอย่างข้อมูล"): st.dataframe(report_df, use_container_width=True)
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")
