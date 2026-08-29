"""W47 统一化修批锁测试(leader 合并裁决 2026-08-25;5 处落地 + 顺手件)。

锁定对象(修法见 ``.debug/temp/currency_war/cw_dev/deep_read/W47_报告.md``):
① ``SystemCard.judge_factions`` 字段 = 卡→判据阵营映射单一源
  (原三处重复:_card_factions / card_active seele 分支 /
  cw_evolution._CARD_FACTION_TIER → 全部改读字段);
② ``cw_system_cards.engine_char_names``/``system_judge_factions`` helper
  (scoring._shop_has_engine_card 改读,五阵营+希儿手抄消除);
③ ``cw_win_model`` 三字面量(_TRIO/_DOT_POOL/_SEELE)改 import/派生单一源;
④ ``Comp.bond_signal`` 字段 + ``FAMILY_BOND_SIGNALS`` 从 COMP_LIBRARY 派生
  (手编 crosswalk 数据化;希儿量子/白厄反甲按设计 None);
⑤ ``TRANSITION_TRAITS`` 从 SYSTEM_CARDS 派生 + cw_sim._TRANSITION_TRAITS
  alias import(常量对双源消除);
⑥ 顺手件:candidates._buy_tag 的 bond_fallback 门恒真死条件清理
  (``has_direction or no_direction`` 恒 True → 删除;锁=有/无方向两态都触发)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_comps import (
    COMP_LIBRARY,
    V2_FAMILIES,
)
from sr_od.application.currency_war.cw_deploy_logic import (
    TRANSITION_TRAITS,
)
from sr_od.application.currency_war.cw_evolution import _CARD_FACTION_TIER
from sr_od.application.currency_war.cw_intention import FAMILY_BOND_SIGNALS
from sr_od.application.currency_war.cw_line_defs import _CORE_TRIO
from sr_od.application.currency_war.cw_state import GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.cw_system_cards import (
    SYSTEM_CARDS,
    _card_factions,
    engine_char_names,
    system_judge_factions,
)
from sr_od.application.currency_war.cw_win_model import (
    _DOT_POOL,
    _SEELE,
    _TRIO,
)
from sr_od.application.currency_war.decision_v2 import discipline
from sr_od.application.currency_war.decision_v2.candidates import _buy_tag
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    _shop_has_engine_card,
)

# --- ① judge_factions 字段(三处重复消除的单一源) --------------------------


def test_judge_factions_field_values() -> None:
    """卡→判据阵营映射的字段真值(希儿系双元组,首位=演进目标锚=量子侧)。"""
    assert SYSTEM_CARDS['xianzhou3'].judge_factions == ('仙舟',)
    assert SYSTEM_CARDS['dot2'].judge_factions == ('持续伤害',)
    assert SYSTEM_CARDS['train2'].judge_factions == ('列车同行',)
    assert SYSTEM_CARDS['seele'].judge_factions == ('量子同频', '贝洛伯格')
    # 兼容视图 _card_factions = 原样返回字段(不再有第二份映射)
    assert all(_card_factions(c) == c.judge_factions
               for c in SYSTEM_CARDS.values())


def test_evolution_card_faction_tier_derived() -> None:
    """cw_evolution._CARD_FACTION_TIER 从字段+FACTIONS 派生,值=原手编表
    (tier 阈值仍经注册表;第五张体系卡加入自动传导,无需改本表)。"""
    assert _CARD_FACTION_TIER == {
        'xianzhou3': ('仙舟', 3),
        'dot2': ('持续伤害', 2),
        'train2': ('列车同行', 2),
        'seele': ('量子同频', 2),
    }


# --- ② 引擎阵营/引擎名 helper(scoring 改读) ------------------------------


def test_engine_helpers_single_source() -> None:
    """阵营并集=五家(仙舟/列车/DOT/量子/贝);引擎名=铁三角+希儿;
    discipline.engine_char_names 与 cw_system_cards 同一函数(单一源)。"""
    assert system_judge_factions() == frozenset(
        {'仙舟', '列车同行', '持续伤害', '量子同频', '贝洛伯格'})
    assert engine_char_names() == frozenset(
        {'藿藿', '丹恒·饮月', '爻光', '希儿'})
    assert discipline.engine_char_names is engine_char_names


def _shop_state(names: list[str]) -> GameState:
    return GameState(
        plane=1, round_num=4, gold=30, level=5, board={}, bench=[],
        shop=[SimpleNamespace(name=n, faction='', cost=2, x=0, star=1)
              for n in names], hp=100)


def test_shop_has_engine_card_reads_registry() -> None:
    """_shop_has_engine_card 经 helper 判:引擎名/判据阵营件命中,线外不命中。"""
    assert _shop_has_engine_card(_shop_state(['希儿']))            # 引擎名单卡
    assert _shop_has_engine_card(_shop_state(['卡芙卡']))          # DOT flow 件
    assert _shop_has_engine_card(_shop_state(['景元']))            # 仙舟件
    assert _shop_has_engine_card(_shop_state(['杰帕德']))          # 贝洛伯格件(希儿系判据阵营)
    assert not _shop_has_engine_card(_shop_state(['银枝']))        # 线外(星间旅人/群攻)
    assert not _shop_has_engine_card(_shop_state(['凑数散件']))    # 未注册名


# --- ③ cw_win_model 三字面量单一源 -----------------------------------------


def test_win_model_literals_derived() -> None:
    """_TRIO=注册表铁三角;_DOT_POOL=FACTIONS['持续伤害'] ≤2 费成员;
    _SEELE=seele 卡 engine_required(无第三处名字字面量)。"""
    assert set(_TRIO) == set(_CORE_TRIO) == {'藿藿', '丹恒·饮月', '爻光'}
    assert set(_DOT_POOL) == {'艾丝妲', '椒丘', '卡芙卡', '桑博'}
    assert _SEELE == '希儿'


# --- ④ Comp.bond_signal + FAMILY_BOND_SIGNALS 派生 -------------------------


def test_family_bond_signals_derived_from_comps() -> None:
    """crosswalk 值锁:7 家族→专属羁绊(与原手编表逐项一致)。"""
    assert FAMILY_BOND_SIGNALS == {
        '姬子列车': '列车同行',
        '圣杯双C': '命运圣杯',
        '欢愉族': '欢愉',
        '黄泉减益': '减益',
        '大黑塔群攻': '银河学者',
        '万敌燃血': '夜之半神',
        'DOT卡芙卡': '持续伤害',
    }


def test_bond_signal_field_consistency() -> None:
    """字段一致性:同家族各套 bond_signal 相同;希儿量子/白厄反甲=None
    (设计缺席:放大器不是独立伤害源 / 独立羁绊绑死单卡)。"""
    for comp in COMP_LIBRARY:
        if comp.family not in V2_FAMILIES:
            continue
        if comp.family in FAMILY_BOND_SIGNALS:
            assert comp.bond_signal == FAMILY_BOND_SIGNALS[comp.family], \
                f'{comp.name} 的 bond_signal 与家族表不一致'
        else:
            assert comp.bond_signal is None, \
                f'{comp.family} 不在信号表但 {comp.name}.bond_signal 非 None'
    assert next(c for c in COMP_LIBRARY
                if c.family == '希儿量子').bond_signal is None
    assert next(c for c in COMP_LIBRARY
                if c.family == '白厄反甲').bond_signal is None


# --- ⑤ TRANSITION_TRAITS 派生 + cw_sim alias -------------------------------


def test_transition_traits_derived_from_system_cards() -> None:
    """三羁绊对值锁(=SYSTEM_CARDS 排除 seele 后的(阵营,tiers[0]));
    cw_sim._TRANSITION_TRAITS 是同一对象(alias import,常量对双源消除)。"""
    assert set(TRANSITION_TRAITS) == {
        ('仙舟', 3), ('持续伤害', 2), ('列车同行', 2)}
    from sr_od.application.currency_war import cw_sim
    assert cw_sim.__dict__.get('_TRANSITION_TRAITS') is None, 期0b锁改判_alias已删_单一源为cw_deploy_logic本体


# --- ⑥ 顺手件:bond_fallback 门死条件清理(无行为变化) ---------------------


def _bf_card() -> SimpleNamespace:
    """bond_fallback 合法件:1 费 + 与已有阵营同阵营 + 不在任何目标集。"""
    return SimpleNamespace(name='凑档件', faction='仙舟罗浮', cost=1,
                           x=0, star=1)


def _bf_state() -> GameState:
    # bench 留空(放同名件会先命中 copy 通道,污染 bond_fallback 断言)
    return GameState(
        plane=1, round_num=4, gold=30, level=5,
        board={'仙舟罗浮': 1}, bench=[], shop=[], hp=100)


def test_bond_fallback_tag_without_direction_unchanged() -> None:
    """死条件清理后:无方向态同阵营件的标签裁决不变——bond_fallback 门
    在 ``_buy_tag`` 序中位于 pair 之后,无方向时同阵营件先被 pair 接管
    (原恒真条件的删除不改变标签优先序;有方向时方向阵营门把 pair
    拒掉,bond_fallback 才独占——见下一条)。"""
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    tag = _buy_tag(_bf_card(), _bf_state(), sess, DEFAULT_REGISTRY)
    assert tag == 'pair'


def test_bond_fallback_fires_with_direction() -> None:
    """有方向(v3_hoard 锁线)时 bond_fallback 正常触发(方向阵营门拒 pair
    后的独占通道——与 ADR-0291 锁线用例同口径,此处直查 _buy_tag)。"""
    from sr_od.application.currency_war.cw_intention import (
        HoardTarget,
        IntentionState,
    )
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    sess.v3_intention = ist
    sess.v3_hoard = HoardTarget(
        frozenset({'姬子·启行'}), frozenset(), 'locked')
    tag = _buy_tag(_bf_card(), _bf_state(), sess, DEFAULT_REGISTRY)
    assert tag == 'bond_fallback'
