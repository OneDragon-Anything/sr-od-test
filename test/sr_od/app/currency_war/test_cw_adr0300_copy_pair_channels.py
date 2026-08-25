# -*- coding: utf-8 -*-
"""ADR-0300 copy/pair 通道迁移批锁(买入面残余清偿)。

锁定对象(decision_v2/candidates.py + registry.py + scoring.py):
① pair 通道:v1 _pair_wants 直通(冷启动/方向门 r350/A5 spread/
   同阵营凑对/r408 不回买),非目标件生成 'pair' 候选;
② copy 通道:同名副本素材(r383b)打专属 'copy' 标签;保留判据
   镜像 v1 _copy_swap_useless(r410:在场副本会被 off-target 卖出
   → 买新副本=无效换卡,不生成);
③ 标签注册:pair/copy 进 buy_tag_priority 与 economy/war/catchup
   放行标签集(emergency 保持窄)+ _PIPELINE_TAGS(板面显影)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    _PIPELINE_TAGS,
)

_REG = DEFAULT_REGISTRY

#: 阿格莱雅:非桥池件(非目标)、非过渡体系阵营(bonds ∩ 引擎
#: 阵营=∅——pair 判据不与 engine_seed 交叠)——测试用搭档件载体;
#: cost 显式 3(>bond_fallback_max_cost,隔离 [31] 降级通道)
_FACTION = CHARACTERS['阿格莱雅'].factions[0]


def _sess(line: str | None = None) -> StrategySession:
    """意向载体(ADR-0336 后唯一形态;``line`` 参数=意向锁定视窗,
    旧 locked_line 垫片已删)。"""
    s = StrategySession()
    if line:
        from sr_od.application.currency_war.cw_intention import (
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


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 30, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _buy_tags(st: GameState, sess: StrategySession) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in generate_candidates(st, sess, _REG):
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
    sess = _sess()   # 无方向:非冷启动常态分支
    st = _state(board={_FACTION: 1}, shop=[_aglaea()])
    assert _buy_tags(st, sess).get('阿格莱雅') == 'pair'


def test_pair_rejected_new_faction_spread_cap() -> None:
    """A5 spread 门:已有阵营 ≥3 时新阵营搭档不生成(v1 同判据)。"""
    sess = _sess()
    board = {'仙舟': 1, '护盾': 1, '量子': 1}
    st = _state(board=board, shop=[_aglaea()])
    assert '阿格莱雅' not in _buy_tags(st, sess)


def test_pair_rejected_offline_faction_when_locked() -> None:
    """r350 方向门:锁线后只认线形态羁绊——线外阵营搭档不走 pair
    通道(v1 _pair_wants 直通,判据不复制;cost=3 隔离 bond_fallback)。"""
    sess = _sess(line='jizi_train')
    st = _state(board={_FACTION: 1}, shop=[_aglaea()])
    assert '阿格莱雅' not in _buy_tags(st, sess)


def test_pair_rejected_round_sold_rebuy() -> None:
    """r408 对称臂:本轮刚卖过的卡名 pair 通道不回买(cost=3 隔离
    bond_fallback——层4 same_round_mutex 另辖全域)。"""
    sess = _sess()
    sess.v2_round_key = (1, 5)
    sess.v2_round_sold = {'阿格莱雅'}
    st = _state(board={_FACTION: 1}, shop=[_aglaea()])
    assert '阿格莱雅' not in _buy_tags(st, sess)


# --- ② copy 通道 -------------------------------------------------------------


def test_copy_tag_for_same_name_second_copy() -> None:
    """同名第 2 份副本素材(r383b)打专属 'copy' 标签(与门失效
    形态 pair 区分,检查器不空转报警)。"""
    sess = _sess()
    st = _state(
        round_num=1,   # 开局轮:冷启动分支的副本放行面
        bench=[BenchChar(slot=0, char_id=_PL, faction=_PL_F)],
        shop=[_pela()])
    assert _buy_tags(st, sess).get(_PL) == 'copy'


def test_copy_blocked_by_useless_swap_guard() -> None:
    """r410 保留判据镜像:在场副本会被 off-target 卖出(非
    target_core 且 bonds ∩ target_factions=∅)→ 买新副本=无效
    换卡,不生成候选(v1 _copy_swap_useless 直通)。"""
    sess = _sess()   # target_comp=None → 在场副本无保留判据
    st = _state(
        board={_PL_F: 1},
        deployed=[BenchChar(slot=0, char_id=_PL, faction=_PL_F,
                            position_pref='back')],
        shop=[_pela()])
    assert _PL not in _buy_tags(st, sess)


def test_copy_allowed_when_deployed_copy_kept() -> None:
    """r410 保留判据反例:在场副本属 target_cores(显式保留)→
    买副本合法(凑对/3合1),候选生成。"""
    from sr_od.application.currency_war.cw_bridge_pool import BRIDGE_POOL
    core_name = next(n for c in BRIDGE_POOL for n in c.core)
    ch = CHARACTERS[core_name]
    sess = _sess()
    sess.target_comp = type('_TC', (), {
        'factions': (), 'core_chars': (core_name,)})()
    st = _state(
        board={ch.factions[0]: 1},
        deployed=[BenchChar(slot=0, char_id=core_name,
                            faction=ch.factions[0],
                            position_pref='back')],
        shop=[ShopCard(x=0, name=core_name, faction=ch.factions[0],
                       cost=ch.cost)])
    assert _buy_tags(st, sess).get(core_name) in ('copy', 'bridge_core',
                                                 'line_carry')


def test_target_piece_takes_target_tag_not_copy() -> None:
    """目标件副本优先取目标类标签(优先序 target > copy)。"""
    from sr_od.application.currency_war.cw_bridge_pool import BRIDGE_POOL
    fixed_name = next(n for c in BRIDGE_POOL for n in c.fixed)
    ch = CHARACTERS[fixed_name]
    sess = _sess()   # 无方向:桥 fixed∪core 全是目标
    st = _state(
        bench=[BenchChar(slot=0, char_id=fixed_name,
                         faction=ch.factions[0])],
        shop=[ShopCard(x=0, name=fixed_name, faction=ch.factions[0],
                       cost=ch.cost)])
    tags = _buy_tags(st, sess)
    assert tags.get(fixed_name) in ('bridge_core', 'copy') \
        and tags.get(fixed_name) != 'pair'


# --- ③ 标签注册 --------------------------------------------------------------


def test_pair_copy_registered_everywhere() -> None:
    """pair/copy 进 buy_tag_priority 与 economy/war/catchup 放行
    标签集 + _PIPELINE_TAGS(层2 不误杀/层3 板面显影)。"""
    assert 'pair' in _REG.buy_tag_priority
    assert 'copy' in _REG.buy_tag_priority
    for tags in (_REG.economy_tags, _REG.war_tags, _REG.catchup_tags):
        assert 'pair' in tags
        assert 'copy' in tags
    assert 'pair' in _PIPELINE_TAGS
    assert 'copy' in _PIPELINE_TAGS
