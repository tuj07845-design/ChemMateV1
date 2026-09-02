import os
import json
import win32com.client as win32

 ============================================================
# 一、类型知识库
# ============================================================
# 【作用】拿到设备真实类型名（如 RStoic）后，查这个字典就能知道：
#    - 中文名 / 类别（category）
#    - 该类型最值得读的"招牌参数"（参数名 → 中文说明）
#
# 注意：参数名如果模型里不存在，会在挑选时自动跳过，
#       不会报错；全部参数仍可从 all_parameters 拿到。

TYPE_KNOWLEDGE = {

    "Pump": {
        "category": "泵",
        "key_parameters": {
            "DISCHARGE_P": "出口压力",
            "EFF": "效率",
            "POWER_REQ": "所需功率",
            "PRES_RATIO": "增压比",
            "VFRAC": "出口气相分率",
            "TEMP": "出口温度",
        },
    },

    "Compr": {
        "category": "压缩机",
        "key_parameters": {
            "DISCHARGE_P": "出口压力",
            "PRES_RATIO": "压缩比",
            "EFF": "效率",
            "POWER_REQ": "轴功率",
            "TEMP": "出口温度",
            "PMODEL": "性能模型",
        },
    },

    "Mixer": {
        "category": "混合器",
        "key_parameters": {
            "NPHASE": "相数",
            "TEMP": "出口温度",
            "PRES": "出口压力",
            "DUTY": "热负荷",
            "BLKOPFREWAT": "自由水选项",
        },
    },

    "Heater": {
        "category": "加热器/冷却器",
        "key_parameters": {
            "TEMP": "出口温度",
            "PRES": "出口压力",
            "DUTY": "热负荷",
            "VFRAC": "出口气相分率",
            "HEATOPT": "热负荷选项",
            "SPEC_OPT": "规定选项(TP/TQ)",
            "DELT": "温差",
        },
    },

    "RStoic": {
        "category": "化学计量反应器",
        "key_parameters": {
            "TEMP": "反应温度",
            "PRES": "反应压力",
            "DUTY": "热负荷",
            "HEATOPT": "热负荷选项",
            "VFRAC": "出口气相分率",
            "STOIC": "化学计量式",
        },
    },

    "Flash2": {
        "category": "两相闪蒸罐",
        "key_parameters": {
            "TEMP": "闪蒸温度",
            "PRES": "闪蒸压力",
            "DUTY": "热负荷",
            "VFRAC": "气相分率",
            "SPEC_OPT": "规定选项",
            "NPHASE": "相数",
        },
    },

    "RadFrac": {
        "category": "严格精馏塔",
        "key_parameters": {
            "BASIS_RR": "回流比",
            "BASIS_D": "馏出物量",
            "NSTAGE": "塔板数",
            "BEG_STAGES": "进料板",
            "CONDENSER": "冷凝器",
            "REBOILER": "再沸器",
            "ALGORITHM": "算法",
            "CALC_MODE": "计算模式",
            "CA_DIAM": "塔径",
            "ABSORBER": "是否吸收塔",
            "BASIS_B": "塔底采出量",
            "TOP_PRES": "塔顶压力",
            "BOT_PRES": "塔底压力",
        },
    },

    "HeatX": {
        "category": "换热器",
        "key_parameters": {
            "AREA": "换热面积",
            "DUTY": "热负荷",
            "LMTD": "对数平均温差",
            "CALC_MODE": "计算模式",
            "HOT_TEMP": "热流出口温度",
            "COLD_TEMP": "冷流出口温度",
        },
    },

    "DSTWU": {
        "category": "简捷精馏塔",
        "key_parameters": {
            "RR": "回流比",
            "NSTAGE": "理论板数",
            "LIGHT_KEY": "轻关键组分",
            "HEAVY_KEY": "重关键组分",
            "CONDENSER": "冷凝器类型",
        },
    },

    "RCSTR": {
        "category": "连续搅拌反应器",
        "key_parameters": {
            "TEMP": "反应温度",
            "PRES": "反应压力",
            "DUTY": "热负荷",
            "HEATOPT": "热负荷选项",
            "VOLUME": "反应器体积",
            "VFRAC": "出口气相分率",
        },
    },

    "RPlug": {
        "category": "平推流反应器",
        "key_parameters": {
            "TEMP": "反应温度",
            "PRES": "反应压力",
            "DUTY": "热负荷",
            "LENGTH": "管长",
            "DIAMETER": "管径",
        },
    },

    "RGibbs": {
        "category": "吉布斯反应器",
        "key_parameters": {
            "TEMP": "反应温度",
            "PRES": "反应压力",
            "DUTY": "热负荷",
            "VFRAC": "出口气相分率",
        },
    },

    "RYield": {
        "category": "收率反应器",
        "key_parameters": {
            "TEMP": "反应温度",
            "PRES": "反应压力",
            "DUTY": "热负荷",
            "YIELD": "收率",
        },
    },

    "Valve": {
        "category": "阀门",
        "key_parameters": {
            "DISCHARGE_P": "出口压力",
            "PDROP": "压降",
            "CV": "流量系数",
            "PERCENT_OPEN": "开度",
        },
    },

    "Sep": {
        "category": "分离器",
        "key_parameters": {
            "SPLIT_FRAC": "分离分率",
            "TEMP": "温度",
            "PRES": "压力",
        },
    },

}

# 类别兜底：知识库里没有的类型，统一归为"其他"
DEFAULT_CATEGORY = "其他"
