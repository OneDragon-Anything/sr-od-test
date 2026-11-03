"""投资通道派生测试(design §3.1/§3.2;2026-11-03-unified-line-scoring 批 1)。

判据正本 = docs/develop/sr_od/application/currency_war/changes/
2026-11-03-unified-line-scoring/design.md §3.1(环境四通道)/§3.2(策略
五通道+实证覆盖升档)。断言全部引设计语义,期望值 = 常数表符号直读
(cw_line_scales 单一源),注册表真实数据现算锚定。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_affinity_table import (
    affix_line_score,
    fuel_set_of,
)
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_invest_channels import (
    DEFINING_CARDS,
    EVIDENCE_UPGRADE,
    env_line_bonus,
    env_line_bonuses,
    strategy_line_bonus,
    strategy_line_bonuses,
)
from sr_od.application.currency_war.kernel.cw_line_scales import (
    EVIDENCE_UPGRADE_BONUS,
    INVEST_DEFINING,
    INVEST_MID,
    INVEST_SOFT,
    INVEST_STRONG,
    RESTART_PENALTY,
)


def _comp(name: str):
    comp = get_comp(name)
    assert comp is not None, name
    return comp


# ===== 环境通道②③④(类目派生;design §3.1)=====


def test_env_concept_stock_strong_channel_full_tier() -> None:
    """概念股 = 通道②定向刷新,强档 +300:击破 ∈ 巡海击破 form_tiers →
    全档(通用类 41 个线分 0 的对照面在 test_env_generic_categories_zero)。"""
    assert env_line_bonus('击破概念股', _comp('巡海击破')) == INVEST_STRONG


def test_env_invitation_mid_channel_and_contract_strong() -> None:
    """邀请 = 通道③星徽中档 +150;契约 = 通道④期货强档 +300——命运圣杯
    双线(红A/双王)主档同键命中同值。"""
    lc = _comp('命运圣杯红A')
    assert env_line_bonus('命运圣杯邀请', lc) == INVEST_MID
    assert env_line_bonus('命运圣杯契约', lc) == INVEST_STRONG
    assert env_line_bonus('命运圣杯契约', _comp('双王圣杯')) == INVEST_STRONG


def test_env_generic_categories_zero() -> None:
    """通用类 41 个线分 0(design §3.1 类目计数:经济 15/规则 10/时代 6/
    专家 10——含特邀专家族,其价值经所赠角色走证据分,通道 0)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        INVESTMENT_ENVS,
    )
    generic = [n for n, e in INVESTMENT_ENVS.items()
               if e.category not in ('概念股', '邀请', '契约')]
    assert len(generic) == 41, '通用类计数锚(design §3.1)'
    for name in generic:
        assert env_line_bonuses(name) == {}, name


def test_env_faction_hit_or_reqs_counts_as_core() -> None:
    """目标线命中含 or_reqs 键(希儿量子:贝洛伯格 ∈ or_reqs)——贝洛伯格
    概念股对希儿量子给全档,不按 flex 降档。"""
    assert env_line_bonus('贝洛伯格概念股', _comp('希儿量子')) == INVEST_STRONG


def test_env_flex_downgrade_strong_to_soft_and_mid_to_zero() -> None:
    """flex 降档(design §3.1:强→+30/中→0):黄泉减益 flex 含击破——
    击破概念股(强)降 +30;击破邀请(中)降 0。"""
    hq = _comp('黄泉减益')
    assert '击破' in hq.flex_factions
    assert env_line_bonus('击破概念股', hq) == INVEST_SOFT
    assert env_line_bonus('击破邀请', hq) == 0


# ===== 策略通道:实证升档/定义卡/⑤引擎匹配/③星徽原文 =====


def test_evidence_upgrade_quantum_emblem_family() -> None:
    """实证覆盖升档(design §2 表):量子星徽×3(邀请〔环境〕+星徽+套组
    〔策略〕)→ 希儿量子 +750,覆盖通道③默认 +150。"""
    seele = _comp('希儿量子')
    assert env_line_bonus('量子同频邀请', seele) == EVIDENCE_UPGRADE_BONUS
    assert strategy_line_bonus('量子同频星徽', seele) == EVIDENCE_UPGRADE_BONUS
    assert strategy_line_bonus('量子同频星徽套组', seele) \
        == EVIDENCE_UPGRADE_BONUS


def test_evidence_upgrade_luocha_to_train() -> None:
    """罗刹→列车 +750(final_jizi_train 直通线信号谱「策略驱动」层)。"""
    assert strategy_line_bonus('本姑娘就是罗刹', _comp('列车同行')) \
        == EVIDENCE_UPGRADE_BONUS


def test_defining_cards_line_named_registration() -> None:
    """定义卡 +500(design §2:黑塔纪元/专家邀请/飞光):点名登记不走羁绊
    命中(黑塔纪元效果原文无线定义文本,手编表承载)。"""
    assert strategy_line_bonus('黑塔纪元', _comp('大黑塔银河学者')) \
        == INVEST_DEFINING
    assert strategy_line_bonus('飞光·映月', _comp('景元仙舟')) == INVEST_DEFINING
    assert strategy_line_bonus('飞光·传剑', _comp('景元仙舟')) == INVEST_DEFINING
    assert strategy_line_bonus('骇客专家:银狼', _comp('狼尊欢愉')) \
        == INVEST_DEFINING
    # 未命中线 0(定义卡不外溢)
    assert strategy_line_bonus('黑塔纪元', _comp('景元仙舟')) == 0


def test_engine_synergy_faction_keyed_mid_tier() -> None:
    """⑤引擎匹配手编表 +150,羁绊键派生:离火燎原(减益)→ 黄泉减益与
    千冶减益同享(两线主派同键,纯加权零特例);量子力学/钢铁美学 → 希儿。"""
    assert strategy_line_bonus('离火燎原', _comp('黄泉减益')) == INVEST_MID
    assert strategy_line_bonus('离火燎原', _comp('千冶减益')) == INVEST_MID
    assert strategy_line_bonus('量子力学', _comp('希儿量子')) == INVEST_MID
    assert strategy_line_bonus('钢铁美学', _comp('希儿量子')) == INVEST_MID


def test_strategy_emblem_effect_text_channel() -> None:
    """③星徽效果原文派生:「获得…【X星徽】」直读——命运圣杯星徽(策略)
    → 圣杯双线 +150;盛会之星星徽类(flex-only 阵营)降 0。"""
    assert strategy_line_bonus('命运圣杯星徽', _comp('命运圣杯红A')) \
        == INVEST_MID
    assert strategy_line_bonus('梦境大舞台', _comp('列车同行')) == 0, \
        '盛会之星 ∈ 列车 flex(中档降 0)'


def test_gift_channel_skipped_and_random_zero() -> None:
    """①送人跳过(证据分自动覆盖)+ 随机类记 0:量子力学之外的送卡策略
    (轮回不止直赠白厄)与随机类(超光速提拔)通道 0——所赠角色走线分
    证据分量,不走通道分。"""
    assert strategy_line_bonus('轮回不止', _comp('反甲白厄')) == 0
    assert strategy_line_bonus('超光速提拔', _comp('万敌单C')) == 0


def test_ocr_variant_normalizes_before_lookup() -> None:
    """查询入口 normalize_invest_name 防线(OCR 间隔号形变 •→·):
    形变名照常命中实证升档(run_20260826_004527 缺陷链同型)。"""
    assert strategy_line_bonus('飞光•映月', _comp('景元仙舟')) == INVEST_DEFINING


def test_manual_table_registry_membership_invariants() -> None:
    """手编表登记完备性锚:EVIDENCE_UPGRADE 恰 4 条目(量子星徽×3+罗刹)、
    DEFINING_CARDS 恰 4 卡(黑塔纪元/飞光×2/骇客专家)——批 2/3 扩表时
    计数锚响亮暴露防误删。"""
    assert len(EVIDENCE_UPGRADE) == 4
    assert set(DEFINING_CARDS) == {'黑塔纪元', '飞光·映月', '飞光·传剑',
                                   '骇客专家:银狼'}


def test_bonuses_dict_scan_shape() -> None:
    """全库扫描口(flow 遥测喂入面):值全 >0、键 = 线名。"""
    got = strategy_line_bonuses('量子同频星徽')
    assert got == {'希儿量子': EVIDENCE_UPGRADE_BONUS}


# ===== 吃怕表与万敌燃料底线(design §4;批 1 万敌行直入)=====


def test_wandi_row_scores() -> None:
    """万敌行直入分值:正当防卫 +900/燃料族 +750;永久创伤重开级(纯局
    无燃料底线叠加 −200000——两重开级分量同档可叠,排序语义不变:命中
    重开级线恒低于无命中线)。"""
    assert affix_line_score('万敌单C', ('正当防卫',)) == 900
    assert affix_line_score('万敌单C', ('忍无可忍',)) == 750
    assert affix_line_score('万敌单C', ('永久创伤',)) == RESTART_PENALTY * 2
    # 行值本体(隔开燃料底线):永久创伤 + 一条燃料词缀 → −100000+750
    assert affix_line_score('万敌单C', ('永久创伤', '一鼓作气')) \
        == RESTART_PENALTY + 750


def test_wandi_fuel_projection_and_bottom_line() -> None:
    """燃料集 = 万敌行正值投影(单一源派生):正当防卫/忍无可忍/应激反应/
    灼热轰炸/一鼓作气;开局词缀 ∩ 燃料集 = 空 → 重开级(无燃料底线)。"""
    assert fuel_set_of('万敌单C') == frozenset(
        {'正当防卫', '忍无可忍', '应激反应', '灼热轰炸', '一鼓作气'})
    # 有燃料:灼热轰炸在局 → 正分,无底线
    assert affix_line_score('万敌单C', ('灼热轰炸', '净化身心', '风之熄火',
                                        '沉重脚步')) == 750
    # 无燃料:四词缀全在燃料集外 → −100000(永久创伤自身再叠加同档)
    no_fuel = affix_line_score('万敌单C', ('永久创伤', '净化身心',
                                           '风之熄火', '沉重脚步'))
    assert no_fuel == RESTART_PENALTY * 2, '永久创伤 −100000 + 无燃料底线 −100000'


def test_unregistered_line_affix_score_zero() -> None:
    """未登记线(批 2 扩行前其余 19 线)词缀分恒 0——垫底/排除全由已登记
    行承载,未登记不误伤。"""
    assert affix_line_score('列车同行', ('正当防卫',)) == 0
