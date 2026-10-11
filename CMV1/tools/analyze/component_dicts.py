COMPONENT_ALIASES = {
    # 中文名（用户/Agent 常用） → 该组分的可能键名（Component ID / Component Name / 分子式别名）

    # ---------- 气体 / 小分子 ----------
    "氢气": ["H2", "HYDROGEN"],
    "氢":   ["H2", "HYDROGEN"],
    "氮气": ["N2", "NITROGEN"],
    "氮":   ["N2", "NITROGEN"],
    "氧气": ["O2", "OXYGEN"],
    "氧":   ["O2", "OXYGEN"],
    "一氧化碳": ["CO", "CARBON-MONOXIDE"],
    "二氧化碳": ["CO2", "CARBON-DIOXIDE"],
    "硫化氢": ["H2S", "HYDROGEN-SULFIDE"],
    "氨":    ["NH3", "AMMONIA", "H3N"],

    # ---------- 链烷烃 ----------
    "甲烷": ["CH4", "METHANE"],
    "乙烷": ["C2H6", "ETHANE"],
    "丙烷": ["C3H8", "PROPANE"],
    "正丁烷": ["N-BUT-01", "N-BUTANE", "C4H10-1"],
    "异丁烷": ["ISOBU-01", "ISOBUTANE", "C4H10-2"],
    "正戊烷": ["N-PEN-01", "N-PENTANE", "C5H12-1"],
    "异戊烷(2-甲基丁烷)": ["2-MET-01", "2-METHYL-BUTANE", "C5H12-2"],
    "正己烷": ["HEXANE", "N-HEXANE", "C6H14-1"],
    "正庚烷": ["HEPTANE", "N-HEPTANE", "C7H16-1"],
    "正辛烷": ["OCTANE", "N-OCTANE", "C8H18-1"],
    "正癸烷": ["DECANE", "N-DECANE", "C10H22-1"],

    # ---------- 烯烃 / 环烷烃 ----------
    "乙烯": ["ETHYLENE", "C2H4"],
    "丙烯": ["PROPENE", "C3H6"],
    "环戊烷": ["CYC5", "CYCLOPENTANE", "C5H10-3"],
    "环己烷": ["CYCLO-01", "CYCLOHEXANE", "C6H12-1"],

    # ---------- 芳烃 ----------
    "苯":   ["BENZENE", "C6H6"],
    "甲苯": ["TOLUE-01", "TOLUENE", "C7H8"],
    "乙苯": ["ETHYL-BENZENE", "C8H10-4"],
    "对二甲苯": ["P-XYLENE", "C8H10-2"],
    "邻二甲苯": ["O-XYLENE", "C8H10-1"],
    "异丙苯": ["PRO-BEN", "CUMENE", "C9H12"],

    # ---------- 醇 ----------
    "水":   ["H2O", "WATER"],
    "甲醇": ["METHANOL", "CH3OH", "CH4O"],
    "乙醇": ["ETHAN-01", "ETHANOL", "C2H6O-2"],
    "异丙醇": ["ISOPR-01", "ISOPROPYL-ALCOHOL", "C3H8O-2"],
    "正丁醇": ["N-BUTANOL", "N-BUTAN-1-OL", "C4H10O-1"],

    # ---------- 醛 / 酮 / 酸 ----------
    "丙醛": ["N-PRO-01", "N-PROPIONALDEHYDE", "C3H6O-3"],
    "丙酮": ["ACETONE", "C3H6O-1"],
    "丁酮": ["MEK", "METHYL-ETHYL-KETONE", "C4H8O-3"],
    "乙酸": ["CH3COOH", "ACETIC-ACID", "C2H4O2-1"],
    "甲酸": ["FORMI-01", "FORMIC-ACID", "CH2O2"],
    "乙腈": ["ACETO-01", "ACETONITRILE", "C2H3N"],
    "苯酚": ["PHENOL", "C6H6O"],

    # ---------- 其他 ----------
    "二甲醚": ["ETHER", "DIMETHYL-ETHER", "C2H6O-3"],
    "1,2-二氯丙烷": ["1:2-D-01", "1,2-DICHLOROPROPANE"],
}