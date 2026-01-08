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

# ฟังก์ชันตรวจสอบ Config และ Redirect URI
def get_google_config():
    """ดึงข้อมูล Config สำหรับ OAuth จาก Secrets (Cloud) หรือ JSON (Local)"""
    # 1. ตรวจสอบใน Streamlit Secrets ก่อน (สำหรับ Cloud)
    if "web" in st.secrets:
        return dict(st.secrets["web"])
    
    # 2. ตรวจสอบจากไฟล์ Local JSON (สำหรับรันเครื่องตัวเอง)
    if os.path.exists(CLIENT_SECRETS_FILE):
        with open(CLIENT_SECRETS_FILE, "r") as f:
            data = json.load(f)
            return data.get("web", data.get("installed"))
    
    return None

# กำหนด Redirect URI ตามสภาพแวดล้อมที่รัน
config_data = get_google_config()
if os.getenv('STREAMLIT_SERVER_ADDRESS') == 'localhost' or os.getenv('STREAMLIT_SERVER_ADDRESS') is None:
    REDIRECT_URI = "http://localhost:8501"
else:
    # ดึงค่า Redirect URL จาก Secrets ที่ตั้งไว้บน Cloud
    if "web" in st.secrets and "redirect_url" in st.secrets["web"]:
        REDIRECT_URI = st.secrets["web"]["redirect_url"]
    else:
        REDIRECT_URI = "https://chinavut-marketing-tor-auditor.streamlit.app"


# --- Custom CSS (ตกแต่งหน้าตาให้สวยงามและเป็นระเบียบ) ---
st.markdown("""
<style>
    /* ตั้งค่าฟอนต์และพื้นหลังหลัก */
    .stApp { 
        background-color: #f8f9fa; 
        font-family: 'Sarabun', -apple-system, BlinkMacSystemFont, sans-serif; 
    }
    
    /* Hero Header (ส่วนหัวสีน้ำเงิน) */
    .hero-header {
        background: linear-gradient(135deg, #1565c0 0%, #1e88e5 100%);
        padding: 2rem; 
        border-radius: 12px; 
        color: white; 
        text-align: center;
        margin-bottom: 2rem; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .hero-title { 
        font-size: 2.5rem; 
        font-weight: 700; 
        margin-bottom: 0.5rem; 
    }
    .hero-subtitle { 
        font-size: 1.1rem; 
        opacity: 0.9; 
        font-weight: 300; 
    }

    /* ปรับแต่งปุ่มกดทั่วไป (Primary) */
    .stButton > button[data-testid="baseButton-primary"] {
        border-radius: 30px; 
        font-weight: bold; 
        height: 50px;
        background: linear-gradient(90deg, #1e88e5 0%, #1565c0 100%); 
        color: white; 
        border: none;
        transition: all 0.3s ease; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        width: 100%;
    }
    .stButton > button[data-testid="baseButton-primary"]:hover {
        transform: translateY(-2px); 
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        background: linear-gradient(90deg, #1565c0 0%, #0d47a1 100%);
    }

    /* ปรับแต่งปุ่มกดรอง (Logout / Secondary) */
    .stButton > button[data-testid="baseButton-secondary"] {
        border-radius: 30px; 
        font-weight: bold; 
        height: 45px;
        border: 1px solid #d32f2f; 
        color: #d32f2f; 
        background-color: white;
        transition: all 0.3s ease;
    }
    .stButton > button[data-testid="baseButton-secondary"]:hover {
        background-color: #d32f2f; 
        color: white;
    }
    
    /* กล่องแจ้งเตือนความสำเร็จ */
    .success-box {
        padding: 1.5rem; 
        background-color: #e8f5e9; 
        border-radius: 10px;
        border-left: 6px solid #4caf50; 
        color: #2e7d32; 
        margin-top: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }

    /* กล่อง Container สำหรับหน้า Login */
    .login-container-box {
        text-align: center; 
        padding: 50px 40px; 
        background: white; 
        border-radius: 24px; 
        box-shadow: 0 15px 35px rgba(0,0,0,0.1); 
        margin-top: 20px; 
        border: 1px solid #f0f0f0; 
        max-width: 500px; 
        margin-left: auto; 
        margin-right: auto;
    }
    .login-logo-img {
        max-width: 220px; 
        margin-bottom: 30px;
    }

    /* ปุ่ม Login with Google ดีไซน์มาตรฐาน */
    .google-btn {
        display: flex; 
        align-items: center; 
        justify-content: center;
        background-color: white; 
        color: #3c4043; 
        border: 1px solid #dadce0;
        border-radius: 8px; 
        padding: 12px 24px; 
        font-weight: 600; 
        cursor: pointer;
        box-shadow: 0 1px 2px rgba(60,64,67,0.3), 0 1px 3px 1px rgba(60,64,67,0.15); 
        text-decoration: none;
        font-family: 'Roboto', arial, sans-serif; 
        font-size: 16px; 
        margin: 0 auto;
        transition: background-color .218s, border-color .218s, box-shadow .218s;
        width: 100%; 
        max-width: 350px;
    }
    .google-btn:hover { 
        background-color: #f8f9fa; 
        border-color: #d2e3fc; 
        box-shadow: 0 1px 2px 0 rgba(60,64,67,0.30), 0 1px 3px 1px rgba(60,64,67,0.15);
    }
    .google-icon { 
        width: 20px; 
        height: 20px;
        margin-right: 12px; 
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔐 2. ส่วนจัดการระบบ Login (Google OAuth)
# ==========================================
def check_login():
    """ฟังก์ชันหลักสำหรับตรวจสอบสถานะการเข้าสู่ระบบ"""
    config = get_google_config()
    
    if config is None:
        st.error("❌ Configuration Error: ไม่พบการตั้งค่า OAuth กรุณาตรวจสอบไฟล์ JSON หรือ Secrets")
        st.stop()

    if 'credentials' not in st.session_state:
        st.session_state.credentials = None

    # จัดการกรณี Google ส่ง Auth Code กลับมาทาง URL (Callback)
    if st.query_params.get('code'):
        try:
            # 🛡️ แก้ไขบั๊กจอแดง: ครอบด้วย key "web" เพื่อให้ Library ยอมรับ
            flow = Flow.from_client_config(
                {"web": config}, 
                scopes=SCOPES, 
                redirect_uri=REDIRECT_URI
            )
            flow.fetch_token(code=st.query_params['code'])
            st.session_state.credentials = flow.credentials
            # ล้าง URL query params ให้สะอาด
            st.query_params.clear()
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดระหว่างกระบวนการ Login: {e}")

    # กรณีที่ผู้ใช้ยังไม่ได้ Login หรือ Token หมดอายุ
    if not st.session_state.credentials:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<br><br>", unsafe_allow_html=True)
            
            # 🛡️ แก้ไขบั๊กตัวหนังสือโค้ด: ประกอบ HTML เป็น String ก้อนเดียว
            login_box_html = '<div class="login-container-box">'
            
            # ตรวจสอบและฝังโลโก้บริษัท
            if os.path.exists("logo.png"):
                with open("logo.png", "rb") as f:
                    encoded_img = base64.b64encode(f.read()).decode("utf-8")
                login_box_html += f'<img src="data:image/png;base64,{encoded_img}" class="login-logo-img">'
            
            login_box_html += """
                <h2 style="color: #0d47a1; margin-bottom: 8px;">🔐 Login System</h2>
                <p style="color: #5f6368; margin-bottom: 32px;">กรุณาเข้าสู่ระบบด้วยบัญชี Google ของบริษัทเพื่อดำเนินการต่อ</p>
            """
            
            try:
                flow = Flow.from_client_config(
                    {"web": config}, 
                    scopes=SCOPES, 
                    redirect_uri=REDIRECT_URI
                )
                auth_url, _ = flow.authorization_url(prompt='consent')
                
                # ปุ่ม Login พร้อมโลโก้ Google ที่เสถียร
                login_box_html += f'''
                    <a href="{auth_url}" target="_self" class="google-btn">
                        <img src="https://fonts.gstatic.com/s/i/productlogos/googleg/v6/24px.svg" class="google-icon">
                        Sign in with Google (@chinavut.com)
                    </a>
                '''
            except Exception as e:
                login_box_html += f'<p style="color: #d32f2f;">การตั้งค่าความปลอดภัยผิดพลาด: {e}</p>'
            
            login_box_html += "</div>"
            
            # 🛡️ สำคัญ: เรียกใช้ markdown เพียงครั้งเดียวเพื่อป้องกันปัญหาการเยื้อง (Indentation)
            st.markdown(login_box_html, unsafe_allow_html=True)
        st.stop()

    # ตรวจสอบสิทธิ์ผู้ใช้หลัง Login สำเร็จ
    if st.session_state.credentials:
        try:
            service = build('oauth2', 'v2', credentials=st.session_state.credentials)
            user_info = service.userinfo().get().execute()
            user_email = user_info.get('email', '')
            
            # 🛡️ ระบบกรอง Domain: ต้องเป็นเมลบริษัทเท่านั้น
            if not user_email.endswith('@chinavut.com'):
                st.warning(f"🔒 เข้าถึงไม่ได้: บัญชี {user_email} ไม่มีสิทธิ์ใช้งาน")
                st.error("ระบบนี้จำกัดการเข้าถึงเฉพาะบุคลากรของ Chinavut Marketing เท่านั้น")
                if st.button("🔙 กลับไปหน้า Login"):
                    st.session_state.credentials = None
                    st.rerun()
                st.stop()
            
            # บันทึกข้อมูล Session
            st.session_state.user_email = user_email
            st.session_state.user_name = user_info.get('name', 'User')
            st.session_state.user_picture = user_info.get('picture', 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png')
            
        except Exception as e:
            st.error(f"เซสชันหมดอายุหรือพบปัญหา: {e}")
            st.session_state.credentials = None
            if st.button("🔄 เข้าสู่ระบบอีกครั้ง"):
                st.rerun()
            st.stop()

# --- ดำเนินการตรวจสอบ Login เป็นอันดับแรก ---
check_login()

# ==========================================
# 3. ส่วนการประมวลผล (PDF & Excel Logic)
# ==========================================
def highlight_pdf_content(pdf_file, data_list):
    """ฟังก์ชันหลักสำหรับทำไฮไลท์ PDF และเขียนข้อกำกับ"""
    pdf_file.seek(0)
    document = fitz.open(stream=pdf_file.read(), filetype="pdf")
    match_count = 0
    
    for entry in data_list:
        try:
            # เตรียมข้อมูลจาก List
            page_index = int(entry.get("page", 0))
            search_text = entry.get("text", entry.get("evidence", ""))
            label = str(entry.get("tor_no", ""))
            
            # ตรวจสอบขอบเขตหน้า
            if 0 <= page_index < len(document):
                current_page = document[page_index]
                
                # ค้นหาข้อความ
                hits = current_page.search_for(search_text)
                if not hits:
                    hits = current_page.search_for(search_text.strip())
                
                if hits:
                    for rect in hits:
                        # 1. วาดไฮไลท์สีเหลือง
                        highlight = current_page.add_highlight_annot(rect)
                        highlight.update()
                        
                        # 2. คำนวณตำแหน่งเขียนเลขข้อ (TOR No.)
                        target_x = rect.x0 - 45 if rect.x0 > 50 else rect.x1 + 10
                        target_y = rect.y0 + 8
                        
                        # 3. เขียนข้อความสีแดงกำกับ
                        current_page.insert_text(
                            fitz.Point(target_x, target_y), 
                            label, 
                            fontsize=9, 
                            color=(1, 0, 0)
                        )
                    match_count += 1
        except Exception:
            continue
            
    # บันทึกไฟล์ที่แก้ไขแล้วลงใน Buffer
    pdf_output = io.BytesIO()
    document.save(pdf_output)
    pdf_output.seek(0)
    return pdf_output, match_count

# ==========================================
# 4. User Interface (หน้าจอการทำงานหลัก)
# ==========================================

# --- Sidebar Management ---
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.info("Chinavut Marketing")
        
    st.markdown("---")

    # ข้อมูลโปรไฟล์ผู้ใช้งาน
    if 'user_picture' in st.session_state:
        st.image(st.session_state.user_picture, width=80)
    st.markdown(f"👤 **{st.session_state.user_name}**")
    st.caption(f"📧 {st.session_state.user_email}")
    st.success("✅ บัญชีได้รับการยืนยัน")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("🚪 Sign out (ออกจากระบบ)", type="secondary", use_container_width=True):
        st.session_state.credentials = None
        st.query_params.clear()
        st.rerun()

    st.markdown("---")
    st.link_button("🧠 เปิด Gemini (Start AI Analysis)", GEMINI_LINK, type="primary", use_container_width=True)
    
    st.info("""
    **ขั้นตอนการใช้งาน:**
    1. คลิกปุ่ม Gemini เพื่อวิเคราะห์
    2. ก๊อปปี้โค้ดมาวาง
    3. อัปโหลด PDF
    4. กดปุ่มเริ่มประมวลผล
    """)

# --- ส่วนหัว (Hero Section) ---
st.markdown("""
    <div class="hero-header">
        <div class="hero-title">📋 TOR Smart Auditor</div>
        <div class="hero-subtitle">ระบบตรวจสอบสเปกสินค้า ทำไฮไลท์เอกสาร และสรุปผลอัตโนมัติ</div>
    </div>
""", unsafe_allow_html=True)

# --- ส่วนของการรับข้อมูล (Main Content) ---
main_col1, main_col2 = st.columns([1, 1], gap="large")

with main_col1:
    st.markdown("### 1️⃣ เตรียมข้อมูลตรวจสอบ")
    input_text = st.text_area(
        label="Input Area for AI Code", 
        height=350, 
        placeholder="highlight_data = [...]",
        label_visibility="collapsed"
    )

with main_col2:
    st.markdown("### 2️⃣ อัปโหลดเอกสารต้นฉบับ")
    pdf_file_upload = st.file_uploader("Upload Catalog PDF", type=["pdf"], label_visibility="collapsed")
    if pdf_file_upload:
        st.success(f"✅ ไฟล์พร้อมใช้งาน: {pdf_file_upload.name}")

# --- ส่วนการประมวลผล ---
st.markdown("<hr>", unsafe_allow_html=True)
if st.button("✨ เริ่มประมวลผลและสร้างรายงาน (Generate) ✨", type="primary"):
    if not input_text or not pdf_file_upload:
        st.warning("⚠️ กรุณาวางโค้ด AI และอัปโหลดไฟล์ PDF ให้เรียบร้อย")
    else:
        with st.spinner("🔄 กำลังประมวลผล..."):
            try:
                clean_str = input_text.strip()
                if "=" in clean_str:
                    clean_str = clean_str.split("=", 1)[1].strip()
                
                final_data_list = ast.literal_eval(clean_str)
                
                if isinstance(final_data_list, list):
                    report_df = pd.DataFrame(final_data_list)
                    if 'page' in report_df.columns:
                        report_df['page'] = pd.to_numeric(report_df['page'], errors='coerce').fillna(0).astype(int) + 1
                    
                    excel_out = io.BytesIO()
                    with pd.ExcelWriter(excel_out, engine='openpyxl') as writer:
                        report_df.to_excel(writer, index=False)
                    
                    pdf_result, total_highlights = highlight_pdf_content(pdf_file_upload, final_data_list)
                    
                    st.balloons()
                    st.markdown(f'<div class="success-box">🎉 สำเร็จ! พบทั้งหมด {total_highlights} จุด</div>', unsafe_allow_html=True)
                    
                    d_col1, d_col2 = st.columns(2)
                    d_col1.download_button("📊 Download Excel", excel_out.getvalue(), "Report.xlsx", use_container_width=True)
                    d_col2.download_button("📕 Download PDF", pdf_result.getvalue(), "Checked.pdf", use_container_width=True)
            except Exception as error:
                st.error(f"❌ เกิดข้อผิดพลาด: {error}")