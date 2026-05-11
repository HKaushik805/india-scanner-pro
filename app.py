import streamlit as st
from PIL import Image
from processor import scan_image
import cv2, numpy as np, os, uuid, fitz, gc
from fpdf import FPDF

# --- CONFIG ---
SHOP_NAME = "Hisar Photostat"
LICENSE_KEY = "HP-ENTERPRISE-PRO-SCAN-2026" 
TEMP_DIR = "/tmp/scanner_pages"
if not os.path.exists(TEMP_DIR):
    try:
        os.makedirs(TEMP_DIR)
    except:
        TEMP_DIR = "temp_processing"
        os.makedirs(TEMP_DIR, exist_ok=True)

st.set_page_config(page_title=f"{SHOP_NAME} Enterprise", layout="wide", page_icon="🛡️")

# --- UI STYLING ---
st.markdown("""
<style>
    .stDeployButton {display:none !important;} 
    footer {visibility: hidden !important;} 
    #MainMenu {visibility: hidden !important;} 
    [data-testid="collapsedControl"] {visibility: visible !important; background-color: #1a73e8 !important; color: white !important; border-radius: 5px !important;} 
    .stButton>button { width: 100%; background-color: #1a73e8; color: white; height: 3.5em; border-radius: 10px; font-weight: bold; border: none;}
</style>
""", unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# --- LOGIN SCREEN ---
if not st.session_state["authenticated"]:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🛡️ Enterprise Login")
        input_key = st.text_input("Enter License Key", type="password")
        if st.button("Activate"):
            if input_key == LICENSE_KEY:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ Invalid Key")
    st.stop()

# --- MAIN APP ---
st.title(f"📄 {SHOP_NAME} Pro Workstation")

# Definition to prevent NameError
export_name = "Final_Scan"

st.sidebar.header("🛠️ Controls")
scan_mode = st.sidebar.selectbox("Filter", ["Magic Color (Pro)", "B&W Pro", "Original"])
ink_power = st.sidebar.slider("Ink Boldness", 1.0, 2.5, 1.3)
do_warp = st.sidebar.checkbox("Auto-Crop Photos", value=True)

with st.sidebar.expander("✂️ Manual Crop"):
    t_m = st.slider("Top %", 0, 50, 0)
    b_m = st.slider("Bottom %", 0, 50, 0)
    l_m = st.slider("Left %", 0, 50, 0)
    r_m = st.slider("Right %", 0, 50, 0)

st.sidebar.markdown("---")
export_name = st.sidebar.text_input("Filename (Without .pdf)", value="Customer_Scan")

if st.sidebar.button("🗑️ Clear All Pages"):
    for f in os.listdir(TEMP_DIR):
        try:
            os.remove(os.path.join(TEMP_DIR, f))
        except:
            pass
    st.rerun()

uploaded_files = st.file_uploader("Upload Photos or PDF", type=["jpg", "png", "jpeg", "pdf"], accept_multiple_files=True)

saved_paths = []
if uploaded_files:
    idx = 0
    cols = st.columns(4)
    for u_file in uploaded_files:
        is_pdf = u_file.name.lower().endswith('.pdf')
        if is_pdf:
            doc = fitz.open(stream=u_file.read(), filetype="pdf")
            for p_n in range(len(doc)):
                with st.spinner(f"Processing PDF P.{p_n+1}"):
                    pix = doc.load_page(p_n).get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                    img_p = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    res = scan_image(img_p, ink_power, False, [t_m, b_m, l_m, r_m], scan_mode, True)
                    
                    p_path = os.path.join(TEMP_DIR, f"p_{uuid.uuid4()}.jpg")
                    save_bgr = cv2.cvtColor(res, cv2.COLOR_RGB2BGR) if len(res.shape) == 3 else res
                    cv2.imwrite(p_path, save_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    saved_paths.append(p_path)
                    
                    with cols[idx % 4]:
                        st.image(res, use_container_width=True)
                    idx += 1
                    gc.collect()
        else:
            with st.spinner("Processing Photo..."):
                img_input = Image.open(u_file)
                res = scan_image(img_input, ink_power, do_warp, [t_m, b_m, l_m, r_m], scan_mode, False)
                
                p_path = os.path.join(TEMP_DIR, f"p_{uuid.uuid4()}.jpg")
                save_bgr = cv2.cvtColor(res, cv2.COLOR_RGB2BGR) if len(res.shape) == 3 else res
                cv2.imwrite(p_path, save_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
                saved_paths.append(p_path)
                
                with cols[idx % 4]:
                    st.image(res, use_container_width=True)
                idx += 1
                gc.collect()

    if st.sidebar.button("🚀 BUILD FINAL PDF"):
        if saved_paths:
            with st.spinner("Finalizing..."):
                pdf = FPDF()
                for p in saved_paths:
                    pdf.add_page()
                    pdf.image(p, 0, 0, 210, 297)
                
                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                st.sidebar.download_button(
                    label="🔥 DOWNLOAD PRINT-PDF", 
                    data=pdf_bytes, 
                    file_name=f"{export_name}.pdf", 
                    mime="application/pdf"
                )