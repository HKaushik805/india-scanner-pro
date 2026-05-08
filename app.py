import streamlit as st
import os

# --- EMERGENCY DIAGNOSTIC ---
try:
    from PIL import Image
    import cv2
    import numpy as np
    from fpdf import FPDF
    import uuid
    import fitz
    import gc
    from processor import scan_image
except Exception as e:
    st.error(f"❌ BOOT ERROR: {e}")
    st.info("Check if requirements.txt contains: streamlit, opencv-python-headless, numpy, Pillow, fpdf, pymupdf")
    st.stop()

# --- CONFIG ---
SHOP_NAME = "Hisar Photostat"
LICENSE_KEY = "HP-ENTERPRISE-PRO-SCAN-2026" 
TEMP_DIR = "/tmp/scanner_pages"
if not os.path.exists(TEMP_DIR):
    try: os.makedirs(TEMP_DIR)
    except: TEMP_DIR = "temp_processing"; os.makedirs(TEMP_DIR, exist_ok=True)

st.set_page_config(page_title=f"{SHOP_NAME} Enterprise", layout="wide", page_icon="🛡️")

# --- CSS ---
st.markdown("""<style>.stDeployButton {display:none !important;} footer {visibility: hidden !important;} #MainMenu {visibility: hidden !important;}</style>""", unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# --- LOGIN ---
if not st.session_state["authenticated"]:
    st.title("🛡️ Enterprise Login")
    input_key = st.text_input("Enter License Key", type="password")
    if st.button("Activate"):
        if input_key == LICENSE_KEY:
            st.session_state["authenticated"] = True
            st.rerun()
        else: st.error("Invalid Key")
    st.stop()

# --- MAIN APP ---
st.title(f"📄 {SHOP_NAME} Pro Workstation")
scan_mode = st.sidebar.selectbox("Filter", ["Magic Color (Pro)", "B&W Pro", "Original"])
ink_power = st.sidebar.slider("Ink Boldness", 1.0, 2.5, 1.25)
do_warp = st.sidebar.checkbox("Auto-Crop", value=True)

uploaded_files = st.file_uploader("Upload Files", type=["jpg", "png", "jpeg", "pdf"], accept_multiple_files=True)

saved_paths = []
if uploaded_files:
    idx = 0
    cols = st.columns(4)
    for u_file in uploaded_files:
        try:
            if u_file.name.lower().endswith('.pdf'):
                doc = fitz.open(stream=u_file.read(), filetype="pdf")
                for p_n in range(len(doc)):
                    pix = doc.load_page(p_n).get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                    img_p = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    res = scan_image(img_p, ink_power, False, [0,0,0,0], scan_mode, True)
                    p_path = os.path.join(TEMP_DIR, f"e_{uuid.uuid4()}.jpg")
                    cv2.imwrite(p_path, cv2.cvtColor(res, cv2.COLOR_RGB2BGR) if len(res.shape)==3 else res)
                    saved_paths.append(p_path); with cols[idx%4]: st.image(res, use_container_width=True)
                    idx += 1
            else:
                res = scan_image(Image.open(u_file), ink_power, do_warp, [0,0,0,0], scan_mode, False)
                p_path = os.path.join(TEMP_DIR, f"e_{uuid.uuid4()}.jpg")
                cv2.imwrite(p_path, cv2.cvtColor(res, cv2.COLOR_RGB2BGR) if len(res.shape)==3 else res)
                saved_paths.append(p_path); with cols[idx%4]: st.image(res, use_container_width=True)
                idx += 1
        except Exception as e:
            st.error(f"Processing error: {e}")

    if st.sidebar.button("🚀 BUILD PDF"):
        if saved_paths:
            pdf = FPDF()
            for p in saved_paths:
                pdf.add_page(); pdf.image(p, 0, 0, 210, 297)
            st.sidebar.download_button("📥 DOWNLOAD PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="scan.pdf")