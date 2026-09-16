import flet as ft

def main(page: ft.Page):
    page.add(ft.Text("Hello World! Рушій працює.", size=30, color=ft.colors.GREEN))

ft.app(target=main)