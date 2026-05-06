import cv2
import numpy as np

def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def apply_white_balance(img):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    avg_a = np.average(lab[:, :, 1])
    avg_b = np.average(lab[:, :, 2])
    lab[:, :, 1] = lab[:, :, 1] - ((avg_a - 128) * (lab[:, :, 0] / 255.0) * 1.1)
    lab[:, :, 2] = lab[:, :, 2] - ((avg_b - 128) * (lab[:, :, 0] / 255.0) * 1.1)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

def scan_image(image, color_boost, do_warp, margins, mode, is_pdf=False):
    # Convert PIL to OpenCV BGR
    img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    
    # Normalization
    if not is_pdf:
        h_orig, w_orig = img.shape[:2]
        if max(h_orig, w_orig) > 3000:
            scale = 3000 / max(h_orig, w_orig)
            img = cv2.resize(img, (int(w_orig * scale), int(h_orig * scale)), interpolation=cv2.INTER_LANCZOS4)

    img = apply_white_balance(img)
    
    # Manual Crop
    h, w = img.shape[:2]
    t, b, l, r = margins
    img = img[int(h*t/100):int(h*(1-b/100)), int(w*l/100):int(w*(1-r/100))]
    orig_working = img.copy()
    
    # Auto-Warp
    if do_warp and not is_pdf:
        gray_w = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edged = cv2.Canny(cv2.GaussianBlur(gray_w, (5, 5), 0), 50, 150)
        cnts, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:5]
        for c in cnts:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4 and cv2.contourArea(c) > (h * w * 0.15):
                try:
                    rect = order_points(approx.reshape(4, 2))
                    width_w = int(max(np.linalg.norm(rect[2]-rect[3]), np.linalg.norm(rect[1]-rect[0])))
                    height_w = int(max(np.linalg.norm(rect[1]-rect[2]), np.linalg.norm(rect[0]-rect[3])))
                    dst = np.array([[0,0], [width_w-1,0], [width_w-1,height_w-1], [0,height_w-1]], dtype="float32")
                    M = cv2.getPerspectiveTransform(rect, dst)
                    img = cv2.warpPerspective(orig_working, M, (width_w, height_w))
                except: pass
                break

    # --- FILTER ENGINES ---
    if mode == "Magic Color (Pro)":
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_c, a_c, b_c = cv2.split(lab)
        # Background Cleaning
        dilated = cv2.dilate(l_c, np.ones((15, 15), np.uint8))
        bg = cv2.medianBlur(dilated, 21)
        l_norm = cv2.normalize(255 - cv2.absdiff(l_c, bg), None, 0, 255, cv2.NORM_MINMAX)
        # Ink Recovery
        ink_mask = cv2.threshold(l_c, 145, 255, cv2.THRESH_BINARY_INV)[1]
        ink_mask = cv2.morphologyEx(ink_mask, cv2.MORPH_CLOSE, np.ones((2,2), np.uint8)) / 255.0
        a_c = (a_c.astype(float) + (a_c.astype(float)-128) * (color_boost-1) * ink_mask).clip(0,255).astype(np.uint8)
        b_c = (b_c.astype(float) + (b_c.astype(float)-128) * (color_boost-1) * ink_mask).clip(0,255).astype(np.uint8)
        img = cv2.cvtColor(cv2.merge((l_norm, a_c, b_c)), cv2.COLOR_LAB2BGR)
        img = cv2.addWeighted(img, 1.4, cv2.GaussianBlur(img, (0,0), 2), -0.4, 0)
        
    elif mode == "B&W Pro":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        if is_pdf:
            img = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 15)
        else:
            # --- THE NEWSPAPER FIX: De-speckle Logic ---
            # 1. Background Normalization
            dilated = cv2.dilate(gray, np.ones((15, 15), np.uint8))
            bg = cv2.medianBlur(dilated, 25)
            norm = cv2.normalize(255 - cv2.absdiff(gray, bg), None, 0, 255, cv2.NORM_MINMAX)
            
            # 2. Thresholding
            thresh = cv2.adaptiveThreshold(norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10)
            
            # 3. Morphological Opening (The "Dot Eater")
            # This deletes anything smaller than 2x2 pixels (the black dots)
            kernel = np.ones((2, 2), np.uint8)
            img = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
            
            # 4. Final Polish
            img = cv2.GaussianBlur(img, (1, 1), 0)

    if len(img.shape) == 2: return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)