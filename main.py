import flet as ft
from PIL import Image, ImageOps
import io
import base64
import requests

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
            
            result_text.value = "Відправка на сервер..."
            result_text.visible = True
            chart_container.visible = False
            legend_column.visible = False
            recommendations_container.visible = False
            page.update()
            
            try:
                with open(file_path, 'rb') as f:
                    files = {'file': f}
                    # УВАГА: ЗАМІНИТИ 192.168.1.XXX НА РЕАЛЬНУ IPv4 АДРЕСУ ТВОГО СЕРВЕРА
                    res = requests.post('http://192.168.0.121:5000/predict', files=files)
                
                data = res.json()
                
                if data.get('status') == 'error':
                    result_text.value = data.get('message', 'Помилка валідації на сервері')
                    result_text.visible = True
                    page.update()
                    return
                
                max_scores = data.get('max_scores', [])
                base64_img = data.get('image_base64', '')
                found_classes = data.get('found_classes', [])
                
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
                result_text.value = f"Помилка з'єднання з сервером: {ex}"
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