import flet as ft
import requests
import traceback
import datetime

LANGUAGES = {
    "UK": {
        "title": "ВетКонтроль AI",
        "animal": "Вид тварини",
        "organ": "Орган",
        "analyze_btn": "Зробити фото та Аналізувати",
        "report_btn": "Створити звіт (HTML)",
        "exit_btn": "Вийти",
        "animals": ["Свиня", "ВРХ", "Птиця", "Вівця", "Кріль", "Страус"],
        "organs": ["Легені", "Серце", "Нирки", "Шлунок", "Кишечник", "Туша"],
        "status_wait": "Очікування фото...",
        "labels": ["Здорова", "Гемоаспірація", "Інша патологія", "Пневмонія"]
    }
}

def main(page: ft.Page):
    try:
        page.theme_mode = ft.ThemeMode.LIGHT
        page.padding = 20
        page.scroll = ft.ScrollMode.AUTO
        
        lang = LANGUAGES["UK"]
        
        animal_dropdown = ft.Dropdown(label=lang["animal"], options=[ft.dropdown.Option(a) for a in lang["animals"]], width=300)
        animal_dropdown.value = lang["animals"][0]
        
        organ_dropdown = ft.Dropdown(label=lang["organ"], options=[ft.dropdown.Option(o) for o in lang["organs"]], width=300)
        organ_dropdown.value = lang["organs"][0]
        
        result_text = ft.Text(value=lang["status_wait"], size=16, weight=ft.FontWeight.BOLD, color=ft.colors.RED_900)
        
        orig_image = ft.Image(src=None, width=300, height=300, fit=ft.ImageFit.CONTAIN)
        ai_image = ft.Image(src=None, width=300, height=300, fit=ft.ImageFit.CONTAIN)
        images_row = ft.Row([orig_image, ai_image], alignment=ft.MainAxisAlignment.CENTER, wrap=True)
        
        chart = ft.PieChart(sections=[], sections_space=2, center_space_radius=40, expand=True)
        chart_container = ft.Container(content=chart, width=200, height=200, visible=False)
        legend_column = ft.Column(visible=False)
        
        recommendations_text = ft.Text(value="", size=14)
        recommendations_container = ft.Container(
            content=ft.Column([ft.Text("РЕКОМЕНДАЦІЇ (Наказ № 28):", weight=ft.FontWeight.BOLD), recommendations_text]),
            border=ft.border.all(1, ft.colors.BLACK), padding=10, visible=False, width=400
        )
        
        report_data = {"animal": "", "organ": "", "results": "", "recs": ""}

        def generate_html_report(path):
            html = f"""
            <html>
            <head><meta charset="utf-8"><title>Висновок Ветсанекспертизи</title></head>
            <body>
                <h2>Звіт ветеринарно-санітарної експертизи</h2>
                <p><b>Дата:</b> {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                <p><b>Вид тварини:</b> {report_data['animal']}</p>
                <p><b>Орган:</b> {report_data['organ']}</p>
                <h3>Результати AI:</h3>
                <p>{report_data['results']}</p>
                <h3>Рекомендації (Наказ № 28):</h3>
                <p>{report_data['recs']}</p>
            </body>
            </html>
            """
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)

        def save_report_result(e: ft.FilePickerResultEvent):
            if e.path:
                generate_html_report(e.path)
                result_text.value = f"Звіт збережено: {e.path}"
                page.update()

        save_picker = ft.FilePicker(on_result=save_report_result)
        page.overlay.append(save_picker)

        def exit_app(e):
            page.window.close()

        def on_photo_selected(e: ft.FilePickerResultEvent):
            if e.files and len(e.files) > 0:
                file_path = e.files[0].path
                orig_image.src = file_path
                orig_image.src_base64 = None
                
                result_text.value = "Відправка на сервер..."
                chart_container.visible = False
                legend_column.visible = False
                recommendations_container.visible = False
                page.update()
                
                try:
                    with open(file_path, 'rb') as f:
                        res = requests.post('http://192.168.0.121:5000/predict', files={'file': f})
                    
                    data = res.json()
                    if data.get('status') == 'error':
                        result_text.value = data.get('message', 'Помилка сервера')
                        page.update()
                        return
                    
                    ai_image.src = None
                    ai_image.src_base64 = data.get('image_base64', '')
                    
                    max_scores = data.get('max_scores', [])
                    found_classes = data.get('found_classes', [])
                    labels = lang["labels"]
                    colors = [ft.colors.GREEN, ft.colors.ORANGE, ft.colors.PURPLE, ft.colors.RED]
                    
                    sections = []
                    legend_controls = []
                    res_html = ""
                    
                    for i, score in enumerate(max_scores):
                        val = float(score) * 100
                        render_val = val if val > 0.1 else 0.1
                        sections.append(ft.PieChartSection(value=render_val, color=colors[i], radius=30))
                        txt = f"{labels[i]}: {val:.1f}%"
                        legend_controls.append(ft.Text(txt, color=colors[i], weight=ft.FontWeight.BOLD))
                        res_html += txt + "<br>"
                    
                    chart.sections = sections
                    chart_container.visible = True
                    legend_column.controls = legend_controls
                    legend_column.visible = True
                    result_text.value = "Аналіз завершено"
                    
                    recs = "Оглянути бронхіальні лімфовузли."
                    if 3 in found_classes: recs += " Провести додаткові розрізи в червоній зоні (Пневмонія)."
                    recommendations_text.value = recs
                    recommendations_container.visible = True

                    report_data["animal"] = animal_dropdown.value
                    report_data["organ"] = organ_dropdown.value
                    report_data["results"] = res_html
                    report_data["recs"] = recs

                except Exception as ex:
                    result_text.value = f"Помилка з'єднання: {ex}"
                
                page.update()

        photo_picker = ft.FilePicker(on_result=on_photo_selected)
        page.overlay.append(photo_picker)

        analyze_btn = ft.ElevatedButton(text=lang["analyze_btn"], icon=ft.icons.CAMERA_ALT, width=300, on_click=lambda _: photo_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE))
        report_btn = ft.ElevatedButton(text=lang["report_btn"], icon=ft.icons.SAVE_ALT, width=300, on_click=lambda _: save_picker.save_file(allowed_extensions=["html"], file_name="vet_report.html"))
        exit_btn = ft.ElevatedButton(text=lang["exit_btn"], icon=ft.icons.EXIT_TO_APP, width=300, color=ft.colors.RED, on_click=exit_app)

        page.add(
            ft.Column([
                ft.Text(lang["title"], size=24, weight=ft.FontWeight.BOLD),
                animal_dropdown,
                organ_dropdown,
                ft.Container(height=10),
                analyze_btn,
                report_btn,
                exit_btn,
                ft.Container(height=10),
                result_text,
                images_row,
                ft.Row([chart_container, legend_column], alignment=ft.MainAxisAlignment.CENTER),
                recommendations_container
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
    except Exception as e:
        page.add(ft.Text("КРИТИЧНА ПОМИЛКА!", color=ft.colors.RED, size=24), ft.Text(traceback.format_exc(), color=ft.colors.RED))
        page.update()

if __name__ == '__main__':
    if hasattr(ft, 'app'):
        ft.app(main)