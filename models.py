import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any, List, Optional


def _make_default_site(name="场地1"):
    """创建默认场地数据"""
    return {
        "name": name,
        # 场地参数
        "site_shape": "矩形",
        "site_length": 0.0,
        "site_width": 0.0,
        "site_gap": 0.5,
        "reserve_ratio": 10,
        # 梯形参数
        "trap_top": 0.0,
        "trap_bottom": 0.0,
        "trap_height": 0.0,
        # 四边形参数
        "quad_top": 0.0,
        "quad_bottom": 0.0,
        "quad_left": 0.0,
        "quad_right": 0.0,
        "quad_diag_type": "左上-右下",
        "quad_diag_len": 0.0,
        # 自定义面积
        "custom_area": 0.0,
        "equiv_length": 0.0,
        "equiv_width": 0.0,
        # 组件参数
        "panel_model": "",
        "panel_length": 2.384,
        "panel_width": 1.303,
        "panel_power": 700,
        # 测算结果（自动计算）
        "calc_panel_count": 0,
        "calc_total_power": 0.0,
    }


@dataclass
class TankanData:
    """踏勘数据模型（支持户用/工商业双模式，工商业支持多场地）"""
    # 通用字段
    survey_type: str = "户用"  # "户用" 或 "工商业"
    survey_note: str = ""

    # 户用字段（精简版）
    longitude: str = ""
    latitude: str = ""
    house_floor: str = ""
    house_height: float = 0.0
    house_span: float = 0.0
    build_time: str = ""
    house_age: int = 0
    grid_distance: float = 0.0
    neighbor_agree: str = "无异议"
    house_direction: str = "正南"
    have_obstacle: str = ""
    install_area: float = 0.0
    panel_count: int = 0
    panel_spec: str = ""
    install_power: float = 0.0
    roof_type_detail: str = ""
    roof_panel_type: str = ""
    roof_length: float = 0.0
    roof_width: float = 0.0

    # 工商业字段（列表：支持多个场地）
    sites: List[Dict[str, Any]] = field(default_factory=lambda: [_make_default_site("场地1")])


@dataclass
class DeviceData:
    """设备配置模型"""
    pv_brand: str = "通威"
    pv_model: str = ""
    pv_num: int = 1
    # 单逆变器字段（兼容旧数据）
    inv_brand: str = "固德威"
    inv_model: str = ""
    inv_num: int = 1
    # 多型号逆变器列表 [{"brand":..., "model":..., "num":...}, ...]
    inv_list: List[Dict] = field(default_factory=list)
    dc_cable: str = ""
    dc_num: int = 1
    ac_cable: str = ""  # 单交流线字段（兼容旧数据）
    ac_num: int = 1
    # 多型号交流线列表 [{"spec": "规格", "num": 数量}, ...]
    ac_cable_list: List[Dict] = field(default_factory=list)
    box: str = ""
    anti: str = ""


@dataclass
class Project:
    """项目核心模型（统一管理所有数据）"""
    name: str
    type: str = "户用光伏"
    mode: str = "全额上网"
    # 基础信息
    station_code: str = ""
    station_name: str = ""
    roof_type: str = ""
    station_addr: str = ""
    station_detail_addr: str = ""
    station_detail_text: str = ""
    # 项目信息
    proj_belong: str = ""
    proj_company: str = ""
    annual_rent: float = 0.0
    builder: str = ""
    general: str = ""
    # 农户信息（户用模式）
    id_number: str = ""  # 折号/手机号
    user_name: str = ""  # 个人姓名
    gender: str = "男"
    marriage: str = "已婚"
    birth_date: str = ""
    age: int = 0
    id_valid_start: str = ""
    id_card: str = ""  # 身份证号
    id_valid_end: str = ""
    id_addr: str = ""  # 身份证地址
    # 工商业单位信息
    company_name: str = ""  # 单位名称
    business_license: str = ""  # 统一社会信用代码
    legal_person: str = ""  # 法人姓名
    legal_phone: str = ""  # 法人电话
    company_addr: str = ""  # 单位地址
    # 收益卡信息
    bank_card: str = ""
    bank_branch: str = ""
    # 核心参数
    kw: float = 0.0
    trans: float = 0.0
    area: float = 0.0
    user: str = ""
    note: str = ""
    progress: List = field(default_factory=lambda: [""]*6)
    # 子模型
    tankan: TankanData = field(default_factory=TankanData)
    device: DeviceData = field(default_factory=DeviceData)
    load: Dict[str, float] = field(default_factory=lambda: {"day":0,"month":0,"rate":70,"use":0})
    files: Dict[str, list] = field(default_factory=lambda: {
        "踏勘":[], "备案":[], "电网":[], "设计":[], "施工":[], 
        "并网":[], "合同":[], "照片":[], "图纸":[], "验收":[], 
        "身份证":[], "房产证":[], "发票":[], "证书":[]
    })

    # 工程付款
    payments: List[Dict] = field(default_factory=list)
    pay_info: Dict[str, Any] = field(default_factory=lambda: {
        "proj_name": "", "panel_count": 0, "unit_price": 0.0,
        "company": "", "tax_no": "", "bank": "", "bank_no": ""
    })
    
    # 居间人付款
    inter_payments: List[Dict] = field(default_factory=list)
    inter_pay_info: Dict[str, Any] = field(default_factory=lambda: {
        "name": "", "phone": "", "idcard": "", "bank": "", "bank_no": "",
        "unit_price": 0.0, "capacity": 0.0
    })

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（支持JSON保存）"""
        data = asdict(self)
        # 处理dataclass嵌套
        data["tankan"] = asdict(self.tankan)
        data["device"] = asdict(self.device)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        """从字典反序列化"""
        # 过滤 tankan 中已删除的字段，兼容旧数据
        tankan_dict = data.pop("tankan", {})
        valid_tankan_fields = {f.name for f in TankanData.__dataclass_fields__.values()}
        tankan_filtered = {k: v for k, v in tankan_dict.items() if k in valid_tankan_fields}

        # 兼容旧数据：旧的 commercial 字段 → 转换为 sites 列表
        if "commercial" in tankan_filtered and "sites" not in tankan_filtered:
            old_commercial = tankan_filtered.pop("commercial")
            if isinstance(old_commercial, dict) and old_commercial.get("site_shape"):
                old_commercial["name"] = "场地1"
                tankan_filtered["sites"] = [old_commercial]
            else:
                tankan_filtered["sites"] = [_make_default_site("场地1")]
        elif "sites" not in tankan_filtered:
            tankan_filtered["sites"] = [_make_default_site("场地1")]

        tankan_data = TankanData(**tankan_filtered)

        device_dict = data.pop("device", {})
        valid_device_fields = {f.name for f in DeviceData.__dataclass_fields__.values()}
        device_filtered = {k: v for k, v in device_dict.items() if k in valid_device_fields}
        device_data = DeviceData(**device_filtered)

        # 兼容旧数据（无 pay_info / payments 字段）
        data.setdefault("payments", [])
        data.setdefault("pay_info", {
            "proj_name": "", "panel_count": 0, "unit_price": 0.0,
            "company": "", "tax_no": "", "bank": "", "bank_no": ""
        })
        # 兼容旧数据（无居间人付款字段）
        data.setdefault("inter_payments", [])
        data.setdefault("inter_pay_info", {
            "name": "", "phone": "", "idcard": "", "bank": "", "bank_no": "",
            "unit_price": 0.0, "capacity": 0.0
        })
        return cls(**data, tankan=tankan_data, device=device_data)
