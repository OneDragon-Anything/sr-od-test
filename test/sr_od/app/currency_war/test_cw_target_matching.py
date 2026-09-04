"""货币战争 target comp 牌归属匹配测试(流派/阵营全羁绊;ADR-0103)。

ADR-0517 迁移批:cw_deploy_seat(_card_hits_target/_card_supports_target)随 flow.py
死码簇传递性删除(生产零调用),其直接测试同批移除;全羁绊语义的存活载体 =
``_char_synergies``(下方锁定)。原验证 ``_card_hits_target`` 用角色**全羁绊**(阵营 + 流派 + 独立)匹配 ``comp.factions`` —— 治本流派
断裂(旧 ``card.faction in target.factions`` 只阵营,流派主派 comp 的过渡/补充角色被误判 off-target)。

**起因**:实跑 DOT 队 P1 输 —— 艾丝妲/椒丘等持续伤害流派角色 ``card.faction``=银河学者/空(= ``Character.factions[0]``,只阵营)∉ DOT.factions([持续伤害(流派), 星核猎手(阵营)])→ commit 后被 prefilter 跳过 → 凑不出 2DOT 过渡。DOT 队为流派主派典型。
"""
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_economy import _char_synergies


def test_char_synergies_includes_flows_and_independent() -> None:
    """_char_synergies 含流派 + 独立,不只阵营(factions[0])。"""
    assert _char_synergies("艾丝妲") == {"银河学者", "持续伤害"}
    assert _char_synergies("桑博") == {"贝洛伯格", "星间旅人", "持续伤害"}
    assert _char_synergies("椒丘") == {"狼狩", "持续伤害", "减益"}      # trait 对齐 plaza:+狼狩(2026-08-15)
    assert _char_synergies("姬子·启行") == {"列车同行", "领航员"}       # 含独立羁绊
    assert _char_synergies("未识别角色") == set()                       # 不在注册表 → 空


def test_equip_allocation_carry_first() -> None:
    """carry 先拿 key_equips 按序(multiplicity);其余 core 次之;容量上限 3。"""
    from types import SimpleNamespace

    from sr_od.application.currency_war.kernel.cw_comps import EQUIP_CAPACITY, equip_allocation

    lt = get_comp("列车同行")   # key_equips: 风暴潮×1/电锯/自适应外骨骼/冷笑话(W55);carry=姬子·启行
    dep = [SimpleNamespace(char_id='三月七', position_pref='back', slot=1),
           SimpleNamespace(char_id='姬子·启行', position_pref='front', slot=2)]
    # W55(R2 §1):池内 以牙还牙甲→自适应外骨骼(三月七=A 流吸仇恨件,甲属姬子拆分批)
    alloc = equip_allocation(lt, dep, ['火力风暴潮', '高周波电锯', '自适应外骨骼', '蓄能帆'])
    # 姬子(carry)按序拿 key(API 口径:风暴/电锯/外骨骼;ADR-0209 换血)
    jz = [e for c, e in alloc if c == '姬子·启行']
    assert jz == ['火力风暴潮', '高周波电锯', '自适应外骨骼'], f"carry 按序拿 key,得 {jz}"
    # 三月七(core)拿第四件(自适应外骨骼不在池 → 通用兜底:蓄能帆)
    sy = [e for c, e in alloc if c == '三月七']
    assert sy == ['蓄能帆'], f"core 兜底拿剩余,得 {sy}"


def test_equip_allocation_capacity_and_fallback() -> None:
    """容量扣减(已穿 3 = 满)与 comp=None 通用兜底(r232 轮转)。

    r232 行为变更(用户实锤「无脑给前台1」修复):comp=None
    从「deployed 顺序灌满第一人」改为**轮转分配**(每人 1 件
    一圈再回头)——前排先序保留,但不再独占。"""
    from types import SimpleNamespace

    from sr_od.application.currency_war.kernel.cw_comps import equip_allocation

    dep = [SimpleNamespace(char_id='瓦尔特', position_pref='front', slot=1),
           SimpleNamespace(char_id='符玄', position_pref='back', slot=2)]
    # comp=None → 轮转:瓦尔特先拿第一件,符玄拿第二件
    # (r232 前:瓦尔特全拿)
    alloc = equip_allocation(None, dep, ['永动机', '蓄能帆'])
    assert alloc == [('瓦尔特', '永动机'), ('符玄', '蓄能帆')]
    # 容量:瓦尔特已穿满 3 → 让位给符玄
    occ = {('front', 1): ['a', 'b', 'c']}
    alloc2 = equip_allocation(None, dep, ['永动机'], occ)
    assert alloc2 == [('符玄', '永动机')]
