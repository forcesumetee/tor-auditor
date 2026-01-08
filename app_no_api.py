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

GEMINI_LINK = "https://gemini.google.com/gem/104gb9EOFpjtI6H3prcO76jchjc4DZE72?usp=sharing"
SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

def get_google_config():
    if "web" in st.secrets:
        return dict(st.secrets["web"])
    if os.path.exists("client_secret.json"):
        with open("client_secret.json", "r") as f:
            data = json.load(f)
            return data.get("web", data.get("installed"))
    return None

# ตั้งค่า Redirect URI
if os.getenv('STREAMLIT_SERVER_ADDRESS') == 'localhost' or os.getenv('STREAMLIT_SERVER_ADDRESS') is None:
    REDIRECT_URI = "http://localhost:8501"
else:
    REDIRECT_URI = "https://chinavut-marketing-tor-auditor.streamlit.app"

# --- Custom CSS ---
st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; font-family: 'Sarabun', sans-serif; }
    .hero-header {
        background: linear-gradient(135deg, #1565c0 0%, #1e88e5 100%);
        padding: 2rem; border-radius: 12px; color: white; text-align: center;
        margin-bottom: 2rem; box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .hero-title { font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem; }
    .stButton > button[data-testid="baseButton-primary"] {
        border-radius: 30px; font-weight: bold; height: 50px; width: 100%;
        background: linear-gradient(90deg, #1e88e5 0%, #1565c0 100%); color: white; border: none;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔐 2. ระบบ Login (แก้ไขบั๊ก Indentation 100%)
# ==========================================
def check_login():
    config = get_google_config()
    if not config:
        st.error("❌ Configuration Error: ไม่พบการตั้งค่า OAuth ใน Secrets")
        st.stop()

    if 'credentials' not in st.session_state:
        st.session_state.credentials = None

    if st.query_params.get('code'):
        try:
            flow = Flow.from_client_config({"web": config}, scopes=SCOPES, redirect_uri=REDIRECT_URI)
            flow.fetch_token(code=st.query_params['code'])
            st.session_state.credentials = flow.credentials
            st.query_params.clear()
        except Exception as e:
            st.error(f"Login Error: {e}")

    if not st.session_state.credentials:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<br><br>", unsafe_allow_html=True)
            
            # --- สร้าง HTML String สำหรับปุ่ม Login ---
            try:
                flow = Flow.from_client_config({"web": config}, scopes=SCOPES, redirect_uri=REDIRECT_URI)
                auth_url, _ = flow.authorization_url(prompt='consent')
                
                logo_html = ""
                if os.path.exists("logo.png"):
                    with open("logo.png", "rb") as f:
                        data = base64.b64encode(f.read()).decode("utf-8")
                    logo_html = f'<img src="data:image/png;base64,{data}" style="max-width:180px; margin-bottom:20px;">'

                # ใช้ Components HTML เพื่อวาดปุ่มแทน Markdown (แก้ปัญหา Indentation ถาวร)
                login_ui = f"""
                <div style="text-align: center; padding: 40px; background: white; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); font-family: sans-serif;">
                    {logo_html}
                    <h2 style="color: #0d47a1; margin-bottom: 10px;">Login System</h2>
                    <p style="color: #666; margin-bottom: 30px;">กรุณาเข้าสู่ระบบด้วยบัญชี @chinavut.com</p>
                    <a href="{auth_url}" target="_top" style="display: flex; align-items: center; justify-content: center; background-color: white; color: #3c4043; border: 1px solid #dadce0; border-radius: 8px; padding: 12px 24px; font-weight: 600; text-decoration: none; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
                        <img src="https://fonts.gstatic.com/s/i/productlogos/googleg/v6/24px.svg" style="width:20px; margin-right:12px;">
                        Sign in with Google
                    </a>
                </div>
                """
                st.components.v1.html(login_ui, height=450)
                
            except Exception as e:
                st.error(f"UI Error: {e}")
        st.stop()

    if st.session_state.credentials:
        try:
            service = build('oauth2', 'v2', credentials=st.session_state.credentials)
            user = service.userinfo().get().execute()
            if not user.get('email', '').endswith('@chinavut.com'):
                st.error("🔒 อนุญาตเฉพาะบัญชี @chinavut.com")
                if st.button("Logout"):
                    st.session_state.credentials = None
                    st.rerun()
                st.stop()
            st.session_state.user_email = user.get('email')
            st.session_state.user_name = user.get('name')
            st.session_state.user_picture = user.get('picture')
        except:
            st.session_state.credentials = None
            st.rerun()

check_login()

# ==========================================
# 3. ส่วนการประมวลผล (Logic)
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
                hits = current_page.search_for(search_text) or current_page.search_for(search_text.strip())
                for rect in hits:
                    current_page.add_highlight_annot(rect).update()
                    current_page.insert_text(fitz.Point(rect.x0 - 45 if rect.x0 > 50 else rect.x1 + 10, rect.y0 + 8), label, fontsize=9, color=(1, 0, 0))
                if hits: match_count += 1
        except: continue
    pdf_output = io.BytesIO()
    document.save(pdf_output)
    pdf_output.seek(0)
    return pdf_output, match_count

# ==========================================
# 4. User Interface
# ==========================================
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
    st.markdown("---")
    st.image(st.session_state.user_picture, width=80)
    st.markdown(f"👤 **{st.session_state.user_name}**")
    if st.button("🚪 Sign out (ออกจากระบบ)", type="secondary", use_container_width=True):
        st.session_state.credentials = None
        st.query_params.clear()
        st.rerun()
    st.markdown("---")
    st.link_button("🧠 เปิด Gemini Analysis", GEMINI_LINK, type="primary", use_container_width=True)

st.markdown('<div class="hero-header"><div class="hero-title">📋 TOR Smart Auditor</div></div>', unsafe_allow_html=True)
c1, c2 = st.columns([1, 1], gap="large")

with c1:
    st.markdown("### 1️⃣ เตรียมข้อมูล")
    input_text = st.text_area("Input Code", height=350, placeholder="highlight_data = [...]", label_visibility="collapsed")

with c2:
    st.markdown("### 2️⃣ อัปโหลดไฟล์")
    pdf_file_upload = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")

if st.button("✨ เริ่มประมวลผล (Generate Report) ✨", type="primary"):
    if input_text and pdf_file_upload:
        with st.spinner("🔄 กำลังประมวลผล..."):
            try:
                clean_str = input_text.strip()
                if "=" in clean_str: clean_str = clean_str.split("=", 1)[1].strip()
                final_data_list = ast.literal_eval(clean_str)
                
                report_df = pd.DataFrame(final_data_list)
                if 'page' in report_df.columns:
                    report_df['page'] = pd.to_numeric(report_df['page'], errors='coerce').fillna(0).astype(int) + 1
                
                excel_out = io.BytesIO()
                with pd.ExcelWriter(excel_out, engine='openpyxl') as writer:
                    report_df.to_excel(writer, index=False)
                
                pdf_res, total = highlight_pdf_content(pdf_file_upload, final_data_list)
                
                st.balloons()
                st.markdown(f'<div style="padding:15px; background:#e8f5e9; border-radius:10px; color:#2e7d32;">🎉 สำเร็จ! พบทั้งหมด {total} จุด</div>', unsafe_allow_html=True)
                d1, d2 = st.columns(2)
                d1.download_button("📊 Download Excel", excel_out.getvalue(), "Report.xlsx", use_container_width=True)
                d2.download_button("📕 Download PDF", pdf_res.getvalue(), "Checked.pdf", use_container_width=True)
            except Exception as e: st.error(f"Error: {e}")
