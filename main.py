import flet as ft
import numpy as np
from PIL import Image, ImageDraw, ImageOps
import io
import base64

try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    import tensorflow.lite as tflite

LANGUAGES = {
    "UK": {
        "title": "ВетКонтроль AI",
        "animal": "Вид тварини",
        "organ": "Орган",
        "analyze_btn": "Зробити фото та Аналізувати",
        "animals": ["Свиня", "ВРХ", "Птиця", "Вівця", "Кріль", "Страус"],
        "organs": ["Легені", "Серце", "Нирки", "Шлунок", "Кишечник", "Туша"],
        "status_wait": "Очікування фото...",
        "disclaimer": "УВАГА: Остаточну оцінку проводить тільки лікар ветсанексперт.",
        "labels": ["Здорова", "Гемоаспірація", "Інша патологія", "Пневмонія"],
        "orig_photo": "Оригінальне фото",
        "ai_photo": "AI Підсвітка зон"
    },
    "EN": {
        "title": "VetControl AI",
        "animal": "Animal Species",
        "organ": "Organ",
        "analyze_btn": "Take Photo & Analyze",
        "animals": ["Pig", "Cattle", "Poultry", "Sheep", "Rabbit", "Ostrich"],
        "organs": ["Lungs", "Heart", "Kidneys", "Stomach", "Intestines", "Carcass"],
        "status_wait": "Waiting for photo...",
        "disclaimer": "ATTENTION: The final assessment is made only by a veterinary sanitary expert.",
        "labels": ["Healthy", "Hemoaspiration", "Other pathology", "Pneumonia"],
        "orig_photo": "Original Photo",
        "ai_photo": "AI Highlight Zones"
    }
}

def nms(boxes, scores, iou_threshold=0.45):
    if len(boxes) == 0: return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        if order.size == 1: break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]
    return keep

def process_image_with_tflite(image_path, lang):
    interpreter = tflite.Interpreter(model_path="assets/best.tflite")
    interpreter.allocate_tensors()
    
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    
    original_img = Image.open(image_path)
    original_img = ImageOps.exif_transpose(original_img).convert('RGB')
    orig_w, orig_h = original_img.size
    
    img = original_img.resize((640, 640))
    img_data = np.array(img, dtype=np.float32) / 255.0
    
    input_shape = input_details[0]['shape']
    if input_shape[1] == 3:
        img_data = np.transpose(img_data, (2, 0, 1))
        
    img_data = np.expand_dims(img_data, axis=0)  
    
    interpreter.set_tensor(input_details[0]['index'], img_data)
    interpreter.invoke()
    
    output_data = interpreter.get_tensor(output_details[0]['index'])
    predictions = output_data[0] 
    
    if predictions.shape[0] > predictions.shape[1]:
        predictions = predictions.T
        
    class_scores = predictions[4:8, :] 
    max_scores_pie = np.max(class_scores, axis=1) 
    
    sum_scores = np.sum(max_scores_pie)
    if sum_scores > 0:
        max_scores_pie = max_scores_pie / sum_scores
        
    boxes_raw = predictions[0:4, :].T
    
    if np.max(boxes_raw) <= 2.0:
        boxes_raw = boxes_raw * 640.0
        
    conf_threshold = 0.05
    
    boxes_out = []
    scores_out = []
    class_ids_out = []
    
    for c in range(4):
        c_scores = class_scores[c, :]
        mask = c_scores > conf_threshold
        if not np.any(mask): continue
        
        c_boxes = boxes_raw[mask]
        c_scores_filtered = c_scores[mask]
        
        x1 = c_boxes[:, 0] - c_boxes[:, 2] / 2
        y1 = c_boxes[:, 1] - c_boxes[:, 3] / 2
        x2 = c_boxes[:, 0] + c_boxes[:, 2] / 2
        y2 = c_boxes[:, 1] + c_boxes[:, 3] / 2
        c_boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)
        
        c_boxes_xyxy[:, 0] = np.clip(c_boxes_xyxy[:, 0], 0, 640)
        c_boxes_xyxy[:, 1] = np.clip(c_boxes_xyxy[:, 1], 0, 640)
        c_boxes_xyxy[:, 2] = np.clip(c_boxes_xyxy[:, 2], 0, 640)
        c_boxes_xyxy[:, 3] = np.clip(c_boxes_xyxy[:, 3], 0, 640)
        
        keep = nms(c_boxes_xyxy, c_scores_filtered)
        for k in keep:
            boxes_out.append(c_boxes_xyxy[k])
            norm_score = (c_scores_filtered[k] / sum_scores) if sum_scores > 0 else c_scores_filtered[k]
            scores_out.append(norm_score)
            class_ids_out.append(c)
    
    overlay = Image.new('RGBA', original_img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    
    colors_rgba = [
        (0, 255, 0, 60),    
        (255, 165, 0, 100), 
        (128, 0, 128, 100), 
        (255, 0, 0, 120)    
    ]
    
    scale_x = orig_w / 640
    scale_y = orig_h / 640
    
    dominant_cls = int(np.argmax(max_scores_pie))
    border_color = colors_rgba[dominant_cls][:3] + (255,)
    labels = LANGUAGES[lang]["labels"]
    
    if len(boxes_out) > 0:
        for i in range(len(boxes_out)):
            box = boxes_out[i]
            cls_id = class_ids_out[i]
            score_val = scores_out[i] * 100
            
            bx1, by1, bx2, by2 = box[0]*scale_x, box[1]*scale_y, box[2]*scale_x, box[3]*scale_y
            solid_color = colors_rgba[cls_id][:3] + (255,)
            
            draw_overlay.rectangle([bx1, by1, bx2, by2], fill=colors_rgba[cls_id], outline=solid_color, width=6)
            
            label_text = f"{labels[cls_id]} {score_val:.1f}%"
            text_bg_y1 = max(0, by1 - 25)
            draw_overlay.rectangle([bx1, text_bg_y1, bx1 + 180, text_bg_y1 + 25], fill=solid_color)
            draw_overlay.text((bx1 + 5, text_bg_y1 + 4), label_text, fill=(255, 255, 255, 255))
    else:
        draw_overlay.rectangle([0, 0, orig_w, orig_h], fill=colors_rgba[dominant_cls])
        
    draw_overlay.rectangle([0, 0, orig_w, orig_h], outline=border_color, width=20)

    annotated_img = Image.alpha_composite(original_img.convert('RGBA'), overlay).convert('RGB')
    
    buffered = io.BytesIO()
    annotated_img.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return max_scores_pie, img_str, class_ids_out

def main(page: ft.Page):
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO
    
    current_lang = "UK"

    lang_switch = ft.Switch(value=False) 
    animal_dropdown = ft.Dropdown(width=300)
    organ_dropdown = ft.Dropdown(width=300)
    
    result_text = ft.Text(value="", size=18, weight=ft.FontWeight.BOLD, color=ft.colors.RED_900)
    
    orig_img_title = ft.Text(value="", weight=ft.FontWeight.BOLD)
    orig_image = ft.Image(src=False, width=300, height=300, fit=ft.ImageFit.CONTAIN)
    orig_col = ft.Column([orig_img_title, orig_image], horizontal_alignment=ft.CrossAxisAlignment.CENTER, visible=False)
    
    ai_img_title = ft.Text(value="", weight=ft.FontWeight.BOLD)
    ai_image = ft.Image(src=False, width=300, height=300, fit=ft.ImageFit.CONTAIN)
    ai_col = ft.Column([ai_img_title, ai_image], horizontal_alignment=ft.CrossAxisAlignment.CENTER, visible=False)
    
    images_row = ft.Row([orig_col, ai_col], alignment=ft.MainAxisAlignment.CENTER, wrap=True)
    
    chart = ft.PieChart(sections=[], sections_space=2, center_space_radius=40, expand=True)
    chart_container = ft.Container(content=chart, width=200, height=200, visible=False)
    legend_column = ft.Column(visible=False)
    
    recommendations_text = ft.Text(value="", size=14, color=ft.colors.BLACK)
    recommendations_container = ft.Container(
        content=ft.Column([
            ft.Text("РЕКОМЕНДАЦІЇ ДЛЯ ЛІКАРЯ ВЕТСАНЕКСПЕРТА:", weight=ft.FontWeight.BOLD, size=16),
            recommendations_text
        ]),
        border=ft.border.all(1, ft.colors.BLACK),
        padding=10,
        visible=False,
        width=400
    )
    
    disclaimer_text = ft.Text(value="", size=14, color=ft.colors.RED_700, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)

    def update_ui(e=None):
        nonlocal current_lang
        current_lang = "EN" if lang_switch.value else "UK"
        
        page.title = LANGUAGES[current_lang]["title"]
        animal_dropdown.label = LANGUAGES[current_lang]["animal"]
        organ_dropdown.label = LANGUAGES[current_lang]["organ"]
        analyze_btn.text = LANGUAGES[current_lang]["analyze_btn"]
        disclaimer_text.value = LANGUAGES[current_lang]["disclaimer"]
        orig_img_title.value = LANGUAGES[current_lang]["orig_photo"]
        ai_img_title.value = LANGUAGES[current_lang]["ai_photo"]
        
        if not orig_col.visible:
            result_text.value = LANGUAGES[current_lang]["status_wait"]

        animal_dropdown.options = [ft.dropdown.Option(a) for a in LANGUAGES[current_lang]["animals"]]
        organ_dropdown.options = [ft.dropdown.Option(o) for o in LANGUAGES[current_lang]["organs"]]
        
        if legend_column.visible:
            labels = LANGUAGES[current_lang]["labels"]
            for i, control in enumerate(legend_column.controls):
                old_text = control.value
                percent_str = old_text.split(":")[-1]
                control.value = f"{labels[i]}:{percent_str}"
        
        page.update()

    lang_switch.on_change = update_ui

    def generate_recommendations(found_classes):
        recs = []
        step = 1
        found_set = set(found_classes)
        
        if 3 in found_set:
            recs.append(f"{step}. Провести додаткові розрізи в червоній зоні (Пневмонія).")
            step += 1
        if 2 in found_set:
            recs.append(f"{step}. Перевірити фіолетову зону (Інша патологія).")
            step += 1
        if 1 in found_set:
            recs.append(f"{step}. Оглянути помаранчеву зону на наявність крові (Гемоаспірація).")
            step += 1
            
        recs.append(f"{step}. Оглянути бронхіальні лімфовузли (Наказ № 28).")
        return "\n".join(recs)

    def on_photo_selected(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            file_path = e.files[0].path
            
            pil_orig = Image.open(file_path)
            pil_orig = ImageOps.exif_transpose(pil_orig).convert('RGB')
            buf_orig = io.BytesIO()
            pil_orig.save(buf_orig, format="JPEG")
            orig_image.src_base64 = base64.b64encode(buf_orig.getvalue()).decode("utf-8")
            
            orig_col.visible = True
            ai_col.visible = False
            
            result_text.value = "Обробка тензорів..."
            result_text.visible = True
            chart_container.visible = False
            legend_column.visible = False
            recommendations_container.visible = False
            page.update()
            
            try:
                max_scores, base64_img, found_classes = process_image_with_tflite(file_path, current_lang)
                
                ai_image.src = None
                ai_image.src_base64 = base64_img
                ai_col.visible = True
                
                labels = LANGUAGES[current_lang]["labels"]
                colors = [ft.colors.GREEN, ft.colors.ORANGE, ft.colors.PURPLE, ft.colors.RED]
                
                sections = []
                legend_controls = []
                
                for i, score in enumerate(max_scores):
                    val = float(score) * 100
                    render_val = val if val > 0.1 else 0.1 
                    sections.append(ft.PieChartSection(value=render_val, color=colors[i], radius=30, title=""))
                    legend_controls.append(ft.Text(f"{labels[i]}: {val:.1f}%", color=colors[i], weight=ft.FontWeight.BOLD, size=16))
                
                chart.sections = sections
                chart_container.visible = True
                legend_column.controls = legend_controls
                legend_column.visible = True
                result_text.visible = False
                
                recommendations_text.value = generate_recommendations(found_classes)
                recommendations_container.visible = True

            except Exception as ex:
                result_text.value = f"Критична помилка: {ex}"
                result_text.visible = True
            
            page.update()

    photo_picker = ft.FilePicker(on_result=on_photo_selected)
    page.overlay.append(photo_picker)

    analyze_btn = ft.ElevatedButton(
        icon=ft.icons.CAMERA_ALT,
        width=300,
        height=50,
        on_click=lambda _: photo_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)
    )

    update_ui()
    if not animal_dropdown.value:
        animal_dropdown.value = LANGUAGES["UK"]["animals"][0]
    if not organ_dropdown.value:
        organ_dropdown.value = LANGUAGES["UK"]["organs"][0]

    page.add(
        ft.Row(
            [ft.Text("UK", weight=ft.FontWeight.BOLD), lang_switch, ft.Text("EN", weight=ft.FontWeight.BOLD)], 
            alignment=ft.MainAxisAlignment.END
        ),
        ft.Column(
            [
                ft.Text("AI Diagnostic Tool", size=24, weight=ft.FontWeight.BOLD),
                animal_dropdown,
                organ_dropdown,
                ft.Container(height=20),
                analyze_btn,
                ft.Container(height=10),
                result_text,
                images_row,
                ft.Row([chart_container, legend_column], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(height=10),
                recommendations_container,
                ft.Container(height=20),
                disclaimer_text
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
    )

ft.app(target=main)