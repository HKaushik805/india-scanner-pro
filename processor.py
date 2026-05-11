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

def apply_studio_white_balance(img):
    result = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    avg_a = np.average(result[:, :, 1])
    avg_b = np.average(result[:, :, 2])
    l_chan = result[:, :, 0] / 255.0
    # Targeted neutralization: force background highlights to 0 saturation
    result[:, :, 1] = result[:, :, 1] - ((avg_a - 128) * l_chan * 1.5)
    result[:, :, 2] = result[:, :, 2] - ((avg_b - 128) * l_chan * 1.5)
    return cv2.cvtColor(result, cv2.COLOR_LAB2BGR)

def magic_color_engine(img, color_boost, is_pdf):
    # 1. White Balance
    img = apply_studio_white_balance(img)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    # 2. Local Contrast Boost (To find text in the 'mush')
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    l = clahe.apply(l)

    # 3. Division Normalization (Shadow Removal)
    k_size = 71 if is_pdf else 151
    dilated = cv2.dilate(l, np.ones((k_size, k_size), np.uint8))
    bg = cv2.medianBlur(dilated, 51 if not is_pdf else 21)
    l_norm = cv2.divide(l, bg, scale=255)
    
    # 4. AGGRESSIVE BLEACH LOGIC (The fix for Gray Background)
    # xp = Input Brightness, fp = Output Brightness
    # We force everything above 145 (light gray) to 255 (Pure White)
    xp = [0, 30, 80, 145, 255]
    fp = [0, 20, 70, 255, 255] 
    table = np.interp(np.arange(256), xp, fp).astype('uint8')
    l_final = cv2.LUT(l_norm, table)

    # 5. Background Color Nuke
    # Ensures no yellow/blue dots remain in the white areas
    background_mask = (l_final >= 245).astype(float)
    a_neutral = (a.astype(float) * (1 - background_mask) + 128 * background_mask).astype(np.uint8)
    b_neutral = (b.astype(float) * (1 - background_mask) + 128 * background_mask).astype(np.uint8)
    
    # Selective Color Boost
    color_mask = cv2.threshold(l_final, 240, 255, cv2.THRESH_BINARY_INV)[1] / 255.0
    a_f, b_f = a_neutral.astype(float), b_neutral.astype(float)
    a_res = (128 + (a_f - 128) * (1 + (color_boost - 1) * color_mask)).clip(0, 255).astype(np.uint8)
    b_res = (128 + (b_f - 128) * (1 + (color_boost - 1) * color_mask)).clip(0, 255).astype(np.uint8)

    merged = cv2.merge((l_final, a_res, b_res))
    result = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
    
    # 6. Sharpness without grainy noise
    sharp_kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]]) * 0.05
    sharp_kernel[1,1] += 1
    final = cv2.filter2D(result, -1, sharp_kernel)
    
    # Force pure white 6-pixel border to hide photo edges
    cv2.rectangle(final, (0,0), (final.shape[1], final.shape[0]), (255,255,255), 10)
    
    return final

def scan_image(image, color_boost, do_warp, margins, mode, is_pdf=False):
    img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    h_o, w_o = img.shape[:2]
    target = 2200
    if not is_pdf and max(h_o, w_o) > target:
        scale = target / max(h_o, w_o)
        img = cv2.resize(img, (int(w_o * scale), int(h_o * scale)), interpolation=cv2.INTER_AREA)

    h, w = img.shape[:2]
    img = img[int(h*margins[0]/100):int(h*(1-margins[1]/100)), int(w*margins[2]/100):int(w*(1-margins[3]/100))]
    orig = img.copy()
    
    if do_warp and not is_pdf:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
        gradient = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)
        _, thresh = cv2.threshold(gradient, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:5]
        for c in cnts:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4 and cv2.contourArea(c) > (h * w * 0.1):
                try:
                    rect = order_points(approx.reshape(4, 2))
                    w_w = int(max(np.linalg.norm(rect[2]-rect[3]), np.linalg.norm(rect[1]-rect[0])))
                    h_w = int(max(np.linalg.norm(rect[1]-rect[2]), np.linalg.norm(rect[0]-rect[3])))
                    M = cv2.getPerspectiveTransform(rect, np.array([[0,0], [w_w-1,0], [w_w-1,h_w-1], [0,h_w-1]], dtype="float32"))
                    img = cv2.warpPerspective(orig, M, (w_w, h_w))
                except: pass
                break

    if mode == "Magic Color (Pro)":
        res = magic_color_engine(img, color_boost, is_pdf)
        return cv2.cvtColor(res, cv2.COLOR_BGR2RGB)
    elif mode == "B&W Pro":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        bg = cv2.medianBlur(cv2.dilate(gray, np.ones((15,15), np.uint8)), 25)
        norm = cv2.divide(gray, bg, scale=255)
        # Bolder B&W Logic to survive high bleaching
        res = cv2.adaptiveThreshold(norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
        return cv2.erode(res, np.ones((2,2), np.uint8), iterations=1)

    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)