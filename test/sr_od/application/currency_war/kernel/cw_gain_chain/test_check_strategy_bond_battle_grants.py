"""策略卡羁绊条件战后发放武装检查效果条目测试(镜像 src = kernel/cw_gain_chain.py
的 check_strategy_bond_battle_grants;两拍制武装拍,零 rng)。

测试面依据 = 设计稿(原件已退役;§ 号 = 原稿节序)§4
锁 2/3/6/9 + 已退役评审稿(直构形态先例 = 同目录
test_check_strategy_boss_battle_grants.py 状态容器直置;激活数评估单一源
= board 状态容器计数与 board_by_row 身份聚合取 max 判激活,cw_system_cards.
_faction_count 同款):
- 条件矩阵短路:未持卡/表外卡 → False 零写;
- 激活数评估口径:双源 max 融合(board 与 deployed 双未观察 → 0
  fail-closed 零武装)、独立羁绊 1 人即激活(tiers=(1,) 与左面板同
  口径)、FACTIONS 外未知名不计、阈值方向 ≥(达到即满足);
- 武装写形态:evidence ``strategy_bond_battle#arm:<卡名>``、armed
  置 True(write_logic 逻辑渠道);条件不满足零写零武装;
- 零 rng:武装拍无采样面(采样归发放拍),固定输入重放零随机性。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_bond_battle_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
)

_SIG_OBS = ChannelSig(family='obs', actor='TestSigWriter')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '不要小看我们的羁绊'

#: 6 个非选边型独立羁绊(tiers=(1,) 单人即激活;布洛妮娅系选边型双羁绊
#: 角色直构引入选边分支,负控直构避开——独立计入口径已由其余 6 名覆盖)。
_INDEPENDENT_TAGS = ('大守护者', '救世主', '头号玩家', '挚爱之人',
                     '魔术师', '命运卜者')
#: 8 激活板(6 独立 + 治疗 2 + 护盾 2,治疗/护盾 tiers[0] 均 = 2)。
_BOARD_ACT8 = {**dict.fromkeys(_INDEPENDENT_TAGS, 1),
               '治疗': 2, '护盾': 2}
#: 7 激活负控板(同形少护盾行)。
_BOARD_ACT7 = {**dict.fromkeys(_INDEPENDENT_TAGS, 1), '治疗': 2}


def _gs(*, card: str | None = _CARD) -> GameState:
    """直构 gs(card=None = 未持卡)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card',
                       sig=_LSIG)
    return gs


def test_no_card_and_out_of_registry_zero_arm() -> None:
    """锁 3:未持卡 → False 零写;持表外卡(躺平,卡面含「羁绊/战斗」
    字样但不在登记表)→ False 零写(表外卡一律无条目,禁从效果原文
    自动猜装的通道纪律)。"""
    for card in (None, '躺平'):
        gs = _gs(card=card)
        gs.observe(gs.board, dict(_BOARD_ACT8), sig=_SIG_OBS)
        before = gs.write_seq
        assert check_strategy_bond_battle_grants(gs, _LSIG) is False, \
            f'card={card!r} 误武装'
        assert gs.strategy_bond_battle_armed.value is None, \
            f'card={card!r} 误写武装标记'
        assert gs.write_seq == before, f'card={card!r} 误写'


def test_eight_bonds_arm_write_shape() -> None:
    """锁 1 单元面(武装拍):持卡 + 8 激活板 → True、armed 置 True
    (write_logic 逻辑渠道)、evidence ``strategy_bond_battle#arm:<卡名>``。"""
    gs = _gs()
    gs.observe(gs.board, dict(_BOARD_ACT8), sig=_SIG_OBS)
    assert check_strategy_bond_battle_grants(gs, _LSIG) is True
    assert gs.strategy_bond_battle_armed.value is True, '武装标记未置位'
    assert gs.strategy_bond_battle_armed.source == 'logic', \
        '武装写应走逻辑渠道'
    assert gs.strategy_bond_battle_armed.evidence == \
        f'strategy_bond_battle#arm:{_CARD}', \
        f'evidence 漂移: {gs.strategy_bond_battle_armed.evidence}'


def test_below_threshold_no_arm() -> None:
    """锁 2(条件不满足零武装):7 激活板(< 阈值 8)→ False、armed
    保持未观察、零写(达标才武装,宁缺勿造)。"""
    gs = _gs()
    gs.observe(gs.board, dict(_BOARD_ACT7), sig=_SIG_OBS)
    before = gs.write_seq
    assert check_strategy_bond_battle_grants(gs, _LSIG) is False
    assert gs.strategy_bond_battle_armed.value is None, '不足阈值误武装'
    assert gs.write_seq == before, '不足阈值误写'


def test_dual_source_max_fusion() -> None:
    """锁 6a(双源 max 融合):board 计数(治疗 1,不足)与 deployed
    身份聚合(治疗 2,达标)不一致时取 max 判激活——max(1, 2) = 2 达
    标,合计 6 独立 + 治疗 + 护盾 = 8 武装(漏判激活比多判更伤,
    _faction_count 判激活侧同款)。"""
    gs = _gs()
    gs.observe(gs.board, {**dict.fromkeys(_INDEPENDENT_TAGS, 1),
                          '治疗': 1, '护盾': 2}, sig=_SIG_OBS)
    gs.observe(gs.deployed, DeployedView(
        back_slots=[Unit(char_id='娜塔莎', star=1),
                    Unit(char_id='藿藿', star=1)]), sig=_SIG_OBS)
    assert check_strategy_bond_battle_grants(gs, _LSIG) is True, \
        '双源 max 融合未按身份聚合补足激活数'
    assert gs.strategy_bond_battle_armed.value is True


def test_fail_closed_when_board_and_deployed_unobserved() -> None:
    """锁 6b(fail-closed):board 与 deployed 双未观察 → 激活数 = 0
    → False 零武装(宁缺勿造,无真值不猜)。"""
    gs = _gs()
    before = gs.write_seq
    assert check_strategy_bond_battle_grants(gs, _LSIG) is False
    assert gs.strategy_bond_battle_armed.value is None
    assert gs.write_seq == before, '双未观察误写'


def test_independent_counts_and_unknown_tag_ignored() -> None:
    """锁 6c(独立羁绊计入 + 未知名不计):6 独立 1 人各计 1 激活
    (tiers=(1,),与左面板显示同口径)——6 独立 + 治疗 2 = 8 武装成功
    即独立计入成立的直接证据(独立不计则最多 2 激活必不武装);
    FACTIONS 外未知名(幻影羁绊 99 人)不计入激活数(未知 = 不可判,
    禁猜)。"""
    gs = _gs()
    gs.observe(gs.board, {**_BOARD_ACT8, '幻影羁绊': 99}, sig=_SIG_OBS)
    assert check_strategy_bond_battle_grants(gs, _LSIG) is True, \
        '独立羁绊计入或未知名排除口径漂移'


def test_threshold_direction_ge() -> None:
    """锁 6d(阈值方向 ≥,达到即满足):治疗 2 人(= tiers[0])达标;
    治疗单独 1 人(< tiers[0])不计——同板替换 1 行对拍,方向取反即
    红的判别形。"""
    gs_ok = _gs()
    gs_ok.observe(gs_ok.board, dict(_BOARD_ACT8), sig=_SIG_OBS)
    assert check_strategy_bond_battle_grants(gs_ok, _LSIG) is True
    gs_lt = _gs()
    gs_lt.observe(gs_lt.board, {**dict.fromkeys(_INDEPENDENT_TAGS, 1),
                                '治疗': 1, '护盾': 2}, sig=_SIG_OBS)
    assert check_strategy_bond_battle_grants(gs_lt, _LSIG) is False, \
        '治疗 1 人(< tiers[0])误计激活'
