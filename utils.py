import re

def is_id_card_valid(id_card: str) -> bool:
    """校验身份证号格式"""
    if not id_card:
        return True  # 空值不校验
    if len(id_card) != 18:
        return False
    pattern = r'^[1-9]\d{5}(19|20)\d{2}((0[1-9])|(1[0-2]))(([0-2][1-9])|10|20|30|31)\d{3}[0-9Xx]$'
    return re.match(pattern, id_card) is not None

def is_bank_card_valid(bank_card: str) -> bool:
    """校验银行卡号格式（支持公司账户和个人账户）"""
    if not bank_card:
        return True
    if not bank_card.isdigit():
        return False
    return 6 <= len(bank_card) <= 30


# ===== Kivy 弹窗工具函数 =====

def show_error_message(parent, title: str, message: str):
    """统一错误提示（Kivy 版）"""
    _show_popup(f"❌ {title}", message, button_text="确定")

def show_success_message(parent, title: str, message: str):
    """统一成功提示（Kivy 版）"""
    _show_popup(f"✅ {title}", message, button_text="确定")

def show_warning_message(parent, title: str, message: str):
    """统一警告提示（Kivy 版）"""
    _show_popup(f"⚠️ {title}", message, button_text="确定")

def confirm_action(parent, title: str, message: str, callback=None) -> None:
    """统一确认对话框（Kivy 版，异步，通过 callback 返回结果）"""
    try:
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button

        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(
            text=message,
            text_size=(360, None),
            halign='center',
            size_hint_y=None,
            height=80
        ))
        btn_row = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=44)

        popup = Popup(
            title=title,
            content=content,
            size_hint=(None, None),
            size=(400, 200),
            auto_dismiss=False
        )

        def on_confirm(instance):
            popup.dismiss()
            if callback:
                callback(True)

        def on_cancel(instance):
            popup.dismiss()
            if callback:
                callback(False)

        btn_ok = Button(text="确定", background_color=(0.2, 0.6, 1, 1))
        btn_cancel = Button(text="取消", background_color=(0.6, 0.6, 0.6, 1))
        btn_ok.bind(on_press=on_confirm)
        btn_cancel.bind(on_press=on_cancel)
        btn_row.add_widget(btn_ok)
        btn_row.add_widget(btn_cancel)
        content.add_widget(btn_row)

        popup.open()
    except Exception as e:
        print(f"[confirm_action] Kivy 弹窗失败: {e}")
        if callback:
            callback(False)


def _show_popup(title: str, message: str, button_text: str = "确定"):
    """内部通用弹窗"""
    try:
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button

        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(
            text=message,
            text_size=(360, None),
            halign='center',
            size_hint_y=None,
            height=80
        ))
        btn = Button(
            text=button_text,
            size_hint_y=None, height=44,
            background_color=(0.2, 0.6, 1, 1)
        )
        popup = Popup(
            title=title,
            content=content,
            size_hint=(None, None),
            size=(400, 200),
            auto_dismiss=False
        )
        btn.bind(on_press=popup.dismiss)
        content.add_widget(btn)
        popup.open()
    except Exception as e:
        print(f"[Popup] {title}: {message} (Kivy 不可用: {e})")
