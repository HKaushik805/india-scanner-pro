import streamlit as st
from PIL import Image
from processor import scan_image
import cv2
import numpy as np
from fpdf import FPDF
import os
import uuid
import fitz
import gc

# --- SETUP ---
SHOP_NAME = "Hisar Photostat" # Branded for your local market
TEMP_DIR = "temp_processing"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

st.set_page_config(page_title=f"{SHOP_NAME} - Scanner Pro", layout="wide", page_icon="📄")

# UI Style
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; background-color: #28a745; color: white; height: 3.5em; border-radius: 10px; font-weight: bold;}
    .download-btn { background-color: #ff4b4b !important; }
    </style>
    """, unsafe_allow_html=True)

st.title(f"📄 {SHOP_NAME} Pro Workstation")
st.write("Advanced Noise Reduction Engine | Optimized for Newspaper & Low-Quality Prints")

# --- SIDEBAR ---
st.sidebar.header("🛠️ Global Controls")
scan_mode = st.sidebar.selectbox("Filter Type", ["Magic Color (Pro)", "B&W Pro", "Original"])
color_vibrancy = st.sidebar.slider("Ink Boldness (Magic Color)", 1.0, 2.5, 1.4)
do_warp = st.sidebar.checkbox("Auto-Crop (Photos only)", value=True)

with st.sidebar.expander("✂️ Manual Crop (Adjust Margins)"):
    top_m = st.slider("Top %", 0, 50, 0)
    bottom_m = st.slider("Bottom %", 0, 50, 0)
    left_m = st.slider("Left %", 0, 50, 0)
    right_m = st.slider("Right %", 0, 50, 0)

st.sidebar.markdown("---")
file_name = st.sidebar.text_input("Export PDF Name", value="Customer_Document")

if st.sidebar.button("🗑️ Reset All Pages"):
    for f in os.listdir(TEMP_DIR):
        try: os.remove(os.path.join(TEMP_DIR, f))
        except: pass
    st.rerun()

# --- MAIN ENGINE ---
uploaded_files = st.file_uploader(
    "Upload Photos or PDF", 
    type=["jpg", "png", "jpeg", "pdf"], 
    accept_multiple_files=True
)

saved_image_paths = []

if uploaded_files:
    current_page_idx = 0
    thumb_cols = st.columns(5)
    
    for uploaded_file in uploaded_files:
        is_pdf_file = uploaded_file.name.lower().endswith('.pdf')
        
        if is_pdf_file:
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            for p_num in range(len(doc)):
                with st.spinner(f"Rendering PDF Page {p_num + 1}..."):
                    page = doc.load_page(p_num)
                    pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
                    img_pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    result = scan_image(img_pil, color_vibrancy, False, [top_m, bottom_m, left_m, right_m], scan_mode, is_pdf=True)
                    
                    page_path = os.path.join(TEMP_DIR, f"img_{uuid.uuid4()}.jpg")
                    save_bgr = cv2.cvtColor(result, cv2.COLOR_RGB2BGR) if len(result.shape)==3 else result
                    cv2.imwrite(page_path, save_bgr, [cv2.IMWRITE_JPEG_QUALITY, 98])
                    saved_image_paths.append(page_path)
                    with thumb_cols[current_page_idx % 5]:
                        st.image(result, caption=f"P.{current_page_idx+1}", use_container_width=True)
                    current_page_idx += 1
                    del result
                    gc.collect()
        else:
            with st.spinner(f"Enhancing Image..."):
                img_pil = Image.open(uploaded_file)
                result = scan_image(img_pil, color_vibrancy, do_warp, [top_m, bottom_m, left_m, right_m], scan_mode, is_pdf=False)
                
                page_path = os.path.join(TEMP_DIR, f"img_{uuid.uuid4()}.jpg")
                save_bgr = cv2.cvtColor(result, cv2.COLOR_RGB2BGR) if len(result.shape)==3 else result
                cv2.imwrite(page_path, save_bgr, [cv2.IMWRITE_JPEG_QUALITY, 98])
                saved_image_paths.append(page_path)
                with thumb_cols[current_page_idx % 5]:
                    st.image(result, caption=f"P.{current_page_idx+1}", use_container_width=True)
                current_page_idx += 1
                del result
                gc.collect()

    st.sidebar.markdown("---")
    if st.sidebar.button("🚀 STEP 1: COMPILE PDF"):
        if saved_image_paths:
            with st.spinner("Building High-Res Document..."):
                pdf = FPDF()
                for path in saved_image_paths:
                    pdf.add_page()
                    pdf.image(path, 0, 0, 210, 297)
                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                st.sidebar.success("✅ Document Built!")
                st.sidebar.download_button(label="🔥 STEP 2: DOWNLOAD TO PRINT", data=pdf_bytes, file_name=f"{file_name}.pdf", mime="application/pdf")
else:
    st.info("👋 Upload a digital PDF or an image screenshot to clean it for printing.")

st.markdown("---")
st.caption(f"Developed by Himanshu AI | {SHOP_NAME} Professional Edition")