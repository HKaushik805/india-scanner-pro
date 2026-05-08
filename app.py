import streamlit as st
from PIL import Image
from processor import scan_image
import cv2, numpy as np, os, uuid, fitz, gc
from fpdf import FPDF

# --- ENTERPRISE CONFIG ---
SHOP_NAME = "Hisar Photostat"
LICENSE_KEY = "HP-ENTERPRISE-PRO-SCAN-2026" 

# CLOUD-SAFE TEMP DIRECTORY
# We use /tmp/ for Linux-based Streamlit Cloud servers
TEMP_DIR = "/tmp/scanner_pages"
if not os.path.exists(TEMP_DIR):
    try:
        os.makedirs(TEMP_DIR)
    except:
        TEMP_DIR = "temp_processing" # Fallback for local Windows
        if not os.path.exists(TEMP_DIR): os.makedirs(TEMP_DIR)

# 1. SET PAGE CONFIG
st.set_page_config(
    page_title=f"{SHOP_NAME} Enterprise Scanner", 
    layout="wide", 
    page_icon="🛡️",
    initial_sidebar_state="expanded"
)

# 2. THE "SAFE" WHITELABEL CSS
st.markdown("""
    <style>
    .stDeployButton {display:none !important;}
    footer {visibility: hidden !important;}
    #MainMenu {visibility: hidden !important;}
    [data-testid="collapsedControl"] {
        visibility: visible !important;
        background-color: #1a73e8 !important;
        color: white !important;
        border-radius: 5px !important;
    }
    .main { background-color: #f8f9fa; }
    .stButton>button { 
        width: 100%; 
        background-color: #1a73e8; 
        color: white; 
        height: 3.5em; 
        border-radius: 10px; 
        font-weight: bold; 
        border: none;
    }
    </style>
    """, unsafe_allow_html=True)

# --- AUTHENTICATION ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🛡️ Enterprise Login")
        st.write(f"Authorized access for {SHOP_NAME} only.")
        input_key = st.text_input("Enter License Key", type="password")
        if st.button("Activate License"):
            if input_key == LICENSE_KEY:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ Invalid Key")
    st.stop()

# --- MAIN APP ---
st.title(f"📄 {SHOP_NAME} Pro Workstation")

# Sidebar
st.sidebar.success("✅ License Active")
scan_mode = st.sidebar.selectbox("Filter Type", ["Magic Color (Pro)", "B&W Pro", "Original"])
ink_power = st.sidebar.slider("Ink Boldness", 1.0, 2.5, 1.2)
do_warp = st.sidebar.checkbox("Auto-Crop Photos", value=True)

with st.sidebar.expander("✂️ Manual Crop"):
    top_m = st.slider("Top %", 0, 50, 0)
    bottom_m = st.slider("Bottom %", 0, 50, 0)
    left_m = st.slider("Left %", 0, 50, 0)
    right_m = st.slider("Right %", 0, 50, 0)

st.sidebar.markdown("---")
file_name = st.sidebar.text_input("Export PDF Name", value="Customer_Scan")

if st.sidebar.button("🗑️ Clear All"):
    for f in os.listdir(TEMP_DIR):
        try: os.remove(os.path.join(TEMP_DIR, f))
        except: pass
    st.rerun()

# Processing
uploaded_files = st.file_uploader("Upload Photos or PDF", type=["jpg", "png", "jpeg", "pdf"], accept_multiple_files=True)

saved_paths = []
if uploaded_files:
    idx = 0
    cols = st.columns(4)
    for u_file in uploaded_files:
        if u_file.name.lower().endswith('.pdf'):
            try:
                doc = fitz.open(stream=u_file.read(), filetype="pdf")
                for p_n in range(len(doc)):
                    pix = doc.load_page(p_n).get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                    img_p = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    res = scan_image(img_p, ink_power, False, [top_m, bottom_m, left_m, right_m], scan_mode, True)
                    p_path = os.path.join(TEMP_DIR, f"p_{uuid.uuid4()}.jpg")
                    cv2.imwrite(p_path, cv2.cvtColor(res, cv2.COLOR_RGB2BGR) if len(res.shape)==3 else res, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    saved_paths.append(p_path)
                    with cols[idx%4]: st.image(res, use_container_width=True)
                    idx += 1; gc.collect()
            except Exception as e:
                st.error(f"Error reading PDF: {e}")
        else:
            res = scan_image(Image.open(u_file), ink_power, do_warp, [top_m, bottom_m, left_m, right_m], scan_mode, False)
            p_path = os.path.join(TEMP_DIR, f"p_{uuid.uuid4()}.jpg")
            cv2.imwrite(p_path, cv2.cvtColor(res, cv2.COLOR_RGB2BGR) if len(res.shape)==3 else res, [cv2.IMWRITE_JPEG_QUALITY, 95])
            saved_paths.append(p_path)
            with cols[idx%4]: st.image(res, use_container_width=True)
            idx += 1; gc.collect()

    if st.sidebar.button("🚀 GENERATE PDF"):
        if saved_paths:
            pdf = FPDF()
            for p in saved_paths:
                pdf.add_page(); pdf.image(p, 0, 0, 210, 297)
            st.sidebar.download_button("🔥 DOWNLOAD PDF", data=pdf.output(dest='S').encode('latin-1'), file_name=f"{file_name}.pdf", mime="application/pdf")

st.markdown("---")
st.caption(f"🛡️ {SHOP_NAME} Enterprise Suite | Developed by Himanshu AI Solutions")