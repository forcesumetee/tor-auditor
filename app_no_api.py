import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import io
import ast
import os
import base64

# ตรวจสอบการติดตั้ง library ที่จำเป็นก่อนเรียกใช้
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
SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

# ตรวจสอบ Environment เพื่อตั้งค่า Redirect URI (Local vs Cloud)
if os.getenv('STREAMLIT_SERVER_ADDRESS') == 'localhost' or os.getenv('STREAMLIT_SERVER_ADDRESS') is None:
     REDIRECT_URI = "http://localhost:8501"
else:
     # กรณี deploy บน cloud อาจต้องใช้ URL จริง หรือดึงจาก secrets
     REDIRECT_URI = st.secrets.get("REDIRECT_URL", "http://localhost:8501")


# --- Custom CSS (ตกแต่งหน้าตา) ---
st.markdown("""
<style>
    /* ตั้งค่าฟอนต์และพื้นหลัง */
    .stApp { background-color: #f8f9fa; font-family: 'Sarabun', -apple-system, BlinkMacSystemFont, sans-serif; }
    
    /* Hero Header (ส่วนหัวสีน้ำเงิน) */
    .hero-header {
        background: linear-gradient(135deg, #1565c0 0%, #1e88e5 100%);
        padding: 1.5rem; border-radius: 12px; color: white; text-align: center;
        margin-bottom: 1.5rem; box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .hero-title { font-size: 2rem; font-weight: 700; margin-bottom: 0.3rem; }
    .hero-subtitle { font-size: 1rem; opacity: 0.9; font-weight: 300; }

    /* ปรับแต่งปุ่มกดทั่วไป (Primary) */
    .stButton > button[data-testid="baseButton-primary"] {
        border-radius: 25px; font-weight: bold; height: 45px;
        background: linear-gradient(90deg, #1e88e5 0%, #1565c0 100%); color: white; border: none;
        transition: all 0.3s ease; box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .stButton > button[data-testid="baseButton-primary"]:hover {
        transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }

    /* ปรับแต่งปุ่มกดรอง (Secondary / Logout) */
    .stButton > button[data-testid="baseButton-secondary"] {
        border-radius: 25px; font-weight: bold; height: 45px;
        border: 1px solid #d32f2f; color: #d32f2f; background-color: white;
        transition: all 0.3s ease;
    }
    .stButton > button[data-testid="baseButton-secondary"]:hover {
        background-color: #d32f2f; color: white;
    }
    
    /* กล่องข้อความสำเร็จ */
    .success-box {
        padding: 1rem; background-color: #e8f5e9; border-radius: 10px;
        border-left: 5px solid #4caf50; color: #2e7d32; margin-top: 1rem;
    }

    /* กล่อง Login หน้าแรก */
    .login-container-box {
        text-align: center; padding: 40px 30px; background: white; 
        border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); 
        margin-top: 20px; border: 1px solid #f0f0f0; max-width: 450px; margin-left: auto; margin-right: auto;
    }
    .login-logo-img {
        max-width: 180px; margin-bottom: 25px;
    }

    /* ปุ่ม Login Google สวยๆ */
    .google-btn {
        display: flex; align-items: center; justify-content: center;
        background-color: white; color: #555; border: 1px solid #ddd;
        border-radius: 8px; padding: 12px; font-weight: 600; cursor: pointer;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05); text-decoration: none;
        font-family: 'Roboto', sans-serif; font-size: 16px; margin: 0 auto;
        transition: all 0.2s ease; width: 100%; max-width: 320px;
    }
    .google-btn:hover { background-color: #f8f9fa; box-shadow: 0 2px 5px rgba(0,0,0,0.1); border-color: #ccc; color: #333; }
    .google-icon { width: 24px; margin-right: 12px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔐 2. ส่วนจัดการ Google Login (OAuth Real)
# ==========================================
def check_login():
    """ระบบตรวจสอบสิทธิ์ผ่าน Google"""
    
    # 1. เช็คไฟล์ client_secret.json (เฉพาะเมื่อรัน Localhost)
    if REDIRECT_URI == "http://localhost:8501":
        if not os.path.exists(CLIENT_SECRETS_FILE):
            st.error(f"❌ ไม่พบไฟล์ '{CLIENT_SECRETS_FILE}' กรุณาดาวน์โหลดจาก Google Cloud Console มาวางในโฟลเดอร์เดียวกับโค้ดนี้ครับ (สำหรับการรันบน Localhost)")
            st.stop()

    # 2. เตรียม Session เก็บข้อมูล Login
    if 'credentials' not in st.session_state:
        st.session_state.credentials = None

    # 3. ตรวจสอบว่า Google ส่งรหัสกลับมาให้หรือยัง (Callback)
    if st.query_params.get('code'):
        try:
            flow = Flow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
            flow.fetch_token(code=st.query_params['code'])
            st.session_state.credentials = flow.credentials
            
            # ล้าง URL ให้สะอาด (ลบ code ออก)
            st.query_params.clear()
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการ Login: {e}")

    # 4. ถ้ายังไม่ได้ Login -> แสดงหน้า Login
    if not st.session_state.credentials:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            
            # --- สร้าง HTML String สำหรับกล่อง Login ---
            # ใช้การต่อสตริงแบบบรรทัดต่อบรรทัดเพื่อป้องกันปัญหา Indentation
            login_html = """<div class="login-container-box">"""
            
            # ใส่โลโก้ (ถ้ามี) ไว้ในกล่อง
            if os.path.exists("logo.png"):
                 # แปลงรูปภาพเป็น base64 เพื่อฝังใน HTML
                import base64
                with open("logo.png", "rb") as f:
                    data = base64.b64encode(f.read()).decode("utf-8")
                login_html += f'<img src="data:image/png;base64,{data}" class="login-logo-img">'
            
            login_html += """<h2 style="color: #0d47a1; margin-bottom: 10px; font-weight: 700;">Login System</h2>"""
            login_html += """<p style="color: gray; margin-bottom: 30px;">กรุณาเข้าสู่ระบบด้วยบัญชี Google ของบริษัท</p>"""
            
            # สร้างลิ้งก์ Login ไปยัง Google
            try:
                if os.path.exists(CLIENT_SECRETS_FILE):
                    flow = Flow.from_client_secrets_file(
                        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
                    auth_url, _ = flow.authorization_url(prompt='consent')
                    
                    # ลิ้งก์ Google Logo แบบใหม่ (เสถียรกว่า)
                    login_html += f'<a href="{auth_url}" target="_self" class="google-btn">'
                    login_html += '<img src="https://fonts.gstatic.com/s/i/productlogos/googleg/v6/24px.svg" class="google-icon">'
                    login_html += 'Sign in with Google (@chinavut.com)</a>'
                else:
                     login_html += '<p style="color: red;">ไม่พบไฟล์ client_secret.json</p>'

            except Exception as e:
                login_html += f'<p style="color: red;">ตั้งค่า Google Auth ผิดพลาด: {e}</p>'
            
            login_html += "</div>" # ปิดกล่อง Login
            
            # Render HTML
            st.markdown(login_html, unsafe_allow_html=True)
            st.markdown("<br><br>", unsafe_allow_html=True)
        st.stop()

    # 5. ถ้า Login แล้ว -> ตรวจสอบอีเมล
    if st.session_state.credentials:
        try:
            service = build('oauth2', 'v2', credentials=st.session_state.credentials)
            user_info = service.userinfo().get().execute()
            email = user_info.get('email', '')
            
            # 🛡️ กฎเหล็ก: ต้องเป็น @chinavut.com เท่านั้น
            if not email.endswith('@chinavut.com'):
                st.warning(f"⚠️ อีเมล {email} ไม่ได้รับอนุญาต")
                st.error("🔒 ระบบอนุญาตเฉพาะอีเมล @chinavut.com เท่านั้นครับ")
                if st.button("🔙 กลับไปหน้า Login"):
                    st.session_state.credentials = None
                    st.rerun()
                st.stop()
            
            # ผ่านฉลุย! เก็บข้อมูลผู้ใช้
            st.session_state.user_email = email
            st.session_state.user_name = user_info.get('name', 'User')
            # ดึงรูปโปรไฟล์ (ถ้าไม่มีให้ใช้ Default)
            st.session_state.user_picture = user_info.get('picture', 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png')
            
        except Exception as e:
            st.error(f"Session หมดอายุหรือมีปัญหา กรุณา Login ใหม่ ({e})")
            st.session_state.credentials = None
            if st.button("Login Again"):
                 st.rerun()
            st.stop()

# --- เรียกใช้ฟังก์ชัน Login เป็นด่านแรก ---
check_login()

# ==========================================
# 3. ฟังก์ชัน Logic (PDF & Excel)
# ==========================================
def highlight_pdf(pdf_file, data_list):
    """ฟังก์ชันไฮไลท์ PDF และเขียนเลขข้อกำกับ"""
    pdf_file.seek(0)
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    found_count = 0
    
    for item in data_list:
        try:
            page_num = int(item.get("page", 0))
            text_to_find = item.get("text", item.get("evidence", ""))
            tor_label = str(item.get("tor_no", ""))
            
            if 0 <= page_num < len(doc):
                page = doc[page_num]
                text_instances = page.search_for(text_to_find)
                if not text_instances:
                    text_instances = page.search_for(text_to_find.strip())
                
                if text_instances:
                    for inst in text_instances:
                        annot = page.add_highlight_annot(inst)
                        annot.update()
                        pos_x = inst.x0 - 40 
                        pos_y = inst.y0 + 8
                        if pos_x < 5: pos_x = inst.x1 + 5
                        page.insert_text(fitz.Point(pos_x, pos_y), f"{tor_label}", fontsize=9, color=(1, 0, 0))
                    found_count += 1
        except Exception: 
            continue
            
    out_buffer = io.BytesIO()
    doc.save(out_buffer)
    out_buffer.seek(0)
    return out_buffer, found_count

# ==========================================
# 4. User Interface (ส่วนหน้าจอหลัก)
# ==========================================

# --- Sidebar ---
with st.sidebar:
    # ✅ 1. ใส่โลโก้บริษัท (ถ้ามีไฟล์ logo.png)
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.info("💡 เพิ่มไฟล์ logo.png เพื่อแสดงโลโก้ตรงนี้")
        
    st.markdown("---")

    # ✅ 2. แสดงรูปโปรไฟล์ Google
    if 'user_picture' in st.session_state:
        st.image(st.session_state.user_picture, width=70)
    
    st.markdown(f"### {st.session_state.user_name}")
    st.caption(f"📧 {st.session_state.user_email}")
    st.success("✅ Verified Account")
    
    st.markdown("<br>", unsafe_allow_html=True)
    # ปุ่ม Logout (ใช้ type=secondary และ CSS จะทำให้เป็นสีแดงเมื่อ hover)
    if st.button("🚪 Sign out (ออกจากระบบ)", type="secondary", use_container_width=True):
        st.session_state.credentials = None
        st.query_params.clear()
        st.rerun()

    st.markdown("---")
    st.link_button("🧠 เปิด Gemini (Start AI)", GEMINI_LINK, type="primary", use_container_width=True)
    
    st.info("""
    **วิธีใช้งาน:**
    1. กดปุ่มด้านบนเพื่อไปหน้า AI
    2. โยนไฟล์ PDF + TOR ให้ AI
    3. ก๊อปปี้ Code `[...]` กลับมาวาง
    4. กดปุ่มเริ่มประมวลผล
    """)
    st.caption("vFinal | Enterprise Edition")

# --- Hero Header ---
st.markdown("""
    <div class="hero-header">
        <div class="hero-title">📋 TOR Smart Auditor</div>
        <div class="hero-subtitle">ระบบตรวจสอบสเปกสินค้า ทำไฮไลท์ และสร้างรายงานอัตโนมัติ</div>
    </div>
""", unsafe_allow_html=True)

# --- Main Layout ---
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.markdown("### 1️⃣ เตรียมข้อมูล")
    # ใช้สไตล์ info box แทนปุ่ม เพื่อลดความซ้ำซ้อนกับ sidebar
    st.info("💡 **ยังไม่มีข้อมูล?** กดปุ่ม **'🧠 เปิด Gemini'** ที่เมนูด้านซ้ายเพื่อเริ่มวิเคราะห์")
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**วางโค้ดที่ได้จาก AI ลงในช่องนี้:**")
    raw_data = st.text_area(
        label="Input Data", height=300,
        placeholder="ตัวอย่าง:\nhighlight_data = [\n  {'page': 0, 'text': 'IP65', 'tor_no': '1.1', ...},\n  ...]",
        label_visibility="collapsed",
        help="ก๊อปปี้มาทั้งก้อนได้เลย ไม่ต้องลบ highlight_data ="
    )

with col2:
    st.markdown("### 2️⃣ ไฟล์ต้นฉบับ")
    st.markdown("อัปโหลดไฟล์ Catalog (.pdf) ที่ต้องการทำไฮไลท์")
    with st.container():
        st.markdown("<br>", unsafe_allow_html=True) 
        uploaded_file = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")
        if uploaded_file: 
            st.success(f"✅ ไฟล์พร้อมใช้งาน: {uploaded_file.name}")
        else:
            # แสดง placeholder ถ่ายังไม่อัปโหลด
            st.markdown("""
                <div style="border: 2px dashed #ddd; padding: 40px; text-align: center; border-radius: 10px; color: #888;">
                    📂 Drag and drop file here<br>Limit 200MB per file • PDF
                </div>
            """, unsafe_allow_html=True)


# --- Action Button ---
st.markdown("<hr>", unsafe_allow_html=True)
col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])

with col_btn2: 
    process_btn = st.button("✨ เริ่มประมวลผล (Generate Report) ✨", type="primary", use_container_width=True)

# --- Processing Logic ---
if process_btn:
    if not raw_data or not uploaded_file:
        st.warning("⚠️ กรุณาวางโค้ดข้อมูล และ อัปโหลดไฟล์ PDF ให้ครบถ้วนก่อนเริ่มครับ")
    else:
        with st.spinner("🔄 กำลังทำงาน... ระบบกำลังอ่าน PDF และสร้างรายงาน..."):
            try:
                # 1. Cleaning Data
                clean_data = raw_data.strip()
                if "=" in clean_data: clean_data = clean_data.split("=", 1)[1].strip()
                data_list = ast.literal_eval(clean_data)
                
                if isinstance(data_list, list) and len(data_list) > 0:
                    
                    # 2. Excel Generation (พร้อมแก้เลขหน้า +1)
                    df = pd.DataFrame(data_list)
                    if 'page' in df.columns:
                        df['page'] = pd.to_numeric(df['page'], errors='coerce').fillna(0).astype(int) + 1
                    
                    rename_map = {
                        "tor_no": "ข้อที่ (TOR)", "desc": "รายละเอียด TOR", 
                        "text": "ข้อความใน Catalog ที่ต้องไฮไลท์ (Evidence)", 
                        "evidence": "ข้อความใน Catalog ที่ต้องไฮไลท์ (Evidence)", 
                        "page": "หน้า (Page)", "status": "สถานะ / คำแนะนำ"
                    }
                    df.rename(columns=rename_map, inplace=True)
                    
                    desired_cols = ["ข้อที่ (TOR)", "รายละเอียด TOR", "ข้อความใน Catalog ที่ต้องไฮไลท์ (Evidence)", "หน้า (Page)", "สถานะ / คำแนะนำ"]
                    final_cols = [c for c in desired_cols if c in df.columns]
                    df_final = df[final_cols]
                    
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer: 
                        df_final.to_excel(writer, index=False)
                    
                    # 3. PDF Highlight (ใช้ data_list เดิมที่เป็น 0-based)
                    pdf_buffer, count = highlight_pdf(uploaded_file, data_list)
                    
                    # 4. Result UI
                    st.balloons()
                    st.markdown(f'<div class="success-box"><h3>🎉 เสร็จเรียบร้อย! ({count} จุด)</h3></div>', unsafe_allow_html=True)
                    
                    st.markdown("### 📥 ดาวน์โหลดเอกสาร")
                    d_c1, d_c2 = st.columns(2)
                    with d_c1: 
                        st.download_button("📊 ดาวน์โหลด Excel Report", excel_buffer.getvalue(), "Compliance_Report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                    with d_c2: 
                        st.download_button("📕 ดาวน์โหลด PDF Highlighted", pdf_buffer, "Catalog_Checked.pdf", "application/pdf", use_container_width=True)
                    
                    with st.expander("👀 ดูตัวอย่างข้อมูลใน Excel"): 
                        st.dataframe(df_final, use_container_width=True)
                else: 
                    st.error("❌ รูปแบบข้อมูลไม่ถูกต้อง: ต้องเป็น List [...] เท่านั้น (ลองตรวจสอบโค้ดที่ได้จาก Gemini อีกครั้ง)")
            except Exception as e: 
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")
                st.markdown("💡 **คำแนะนำ:** ลองตรวจสอบว่าก๊อปปี้โค้ดมาครบถ้วนหรือไม่ หรือไฟล์ PDF เสียหายหรือไม่")