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
    brightness_weight = (result[:, :, 0] / 255.0)
    result[:, :, 1] = result[:, :, 1] - ((avg_a - 128) * brightness_weight)
    result[:, :, 2] = result[:, :, 2] - ((avg_b - 128) * brightness_weight)
    return cv2.cvtColor(result, cv2.COLOR_LAB2BGR)

def magic_color_engine(img, color_boost):
    img = apply_studio_white_balance(img)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    kernel_size = 121 
    dilated = cv2.dilate(l, np.ones((kernel_size, kernel_size), np.uint8))
    bg = cv2.medianBlur(dilated, kernel_size)
    l_norm = cv2.divide(l, bg, scale=255)
    xp = [0, 50, 150, 225, 255]
    fp = [0, 40, 155, 255, 255] 
    table = np.interp(np.arange(256), xp, fp).astype('uint8')
    l_final = cv2.LUT(l_norm, table)
    color_mask = cv2.threshold(l_final, 250, 255, cv2.THRESH_BINARY_INV)[1] / 255.0
    background_mask = (l_final >= 250).astype(float)
    a_neutral = (a.astype(float) * (1 - background_mask) + 128 * background_mask).astype(np.uint8)
    b_neutral = (b.astype(float) * (1 - background_mask) + 128 * background_mask).astype(np.uint8)
    a_float, b_float = a_neutral.astype(float), b_neutral.astype(float)
    a_res = (128 + (a_float - 128) * (1 + (color_boost - 1) * color_mask)).clip(0, 255).astype(np.uint8)
    b_res = (128 + (b_float - 128) * (1 + (color_boost - 1) * color_mask)).clip(0, 255).astype(np.uint8)
    merged = cv2.merge((l_final, a_res, b_res))
    result = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
    sharp_kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]]) * 0.05
    sharp_kernel[1,1] += 1
    return cv2.filter2D(result, -1, sharp_kernel)

def scan_image(image, color_boost, do_warp, margins, mode, is_pdf=False):
    img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    h_orig, w_orig = img.shape[:2]
    if not is_pdf and max(h_orig, w_orig) > 2200:
        scale = 2200 / max(h_orig, w_orig)
        img = cv2.resize(img, (int(w_orig * scale), int(h_orig * scale)), interpolation=cv2.INTER_AREA)
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
            if len(approx) == 4 and cv2.contourArea(c) > (h * w * 0.05):
                try:
                    rect = order_points(approx.reshape(4, 2))
                    w_w = int(max(np.linalg.norm(rect[2]-rect[3]), np.linalg.norm(rect[1]-rect[0])))
                    h_w = int(max(np.linalg.norm(rect[1]-rect[2]), np.linalg.norm(rect[0]-rect[3])))
                    M = cv2.getPerspectiveTransform(rect, np.array([[0,0], [w_w-1,0], [w_w-1,h_w-1], [0,h_w-1]], dtype="float32"))
                    img = cv2.warpPerspective(orig, M, (w_w, h_w))
                except: pass
                break
    if mode == "Magic Color (Pro)":
        return cv2.cvtColor(magic_color_engine(img, color_boost), cv2.COLOR_BGR2RGB)
    elif mode == "B&W Pro":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        bg = cv2.medianBlur(cv2.dilate(gray, np.ones((11,11), np.uint8)), 21)
        norm = cv2.divide(gray, bg, scale=255)
        blurred = cv2.GaussianBlur(norm, (0, 0), 2)
        norm = cv2.addWeighted(norm, 1.8, blurred, -0.8, 0)
        res = cv2.adaptiveThreshold(norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 20)
        return cv2.morphologyEx(res, cv2.MORPH_OPEN, np.ones((2,2), np.uint8))
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)