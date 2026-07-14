import numpy as np
from PIL import Image, ImageFilter
from typing import Optional, Tuple


def find_page_spine(img: Image.Image) -> int:
    """Find the x-coordinate of the book gutter/spine on a double-page spread,
    by locating the darkest column in the middle 40-60% width band."""
    w, h = img.size
    gray = img.convert('L')
    arr = np.array(gray)
    start_x, end_x = int(0.4 * w), int(0.6 * w)
    return start_x + int(np.argmin(arr[:, start_x:end_x].mean(axis=0)))


def split_page_halves(img: Image.Image, overlap: int = 15) -> Tuple[Image.Image, Optional[Image.Image]]:
    """Split a double-page spread image into left/right halves at the detected spine.

    Returns (left_img, right_img). If the image isn't a double-page spread
    (width <= height), returns (img, None) and the caller should treat it as
    a single "full" page.
    """
    w, h = img.size
    if w <= h:
        return img, None
    spine_x = find_page_spine(img)
    left_img = img.crop((0, 0, min(w, spine_x + overlap), h))
    right_img = img.crop((max(0, spine_x - overlap), 0, w, h))
    return left_img, right_img


def find_footnote_split_y(img: Image.Image) -> int:
    """Find the horizontal y-coordinate splitting main text from footnotes."""
    w, h = img.size
    gray = img.convert('L')
    arr = np.array(gray, dtype=np.float32)
    mean_img = gray.filter(ImageFilter.BoxBlur(15))
    mean_arr = np.array(mean_img, dtype=np.float32)
    binary_arr = np.where(arr > (mean_arr - 15), 255, 0).astype(np.uint8)

    start_y = int(0.72 * h)
    end_y = int(0.92 * h)

    line_y = None
    min_mean = 255
    for y in range(start_y, end_y):
        row = binary_arr[y, int(0.2 * w):int(0.8 * w)]
        m = row.mean()
        if m < 180 and m < min_mean:
            above = binary_arr[max(0, y - 10):y, int(0.2 * w):int(0.8 * w)].mean()
            below = binary_arr[y + 1:min(h, y + 11), int(0.2 * w):int(0.8 * w)].mean()
            if m < above - 40 and m < below - 40:
                min_mean = m
                line_y = y
    if line_y is not None:
        return line_y

    bright_rows = []
    for y in range(start_y, end_y):
        row = binary_arr[y, int(0.2 * w):int(0.8 * w)]
        if row.min() == 255:
            bright_rows.append(y)
    if bright_rows:
        runs = []
        current_run = [bright_rows[0]]
        for y_val in bright_rows[1:]:
            if y_val == current_run[-1] + 1:
                current_run.append(y_val)
            else:
                runs.append(current_run)
                current_run = [y_val]
        runs.append(current_run)
        longest_run = max(runs, key=len)
        if len(longest_run) > 10:
            return longest_run[len(longest_run) // 2]
    return int(0.85 * h)


def find_footnote_column_split_x(img: Image.Image) -> int:
    """Find the vertical gutter splitting the two footnote columns."""
    w, h = img.size
    if h < 50:
        return w // 2
    gray = img.convert('L')
    arr = np.array(gray, dtype=np.float32)
    mean_img = gray.filter(ImageFilter.BoxBlur(15))
    mean_arr = np.array(mean_img, dtype=np.float32)
    binary_arr = np.where(arr > (mean_arr - 15), 255, 0).astype(np.uint8)

    x1, x2 = int(0.25 * w), int(0.75 * w)
    col_means = binary_arr.mean(axis=0)[x1:x2]
    bright_indices = np.where(col_means > 238)[0]
    if len(bright_indices) > 0:
        runs = []
        current_run = [bright_indices[0]]
        for idx in bright_indices[1:]:
            if idx == current_run[-1] + 1:
                current_run.append(idx)
            else:
                runs.append(current_run)
                current_run = [idx]
        runs.append(current_run)
        longest_run = max(runs, key=len)
        if len(longest_run) >= 8:
            return x1 + longest_run[len(longest_run) // 2]
    return w // 2


def split_footnotes(img: Image.Image):
    """Split a single column image into (main_img, footnote_left_img,
    footnote_right_img, split_y, footnote_split_x)."""
    w, h = img.size
    split_y = find_footnote_split_y(img)

    main_img = img.crop((0, 0, w, split_y))

    fn_img = img.crop((0, split_y, w, h))
    fn_split_x = find_footnote_column_split_x(fn_img)
    fn_left_img = fn_img.crop((0, 0, fn_split_x, fn_img.height))
    fn_right_img = fn_img.crop((fn_split_x, 0, w, fn_img.height))

    return main_img, fn_left_img, fn_right_img, split_y, fn_split_x
