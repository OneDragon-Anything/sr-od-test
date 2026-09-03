# -*- coding: utf-8 -*-
"""test_cw_candidates 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- adr0296_candidate_generators: test_cw_adr0296_candidate_generators.py
- adr0299_buy_gap: test_cw_adr0299_buy_gap.py
- adr0300_copy_pair_channels: test_cw_adr0300_copy_pair_channels.py
- w611_o1_fill_buy: test_cw_w611_o1_fill_buy.py
- w611_reserve_admission: test_cw_w611_reserve_admission.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== adr0296_candidate_generators ====================

from sr_od.application.currency_war.sim.checks.decision_v2 import check_decision_v2_candidate_coverage
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Synthesize,
    generate_candidates,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY


def _sess(line: str | None = None) -> StrategySession:
    """意向载体(ADR-0336 后唯一形态;``line`` 参数=意向 hoard 目标集,
    旧 locked_line 垫片已删)。"""
    s = StrategySession()
    if line:
        from sr_od.application.currency_war.kernel.cw_intention import (
            HoardTarget,
            IntentionState,
        )
        ist = IntentionState()
        ist.phase = 'locked'
        ist.locked_comp = '姬子列车'
        s.v3_intention = ist
        s.v3_hoard = HoardTarget(
            frozenset({'娜塔莎', '姬子·启行', '瓦尔特', '三月七', '黄泉'}),
            frozenset(), 'locked')
        s.v3_core_names = {'姬子·启行'}
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 60, 'level': 5,
            'board': {'仙舟': 2}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _sell_tags(st: GameState, sess: StrategySession) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in generate_candidates(st, sess, _REG):
        if c.tag in ('off_target', 'for_gold', 'free_bench'):
            out[c.breakdown_hint.get('name', '')] = c.tag
    return out


# --- ① sell 标签正确性 ------------------------------------------------------


def test_sell_off_target_normal_state() -> None:
    """常态:非目标 bench 件 → off_target(引擎阵营件无卖禁——旧
    engine 阵营级保护删除,件值交评分层)。W184/ADR-0373 后 TT 件
    (青雀=仙舟)在 owned≤tier 时另有唯一引擎卖禁(辖域锁见
    test_cw_w184_sole_engine_sell_guard),本锁改用非 TT 件银枝锁
    通用 off_target 语义。"""
    sess = _sess(line='jizi')
    st = _state(bench=[BenchChar(slot=0, char_id='银枝', faction='智识')])
    assert _sell_tags(st, sess) == {'银枝': 'off_target'}


def test_sell_target_piece_not_sellable() -> None:
    """目标件(锁线 opportunistic)常态不生成卖候选。"""
    sess = _sess(line='jizi')
    st = _state(bench=[BenchChar(slot=0, char_id='娜塔莎', faction='护盾')])
    assert '娜塔莎' not in _sell_tags(st, sess)


def test_sell_for_gold_emergency() -> None:
    """应急态(hp≤emergency_hp):非目标弱件 → for_gold(折现换金)。"""
    sess = _sess(line='jizi')
    st = _state(hp=20, bench=[
        BenchChar(slot=0, char_id='银枝', faction='智识')])
    assert _sell_tags(st, sess) == {'银枝': 'for_gold'}


def test_sell_free_bench_full_target_yields() -> None:
    """bench 满:目标件也降保护集让位(free_bench,v1 carry 腾位门
    语义);非目标件在 bench 满时同样 free_bench 语义域。

    W192/ADR-0375 适配:目标件由娜塔莎(贝洛伯格=希儿系贡献件,唯一
    在手时卖禁;瓦尔特/三月七/姬子·启行=TT 件同因 W184 卖禁)换黄泉
    并入 hoard 目标集——目标件让位语义与守卫辖域正交,辖域由
    test_cw_w192_seele_scope 锁。"""
    sess = _sess(line='jizi')
    bench = [BenchChar(slot=i, char_id='黄泉' if i == 0 else '银枝',
                       faction='巡海游侠' if i == 0 else '智识')
             for i in range(_REG.bench_capacity)]
    st = _state(bench=bench)
    tags = _sell_tags(st, sess)
    assert tags.get('黄泉') == 'free_bench', \
        f'bench 满时目标件应让位:{tags}'


# --- ② 豁免过滤(v1 语义对齐,生成器层)------------------------------------


def test_sell_blocked_same_round_bought_r408() -> None:
    """r408:同轮已买件不生成卖候选;同名 ≥3 份(让位语境)放行。"""
    sess = _sess(line='jizi')
    sess.v2_round_key = (1, 5)
    sess.v2_round_bought = {'银枝'}
    st = _state(bench=[BenchChar(slot=0, char_id='银枝', faction='智识')])
    assert '银枝' not in _sell_tags(st, sess), '同轮已买不卖(r408)'
    # 3合1 让位豁免:3 份(其中含同轮买入)→ 放行(free_bench 域外
    # 不可卖因素材豁免,构造 4 份冗余语境 → 可卖)
    st2 = _state(bench=[BenchChar(slot=i, char_id='银枝', faction='智识')
                        for i in range(4)])
    assert '银枝' in _sell_tags(st2, sess), \
        '同轮买 ≥3 份让位语境应放行(r408 豁免边)'


def test_sell_blocked_seed_age_window() -> None:
    """ADR-0289 §5:买入 ≤2 轮的种子(engine_seed)不进可卖集。"""
    sess = _sess(line='jizi')
    sess.v2_seed_bought = {'银枝': ((1, 3), 1)}   # r3 买 1 份
    st = _state(round_num=4, bench=[
        BenchChar(slot=0, char_id='银枝', faction='智识')])
    assert '银枝' not in _sell_tags(st, sess), '种子 2 轮窗内不卖'
    st3 = _state(round_num=7, bench=[   # r7 = 买后第 4 轮 → 可卖
        BenchChar(slot=0, char_id='银枝', faction='智识')])
    assert _sell_tags(st3, sess).get('银枝') == 'off_target'


def test_sell_blocked_complete_merge_material() -> None:
    """3合1 素材豁免:同名星级加权恰 3 份(完整合成份)不卖;
    >3 冗余份可卖(v1 copies>cap 优先腾语义)。"""
    sess = _sess(line='jizi')
    st = _state(bench=[BenchChar(slot=i, char_id='银枝', faction='智识')
                       for i in range(3)])
    assert '银枝' not in _sell_tags(st, sess), '完整 3合1 份不拆卖'
    st4 = _state(bench=[BenchChar(slot=i, char_id='银枝', faction='智识')
                        for i in range(4)])
    assert '银枝' in _sell_tags(st4, sess), '第 4 份冗余可卖'


# --- ③ synthesize 独立生成器 ------------------------------------------------


def test_synthesize_full_field_group() -> None:
    """全场域同名同星 ≥3(bench 2 + deployed 1)→ 每组一个候选
    (cw_state._merge_bench 口径镜像;ADR-0296)。"""
    sess = _sess(line='jizi')
    st = _state(
        bench=[BenchChar(slot=0, char_id='青雀', faction='仙舟'),
               BenchChar(slot=1, char_id='青雀', faction='仙舟')],
        deployed=[BenchChar(slot=0, char_id='青雀', faction='仙舟')],
    )
    syn = [c for c in generate_candidates(st, sess, _REG)
           if c.tag == 'synthesize']
    assert len(syn) == 1
    assert isinstance(syn[0].action, Synthesize)
    assert syn[0].action.name == '青雀' and syn[0].action.star == 1
    assert syn[0].action.copies == 3 and syn[0].merge


def test_synthesize_insufficient_or_mixed_star() -> None:
    """不足 3 份 / 同名混星(2+1 不成组)不生成。"""
    sess = _sess(line='jizi')
    st = _state(
        bench=[BenchChar(slot=0, char_id='青雀', faction='仙舟'),
               BenchChar(slot=1, char_id='青雀', faction='仙舟',
                         star=2)],
        deployed=[BenchChar(slot=0, char_id='青雀', faction='仙舟')],
    )
    assert not [c for c in generate_candidates(st, sess, _REG)
                if c.tag == 'synthesize']


# --- ④ 检查项转绿锁 --------------------------------------------------------


def test_candidate_coverage_check_green() -> None:
    """decision_v2_candidate_coverage 结构层 0 违规(ADR-0294 豁免
    表移除的依据;红 = 生成器覆盖面回归)。"""
    r = check_decision_v2_candidate_coverage()
    assert r['violations'] == 0, f'{r}'
    assert set(r['struct_classes']) >= {'buy', 'sell', 'synthesize',
                                        'levelup', 'refresh', 'deploy'}


# ==================== adr0299_buy_gap ====================

from sr_od.application.currency_war.kernel.cw_intention import HoardTarget
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    _target_names,
    generate_candidates,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_adr0299_buy_gap_REG = DEFAULT_REGISTRY


def _adr0299_buy_gap_sess(hoard: set[str] | None = None) -> StrategySession:
    s = StrategySession()
    if hoard is not None:
        # 意向载体(生产真实形态;旧 locked_line 垫片已删)
        s.v3_hoard = HoardTarget(frozenset(hoard), frozenset(), 'locked')
    return s


def _adr0299_buy_gap_state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 60, 'level': 5,
            'board': {'仙舟': 2}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _buy_tags(st: GameState, sess: StrategySession) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in generate_candidates(st, sess, _adr0299_buy_gap_REG):
        a = c.action
        card = getattr(a, 'card', None)
        if card is not None and card.name:
            out[card.name] = c.tag
    return out


# --- ① engine_seed 生成通道 -------------------------------------------------


def test_engine_seed_generated_for_transition_unheld() -> None:
    """P1 未持有的过渡体系件(青雀=仙舟)→ engine_seed 候选
    (v2 买入面缺口主导层的修复:首块砖无需先凑档/锁线)。"""
    sess = _adr0299_buy_gap_sess(hoard={'三月七'})   # 意向目标不含青雀
    st = _adr0299_buy_gap_state(round_num=1, board={}, shop=[
        ShopCard(x=0, name='青雀', faction='仙舟', cost=1)])
    assert _buy_tags(st, sess).get('青雀') == 'engine_seed'

def test_engine_seed_not_generated_when_held() -> None:
    """已持有同名(engine_seed 语义=未持有的第一块砖)不走
    engine_seed——副本走 copy 通道(ADR-0300 迁移后生成 'copy',
    上限归 copies_cap/层4,v1 同式)。"""
    sess = _adr0299_buy_gap_sess(hoard={'三月七'})
    st = _adr0299_buy_gap_state(round_num=1, board={}, bench=[
        BenchChar(slot=0, char_id='青雀', faction='仙舟')], shop=[
        ShopCard(x=0, name='青雀', faction='仙舟', cost=1)])
    assert _buy_tags(st, sess).get('青雀') != 'engine_seed'


def test_engine_seed_not_generated_bench_full() -> None:
    """bench 满不种(r408 容量门:满员态「未持有」与卖出态构成
    永动机,ADR-0267 F1)——engine_seed 通道不触发;生成层其他
    通道(copy/pair)不受此门辖,容量由层4 bench_capacity 收口。"""
    sess = _adr0299_buy_gap_sess(hoard={'三月七'})
    bench = [BenchChar(slot=i, char_id='娜塔莎', faction='护盾')
             for i in range(_adr0299_buy_gap_REG.bench_capacity)]
    st = _adr0299_buy_gap_state(round_num=1, board={}, bench=bench, shop=[
        ShopCard(x=0, name='青雀', faction='仙舟', cost=1)])
    assert _buy_tags(st, sess).get('青雀') != 'engine_seed'


def test_engine_seed_not_generated_plane2() -> None:
    """P2 不辖(过渡期种子是 P1 语义;v1 同式)——engine_seed 不
    触发;冷启动 pair 分支(classify_buy=engine)P2 照放(ADR-0300
    迁移,与 v1 _pair_wants 同判据)。"""
    sess = _adr0299_buy_gap_sess(hoard={'三月七'})
    st = _adr0299_buy_gap_state(plane=2, round_num=1, board={}, shop=[
        ShopCard(x=0, name='青雀', faction='仙舟', cost=1)])
    assert _buy_tags(st, sess).get('青雀') != 'engine_seed'


def test_engine_seed_not_generated_non_transition() -> None:
    """非过渡体系阵营件(阿格莱雅=昼之半神/能量)不生成
    (engine_seed 不是散买通道)。"""
    sess = _adr0299_buy_gap_sess(hoard={'三月七'})
    st = _adr0299_buy_gap_state(round_num=1, board={}, shop=[
        ShopCard(x=0, name='阿格莱雅', faction='昼之半神', cost=1)])
    assert '阿格莱雅' not in _buy_tags(st, sess)


def test_engine_seed_target_piece_takes_target_tag() -> None:
    """目标件优先取目标类标签(line_opportunistic),不被 engine_seed
    降级(目标件优先于 engine_seed 通道)。"""
    sess = _adr0299_buy_gap_sess(hoard={'三月七'})
    st = _adr0299_buy_gap_state(round_num=1, board={}, shop=[
        ShopCard(x=0, name='三月七', faction='列车同行', cost=1)])
    assert _buy_tags(st, sess).get('三月七') == 'line_opportunistic'


# --- ② 标签注册 --------------------------------------------------------------


def test_engine_seed_registered_everywhere() -> None:
    """engine_seed 进 buy_tag_priority 与各放行标签集
    (层2 过滤不误杀;追赶标签集已随 W126/ADR-0349 退场)。"""
    assert 'engine_seed' in _adr0299_buy_gap_REG.buy_tag_priority
    for tags in (_adr0299_buy_gap_REG.economy_tags, _adr0299_buy_gap_REG.war_tags,
                 _adr0299_buy_gap_REG.emergency_tags):
        assert 'engine_seed' in tags


# --- ③ 目标集语义(意向载体) ------------------------------------------------


def test_target_names_include_hoard_and_engines() -> None:
    """意向载体目标集 = hoard char_targets + 体系引擎件(ADR-0336
    后唯一形态;旧线库/桥池派生垫片已删)。"""
    sess = _adr0299_buy_gap_sess(hoard={'飞霄', '三月七'})
    st = _adr0299_buy_gap_state()
    names = _target_names(st, sess)
    assert {'飞霄', '三月七'} <= names, 'hoard 目标件漏入目标集'
    from sr_od.application.currency_war.kernel.cw_system_cards import (
        engine_char_names,
    )
    assert set(engine_char_names()) <= names, '体系引擎件漏入目标集'


def test_target_names_bare_session_engines() -> None:
    """裸 session(无 v3_hoard)= 引擎件全集种子(旧全桥名单派生已删)。"""
    sess = _adr0299_buy_gap_sess()
    st = _adr0299_buy_gap_state()
    from sr_od.application.currency_war.kernel.cw_system_cards import (
        engine_char_names,
    )
    assert _target_names(st, sess) == set(engine_char_names())


def test_locked_bridge_fixed_buy_candidate_generated() -> None:
    """桥 fixed 件(飞霄)在意向目标态仍生成买候选(目标类标签)。"""
    sess = _adr0299_buy_gap_sess(hoard={'飞霄', '三月七'})
    st = _adr0299_buy_gap_state(round_num=2, board={}, shop=[
        ShopCard(x=0, name='飞霄', faction='追击', cost=2)])
    assert _buy_tags(st, sess).get('飞霄') == 'line_opportunistic'


# ==================== adr0300_copy_pair_channels ====================

from dataclasses import replace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import (
    _PIPELINE_TAGS,
)

_adr0300_copy_pair_channels_REG = DEFAULT_REGISTRY

# 注入「press 通道关」注册表:press 通道已正式开臂(commit cb7688d4,
# press_channel_enabled 默认 True)。r410 无效换卡守卫锁与该通道无关,
# 锁守卫自身判据时注入关臂隔离 press 豁免臂。
_REG_NO_PRESS = replace(_adr0300_copy_pair_channels_REG, press_channel_enabled=False)

#: 阿格莱雅:非桥池件(非目标)、非过渡体系阵营(bonds ∩ 引擎
#: 阵营=∅——pair 判据不与 engine_seed 交叠)——测试用搭档件载体;
#: cost 显式 3(>bond_fallback_max_cost,隔离 [31] 降级通道)
_FACTION = CHARACTERS['阿格莱雅'].factions[0]


def _adr0300_copy_pair_channels_sess(line: str | None = None) -> StrategySession:
    """意向载体(ADR-0336 后唯一形态;``line`` 参数=意向锁定视窗,
    旧 locked_line 垫片已删)。"""
    s = StrategySession()
    if line:
        from sr_od.application.currency_war.kernel.cw_intention import (
            HoardTarget,
            IntentionState,
        )
        ist = IntentionState()
        ist.phase = 'locked'
        ist.locked_comp = '姬子列车'
        s.v3_intention = ist
        s.v3_hoard = HoardTarget(
            frozenset({'姬子·启行', '瓦尔特', '三月七', '花火'}),
            frozenset(), 'locked')
        s.v3_core_names = {'姬子·启行'}
    return s


def _adr0300_copy_pair_channels_state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 30, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _adr0300_copy_pair_channels_buy_tags(st: GameState, sess: StrategySession,
              reg: object | None = None) -> dict[str, str]:
    """reg=None 用默认注册表;锁通道无关行为时传 _REG_NO_PRESS。"""
    use = _adr0300_copy_pair_channels_REG if reg is None else reg
    out: dict[str, str] = {}
    for c in generate_candidates(st, sess, use):
        card = getattr(c.action, 'card', None)
        if card is not None and card.name:
            out[card.name] = c.tag
    return out


def _aglaea(cost: int = 3) -> ShopCard:
    return ShopCard(x=0, name='阿格莱雅', faction=_FACTION, cost=cost)


#: 佩拉(贝洛伯格,引擎阵营但非桥池件):copy 通道载体——副本放行
#: 与阵营无关(r383b 只判同名),引擎阵营冷启动分支同样放行副本
_PL = '佩拉'
_PL_F = CHARACTERS[_PL].factions[0]


def _pela(cost: int = 2) -> ShopCard:
    return ShopCard(x=0, name=_PL, faction=_PL_F, cost=cost)


# --- ① pair 通道 -------------------------------------------------------------


def test_pair_partner_generated_for_owned_faction() -> None:
    """同阵营搭档件(阿格莱雅=已拥有阵营,非目标非引擎)生成 'pair'
    候选——v1 解剖表残余 pair 桶的 v2 生成通道。"""
    sess = _adr0300_copy_pair_channels_sess()   # 无方向:非冷启动常态分支
    st = _adr0300_copy_pair_channels_state(board={_FACTION: 1}, shop=[_aglaea()])
    assert _adr0300_copy_pair_channels_buy_tags(st, sess).get('阿格莱雅') == 'pair'


def test_pair_rejected_new_faction_spread_cap() -> None:
    """A5 spread 门:已有阵营 ≥3 时新阵营搭档不生成(v1 同判据)。"""
    sess = _adr0300_copy_pair_channels_sess()
    board = {'仙舟': 1, '护盾': 1, '量子': 1}
    st = _adr0300_copy_pair_channels_state(board=board, shop=[_aglaea()])
    assert '阿格莱雅' not in _adr0300_copy_pair_channels_buy_tags(st, sess)


def test_pair_rejected_offline_faction_when_locked() -> None:
    """r350 方向门:锁线后只认线形态羁绊——线外阵营搭档不走 pair
    通道(v1 _pair_wants 直通,判据不复制;cost=3 隔离 bond_fallback)。"""
    sess = _adr0300_copy_pair_channels_sess(line='jizi_train')
    st = _adr0300_copy_pair_channels_state(board={_FACTION: 1}, shop=[_aglaea()])
    assert '阿格莱雅' not in _adr0300_copy_pair_channels_buy_tags(st, sess)


def test_pair_rejected_round_sold_rebuy() -> None:
    """r408 对称臂:本轮刚卖过的卡名 pair 通道不回买(cost=3 隔离
    bond_fallback——层4 same_round_mutex 另辖全域)。"""
    sess = _adr0300_copy_pair_channels_sess()
    sess.v2_round_key = (1, 5)
    sess.v2_round_sold = {'阿格莱雅'}
    st = _adr0300_copy_pair_channels_state(board={_FACTION: 1}, shop=[_aglaea()])
    assert '阿格莱雅' not in _adr0300_copy_pair_channels_buy_tags(st, sess)


# --- ② copy 通道 -------------------------------------------------------------


def test_copy_tag_for_same_name_second_copy() -> None:
    """同名第 2 份副本素材(r383b)打专属 'copy' 标签(与门失效
    形态 pair 区分,检查器不空转报警)。"""
    sess = _adr0300_copy_pair_channels_sess()
    st = _adr0300_copy_pair_channels_state(
        round_num=1,   # 开局轮:冷启动分支的副本放行面
        bench=[BenchChar(slot=0, char_id=_PL, faction=_PL_F)],
        shop=[_pela()])
    assert _adr0300_copy_pair_channels_buy_tags(st, sess).get(_PL) == 'copy'


def test_copy_blocked_by_useless_swap_guard() -> None:
    """r410 保留判据镜像:在场副本会被 off-target 卖出(非
    target_core 且 bonds ∩ target_factions=∅)→ 买新副本=无效
    换卡,不生成候选(v1 _copy_swap_useless 直通;注入关臂隔离
    press 豁免臂——开臂后该臂会另行授权 band 内副本,非守卫判据)。"""
    sess = _adr0300_copy_pair_channels_sess()   # target_comp=None → 在场副本无保留判据
    st = _adr0300_copy_pair_channels_state(
        board={_PL_F: 1},
        deployed=[BenchChar(slot=0, char_id=_PL, faction=_PL_F,
                            position_pref='back')],
        shop=[_pela()])
    assert _PL not in _adr0300_copy_pair_channels_buy_tags(st, sess, _REG_NO_PRESS)


def test_copy_allowed_when_deployed_copy_kept() -> None:
    """r410 保留判据反例:在场副本属 target_cores(显式保留)→
    买副本合法(凑对/3合1),候选生成。"""
    from sr_od.application.currency_war.kernel.cw_bridge_pool import BRIDGE_POOL
    core_name = next(n for c in BRIDGE_POOL for n in c.core)
    ch = CHARACTERS[core_name]
    sess = _adr0300_copy_pair_channels_sess()
    sess.target_comp = type('_TC', (), {
        'factions': (), 'core_chars': (core_name,)})()
    st = _adr0300_copy_pair_channels_state(
        board={ch.factions[0]: 1},
        deployed=[BenchChar(slot=0, char_id=core_name,
                            faction=ch.factions[0],
                            position_pref='back')],
        shop=[ShopCard(x=0, name=core_name, faction=ch.factions[0],
                       cost=ch.cost)])
    assert _adr0300_copy_pair_channels_buy_tags(st, sess).get(core_name) in ('copy', 'bridge_core',
                                                 'line_carry')


def test_target_piece_takes_target_tag_not_copy() -> None:
    """目标件副本优先取目标类标签(优先序 target > copy)。"""
    from sr_od.application.currency_war.kernel.cw_bridge_pool import BRIDGE_POOL
    fixed_name = next(n for c in BRIDGE_POOL for n in c.fixed)
    ch = CHARACTERS[fixed_name]
    sess = _adr0300_copy_pair_channels_sess()   # 无方向:桥 fixed∪core 全是目标
    st = _adr0300_copy_pair_channels_state(
        bench=[BenchChar(slot=0, char_id=fixed_name,
                         faction=ch.factions[0])],
        shop=[ShopCard(x=0, name=fixed_name, faction=ch.factions[0],
                       cost=ch.cost)])
    tags = _adr0300_copy_pair_channels_buy_tags(st, sess)
    assert tags.get(fixed_name) in ('bridge_core', 'copy') \
        and tags.get(fixed_name) != 'pair'


# --- ③ 标签注册 --------------------------------------------------------------


def test_pair_copy_registered_everywhere() -> None:
    """pair/copy 进 buy_tag_priority 与 economy/war 放行
    标签集 + _PIPELINE_TAGS(层2 不误杀/层3 板面显影;
    追赶标签集已随 W126/ADR-0349 退场)。"""
    assert 'pair' in _adr0300_copy_pair_channels_REG.buy_tag_priority
    assert 'copy' in _adr0300_copy_pair_channels_REG.buy_tag_priority
    for tags in (_adr0300_copy_pair_channels_REG.economy_tags, _adr0300_copy_pair_channels_REG.war_tags):
        assert 'pair' in tags
        assert 'copy' in tags
    assert 'pair' in _PIPELINE_TAGS
    assert 'copy' in _PIPELINE_TAGS


# ==================== w611_o1_fill_buy ====================

from sr_od.application.currency_war.kernel.cw_plane_table import (
    level_cost,
)
from sr_od.application.currency_war.decision.decision_v2.posture import Posture
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import (
    _check_constraint,
)
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision.decision_v2.ev import RoundPosture
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import (
    score_candidate,
)

_w611_o1_fill_buy_REG = DEFAULT_REGISTRY


def _w611_o1_fill_buy_state(*, gold: int = 100, plane: int = 1, r: int = 3, level: int = 6,
           bench: list[BenchChar | None] | None = None,
           shop: list[ShopCard] | None = None,
           board: dict | None = None,
           hp: int = 80) -> GameState:
    return GameState(
        plane=plane, round_num=r, gold=gold, level=level, hp=hp,
        shop_refresh_cost=2,
        deployed=[], bench=bench if bench is not None else [None] * BENCH_CAPACITY,
        shop=shop if shop is not None else [], node_type='battle',
        board=board or {})


def _sc(name: str, cost: int = 2) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


def _full_bench() -> list[BenchChar]:
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS

    def _ch(name: str, slot: int) -> BenchChar:
        fac = (CHARACTERS[name].factions or ('?',))[0]
        return BenchChar(slot=slot, char_id=name, faction=fac, star=1)
    return [_ch('阿格莱雅', i) for i in range(BENCH_CAPACITY)]


def _w611_o1_fill_buy_sess(state: GameState, *, level_up: bool = False) -> StrategySession:
    s = StrategySession()
    s.v3_dp_posture = RoundPosture(
        (state.plane, state.round_num),
        Posture(save=False, level_up=level_up, refresh_budget=0))
    return s


def _o1_cands(state: GameState, session: StrategySession) -> list:
    return [c for c in generate_candidates(state, session, _w611_o1_fill_buy_REG)
            if c.tag == 'o1_bench_fill']


# --- 放行域命中 ---------------------------------------------------------------


def test_o1_fill_generated_in_overflow_free_bench_frame() -> None:
    """局23 型帧(g=100+备战空+非目标件):散件生成 o1 标签、评 0 中性
    (义务证明背书,bd 带通道标记)。"""
    st = _w611_o1_fill_buy_state(gold=100, shop=[_sc('乱破', 2)], board={})
    s = _w611_o1_fill_buy_sess(st)
    cands = _o1_cands(st, s)
    assert len(cands) == 1
    val, bd = score_candidate(cands[0], st, s, _w611_o1_fill_buy_REG)
    assert val == 0.0 and bd.get('o1_bench_fill') is True
    assert bd.get('int_emb') == 0.0    # 无息分量可剥离(EV 剥离单一源)


def test_o1_buy_allowed_above_reserve_cap() -> None:
    """逐笔可行性(放行侧):花后 ≥R*(常态无排程 R*=息线)→ gold_floor
    不拒(散件 2 费,100→58 ≥50)。"""
    st = _w611_o1_fill_buy_state(gold=100, shop=[_sc('乱破', 2)], board={})
    s = _w611_o1_fill_buy_sess(st)
    cand = _o1_cands(st, s)[0]
    assert _check_constraint('gold_floor', cand, st.copy(), st, s,
                             _w611_o1_fill_buy_REG, val=0.0, bd={}, auth=None) is None


def test_o1_buy_rejected_below_reserve_cap() -> None:
    """逐笔可行性(拒侧):排程升级帧(R*=息线+升级费)花后吃储蓄 →
    gold_floor 的 o1 地板加深拒(g=50+level_cost(5)+3,买 6 费 →
    花后 <R*)。level=5 < 峰值级 6 → 排程预告态成立(批 3 确定性核)。"""
    st = _w611_o1_fill_buy_state(gold=50 + level_cost(5) + 3, r=5, level=5,
                shop=[_sc('乱破', 6)], board={})
    s = _w611_o1_fill_buy_sess(st)
    cand = _o1_cands(st, s)[0]
    reason = _check_constraint('gold_floor', cand, st.copy(), st, s,
                               _w611_o1_fill_buy_REG, val=0.0, bd={}, auth=None)
    assert reason is not None and reason.constraint == 'gold_floor'


# --- 其余域原样([31] 限域取代的边界)----------------------------------------


def test_no_o1_below_reserve_cap() -> None:
    """凑息期(g≤R*):散件不生成([2]/[28] 凑息优先,零漂移锚)。"""
    st = _w611_o1_fill_buy_state(gold=30, shop=[_sc('乱破', 2)], board={})
    assert _o1_cands(st, _w611_o1_fill_buy_sess(st)) == []


def test_no_o1_when_bench_full() -> None:
    """满槽帧:散件不生成(A-1/A-2 槽位约束原样)。"""
    st = _w611_o1_fill_buy_state(gold=100, bench=_full_bench(),
                shop=[_sc('乱破', 2)], board={})
    assert _o1_cands(st, _w611_o1_fill_buy_sess(st)) == []


def test_no_o1_in_emergency() -> None:
    """应急帧让位(保血域,辖区不相交)。"""
    st = _w611_o1_fill_buy_state(gold=100, hp=20, shop=[_sc('乱破', 2)], board={})
    assert _o1_cands(st, _w611_o1_fill_buy_sess(st)) == []


def test_bond_fallback_beats_o1_quality_order() -> None:
    """质量序(直查 _buy_tag,W47 锁同口径):锁线帧同阵营 1 费件 →
    bond_fallback(凑羁绊填充,O1 前置);不同阵营非引擎件 → o1 标签
    (散件末位)。O1 只兜 bond_fallback 之后的尾。"""
    from types import SimpleNamespace
    from sr_od.application.currency_war.kernel.cw_intention import (
        HoardTarget,
        IntentionState,
    )
    from sr_od.application.currency_war.decision.decision_v2.candidates import _buy_tag
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    sess.v3_intention = ist
    sess.v3_hoard = HoardTarget(
        frozenset({'姬子·启行'}), frozenset(), 'locked')
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    fac = (CHARACTERS['桑博'].factions or ('?',))[0]
    st = _w611_o1_fill_buy_state(gold=100, board={},
                bench=[BenchChar(slot=0, char_id='桑博', faction=fac,
                                 star=1)] + [None] * (BENCH_CAPACITY - 1))
    fill_card = SimpleNamespace(name='凑档件', faction=fac, cost=1,
                                x=0, star=1)
    loose_card = SimpleNamespace(name='乱破', faction='巡海游侠', cost=2,
                                 x=0, star=1)
    assert _buy_tag(fill_card, st, sess, _w611_o1_fill_buy_REG) == 'bond_fallback'
    assert _buy_tag(loose_card, st, sess, _w611_o1_fill_buy_REG) == 'o1_bench_fill'


def test_engine_seed_rejection_not_bypassed_by_o1() -> None:
    """引擎种子散买断(ADR-0333)先于 O1:板面已有未成型体系时新体系
    引擎件仍不生成(O1 不绕开既有方向门)。"""
    st = _w611_o1_fill_buy_state(gold=100, board={'仙舟': 1}, shop=[_sc('卡芙卡', 4)])
    assert _o1_cands(st, _w611_o1_fill_buy_sess(st)) == []



# ==================== w611_reserve_admission ====================

import dataclasses

from sr_od.application.currency_war.kernel.cw_economy import (
    reserve_cap,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.economy_cycle import (
    bench_fill_account,
    channel_capacity,
    obligation,
)
from sr_od.application.currency_war.decision.decision_v2.ev import RoundPosture
from sr_od.application.currency_war.decision.decision_v2.posture import Posture
from sr_od.application.currency_war.decision.decision_v2.posture_release import (
    authorize_release_refresh,
    release_directive,
    wrap_posture,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_w611_reserve_admission_REG = DEFAULT_REGISTRY

# 关行为锁显式注入(危机臂开臂后默认 registry=True,ADR-0503;应急让位语义
# 锁改注入 False 仍测,不删——与 test_cw_w633 同款形态)。
_REG_CRISIS_OFF = dataclasses.replace(_w611_reserve_admission_REG, crisis_release_enabled=False)


def _w611_reserve_admission_state(*, gold: int = 80, plane: int = 1, r: int = 3, level: int = 6,
           deployed: list[BenchChar] | None = None,
           bench: list[BenchChar | None] | None = None,
           shop: list[ShopCard] | None = None,
           board: dict | None = None,
           hp: int = 80) -> GameState:
    return GameState(
        plane=plane, round_num=r, gold=gold, level=level, hp=hp,
        shop_refresh_cost=2,
        deployed=deployed if deployed is not None else [],
        bench=bench if bench is not None else [None] * BENCH_CAPACITY,
        shop=shop if shop is not None else [], node_type='battle',
        board=board or {})


def _w611_reserve_admission_sc(name: str, cost: int = 2) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


def _w611_reserve_admission_sess(state: GameState, *, level_up: bool = False,
          refresh_budget: int = 0) -> StrategySession:
    s = StrategySession()
    s.v3_dp_posture = RoundPosture(
        (state.plane, state.round_num),
        Posture(save=False, level_up=level_up, refresh_budget=refresh_budget))
    return s


def _saving_posture() -> Posture:
    """DP 解出存息的姿态(局23 帧形态:无升级、无 D 预算)。"""
    return Posture(save=True, level_up=False, refresh_budget=0, tag='存息')


def _ch(name: str, slot: int) -> BenchChar:
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    fac = (CHARACTERS[name].factions or ('?',))[0]
    return BenchChar(slot=slot, char_id=name, faction=fac, star=1)


def _w611_reserve_admission_full_bench() -> list[BenchChar]:
    return [_ch('阿格莱雅', i) for i in range(BENCH_CAPACITY)]


# --- O1 · 备战空位填补容量(W611 §1.2/§1.3)------------------------------


def test_bench_fill_capacity_unlocks_obligation_in_targetless_frame() -> None:
    """锁 1·局23 型帧(comp 空+备战空):填补件计入容量 → 义务开工。
    病灶机制=无目标帧正 EV 帧空 → C_t=0 → 义务恒 0(三次复发根);
    O1 后 g=100、店有 2 费件 → 填补账=2;容量另含刷新预算分量
    (批 3 预算收权:min(6,⌊50/2⌋)=6 刷×2=12)→ 容量 14;义务=min(50,14)
    =14,flip 预算=max(义务, 排程预算×刷价)=14。"""
    st = _w611_reserve_admission_state(gold=100, shop=[_w611_reserve_admission_sc('桑博', 2)], board={})
    s = _w611_reserve_admission_sess(st)
    assert bench_fill_account(st, _w611_reserve_admission_REG) == 2
    assert channel_capacity(st, s, _w611_reserve_admission_REG) == 14
    assert obligation(st, s, _w611_reserve_admission_REG) == 14
    d = release_directive(st, s, _w611_reserve_admission_REG, 'FORM', _saving_posture())
    assert d is not None and d.reason == 'flip' and d.budget_gold == 14
    assert wrap_posture(_saving_posture(), d).tag == 'release'


def test_fill_and_crossing_share_one_slot_account() -> None:
    """锁 2·槽位账单源唯一:跨档件(countable)与填补件(fill)共享
    同一份空槽——2 空槽时两路并计、1 空槽时跨档件占槽后填补计 0
    (A-2 槽位机会成本在两路间不双计)。"""
    st = _w611_reserve_admission_state(gold=80, board={'仙舟': 2},
                shop=[_w611_reserve_admission_sc('丹恒·饮月', 2), _w611_reserve_admission_sc('桑博', 1)])
    s = _w611_reserve_admission_sess(st)
    # 容量 15 = 刷新预算 6 刷×2 + 跨档 2 + 填补 1(两空槽;批 3 加刷新分量)
    assert channel_capacity(st, s, _w611_reserve_admission_REG) == 15
    st.bench = _w611_reserve_admission_full_bench()[:8] + [None]       # 仅 1 空槽(bench 占用数口径)
    assert channel_capacity(st, s, _w611_reserve_admission_REG) == 14  # 槽被跨档件占用,填补=0


def test_fill_zero_when_bench_full_a1_a2_preserved() -> None:
    """A-1/A-2 原样:满槽帧非合成件不计容量(期权泵死法 W469 的防线上
    移为「槽位约束」,不是废除——义务不把金推进无槽可放的件)。"""
    st = _w611_reserve_admission_state(gold=100, bench=_w611_reserve_admission_full_bench(),
                shop=[_w611_reserve_admission_sc('桑博', 2)], board={})
    assert bench_fill_account(st, _w611_reserve_admission_REG) == 0


# --- E1 · 存息准入门(W611 §2.1)------------------------------------------


def test_admission_zero_capacity_frame_carry_label_honest() -> None:
    """锁 4·无对象结转帧(g>R*,bench 满,店无跨档件):义务=0 但存息
    非法 → 零预算 release 指令,标签诚实(tag='release'),authorize
    恒拒 = 容量不足的合法结转(量=溢余,遥测披露面)。
    批 3 机制口径(W623 D2):刷新预算计入容量后,溢余 ≥ 刷价的帧由
    flip 承接(义务通道有对象);准入门的残余辖域=溢余 < 刷价且无店内
    账的帧——gold 51(溢余 1 < 刷价 2)即此,容量真 0。"""
    st = _w611_reserve_admission_state(gold=51, bench=_w611_reserve_admission_full_bench(), shop=[_w611_reserve_admission_sc('桑博', 1)],
                board={})
    s = _w611_reserve_admission_sess(st)
    d = release_directive(st, s, _w611_reserve_admission_REG, 'FORM', _saving_posture())
    assert d is not None and d.reason == 'reserve_admission'
    assert d.budget_gold == 0
    assert wrap_posture(_saving_posture(), d).tag == 'release'
    s.v3_release = d
    assert authorize_release_refresh(s, 51, 2, _w611_reserve_admission_REG) == ''


def test_action_postures_never_get_admission_reason() -> None:
    """DP 行动姿态(升级)不经准入门——义务只禁存息,不禁 DP 已授权的
    行动;升级帧的溢余花费走 flip 义务预算(reason='flip',升级费已计
    R* 储蓄,溢余段义务=min(溢余,容量)),reason 恒非 'reserve_admission'。"""
    st = _w611_reserve_admission_state(gold=100)   # 店空:容量=升级费
    s = _w611_reserve_admission_sess(st, level_up=True)
    d = release_directive(st, s, _w611_reserve_admission_REG, 'FORM',
                          Posture(save=False, level_up=True,
                                  refresh_budget=0))
    assert d is not None and d.reason == 'flip'
    assert d.budget_gold == obligation(st, s, _w611_reserve_admission_REG)


def test_zero_drift_below_reserve_cap() -> None:
    """锁 3·零漂移锚:g≤R* 帧义务=0、准入门不辖(息线以内持有弱占优,
    [2]/[28] 凑息期行为逐字段不变——sim 息基守卫的结构性依据)。"""
    st = _w611_reserve_admission_state(gold=30, shop=[_w611_reserve_admission_sc('桑博', 2)], board={})
    s = _w611_reserve_admission_sess(st)
    assert obligation(st, s, _w611_reserve_admission_REG) == 0
    assert release_directive(st, s, _w611_reserve_admission_REG, 'FORM', _saving_posture()) is None


def test_emergency_frame_release_yields() -> None:
    """应急帧让位(保血域,辖区不相交):hp≤25 时 flip 与准入门都不辖,
    姿态维持原样(W516 保血域不被义务模型侵入)。
    危机臂开臂(ADR-0503)后应急让位语义锁改注入 False 仍测——钉
    ADR-0426 让位结构本身(关行为),不随第三臂消失。"""
    st = _w611_reserve_admission_state(gold=100, hp=20, bench=_w611_reserve_admission_full_bench(),
                shop=[_w611_reserve_admission_sc('桑博', 2)], board={})
    s = _w611_reserve_admission_sess(st)
    assert release_directive(st, s, _REG_CRISIS_OFF, 'FORM',
                             _saving_posture()) is None


def test_emergency_frame_crisis_arm_directive() -> None:
    """危机臂 ON 对照(ADR-0503 第三臂):同帧默认 registry 下危机指令
    开火(reason='crisis')——让位语义由本臂接管,非消失。"""
    st = _w611_reserve_admission_state(gold=100, hp=20, bench=_w611_reserve_admission_full_bench(),
                shop=[_w611_reserve_admission_sc('桑博', 2)], board={})
    s = _w611_reserve_admission_sess(st)
    d = release_directive(st, s, _w611_reserve_admission_REG, 'FORM', _saving_posture())
    assert d is not None and d.reason == 'crisis'
    assert d.budget_gold > 0
    assert wrap_posture(_saving_posture(), d).tag == 'release'


# --- 守息线 ≡ 封顶线(W611 §2.2 恒等式)----------------------------------


def test_reserve_floor_identical_to_interest_cap_line() -> None:
    """锁 6·恒等式:R* 的息线分量 = interest_cap×10(息帽同源派生),
    基参数下 == interest_floor(50)且恒 ≥ 封顶线——「守息线 ≤ 封顶线」
    结构性成立,不依赖两常量手工同步。"""
    st = _w611_reserve_admission_state()
    s = _w611_reserve_admission_sess(st)
    assert _w611_reserve_admission_REG.interest_cap * 10 == _w611_reserve_admission_REG.interest_floor()
    assert reserve_cap(st, s, _w611_reserve_admission_REG) >= _w611_reserve_admission_REG.interest_cap * 10
    # 默认无 override(并自 test_cw_w628 d3 单一源锁;override 行为面由
    # test_cw_w606_switch 注入锁辖,D3 三处重复按 README 纪律 8 择一保留)
    assert _w611_reserve_admission_REG.interest_floor_override is None

# —— 换核隔离桶(2026-09-03 测试分层批)——
# 本文件属 legacy_baseline 桶:锁的是旧决策核(decision_v2)内部行为语义,
# 随旧核退役而消亡;默认全量与快速集均不跑,仅基线冻结审计/A-B 开跑前
# 两时点单独跑。口径见 sr-od-test/README.md「测试纪律 · legacy 桶」。
import pytest

pytestmark = pytest.mark.legacy_baseline
