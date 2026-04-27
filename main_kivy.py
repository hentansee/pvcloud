"""
光伏智云管理系统 · Kivy 版
将原 PySide6 桌面端逻辑移植到 Kivy，支持 Buildozer 打包为 Android APK。
"""

import os
import sys
import json
import shutil
from datetime import datetime

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.properties import (
    StringProperty, NumericProperty, ListProperty,
    BooleanProperty, ObjectProperty, DictProperty
)
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.core.window import Window
from kivy.utils import get_color_from_hex

# 本地模块
from models import Project, TankanData, DeviceData, _make_default_site
from config import (
    PV_MODULES, INVERTERS, DC_CABLE, AC_CABLE,
    ROOT_PATH, DATA_FILE, BACKUP_PATH, PROGRESS_STAGES
)
from utils import (
    show_error_message, show_success_message,
    show_warning_message, confirm_action,
    is_id_card_valid, is_bank_card_valid
)

# 颜色常量
C_PRIMARY   = get_color_from_hex("#0969da")
C_BG        = get_color_from_hex("#f0f2f5")
C_WHITE     = get_color_from_hex("#ffffff")
C_DANGER    = get_color_from_hex("#dc2626")
C_SUCCESS   = get_color_from_hex("#1a7f37")
C_TEXT      = get_color_from_hex("#24292f")
C_MUTED     = get_color_from_hex("#57606a")
C_BORDER    = get_color_from_hex("#d0d7de")

# 屏幕宽度跟随窗口
Window.clearcolor = C_BG


# ─────────────────────────────────────────────
#  KV 字符串：公共样式组件
# ─────────────────────────────────────────────
KV = """
#:import dp kivy.metrics.dp
#:import get_color_from_hex kivy.utils.get_color_from_hex

<PvButton@Button>:
    background_normal: ''
    background_color: get_color_from_hex('#0969da')
    color: 1,1,1,1
    font_size: dp(14)
    size_hint_y: None
    height: dp(40)
    bold: True

<DangerButton@Button>:
    background_normal: ''
    background_color: get_color_from_hex('#dc2626')
    color: 1,1,1,1
    font_size: dp(14)
    size_hint_y: None
    height: dp(40)
    bold: True

<GrayButton@Button>:
    background_normal: ''
    background_color: get_color_from_hex('#8c959f')
    color: 1,1,1,1
    font_size: dp(14)
    size_hint_y: None
    height: dp(40)

<SectionLabel@Label>:
    color: get_color_from_hex('#1f2328')
    font_size: dp(15)
    bold: True
    size_hint_y: None
    height: dp(30)
    halign: 'left'
    text_size: self.size

<FieldLabel@Label>:
    color: get_color_from_hex('#57606a')
    font_size: dp(13)
    size_hint_y: None
    height: dp(30)
    halign: 'left'
    text_size: self.size

<PvTextInput@TextInput>:
    multiline: False
    background_color: 1,1,1,1
    foreground_color: get_color_from_hex('#24292f')
    cursor_color: get_color_from_hex('#0969da')
    font_size: dp(13)
    size_hint_y: None
    height: dp(38)
    padding: [dp(8), dp(8), dp(8), dp(8)]

<NavButton@ToggleButton>:
    group: 'nav'
    background_normal: ''
    background_down: ''
    background_color: 0,0,0,0
    color: get_color_from_hex('#57606a')
    font_size: dp(13)
    size_hint_y: None
    height: dp(46)
    halign: 'left'
    text_size: self.size
    padding: [dp(14), 0]
    canvas.before:
        Color:
            rgba: get_color_from_hex('#0969da') if self.state=='down' else (0,0,0,0)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(6)]
"""

Builder.load_string(KV)


# ─────────────────────────────────────────────
#  工具：带圆角背景的卡片 Box
# ─────────────────────────────────────────────
class CardBox(BoxLayout):
    """带白色圆角背景的 BoxLayout"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(rgba=C_WHITE)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size


class SepLine(Widget):
    """水平分割线"""
    def __init__(self, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(1))
        super().__init__(**kwargs)
        with self.canvas:
            Color(rgba=C_BORDER)
            self._line = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._line.pos = self.pos
        self._line.size = self.size


# ─────────────────────────────────────────────
#  弹窗工具：输入对话框
# ─────────────────────────────────────────────
def input_dialog(title, hint, callback, default=""):
    content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(12))
    ti = TextInput(text=default, multiline=False,
                   size_hint_y=None, height=dp(40),
                   background_color=(1, 1, 1, 1),
                   foreground_color=C_TEXT)
    content.add_widget(Label(text=hint, size_hint_y=None, height=dp(30),
                              color=C_TEXT, halign='left', text_size=(dp(300), None)))
    content.add_widget(ti)
    btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
    pop = Popup(title=title, content=content,
                size_hint=(None, None), size=(dp(340), dp(180)),
                auto_dismiss=False)

    def _ok(_):
        pop.dismiss()
        callback(ti.text.strip())

    def _cancel(_):
        pop.dismiss()
        callback(None)

    b_ok = Button(text="确定", background_normal='',
                  background_color=C_PRIMARY, color=(1,1,1,1))
    b_cancel = Button(text="取消", background_normal='',
                      background_color=C_MUTED, color=(1,1,1,1))
    b_ok.bind(on_press=_ok)
    b_cancel.bind(on_press=_cancel)
    btn_row.add_widget(b_ok)
    btn_row.add_widget(b_cancel)
    content.add_widget(btn_row)
    pop.open()


# ─────────────────────────────────────────────
#  左侧导航面板
# ─────────────────────────────────────────────
class NavPanel(BoxLayout):
    """左侧导航：项目列表 + 功能导航"""

    def __init__(self, app_ref, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_x', None)
        kwargs.setdefault('width', dp(220))
        kwargs.setdefault('spacing', dp(4))
        kwargs.setdefault('padding', [dp(8), dp(8), dp(8), dp(8)])
        super().__init__(**kwargs)
        self.app = app_ref

        with self.canvas.before:
            Color(rgba=C_WHITE)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd_bg, size=self._upd_bg)

        self._build()

    def _upd_bg(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _build(self):
        # 标题
        self.add_widget(Label(
            text="☀ 光伏智云管理",
            font_size=dp(16), bold=True,
            color=C_PRIMARY,
            size_hint_y=None, height=dp(36),
            halign='left', text_size=(dp(200), None)
        ))
        self.add_widget(Label(
            text="专业版 · 户用/工商业双模式",
            font_size=dp(11), color=C_MUTED,
            size_hint_y=None, height=dp(20),
            halign='left', text_size=(dp(200), None)
        ))
        self.add_widget(SepLine())

        # 搜索框
        self.search_input = TextInput(
            hint_text="🔍 搜索项目",
            multiline=False,
            background_color=(1, 1, 1, 1),
            foreground_color=C_TEXT,
            size_hint_y=None, height=dp(36),
            font_size=dp(13)
        )
        self.search_input.bind(text=self._on_search)
        self.add_widget(self.search_input)

        # 项目列表
        self.add_widget(Label(
            text="📋 项目列表",
            font_size=dp(12), color=C_MUTED,
            size_hint_y=None, height=dp(24),
            halign='left', text_size=(dp(200), None)
        ))
        self.proj_scroll = ScrollView(size_hint_y=1)
        self.proj_list_layout = GridLayout(
            cols=1, spacing=dp(2),
            size_hint_y=None, padding=[0, 0, 0, 0]
        )
        self.proj_list_layout.bind(
            minimum_height=self.proj_list_layout.setter('height')
        )
        self.proj_scroll.add_widget(self.proj_list_layout)
        self.add_widget(self.proj_scroll)

        # 新增/删除按钮
        btn_row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        b_add = Button(text="➕ 新增", background_normal='',
                       background_color=C_PRIMARY, color=(1,1,1,1),
                       font_size=dp(13))
        b_del = Button(text="🗑 删除", background_normal='',
                       background_color=C_DANGER, color=(1,1,1,1),
                       font_size=dp(13))
        b_add.bind(on_press=self.app.add_project)
        b_del.bind(on_press=self.app.delete_project)
        btn_row.add_widget(b_add)
        btn_row.add_widget(b_del)
        self.add_widget(btn_row)

        # 备份按钮
        btn_bk = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        b_backup = Button(text="📦 备份", background_normal='',
                          background_color=get_color_from_hex('#6366f1'),
                          color=(1,1,1,1), font_size=dp(13))
        b_restore = Button(text="🔄 恢复", background_normal='',
                           background_color=get_color_from_hex('#8c959f'),
                           color=(1,1,1,1), font_size=dp(13))
        b_backup.bind(on_press=self.app.manual_backup)
        b_restore.bind(on_press=self.app.restore_backup)
        btn_bk.add_widget(b_backup)
        btn_bk.add_widget(b_restore)
        self.add_widget(btn_bk)

        self.add_widget(SepLine())

        # 功能导航
        nav_items = [
            ("📌 项目信息",  "project"),
            ("🔍 踏勘信息",  "tankan"),
            ("📁 资料管理",  "files"),
            ("🔌 设备配置",  "device"),
            ("💰 收益测算",  "profit"),
            ("🏗 项目付款",  "payment"),
            ("📄 导出报告",  "report"),
        ]
        for label, screen_name in nav_items:
            btn = ToggleButton(
                text=label, group='nav',
                background_normal='', background_down='',
                background_color=(0, 0, 0, 0),
                color=C_MUTED,
                font_size=dp(13),
                size_hint_y=None, height=dp(42),
                halign='left',
                text_size=(dp(200), dp(42)),
                padding=[dp(14), 0]
            )
            btn.bind(on_press=lambda b, s=screen_name: self.app.goto_screen(s))
            self.add_widget(btn)
            if screen_name == 'project':
                btn.state = 'down'

    def _on_search(self, instance, value):
        self.app.refresh_project_list(keyword=value)

    def refresh_list(self, projects, selected_name=None):
        self.proj_list_layout.clear_widgets()
        for p in projects:
            btn = Button(
                text=p.name,
                background_normal='',
                background_color=C_PRIMARY if p.name == selected_name
                                 else (0.94, 0.95, 0.97, 1),
                color=(1, 1, 1, 1) if p.name == selected_name else C_TEXT,
                font_size=dp(13),
                size_hint_y=None, height=dp(38),
                halign='left',
                text_size=(dp(195), dp(38)),
                padding=[dp(10), 0]
            )
            btn.bind(on_press=lambda b, proj=p: self.app.select_project(proj))
            self.proj_list_layout.add_widget(btn)


# ─────────────────────────────────────────────
#  通用表单辅助：FormRow
# ─────────────────────────────────────────────
def form_row(label_text, widget, label_width=dp(120)):
    row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
    lbl = Label(
        text=label_text, color=C_TEXT,
        font_size=dp(13),
        size_hint_x=None, width=label_width,
        halign='right', text_size=(label_width, dp(42))
    )
    row.add_widget(lbl)
    row.add_widget(widget)
    return row


def make_spinner(values, selected=""):
    sp = Spinner(
        values=values,
        text=selected or (values[0] if values else ""),
        background_normal='',
        background_color=C_WHITE,
        color=C_TEXT,
        font_size=dp(13),
        size_hint_y=None, height=dp(38)
    )
    return sp


def make_text_input(hint="", text="", multiline=False):
    ti = TextInput(
        hint_text=hint, text=text,
        multiline=multiline,
        background_color=(1, 1, 1, 1),
        foreground_color=C_TEXT,
        cursor_color=C_PRIMARY,
        font_size=dp(13),
        size_hint_y=None,
        height=dp(80) if multiline else dp(38),
        padding=[dp(8), dp(8), dp(8), dp(8)]
    )
    return ti


# ─────────────────────────────────────────────
#  基础 Screen 模板
# ─────────────────────────────────────────────
class BaseScreen(Screen):
    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app = app_ref
        self._scroll = ScrollView()
        self._inner = GridLayout(
            cols=1, spacing=dp(10),
            size_hint_y=None,
            padding=[dp(12), dp(12), dp(12), dp(12)]
        )
        self._inner.bind(minimum_height=self._inner.setter('height'))
        self._scroll.add_widget(self._inner)
        self.add_widget(self._scroll)
        self.build_ui()

    def build_ui(self):
        """子类重写此方法构建 UI"""
        pass

    def on_enter(self):
        """进入屏幕时刷新数据"""
        self.load_data()

    def load_data(self):
        """子类重写"""
        pass

    def _add(self, widget):
        self._inner.add_widget(widget)

    def _section(self, title):
        lbl = Label(
            text=title, bold=True, color=C_PRIMARY,
            font_size=dp(14),
            size_hint_y=None, height=dp(32),
            halign='left', text_size=(dp(600), dp(32))
        )
        self._add(lbl)

    def _sep(self):
        self._add(SepLine())


# ─────────────────────────────────────────────
#  1. 项目信息 Screen
# ─────────────────────────────────────────────
class ProjectScreen(BaseScreen):
    def build_ui(self):
        # 电站信息
        self._section("📍 电站信息")
        self.station_code   = make_text_input("电站编号")
        self.station_name   = make_text_input("电站名称")
        self.roof_type      = make_spinner(["彩钢瓦","水泥顶","琉璃瓦","单坡阳光房","其他"])
        self.station_addr   = make_text_input("电站地址")

        self._add(form_row("电站编号", self.station_code))
        self._add(form_row("电站名称", self.station_name))
        self._add(form_row("屋顶类型", self.roof_type))
        self._add(form_row("电站地址", self.station_addr))
        self._sep()

        # 项目信息
        self._section("📋 项目信息")
        self.p_type    = make_spinner(["户用光伏","工商业光伏"])
        self.p_mode    = make_spinner(["全额上网","全自用","自发自用+余电上网"])
        self.proj_belong   = make_text_input("所属项目")
        self.proj_company  = make_text_input("项目公司", text="澄观新能源")
        self.annual_rent   = make_text_input("年单租金(元)")
        self.builder       = make_text_input("建设方")
        self.general       = make_text_input("合作模式")

        self._add(form_row("项目类型", self.p_type))
        self._add(form_row("并网模式", self.p_mode))
        self._add(form_row("所属项目", self.proj_belong))
        self._add(form_row("项目公司", self.proj_company))
        self._add(form_row("年单租金", self.annual_rent))
        self._add(form_row("建设方",   self.builder))
        self._add(form_row("合作模式", self.general))
        self._sep()

        # 农户信息（户用）
        self._section("👤 农户信息（户用）")
        self.id_number   = make_text_input("手机号/折号")
        self.user_name   = make_text_input("个人姓名")
        self.gender      = make_spinner(["男","女"])
        self.marriage    = make_spinner(["已婚","未婚","离异","丧偶"])
        self.birth_date  = make_text_input("出生日期 yyyy-MM-dd")
        self.id_card     = make_text_input("身份证号")
        self.id_valid_start = make_text_input("身份证有效起始")
        self.id_valid_end   = make_text_input("身份证有效结束")
        self.id_addr     = make_text_input("身份证地址")

        self._add(form_row("手机/折号",   self.id_number))
        self._add(form_row("个人姓名",    self.user_name))
        self._add(form_row("性别",        self.gender))
        self._add(form_row("婚姻状态",    self.marriage))
        self._add(form_row("出生日期",    self.birth_date))
        self._add(form_row("身份证号",    self.id_card))
        self._add(form_row("证件有效起",  self.id_valid_start))
        self._add(form_row("证件有效止",  self.id_valid_end))
        self._add(form_row("身份证地址",  self.id_addr))
        self._sep()

        # 单位信息（工商业）
        self._section("🏢 单位信息（工商业）")
        self.company_name     = make_text_input("单位名称")
        self.business_license = make_text_input("统一社会信用代码")
        self.legal_person     = make_text_input("法人姓名")
        self.legal_phone      = make_text_input("法人电话")
        self.company_addr     = make_text_input("单位地址")

        self._add(form_row("单位名称",    self.company_name))
        self._add(form_row("信用代码",    self.business_license))
        self._add(form_row("法人姓名",    self.legal_person))
        self._add(form_row("法人电话",    self.legal_phone))
        self._add(form_row("单位地址",    self.company_addr))
        self._sep()

        # 收益卡 & 其他
        self._section("💳 收益卡 & 其他信息")
        self.bank_card   = make_text_input("收益银行卡号")
        self.bank_branch = make_text_input("收益银行卡开户行")
        self.p_kw        = make_text_input("装机容量(kW)")
        self.p_trans     = make_text_input("变压器容量(kW)")
        self.p_area      = make_text_input("屋顶面积(㎡)")
        self.p_user      = make_text_input("居间人")
        self.p_note      = make_text_input("备注", multiline=True)

        self._add(form_row("银行卡号",   self.bank_card))
        self._add(form_row("开户行",     self.bank_branch))
        self._add(form_row("装机容量",   self.p_kw))
        self._add(form_row("变压器",     self.p_trans))
        self._add(form_row("屋顶面积",   self.p_area))
        self._add(form_row("居间人",     self.p_user))
        self._add(form_row("备注",       self.p_note))

        # 保存按钮
        btn = Button(
            text="💾 保存项目信息",
            background_normal='', background_color=C_PRIMARY,
            color=(1,1,1,1), font_size=dp(15), bold=True,
            size_hint_y=None, height=dp(46)
        )
        btn.bind(on_press=lambda _: self.app.save_project_info(self))
        self._add(btn)

    def load_data(self):
        p = self.app.current_project
        if not p:
            return
        self.station_code.text   = p.station_code or ""
        self.station_name.text   = p.station_name or ""
        self.roof_type.text      = p.roof_type or self.roof_type.values[0]
        self.station_addr.text   = p.station_addr or ""
        self.p_type.text         = p.type or "户用光伏"
        self.p_mode.text         = p.mode or "全额上网"
        self.proj_belong.text    = p.proj_belong or ""
        self.proj_company.text   = p.proj_company or "澄观新能源"
        self.annual_rent.text    = str(p.annual_rent) if p.annual_rent else ""
        self.builder.text        = p.builder or ""
        self.general.text        = p.general or ""
        self.id_number.text      = p.id_number or ""
        self.user_name.text      = p.user_name or ""
        self.gender.text         = p.gender or "男"
        self.marriage.text       = p.marriage or "已婚"
        self.birth_date.text     = p.birth_date or ""
        self.id_card.text        = p.id_card or ""
        self.id_valid_start.text = p.id_valid_start or ""
        self.id_valid_end.text   = p.id_valid_end or ""
        self.id_addr.text        = p.id_addr or ""
        self.company_name.text   = p.company_name or ""
        self.business_license.text = p.business_license or ""
        self.legal_person.text   = p.legal_person or ""
        self.legal_phone.text    = p.legal_phone or ""
        self.company_addr.text   = p.company_addr or ""
        self.bank_card.text      = p.bank_card or ""
        self.bank_branch.text    = p.bank_branch or ""
        self.p_kw.text           = str(p.kw) if p.kw else ""
        self.p_trans.text        = str(p.trans) if p.trans else ""
        self.p_area.text         = str(p.area) if p.area else ""
        self.p_user.text         = p.user or ""
        self.p_note.text         = p.note or ""

    def collect_data(self):
        """从 UI 收集数据，写回到 current_project"""
        p = self.app.current_project
        if not p:
            return
        p.station_code   = self.station_code.text.strip()
        p.station_name   = self.station_name.text.strip()
        p.roof_type      = self.roof_type.text
        p.station_addr   = self.station_addr.text.strip()
        p.type           = self.p_type.text
        p.mode           = self.p_mode.text
        p.proj_belong    = self.proj_belong.text.strip()
        p.proj_company   = self.proj_company.text.strip()
        try:
            p.annual_rent = float(self.annual_rent.text)
        except Exception:
            p.annual_rent = 0.0
        p.builder        = self.builder.text.strip()
        p.general        = self.general.text.strip()
        p.id_number      = self.id_number.text.strip()
        p.user_name      = self.user_name.text.strip()
        p.gender         = self.gender.text
        p.marriage       = self.marriage.text
        p.birth_date     = self.birth_date.text.strip()
        p.id_card        = self.id_card.text.strip()
        p.id_valid_start = self.id_valid_start.text.strip()
        p.id_valid_end   = self.id_valid_end.text.strip()
        p.id_addr        = self.id_addr.text.strip()
        p.company_name   = self.company_name.text.strip()
        p.business_license = self.business_license.text.strip()
        p.legal_person   = self.legal_person.text.strip()
        p.legal_phone    = self.legal_phone.text.strip()
        p.company_addr   = self.company_addr.text.strip()
        p.bank_card      = self.bank_card.text.strip()
        p.bank_branch    = self.bank_branch.text.strip()
        try:
            p.kw  = float(self.p_kw.text)
        except Exception:
            p.kw = 0.0
        try:
            p.trans = float(self.p_trans.text)
        except Exception:
            p.trans = 0.0
        try:
            p.area = float(self.p_area.text)
        except Exception:
            p.area = 0.0
        p.user = self.p_user.text.strip()
        p.note = self.p_note.text.strip()
        # 用电站名称作为项目名（如果非空）
        if p.station_name:
            p.name = p.station_name


# ─────────────────────────────────────────────
#  2. 踏勘信息 Screen
# ─────────────────────────────────────────────
class TankanScreen(BaseScreen):
    def build_ui(self):
        # 踏勘类型选择
        self._section("🔧 踏勘类型")
        row_type = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        self.btn_huyong    = ToggleButton(text="🏠 户用",   group='tankan_type', state='down',
                                          background_normal='', background_down='',
                                          font_size=dp(14))
        self.btn_gongshang = ToggleButton(text="🏭 工商业", group='tankan_type',
                                          background_normal='', background_down='',
                                          font_size=dp(14))
        self.btn_huyong.bind(on_press=lambda _: self._switch_mode('户用'))
        self.btn_gongshang.bind(on_press=lambda _: self._switch_mode('工商业'))
        row_type.add_widget(self.btn_huyong)
        row_type.add_widget(self.btn_gongshang)
        self._add(row_type)
        self._sep()

        # ── 户用区域
        self._section("📏 基本勘查信息（户用）")
        self.longitude     = make_text_input("经度")
        self.latitude      = make_text_input("纬度")
        self.house_floor   = make_spinner(["","1层","2层","3层","4层及以上"])
        self.house_direction = make_spinner(["正南","南偏东","南偏西"])
        self.have_obstacle = make_spinner(["","有遮挡物","无遮挡物"])
        self.grid_distance = make_text_input("并网箱至并网点距离(m)")

        self._add(form_row("经度",   self.longitude))
        self._add(form_row("纬度",   self.latitude))
        self._add(form_row("房屋层数", self.house_floor))
        self._add(form_row("房屋朝向", self.house_direction))
        self._add(form_row("遮挡物",   self.have_obstacle))
        self._add(form_row("并网距离", self.grid_distance))

        self._section("🏗 屋面信息（户用）")
        self.roof_type_detail = make_spinner(["单坡阳光房","双坡房","平顶房","其他"])
        self.roof_panel_type  = make_spinner(["现浇板","预制板","木檩条","混凝土檩条","彩钢瓦"])
        self.roof_length      = make_text_input("屋面长度(m)")
        self.roof_width       = make_text_input("屋面宽度(m)")
        self.install_area     = make_text_input("预估安装面积(㎡)")
        self.panel_count_hy   = make_text_input("预估组件数量")
        self.panel_spec       = make_text_input("组件规格(W)")
        self.install_power    = make_text_input("预估装机容量(kW)")

        self._add(form_row("屋面类型",   self.roof_type_detail))
        self._add(form_row("屋面板类型", self.roof_panel_type))
        self._add(form_row("屋面长度",   self.roof_length))
        self._add(form_row("屋面宽度",   self.roof_width))
        self._add(form_row("安装面积",   self.install_area))
        self._add(form_row("组件数量",   self.panel_count_hy))
        self._add(form_row("组件规格",   self.panel_spec))
        self._add(form_row("装机容量",   self.install_power))
        self._sep()

        # ── 工商业区域（场地）
        self._section("📍 工商业场地参数")

        # 场地选择行
        site_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.site_spinner = Spinner(
            text="场地1", values=["场地1"],
            background_normal='', background_color=C_WHITE,
            color=C_TEXT, font_size=dp(13),
            size_hint_x=0.4
        )
        self.site_spinner.bind(text=self._on_site_changed)
        b_add_site = Button(text="➕", background_normal='',
                            background_color=C_PRIMARY, color=(1,1,1,1),
                            size_hint_x=None, width=dp(40))
        b_del_site = Button(text="🗑", background_normal='',
                            background_color=C_DANGER, color=(1,1,1,1),
                            size_hint_x=None, width=dp(40))
        b_rename   = Button(text="✏", background_normal='',
                            background_color=get_color_from_hex('#6366f1'),
                            color=(1,1,1,1), size_hint_x=None, width=dp(40))
        b_add_site.bind(on_press=lambda _: self.app.add_site())
        b_del_site.bind(on_press=lambda _: self.app.delete_site())
        b_rename.bind(on_press=lambda _: self.app.rename_site())
        site_row.add_widget(Label(text="当前场地:", size_hint_x=None, width=dp(70),
                                   color=C_TEXT, font_size=dp(13)))
        site_row.add_widget(self.site_spinner)
        site_row.add_widget(b_add_site)
        site_row.add_widget(b_del_site)
        site_row.add_widget(b_rename)
        self._add(site_row)

        self.site_summary_label = Label(
            text="", color=C_MUTED, font_size=dp(12),
            size_hint_y=None, height=dp(22),
            halign='left', text_size=(dp(500), dp(22))
        )
        self._add(self.site_summary_label)

        # 场地形状
        self.site_shape  = make_spinner(["矩形","梯形","四边形","自定义面积"])
        self.site_shape.bind(text=self._on_shape_changed)
        self.site_length = make_text_input("场地长度(m)")
        self.site_width  = make_text_input("场地宽度(m)")
        self.site_gap    = make_text_input("预留间隙(m)", text="0.5")
        self.reserve_ratio = make_text_input("建议预留比例(%)", text="10")

        self._add(form_row("场地形状",   self.site_shape))
        self._add(form_row("场地长度",   self.site_length))
        self._add(form_row("场地宽度",   self.site_width))
        self._add(form_row("预留间隙",   self.site_gap))
        self._add(form_row("预留比例",   self.reserve_ratio))

        # 梯形参数
        self._section("↕ 梯形参数（仅梯形场地填写）")
        self.trap_top    = make_text_input("上底(m)")
        self.trap_bottom = make_text_input("下底(m)")
        self.trap_height = make_text_input("高(m)")
        self._add(form_row("上底", self.trap_top))
        self._add(form_row("下底", self.trap_bottom))
        self._add(form_row("高",   self.trap_height))

        # 四边形参数
        self._section("↔ 四边形参数（仅四边形场地填写）")
        self.quad_top    = make_text_input("上边(m)")
        self.quad_bottom = make_text_input("下边(m)")
        self.quad_left   = make_text_input("左边(m)")
        self.quad_right  = make_text_input("右边(m)")
        self._add(form_row("上边", self.quad_top))
        self._add(form_row("下边", self.quad_bottom))
        self._add(form_row("左边", self.quad_left))
        self._add(form_row("右边", self.quad_right))

        # 自定义面积
        self._section("🔲 自定义面积")
        self.custom_area  = make_text_input("可用面积(㎡)")
        self.equiv_length = make_text_input("等效长度(m，可选)")
        self.equiv_width  = make_text_input("等效宽度(m，可选)")
        self._add(form_row("可用面积",   self.custom_area))
        self._add(form_row("等效长度",   self.equiv_length))
        self._add(form_row("等效宽度",   self.equiv_width))

        # 光伏板参数
        self._section("☀ 光伏板参数")
        panel_brands = list(set(p.brand for p in _get_presets()))
        self.panel_brand  = make_spinner(panel_brands or ["通威"])
        self.panel_length_gs = make_text_input("板长(m)", text="2.384")
        self.panel_width_gs  = make_text_input("板宽(m)", text="1.303")
        self.panel_power_gs  = make_text_input("单块容量(W)", text="700")

        self._add(form_row("组件品牌", self.panel_brand))
        self._add(form_row("板长(m)",  self.panel_length_gs))
        self._add(form_row("板宽(m)",  self.panel_width_gs))
        self._add(form_row("单块容量", self.panel_power_gs))

        # 测算按钮 & 结果
        btn_calc = Button(
            text="▶ 开始测算",
            background_normal='', background_color=C_SUCCESS,
            color=(1,1,1,1), font_size=dp(15), bold=True,
            size_hint_y=None, height=dp(46)
        )
        btn_calc.bind(on_press=lambda _: self.app.calc_commercial(self))
        self._add(btn_calc)

        self.calc_result_label = Label(
            text="点击「开始测算」计算可装板数量和总容量",
            color=C_PRIMARY, font_size=dp(13),
            size_hint_y=None, height=dp(40),
            halign='center', text_size=(dp(500), dp(40))
        )
        self._add(self.calc_result_label)
        self._sep()

        # 保存按钮
        btn_save = Button(
            text="💾 保存踏勘信息",
            background_normal='', background_color=C_PRIMARY,
            color=(1,1,1,1), font_size=dp(15), bold=True,
            size_hint_y=None, height=dp(46)
        )
        btn_save.bind(on_press=lambda _: self.app.save_tankan_info(self))
        self._add(btn_save)

    def _switch_mode(self, mode):
        pass  # UI 切换在此可扩展显隐，当前移动端展示全部字段

    def _on_shape_changed(self, instance, value):
        pass  # 可在此动态显隐梯形/四边形/自定义字段

    def _on_site_changed(self, instance, value):
        self.app.on_site_changed(value, self)

    def refresh_site_spinner(self, sites, current_name):
        names = [s.get("name", f"场地{i+1}") for i, s in enumerate(sites)]
        self.site_spinner.values = names
        self.site_spinner.text = current_name if current_name in names else (names[0] if names else "")

    def load_data(self):
        p = self.app.current_project
        if not p:
            return
        t = p.tankan
        if t.survey_type == "工商业":
            self.btn_gongshang.state = 'down'
            self.btn_huyong.state = 'normal'
        else:
            self.btn_huyong.state = 'down'
            self.btn_gongshang.state = 'normal'

        # 户用字段
        self.longitude.text   = t.longitude or ""
        self.latitude.text    = t.latitude or ""
        self.house_floor.text = t.house_floor or self.house_floor.values[0]
        self.house_direction.text = t.house_direction or "正南"
        self.have_obstacle.text   = t.have_obstacle or ""
        self.grid_distance.text   = str(t.grid_distance) if t.grid_distance else ""
        self.roof_type_detail.text = t.roof_type_detail or "单坡阳光房"
        self.roof_panel_type.text  = t.roof_panel_type or "现浇板"
        self.roof_length.text      = str(t.roof_length) if t.roof_length else ""
        self.roof_width.text       = str(t.roof_width) if t.roof_width else ""
        self.install_area.text     = str(t.install_area) if t.install_area else ""
        self.panel_count_hy.text   = str(t.panel_count) if t.panel_count else ""
        self.panel_spec.text       = t.panel_spec or ""
        self.install_power.text    = str(t.install_power) if t.install_power else ""

        # 工商业：场地
        sites = t.sites or [_make_default_site("场地1")]
        self.refresh_site_spinner(sites, sites[0].get("name","场地1"))
        self._load_site_to_ui(sites[0])
        self._refresh_summary()

    def _load_site_to_ui(self, site):
        self.site_shape.text   = site.get("site_shape","矩形")
        self.site_length.text  = str(site.get("site_length",0))
        self.site_width.text   = str(site.get("site_width",0))
        self.site_gap.text     = str(site.get("site_gap",0.5))
        self.reserve_ratio.text = str(site.get("reserve_ratio",10))
        self.trap_top.text     = str(site.get("trap_top",0))
        self.trap_bottom.text  = str(site.get("trap_bottom",0))
        self.trap_height.text  = str(site.get("trap_height",0))
        self.quad_top.text     = str(site.get("quad_top",0))
        self.quad_bottom.text  = str(site.get("quad_bottom",0))
        self.quad_left.text    = str(site.get("quad_left",0))
        self.quad_right.text   = str(site.get("quad_right",0))
        self.custom_area.text  = str(site.get("custom_area",0))
        self.equiv_length.text = str(site.get("equiv_length",0))
        self.equiv_width.text  = str(site.get("equiv_width",0))
        self.panel_length_gs.text = str(site.get("panel_length",2.384))
        self.panel_width_gs.text  = str(site.get("panel_width",1.303))
        self.panel_power_gs.text  = str(site.get("panel_power",700))
        cnt = site.get("calc_panel_count",0)
        pw  = site.get("calc_total_power",0)
        if cnt > 0:
            self.calc_result_label.text = f"✅ 可装 {cnt} 块 / {pw:.2f} kW"
        else:
            self.calc_result_label.text = "点击「开始测算」计算可装板数量和总容量"

    def collect_site_to_dict(self):
        def f(ti, default=0.0):
            try:
                return float(ti.text)
            except Exception:
                return default
        return {
            "site_shape":    self.site_shape.text,
            "site_length":   f(self.site_length),
            "site_width":    f(self.site_width),
            "site_gap":      f(self.site_gap, 0.5),
            "reserve_ratio": int(f(self.reserve_ratio, 10)),
            "trap_top":      f(self.trap_top),
            "trap_bottom":   f(self.trap_bottom),
            "trap_height":   f(self.trap_height),
            "quad_top":      f(self.quad_top),
            "quad_bottom":   f(self.quad_bottom),
            "quad_left":     f(self.quad_left),
            "quad_right":    f(self.quad_right),
            "custom_area":   f(self.custom_area),
            "equiv_length":  f(self.equiv_length),
            "equiv_width":   f(self.equiv_width),
            "panel_length":  f(self.panel_length_gs, 2.384),
            "panel_width":   f(self.panel_width_gs, 1.303),
            "panel_power":   int(f(self.panel_power_gs, 700)),
        }

    def _refresh_summary(self):
        p = self.app.current_project
        if not p:
            return
        sites = p.tankan.sites
        total_power  = sum(s.get("calc_total_power",0) for s in sites)
        total_panels = sum(s.get("calc_panel_count",0) for s in sites)
        self.site_summary_label.text = (
            f"共 {len(sites)} 个场地 | 合计 {total_panels} 块 | {total_power:.2f} kW"
        )


# ─────────────────────────────────────────────
#  3. 资料管理 Screen
# ─────────────────────────────────────────────
class FilesScreen(BaseScreen):
    CATEGORIES = ["踏勘","备案","电网","设计","施工","并网","合同","照片","图纸","验收","身份证","房产证","发票","证书"]

    def build_ui(self):
        self._section("📁 资料管理")

        self.cate_spinner = make_spinner(self.CATEGORIES)
        self.cate_spinner.bind(text=self._on_cate_changed)
        self._add(form_row("文件分类", self.cate_spinner))
        self._sep()

        self.file_list_layout = GridLayout(
            cols=1, spacing=dp(4), size_hint_y=None, padding=[0,0,0,0]
        )
        self.file_list_layout.bind(minimum_height=self.file_list_layout.setter('height'))
        scroll = ScrollView(size_hint_y=None, height=dp(300))
        scroll.add_widget(self.file_list_layout)
        self._add(scroll)

        # 按钮行
        btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        b_pick = Button(text="📎 选择文件", background_normal='',
                        background_color=C_PRIMARY, color=(1,1,1,1), font_size=dp(13))
        b_open = Button(text="📄 打开", background_normal='',
                        background_color=get_color_from_hex('#6366f1'),
                        color=(1,1,1,1), font_size=dp(13))
        b_del  = Button(text="🗑 删除", background_normal='',
                        background_color=C_DANGER, color=(1,1,1,1), font_size=dp(13))
        b_pick.bind(on_press=lambda _: self.app.pick_file(self))
        b_open.bind(on_press=lambda _: self.app.open_file(self))
        b_del.bind(on_press=lambda _: self.app.delete_file(self))
        btn_row.add_widget(b_pick)
        btn_row.add_widget(b_open)
        btn_row.add_widget(b_del)
        self._add(btn_row)

        self.selected_file = None

    def _on_cate_changed(self, instance, value):
        self.load_data()

    def load_data(self):
        p = self.app.current_project
        self.file_list_layout.clear_widgets()
        if not p:
            return
        cate = self.cate_spinner.text
        files = p.files.get(cate, [])
        for f in files:
            btn = Button(
                text=os.path.basename(f),
                background_normal='', background_color=C_WHITE,
                color=C_TEXT, font_size=dp(12),
                size_hint_y=None, height=dp(36),
                halign='left', text_size=(dp(450), dp(36)),
                padding=[dp(8), 0]
            )
            btn.bind(on_press=lambda b, fp=f: self._select_file(b, fp))
            self.file_list_layout.add_widget(btn)

    def _select_file(self, btn, filepath):
        self.selected_file = filepath
        # 高亮选中
        for child in self.file_list_layout.children:
            child.background_color = C_WHITE
            child.color = C_TEXT
        btn.background_color = C_PRIMARY
        btn.color = (1,1,1,1)


# ─────────────────────────────────────────────
#  4. 设备配置 Screen
# ─────────────────────────────────────────────
class DeviceScreen(BaseScreen):
    def build_ui(self):
        self._section("🔹 光伏组件")
        self.pv_brand = make_spinner(list(PV_MODULES.keys()))
        self.pv_brand.bind(text=self._on_pv_brand_changed)
        self.pv_model = make_spinner(list(PV_MODULES[list(PV_MODULES.keys())[0]]))
        self.pv_num   = make_text_input("组件数量", text="1")

        self._add(form_row("组件品牌", self.pv_brand))
        self._add(form_row("组件型号", self.pv_model))
        self._add(form_row("组件数量", self.pv_num))
        self._sep()

        # 逆变器
        self._section("🔹 逆变器（可添加多台）")
        self.inv_brand = make_spinner(list(INVERTERS.keys()))
        self.inv_brand.bind(text=self._on_inv_brand_changed)
        self.inv_model = make_spinner(list(INVERTERS[list(INVERTERS.keys())[0]]))
        self.inv_num   = make_text_input("数量", text="1")

        self._add(form_row("逆变器品牌", self.inv_brand))
        self._add(form_row("逆变器型号", self.inv_model))
        self._add(form_row("数量",       self.inv_num))

        self.inv_list_label = Label(
            text="逆变器列表：（空）",
            color=C_MUTED, font_size=dp(12),
            size_hint_y=None, height=dp(60),
            halign='left', text_size=(dp(500), None)
        )
        self._add(self.inv_list_label)

        btn_add_inv = Button(
            text="➕ 添加到逆变器列表",
            background_normal='', background_color=C_SUCCESS,
            color=(1,1,1,1), font_size=dp(13),
            size_hint_y=None, height=dp(40)
        )
        btn_add_inv.bind(on_press=lambda _: self._add_inv())
        self._add(btn_add_inv)

        btn_clear_inv = Button(
            text="🗑 清空逆变器列表",
            background_normal='', background_color=C_DANGER,
            color=(1,1,1,1), font_size=dp(13),
            size_hint_y=None, height=dp(40)
        )
        btn_clear_inv.bind(on_press=lambda _: self._clear_inv())
        self._add(btn_clear_inv)
        self._sep()

        # 线缆
        self._section("🔹 线缆")
        self.dc_cable = make_spinner(DC_CABLE)
        self.dc_num   = make_text_input("直流线数量", text="1")
        self.ac_cable = make_spinner(AC_CABLE)
        self.ac_num   = make_text_input("交流线数量", text="1")
        self.box      = make_text_input("并网箱型号")
        self.anti     = make_text_input("防逆流装置型号")

        self._add(form_row("直流线缆", self.dc_cable))
        self._add(form_row("直流数量", self.dc_num))
        self._add(form_row("交流线缆", self.ac_cable))
        self._add(form_row("交流数量", self.ac_num))
        self._add(form_row("并网箱",   self.box))
        self._add(form_row("防逆流",   self.anti))

        # 总容量
        self.total_cap_label = Label(
            text="总装机容量：-- kW",
            color=C_SUCCESS, font_size=dp(16), bold=True,
            size_hint_y=None, height=dp(40),
            halign='center', text_size=(dp(400), dp(40))
        )
        self._add(self.total_cap_label)

        btn_save = Button(
            text="💾 保存设备配置",
            background_normal='', background_color=C_PRIMARY,
            color=(1,1,1,1), font_size=dp(15), bold=True,
            size_hint_y=None, height=dp(46)
        )
        btn_save.bind(on_press=lambda _: self.app.save_device_data(self))
        self._add(btn_save)

        self._inv_list = []  # [(brand, model, num)]

    def _on_pv_brand_changed(self, instance, value):
        models = PV_MODULES.get(value, [])
        self.pv_model.values = models
        self.pv_model.text   = models[0] if models else ""

    def _on_inv_brand_changed(self, instance, value):
        models = list(INVERTERS.get(value, []))
        self.inv_model.values = models
        self.inv_model.text   = models[0] if models else ""

    def _add_inv(self):
        try:
            num = int(self.inv_num.text)
        except Exception:
            num = 1
        entry = (self.inv_brand.text, self.inv_model.text, num)
        self._inv_list.append(entry)
        self._refresh_inv_label()

    def _clear_inv(self):
        self._inv_list = []
        self._refresh_inv_label()

    def _refresh_inv_label(self):
        if not self._inv_list:
            self.inv_list_label.text = "逆变器列表：（空）"
        else:
            lines = [f"  {b} {m} × {n}" for b, m, n in self._inv_list]
            self.inv_list_label.text = "逆变器列表：\n" + "\n".join(lines)
            self.inv_list_label.height = dp(20 + 20 * len(lines))

    def load_data(self):
        p = self.app.current_project
        if not p:
            return
        d = p.device
        if d.pv_brand in PV_MODULES:
            self.pv_brand.text = d.pv_brand
            models = PV_MODULES[d.pv_brand]
            self.pv_model.values = models
            if d.pv_model in models:
                self.pv_model.text = d.pv_model
        self.pv_num.text = str(d.pv_num)
        self._inv_list = [(r["brand"], r["model"], r["num"]) for r in (d.inv_list or [])]
        if not self._inv_list and d.inv_brand:
            self._inv_list = [(d.inv_brand, d.inv_model, d.inv_num)]
        self._refresh_inv_label()
        if d.dc_cable in DC_CABLE:
            self.dc_cable.text = d.dc_cable
        self.dc_num.text  = str(d.dc_num)
        ac_spec = ""
        if d.ac_cable_list:
            ac_spec = d.ac_cable_list[0].get("spec","")
            self.ac_num.text = str(d.ac_cable_list[0].get("num",1))
        elif d.ac_cable:
            ac_spec = d.ac_cable
            self.ac_num.text = str(d.ac_num)
        if ac_spec in AC_CABLE:
            self.ac_cable.text = ac_spec
        self.box.text  = d.box or ""
        self.anti.text = d.anti or ""
        self._update_total_cap()

    def _update_total_cap(self):
        p = self.app.current_project
        if not p:
            return
        try:
            pv_num  = int(self.pv_num.text)
            # 从踏勘计算
            sites = p.tankan.sites or []
            total_kw = sum(s.get("calc_total_power",0) for s in sites)
            if total_kw == 0:
                total_kw = p.kw
            self.total_cap_label.text = f"总装机容量：{total_kw:.2f} kW / {pv_num} 块"
        except Exception:
            pass

    def collect_data(self):
        p = self.app.current_project
        if not p:
            return
        d = p.device
        d.pv_brand = self.pv_brand.text
        d.pv_model = self.pv_model.text
        try:
            d.pv_num = int(self.pv_num.text)
        except Exception:
            d.pv_num = 1
        d.inv_list = [{"brand": b, "model": m, "num": n} for b, m, n in self._inv_list]
        if d.inv_list:
            d.inv_brand = d.inv_list[0]["brand"]
            d.inv_model = d.inv_list[0]["model"]
            d.inv_num   = d.inv_list[0]["num"]
        d.dc_cable = self.dc_cable.text
        try:
            d.dc_num = int(self.dc_num.text)
        except Exception:
            d.dc_num = 1
        d.ac_cable_list = [{
            "spec": self.ac_cable.text,
            "num": int(self.ac_num.text) if self.ac_num.text.isdigit() else 1
        }]
        d.ac_cable = self.ac_cable.text
        d.box  = self.box.text.strip()
        d.anti = self.anti.text.strip()


# ─────────────────────────────────────────────
#  5. 收益测算 Screen
# ─────────────────────────────────────────────
class ProfitScreen(BaseScreen):
    def build_ui(self):
        self._section("💰 收益测算")

        self.sun        = make_text_input("年等效日照时长(h)", text="1200")
        self.invest     = make_text_input("项目总投资(万元)")
        self.maintain   = make_text_input("年运维成本(%)", text="2.0")
        self.proj_years = make_spinner([str(i) for i in range(6,26)], "25")
        self.elect_price = make_text_input("上网电价(元/kWh)", text="0.39")
        self.self_use_rate = make_text_input("自用比例(%)", text="30")
        self.self_price = make_text_input("自用电价(元/kWh)", text="0.85")

        self._add(form_row("年日照时长", self.sun))
        self._add(form_row("总投资(万)", self.invest))
        self._add(form_row("运维成本%",  self.maintain))
        self._add(form_row("项目年限",   self.proj_years))
        self._add(form_row("上网电价",   self.elect_price))
        self._add(form_row("自用比例%",  self.self_use_rate))
        self._add(form_row("自用电价",   self.self_price))
        self._sep()

        btn_calc = Button(
            text="▶ 开始测算",
            background_normal='', background_color=C_SUCCESS,
            color=(1,1,1,1), font_size=dp(15), bold=True,
            size_hint_y=None, height=dp(46)
        )
        btn_calc.bind(on_press=lambda _: self._do_calc())
        self._add(btn_calc)

        self.result_label = Label(
            text="",
            color=C_PRIMARY, font_size=dp(13),
            size_hint_y=None, height=dp(300),
            halign='left', valign='top',
            text_size=(dp(540), None)
        )
        self._add(self.result_label)

    def load_data(self):
        p = self.app.current_project
        if not p:
            self.result_label.text = ""
            return
        self.invest.text = str(round(p.kw * 3.5, 2)) if p.kw else ""

    def _do_calc(self):
        p = self.app.current_project
        if not p:
            show_warning_message(None, "提示", "请先选择项目")
            return
        try:
            kw = p.kw or 0
            sun = float(self.sun.text)
            invest_wan = float(self.invest.text) if self.invest.text else kw * 3.5
            maintain_r = float(self.maintain.text) / 100
            years = int(self.proj_years.text)
            elect_price = float(self.elect_price.text)
            self_rate = float(self.self_use_rate.text) / 100
            self_price = float(self.self_price.text)

            year_gen = kw * sun  # 年发电量 kWh
            grid_gen = year_gen * (1 - self_rate)
            self_gen = year_gen * self_rate
            year_income = grid_gen * elect_price + self_gen * self_price
            year_maintain = invest_wan * 10000 * maintain_r
            year_net = year_income - year_maintain
            total_net = year_net * years
            payback = invest_wan * 10000 / year_net if year_net > 0 else 999

            lines = [
                f"📊 装机容量：{kw:.2f} kW",
                f"⚡ 年发电量：{year_gen:.0f} kWh",
                f"  ├ 上网电量：{grid_gen:.0f} kWh × ¥{elect_price} = ¥{grid_gen*elect_price:,.0f}",
                f"  └ 自用电量：{self_gen:.0f} kWh × ¥{self_price} = ¥{self_gen*self_price:,.0f}",
                f"💰 年收益：¥{year_income:,.0f}",
                f"🔧 年运维：¥{year_maintain:,.0f}",
                f"📈 年净收益：¥{year_net:,.0f}",
                f"📅 {years}年总收益：¥{total_net:,.0f}",
                f"💡 回收期：约 {payback:.1f} 年",
            ]
            self.result_label.text = "\n".join(lines)
            self.result_label.height = dp(30 * len(lines))
        except Exception as e:
            show_error_message(None, "计算错误", str(e))


# ─────────────────────────────────────────────
#  6. 项目付款 Screen
# ─────────────────────────────────────────────
class PaymentScreen(BaseScreen):
    def build_ui(self):
        self._section("🏗 项目付款")

        # 付款基本信息
        self.pay_proj    = make_text_input("项目名称")
        self.pay_panels  = make_text_input("组件数量")
        self.pay_uprice  = make_text_input("单价(元/块)")
        self.pay_company = make_text_input("公司名称")
        self.pay_tax_no  = make_text_input("税号")
        self.pay_bank    = make_text_input("开户银行")
        self.pay_bank_no = make_text_input("银行账号")

        self._add(form_row("项目名称", self.pay_proj))
        self._add(form_row("组件数量", self.pay_panels))
        self._add(form_row("单价(元)", self.pay_uprice))
        self._add(form_row("公司名称", self.pay_company))
        self._add(form_row("税号",     self.pay_tax_no))
        self._add(form_row("开户银行", self.pay_bank))
        self._add(form_row("银行账号", self.pay_bank_no))
        self._sep()

        # 付款批次
        self._section("付款批次列表")
        self.pay_list_label = Label(
            text="（暂无批次）",
            color=C_MUTED, font_size=dp(12),
            size_hint_y=None, height=dp(60),
            halign='left', text_size=(dp(500), None)
        )
        self._add(self.pay_list_label)

        # 新增批次
        batch_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.pay_batch_name   = make_spinner(["进度款","结算款","质保金","预付款","材料款","其他"])
        self.pay_batch_ratio  = make_text_input("比例(%)")
        self.pay_batch_amount = make_text_input("实付金额(元)")
        self.pay_batch_date   = make_text_input("付款日期")
        self.pay_batch_remark = make_text_input("备注")

        self._add(form_row("批次名",   self.pay_batch_name))
        self._add(form_row("比例(%)",  self.pay_batch_ratio))
        self._add(form_row("实付金额", self.pay_batch_amount))
        self._add(form_row("付款日期", self.pay_batch_date))
        self._add(form_row("备注",     self.pay_batch_remark))

        btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        b_add = Button(text="➕ 添加批次", background_normal='',
                       background_color=C_SUCCESS, color=(1,1,1,1), font_size=dp(13))
        b_del = Button(text="🗑 删除最后", background_normal='',
                       background_color=C_DANGER, color=(1,1,1,1), font_size=dp(13))
        b_add.bind(on_press=lambda _: self._add_batch())
        b_del.bind(on_press=lambda _: self._del_last_batch())
        btn_row.add_widget(b_add)
        btn_row.add_widget(b_del)
        self._add(btn_row)

        btn_save = Button(
            text="💾 保存付款信息",
            background_normal='', background_color=C_PRIMARY,
            color=(1,1,1,1), font_size=dp(15), bold=True,
            size_hint_y=None, height=dp(46)
        )
        btn_save.bind(on_press=lambda _: self.app.save_payment_data(self))
        self._add(btn_save)

    def _add_batch(self):
        p = self.app.current_project
        if not p:
            return
        try:
            ratio = float(self.pay_batch_ratio.text)
            amount = float(self.pay_batch_amount.text)
        except Exception:
            show_error_message(None, "输入错误", "请正确填写比例和金额")
            return
        batch = {
            "batch_name":   self.pay_batch_name.text,
            "ratio":        ratio,
            "paid_amount":  amount,
            "pay_date":     self.pay_batch_date.text.strip(),
            "remark":       self.pay_batch_remark.text.strip()
        }
        p.payments.append(batch)
        self._refresh_pay_list()

    def _del_last_batch(self):
        p = self.app.current_project
        if not p or not p.payments:
            return
        p.payments.pop()
        self._refresh_pay_list()

    def _refresh_pay_list(self):
        p = self.app.current_project
        if not p or not p.payments:
            self.pay_list_label.text = "（暂无批次）"
            self.pay_list_label.height = dp(40)
            return
        lines = []
        total_paid = 0
        for i, b in enumerate(p.payments, 1):
            amt = b.get("paid_amount",0)
            total_paid += amt
            lines.append(
                f"  {i}. {b.get('batch_name','')}  {b.get('ratio',0):.1f}%  "
                f"实付¥{amt:,.0f}  {b.get('pay_date','')}  {b.get('remark','')}"
            )
        lines.append(f"\n  合计实付：¥{total_paid:,.0f}")
        self.pay_list_label.text = "\n".join(lines)
        self.pay_list_label.height = dp(24 * len(lines) + 10)

    def load_data(self):
        p = self.app.current_project
        if not p:
            return
        pi = p.pay_info or {}
        self.pay_proj.text    = pi.get("proj_name","") or p.name
        self.pay_panels.text  = str(pi.get("panel_count","") or "")
        self.pay_uprice.text  = str(pi.get("unit_price","") or "")
        self.pay_company.text = pi.get("company","")
        self.pay_tax_no.text  = pi.get("tax_no","")
        self.pay_bank.text    = pi.get("bank","")
        self.pay_bank_no.text = pi.get("bank_no","")
        self._refresh_pay_list()

    def collect_data(self):
        p = self.app.current_project
        if not p:
            return
        try:
            panels = int(self.pay_panels.text)
        except Exception:
            panels = 0
        try:
            uprice = float(self.pay_uprice.text)
        except Exception:
            uprice = 0.0
        p.pay_info = {
            "proj_name":   self.pay_proj.text.strip(),
            "panel_count": panels,
            "unit_price":  uprice,
            "company":     self.pay_company.text.strip(),
            "tax_no":      self.pay_tax_no.text.strip(),
            "bank":        self.pay_bank.text.strip(),
            "bank_no":     self.pay_bank_no.text.strip(),
        }


# ─────────────────────────────────────────────
#  7. 导出报告 Screen
# ─────────────────────────────────────────────
class ReportScreen(BaseScreen):
    def build_ui(self):
        self._section("📄 导出报告")

        self.info_label = Label(
            text="选择需要导出的内容：",
            color=C_TEXT, font_size=dp(14),
            size_hint_y=None, height=dp(30),
            halign='left', text_size=(dp(500), dp(30))
        )
        self._add(self.info_label)

        btn_json = Button(
            text="📦 导出项目 JSON 数据",
            background_normal='', background_color=C_PRIMARY,
            color=(1,1,1,1), font_size=dp(14),
            size_hint_y=None, height=dp(46)
        )
        btn_json.bind(on_press=lambda _: self.app.export_json(self))
        self._add(btn_json)

        btn_summary = Button(
            text="📋 导出项目摘要（TXT）",
            background_normal='', background_color=get_color_from_hex('#6366f1'),
            color=(1,1,1,1), font_size=dp(14),
            size_hint_y=None, height=dp(46)
        )
        btn_summary.bind(on_press=lambda _: self.app.export_summary_txt(self))
        self._add(btn_summary)

        self.export_result = Label(
            text="",
            color=C_SUCCESS, font_size=dp(13),
            size_hint_y=None, height=dp(60),
            halign='left', text_size=(dp(500), dp(60))
        )
        self._add(self.export_result)

    def load_data(self):
        self.export_result.text = ""


# ─────────────────────────────────────────────
#  辅助：获取组件预设品牌列表
# ─────────────────────────────────────────────
def _get_presets():
    """获取光伏组件预置列表（复用 main.py 的逻辑）"""
    from dataclasses import dataclass
    @dataclass(frozen=True)
    class Ps:
        brand: str
    result = []
    for brand in PV_MODULES:
        result.append(Ps(brand=brand))
    return result


# ─────────────────────────────────────────────
#  主 App
# ─────────────────────────────────────────────
class PVApp(App):
    title = "☀ 光伏智云管理系统"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.projects: list = []
        self.current_project = None
        self._current_site_idx = 0

    # ─── 数据 I/O ───
    def load_data(self):
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.projects = [Project.from_dict(item) for item in data]
        except Exception as e:
            show_error_message(None, "加载失败", str(e))
            self.projects = []

    def save_data(self):
        try:
            dicts = [p.to_dict() for p in self.projects]
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(dicts, f, ensure_ascii=False, indent=2)
            os.makedirs(BACKUP_PATH, exist_ok=True)
            bk = os.path.join(BACKUP_PATH,
                              f"备份_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            shutil.copy2(DATA_FILE, bk)
        except Exception as e:
            show_error_message(None, "保存失败", str(e))

    # ─── 构建 UI ───
    def build(self):
        self.load_data()

        root = BoxLayout(orientation='horizontal')

        # 左侧导航
        self.nav = NavPanel(app_ref=self)
        root.add_widget(self.nav)

        # 右侧屏幕管理器
        self.sm = ScreenManager(transition=SlideTransition(duration=0.15))

        self.screen_project = ProjectScreen(app_ref=self, name='project')
        self.screen_tankan  = TankanScreen(app_ref=self, name='tankan')
        self.screen_files   = FilesScreen(app_ref=self, name='files')
        self.screen_device  = DeviceScreen(app_ref=self, name='device')
        self.screen_profit  = ProfitScreen(app_ref=self, name='profit')
        self.screen_payment = PaymentScreen(app_ref=self, name='payment')
        self.screen_report  = ReportScreen(app_ref=self, name='report')

        for s in [self.screen_project, self.screen_tankan, self.screen_files,
                  self.screen_device, self.screen_profit, self.screen_payment,
                  self.screen_report]:
            self.sm.add_widget(s)

        root.add_widget(self.sm)

        # 初始化项目列表
        self.refresh_project_list()
        return root

    # ─── 导航 ───
    def goto_screen(self, name):
        if self.sm.current != name:
            self.sm.current = name

    # ─── 项目管理 ───
    def refresh_project_list(self, keyword=""):
        kw = keyword.lower().strip()
        filtered = [p for p in self.projects
                    if not kw or kw in p.name.lower()]
        sel_name = self.current_project.name if self.current_project else None
        self.nav.refresh_list(filtered, selected_name=sel_name)

    def select_project(self, proj):
        self.current_project = proj
        self._current_site_idx = 0
        self.refresh_project_list()
        # 刷新当前屏幕
        cur = self.sm.current_screen
        if hasattr(cur, 'load_data'):
            cur.load_data()

    def add_project(self, *args):
        def _on_name(name):
            if not name:
                return
            if any(p.name == name for p in self.projects):
                show_warning_message(None, "重名", f"已存在项目「{name}」")
                return
            new_p = Project(name=name)
            self.projects.append(new_p)
            self.save_data()
            self.current_project = new_p
            self.refresh_project_list()
            self.goto_screen('project')
            self.screen_project.load_data()
        input_dialog("新增项目", "请输入项目名称：", _on_name)

    def delete_project(self, *args):
        if not self.current_project:
            show_warning_message(None, "提示", "请先选择项目")
            return
        name = self.current_project.name
        def _confirm(ok):
            if ok:
                self.projects = [p for p in self.projects if p.name != name]
                self.current_project = None
                self.save_data()
                self.refresh_project_list()
        confirm_action(None, "确认删除", f"确定要删除项目「{name}」吗？", _confirm)

    def manual_backup(self, *args):
        try:
            self.save_data()
            show_success_message(None, "备份成功", "数据已备份至备份目录")
        except Exception as e:
            show_error_message(None, "备份失败", str(e))

    def restore_backup(self, *args):
        show_warning_message(None, "提示", "请从备份目录手动复制 JSON 文件到应用目录")

    # ─── 项目信息保存 ───
    def save_project_info(self, screen):
        if not self.current_project:
            show_warning_message(None, "提示", "请先选择项目")
            return
        screen.collect_data()
        self.save_data()
        self.refresh_project_list()
        show_success_message(None, "保存成功", "项目信息已保存")

    # ─── 踏勘信息保存 ───
    def save_tankan_info(self, screen: TankanScreen):
        if not self.current_project:
            show_warning_message(None, "提示", "请先选择项目")
            return
        t = self.current_project.tankan
        t.survey_type = "工商业" if screen.btn_gongshang.state == 'down' else "户用"
        t.longitude   = screen.longitude.text.strip()
        t.latitude    = screen.latitude.text.strip()
        t.house_floor = screen.house_floor.text
        t.house_direction = screen.house_direction.text
        t.have_obstacle   = screen.have_obstacle.text
        try:
            t.grid_distance = float(screen.grid_distance.text)
        except Exception:
            t.grid_distance = 0.0
        t.roof_type_detail = screen.roof_type_detail.text
        t.roof_panel_type  = screen.roof_panel_type.text
        try:
            t.roof_length = float(screen.roof_length.text)
        except Exception:
            t.roof_length = 0.0
        try:
            t.roof_width = float(screen.roof_width.text)
        except Exception:
            t.roof_width = 0.0
        try:
            t.install_area = float(screen.install_area.text)
        except Exception:
            t.install_area = 0.0
        try:
            t.panel_count = int(screen.panel_count_hy.text)
        except Exception:
            t.panel_count = 0
        t.panel_spec = screen.panel_spec.text.strip()
        try:
            t.install_power = float(screen.install_power.text)
        except Exception:
            t.install_power = 0.0

        # 保存当前工商业场地
        site_data = screen.collect_site_to_dict()
        sites = t.sites or [_make_default_site("场地1")]
        idx = self._current_site_idx
        if 0 <= idx < len(sites):
            name = sites[idx].get("name", f"场地{idx+1}")
            site_data["name"] = name
            # 保留测算结果
            site_data["calc_panel_count"] = sites[idx].get("calc_panel_count",0)
            site_data["calc_total_power"]  = sites[idx].get("calc_total_power",0)
            sites[idx] = site_data
        t.sites = sites

        self.save_data()
        show_success_message(None, "保存成功", "踏勘信息已保存")

    # ─── 场地管理 ───
    def add_site(self):
        if not self.current_project:
            return
        # 先保存当前场地
        t = self.current_project.tankan
        sites = t.sites or [_make_default_site("场地1")]
        new_name = f"场地{len(sites)+1}"
        sites.append(_make_default_site(new_name))
        t.sites = sites
        self._current_site_idx = len(sites) - 1
        screen = self.screen_tankan
        screen.refresh_site_spinner(sites, new_name)

    def delete_site(self):
        if not self.current_project:
            return
        t = self.current_project.tankan
        sites = t.sites or []
        if len(sites) <= 1:
            show_warning_message(None, "提示", "至少保留一个场地")
            return
        idx = self._current_site_idx
        sites.pop(idx)
        t.sites = sites
        self._current_site_idx = max(0, idx - 1)
        screen = self.screen_tankan
        screen.refresh_site_spinner(sites, sites[self._current_site_idx].get("name","场地1"))
        screen._load_site_to_ui(sites[self._current_site_idx])

    def rename_site(self):
        if not self.current_project:
            return
        sites = self.current_project.tankan.sites
        idx = self._current_site_idx
        old = sites[idx].get("name","")
        def _on_name(name):
            if not name:
                return
            sites[idx]["name"] = name
            self.screen_tankan.refresh_site_spinner(sites, name)
        input_dialog("重命名场地", "新名称：", _on_name, default=old)

    def on_site_changed(self, site_name, screen: TankanScreen):
        if not self.current_project:
            return
        sites = self.current_project.tankan.sites
        for i, s in enumerate(sites):
            if s.get("name") == site_name:
                self._current_site_idx = i
                screen._load_site_to_ui(s)
                break

    # ─── 工商业测算 ───
    def calc_commercial(self, screen: TankanScreen):
        site_data = screen.collect_site_to_dict()
        shape   = site_data["site_shape"]
        gap     = site_data["site_gap"]
        reserve = site_data["reserve_ratio"] / 100
        pl      = site_data["panel_length"]
        pw      = site_data["panel_width"]
        pp      = site_data["panel_power"]

        try:
            if shape == "矩形":
                L = site_data["site_length"]
                W = site_data["site_width"]
                area = L * W
                use_L, use_W = L, W
            elif shape == "梯形":
                a = site_data["trap_top"]
                b = site_data["trap_bottom"]
                h = site_data["trap_height"]
                area = (a + b) * h / 2
                use_L = max(a, b)
                use_W = h
            elif shape == "四边形":
                t = site_data["quad_top"]
                bt = site_data["quad_bottom"]
                use_L = max(t, bt)
                use_W = (site_data["quad_left"] + site_data["quad_right"]) / 2
                area = use_L * use_W
            else:  # 自定义
                area = site_data["custom_area"]
                use_L = site_data["equiv_length"] or (area ** 0.5)
                use_W = site_data["equiv_width"]  or (area / max(use_L, 0.01))

            usable_area = area * (1 - reserve)
            step_L = pl + gap
            step_W = pw + gap
            cols = max(1, int(use_L / step_L))
            rows = max(1, int(use_W / step_W))
            target = cols * rows
            actual = min(target, int(usable_area / (pl * pw)))
            total_kw = actual * pp / 1000

            screen.calc_result_label.text = (
                f"✅ {cols}列 × {rows}行 = {target}块 → 可用面积约装 {actual}块 / {total_kw:.2f} kW"
            )

            # 写回场地测算结果
            if self.current_project:
                sites = self.current_project.tankan.sites
                idx = self._current_site_idx
                if 0 <= idx < len(sites):
                    sites[idx].update(site_data)
                    sites[idx]["calc_panel_count"] = actual
                    sites[idx]["calc_total_power"]  = total_kw
                    sites[idx]["_layout_rows"] = rows
                    sites[idx]["_layout_cols"] = cols
            screen._refresh_summary()
        except Exception as e:
            show_error_message(None, "测算错误", str(e))

    # ─── 文件管理 ───
    def pick_file(self, screen: FilesScreen):
        """Android 端通过 plyer 文件选择器，桌面端简单弹窗提示"""
        try:
            from plyer import filechooser
            def _on_sel(selection):
                if not selection or not self.current_project:
                    return
                cate = screen.cate_spinner.text
                proj_path = os.path.join(ROOT_PATH, self.current_project.name, cate)
                os.makedirs(proj_path, exist_ok=True)
                for src in selection:
                    fname = os.path.basename(src)
                    dst = os.path.join(proj_path, fname)
                    shutil.copy2(src, dst)
                    if dst not in self.current_project.files.get(cate, []):
                        self.current_project.files.setdefault(cate, []).append(dst)
                self.save_data()
                screen.load_data()
            filechooser.open_file(on_selection=_on_sel, multiple=True)
        except Exception:
            show_warning_message(None, "提示", "请确保已安装 plyer，或直接将文件放入项目目录")

    def open_file(self, screen: FilesScreen):
        if not screen.selected_file:
            show_warning_message(None, "提示", "请先选择文件")
            return
        try:
            if sys.platform.startswith('android'):
                from android.permissions import request_permissions, Permission
                # Android 使用 Intent 打开
                import subprocess
                subprocess.Popen(['am', 'start', '--data-uri', screen.selected_file])
            elif sys.platform == 'win32':
                os.startfile(screen.selected_file)
            else:
                import subprocess
                subprocess.Popen(['xdg-open', screen.selected_file])
        except Exception as e:
            show_error_message(None, "打开失败", str(e))

    def delete_file(self, screen: FilesScreen):
        if not screen.selected_file or not self.current_project:
            return
        fp = screen.selected_file
        def _confirm(ok):
            if ok:
                cate = screen.cate_spinner.text
                files = self.current_project.files.get(cate, [])
                if fp in files:
                    files.remove(fp)
                try:
                    if os.path.exists(fp):
                        os.remove(fp)
                except Exception:
                    pass
                screen.selected_file = None
                self.save_data()
                screen.load_data()
        confirm_action(None, "确认删除", f"确定删除文件 {os.path.basename(fp)}？", _confirm)

    # ─── 设备配置保存 ───
    def save_device_data(self, screen: DeviceScreen):
        if not self.current_project:
            show_warning_message(None, "提示", "请先选择项目")
            return
        screen.collect_data()
        self.save_data()
        show_success_message(None, "保存成功", "设备配置已保存")

    # ─── 付款保存 ───
    def save_payment_data(self, screen: PaymentScreen):
        if not self.current_project:
            show_warning_message(None, "提示", "请先选择项目")
            return
        screen.collect_data()
        self.save_data()
        show_success_message(None, "保存成功", "付款信息已保存")

    # ─── 导出 ───
    def export_json(self, screen: ReportScreen):
        if not self.current_project:
            show_warning_message(None, "提示", "请先选择项目")
            return
        try:
            out_path = os.path.join(
                ROOT_PATH, self.current_project.name,
                f"{self.current_project.name}_导出.json"
            )
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(self.current_project.to_dict(), f, ensure_ascii=False, indent=2)
            screen.export_result.text = f"✅ 已导出：{out_path}"
        except Exception as e:
            show_error_message(None, "导出失败", str(e))

    def export_summary_txt(self, screen: ReportScreen):
        if not self.current_project:
            show_warning_message(None, "提示", "请先选择项目")
            return
        p = self.current_project
        try:
            lines = [
                f"【{p.name}】项目摘要",
                f"导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "=" * 40,
                f"项目类型：{p.type}",
                f"并网模式：{p.mode}",
                f"装机容量：{p.kw} kW",
                f"电站地址：{p.station_addr}",
                f"建设方：{p.builder}",
                "─" * 40,
                f"联系人：{p.user_name or p.legal_person}",
                f"联系电话：{p.id_number or p.legal_phone}",
                "─" * 40,
            ]
            sites = p.tankan.sites or []
            if sites:
                lines.append("工商业场地：")
                for s in sites:
                    lines.append(
                        f"  {s.get('name','')}：{s.get('calc_panel_count',0)}块 / {s.get('calc_total_power',0):.2f}kW"
                    )
            if p.payments:
                lines.append("付款批次：")
                total_paid = 0
                for b in p.payments:
                    amt = b.get("paid_amount",0)
                    total_paid += amt
                    lines.append(f"  {b.get('batch_name','')} ¥{amt:,.0f} {b.get('pay_date','')}")
                lines.append(f"  合计：¥{total_paid:,.0f}")

            content = "\n".join(lines)
            out_path = os.path.join(
                ROOT_PATH, p.name, f"{p.name}_摘要.txt"
            )
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(content)
            screen.export_result.text = f"✅ 已导出：{out_path}"
        except Exception as e:
            show_error_message(None, "导出失败", str(e))


# ─────────────────────────────────────────────
#  入口
# ─────────────────────────────────────────────
if __name__ == "__main__":
    PVApp().run()
