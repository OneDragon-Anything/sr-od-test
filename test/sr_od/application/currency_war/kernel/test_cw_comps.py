"""cw_comps 条目与机器的回归锁(镜像 src = kernel/cw_comps.py)。

两主题:①gift_hit_tier 送卡档位机器(此前零直测,本锁 = 估值域「现值
不变」防线;测试面依据 = T-28 设计稿(迭代 2026-09-23-invest-effects-calc)
§2.5 + §4.3:条件分支建模批对估值域零动作——持续伤害契约(即时集非空,
走规则①即时优先)的档位由 COMP_LIBRARY 数据派生,不得随条件分支引擎
落地漂移);②终局希儿量子条目改档结构锁与 fp 曲线(档 0 = 量4+贝4
纯 AND/档 1 = 战技点2/治疗2 加分层;条目值单一源 = cw_comps 本体,
fp 折算契约 = form_progress docstring)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_comps import (
    COMMIT_FRAC,
    COMP_LIBRARY,
    Comp,
    derive_member_priority,
    form_progress,
    get_comp,
    gift_hit_tier,
    member_rank_of,
)
from sr_od.application.currency_war.kernel.cw_investments import ENV_GIFTS


class _Box:
    """form_progress 鸭型读的最小值箱(属性名与状态容器视图对齐)。"""

    def __init__(self, value: object) -> None:
        self.value = value


class _Slots:
    """deployed 视图最小桩(front/back 槽位单位,鸭型同名读口)。"""

    def __init__(self, *front_names: str) -> None:
        self.front_slots = [SimpleNamespace(char_id=n) for n in front_names]
        self.back_slots: list[SimpleNamespace] = []


class _Panel:
    """轻量假想面板桩:board.value = 羁绊计数 dict + deployed 视图
    (required_deployed 在板判定;缺省 deployed 视图 = 按 0 计保守向)。"""

    def __init__(self, board: dict[str, int],
                 front: tuple[str, ...] = ()) -> None:
        self.board = _Box(dict(board))
        self.deployed = _Box(_Slots(*front))


def test_dot_contract_gift_tier_unchanged() -> None:
    """持续伤害契约估值档位现值锁(T-28 设计稿 §2.5 估值域零动作):
    即时集 {椒丘, 卡芙卡} 非空 → 规则①即时优先取成员最优档;卡芙卡在
    DOT 队等套为 core(COMP_LIBRARY 分档数据派生,档位语义单一源 =
    gift_hit_tier docstring),整卡档 = 'core'。条件分支建模(猜测写+证实)
    不触碰估值域,本值漂移 = 回归信号。"""
    assert gift_hit_tier(ENV_GIFTS['持续伤害契约']) == 'core'


def test_concept_stock_gift_tier_off() -> None:
    """追击概念股估值档恒 'off'(概念股族模式卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记):档位机器只读 chars_immediate/
    chars_conditional 两个具名估值域字段,随机规格(阵营轴)/随机装备
    条目不入 → 恒 off → named_gift_value 恒 0——登记概念股不产生策略层
    双重计分(与策略层 random_faction_gift_value 随机阵营路径正交)。"""
    assert gift_hit_tier(ENV_GIFTS['追击概念股']) == 'off'


def test_ranxue_concept_stock_gift_tier_off() -> None:
    """燃血概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第二实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交。"""
    assert gift_hit_tier(ENV_GIFTS['燃血概念股']) == 'off'


def test_nengliang_concept_stock_gift_tier_off() -> None:
    """能量概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第三实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交。"""
    assert gift_hit_tier(ENV_GIFTS['能量概念股']) == 'off'


def test_lieche_concept_stock_gift_tier_off() -> None:
    """列车同行概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第四实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交。"""
    assert gift_hit_tier(ENV_GIFTS['列车同行概念股']) == 'off'


def test_yinhe_concept_stock_gift_tier_off() -> None:
    """银河学者概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第五实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交。"""
    assert gift_hit_tier(ENV_GIFTS['银河学者概念股']) == 'off'


def test_beluoboge_concept_stock_gift_tier_off() -> None:
    """贝洛伯格概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第六实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(注册表修正使贝洛伯格期望域扩为 6 名 = 随机路径既定传导,
    本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['贝洛伯格概念股']) == 'off'


def test_xingjianlvren_concept_stock_gift_tier_off() -> None:
    """星间旅人概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第七实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(域成员构成随注册表传导〔采样域牌库时点过滤见 cw_pool
    grant_char_pool,2026-10-28 用户裁定〕,本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['星间旅人概念股']) == 'off'


def test_xianzhou_concept_stock_gift_tier_off() -> None:
    """仙舟概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第八实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(域 9 名含专家青雀/停云 = 随机路径注册表传导,估值分母与流程
    采样域的牌库时点分叉系范围外申报,本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['仙舟概念股']) == 'off'


def test_langshou_concept_stock_gift_tier_off() -> None:
    """狼狩概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第九实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(域 7 名含专家貊泽 = 随机路径注册表传导,估值分母与流程采样域
    的牌库时点分叉系范围外申报沿仙舟实例同指针,本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['狼狩概念股']) == 'off'


def test_zhouzhibanshen_concept_stock_gift_tier_off() -> None:
    """昼之半神概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第十实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(域 6 名 is_expert 全空 = 非专家域,随机路径期望域与流程过滤域
    同集,无仙舟/狼狩型分叉申报,本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['昼之半神概念股']) == 'off'


def test_yezhibanshen_concept_stock_gift_tier_off() -> None:
    """夜之半神概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第十一实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(域 7 名 is_expert 全空 = 非专家域,随机路径期望域与流程过滤域
    同集,无仙舟/狼狩型分叉申报,本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['夜之半神概念股']) == 'off'


def test_jipo_concept_stock_gift_tier_off() -> None:
    """击破概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第十二实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(域 9 名含专家加拉赫/姬子 = 随机路径注册表传导,估值分母与流程
    采样域的牌库时点分叉系范围外申报沿仙舟/狼狩实例同指针,本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['击破概念股']) == 'off'


def test_qungong_concept_stock_gift_tier_off() -> None:
    """群攻概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第十三实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(域 7 名 is_expert 全空 = 非专家域,随机路径期望域与流程过滤域
    同集,无仙舟/狼狩型分叉申报,本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['群攻概念股']) == 'off'


def test_jianyi_concept_stock_gift_tier_off() -> None:
    """减益概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第十四实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(域 7 名含专家佩拉 = 随机路径注册表传导,估值分母与流程采样域
    的牌库时点分叉系范围外申报沿仙舟/狼狩/击破实例同指针;本域双口径
    探针现值零偏差 37.5/37.5,本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['减益概念股']) == 'off'


def test_zhanjidian_concept_stock_gift_tier_off() -> None:
    """战技点概念股估值档恒 'off'(概念股族展开卡登记约定,正本 =
    fields.md §5.2 效果缺口与载体登记,追击首例同锁第十五实例):随机规格
    (阵营轴)/随机装备条目不入档位机器估值域 → 恒 off——族展开登记
    不产生策略层双重计分,与 random_faction_gift_value 随机阵营路径
    正交(域 7 名含专家青雀 = 随机路径注册表传导,估值分母与流程采样域
    的牌库时点分叉系范围外申报沿仙舟/狼狩/击破/减益实例同指针;本域双
    口径探针现值零偏差 50.0/50.0,本档零扰动)。"""
    assert gift_hit_tier(ENV_GIFTS['战技点概念股']) == 'off'


def test_member_priority_two_tier_derivation() -> None:
    """成员优先级两档派生语义(统一让位优先级迭代 design §2.1.1):
    ``member_rank_of`` = core 0/其余 1 现算——字段化形态已退役
    (20/20 恒派生值零手编,「精调登记」从未发生);本测试锁派生式
    全库等价 + 读口语义。

    - 全库:每套 member_rank_of 覆盖 core ∪ shared 且取值与两档派生式一致;
    - 同名双列(core ∩ shared,列车同行三月七类)core 优先;
    - 手构 Comp(含 pair 伪阵容同路径)派生即两档。"""
    for comp in COMP_LIBRARY:
        expected = {n: (0 if n in comp.core_chars else 1)
                    for n in set(comp.core_chars) | set(comp.shared_chars)}
        assert member_rank_of(comp) == expected, f'{comp.name} 两档派生'
    assert member_rank_of(get_comp('列车同行·反震'))['三月七'] == 0, \
        '同名双列 core 优先'
    hand = Comp(name='手构线', core_chars=['甲', '乙'],
                faction_reqs={},
                shared_chars=['乙', '丙'])
    assert member_rank_of(hand) == {'甲': 0, '乙': 0, '丙': 1}, \
        '派生即两档'
    assert derive_member_priority(hand) == {'甲': 0, '乙': 0, '丙': 1}


def test_seele_quantum_final_tiers() -> None:
    """终局希儿量子条目改档结构锁(档 0 = 量4+贝4 纯 AND、档 1 =
    战技点2/治疗2 加分层;条目值单一源 = cw_comps COMP_LIBRARY 条目
    本体,本测试锁结构不被手改漂移):
    档 0 = 量子4+贝洛伯格4 纯 AND(终局完全体,双修即唯一主流终局形态)、
    档 1 = 战技点2/治疗2(实证 53/67 与 36/67,加分层不进成型判定)、
    flex 收敛为盛会之星/列车同行、required = 希儿在场。"""
    comp = get_comp('希儿量子')
    assert comp.faction_reqs == {
        0: {'量子同频': 4, '贝洛伯格': 4}, 1: {'战技点': 2, '治疗': 2}}
    assert comp.flex_factions == ['盛会之星', '列车同行']
    assert comp.required_deployed == ('希儿',)


def test_seele_quantum_fp_curve() -> None:
    """希儿量子 fp 曲线五值:改档后 form_progress 按纯 AND 折算,
    新 fp = (min(量,4)/4 + min(贝,4)/4 + [希儿在板])/3——分度恢复,
    量2 不再虚假满成型,完全体(量4贝4)才 1.0;希儿+量1 ≈ 0.417 仍过
    COMMIT_FRAC(装备工具激活面 =「希儿到手即开线」不丢)。"""
    seele = get_comp('希儿量子')

    def fp(board: dict[str, int]) -> float:
        return form_progress(seele, _Panel(board, front=('希儿',)))

    assert fp({'量子同频': 1}) == pytest.approx(1.25 / 3)   # ≈ 0.417
    assert fp({'量子同频': 2}) == pytest.approx(0.5)
    assert fp({'量子同频': 2, '贝洛伯格': 2}) == pytest.approx(2 / 3)
    assert fp({'量子同频': 4, '贝洛伯格': 2}) == pytest.approx(2.5 / 3)
    assert fp({'量子同频': 4, '贝洛伯格': 4}) == 1.0
    assert fp({'量子同频': 1}) >= COMMIT_FRAC, '希儿+量1 仍过 commit 线'
