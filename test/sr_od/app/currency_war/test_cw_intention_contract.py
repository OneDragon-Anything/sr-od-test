"""意向域合同（kernel 判策第三层：方向状态机怎么驱动、怎么判定定型）。

被测模块：``kernel/cw_intention.py``（意向状态机/committed 权威派生/
锁定帧买侧约束）、``kernel/cw_strategy_session.py``（会话与策略状态
工厂注入槽）。

合同面（从源码推导）：
- §1 IntentionState 初始态（状态机冷建形态）;
- §2 drive_intention 驱动幂等（P7 契约:每 game-round 恰一次,键守卫,
  工厂未注册保守跳过）;
- §3 committed_authority 权威序（三支任一成立即 True;缺供给帧 =
  保守侧 False——True=激进侧,拔掉供给探针必须落 False）;
- §4 locked_buy_scope 约束基准（空窗/弱意向 → None 不约束）。
本文件不重复:方向层行为锁的桌面推导（归 S3 statefn 数学锚）、
预算核消费面（K2）。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    BS_SCHEMA_VERSION,
    SCREEN_BOSS_BRIEFING,
    SCREEN_PREP_FRAME,
    GameState,
    board_state_of,
    register_sig_actors,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig as Sig,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    committed_authority,
    drive_intention,
    locked_buy_scope,
    plane_of,
    round_num_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
    install_strategy_state_factory,
    strategy_state_of,
)

register_sig_actors('TestSigWriter')


def _sig() -> Sig:
    return Sig(family='obs', actor='TestSigWriter', mode='read')


def _bs_with_node(plane: int = 1, round_num: int = 3) -> GameState:
    """构带 node 组合键的容器(经观察链派生,BOSS 简报腿直定类型)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe_screen_context(SCREEN_PREP_FRAME, phase_round=(plane, round_num),
                              sig=_sig())
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING, sig=_sig())
    return bs


# ============================================================ §1 初始态

def test_intention_state_cold_defaults() -> None:
    """状态机冷建形态:phase 空/锁定与对字段空/驱逐与旱位计数清零
    (每局新建 StrategySession 保证跨局零残留的结构前提)。"""
    ist = IntentionState()
    assert ist.phase == 'unlocked' and ist.locked_comp == ''
    assert ist.p1_pair == () and ist.transition_pair == ()
    assert ist.evicted == set() and ist.pair_evicted == set()
    assert ist.pair_drought == {}


# ============================================================ §2 驱动幂等

@pytest.fixture()
def strategy_state_factory():
    """注册 mandate_v1 StrategyState 工厂(全局注入槽,teardown 还原)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
        StrategyState,
    )
    install_strategy_state_factory(StrategyState)
    yield StrategyState
    install_strategy_state_factory(None)


def test_drive_intention_idempotent_per_round(strategy_state_factory) -> None:
    """P7 契约:同轮重入只驱动一次(键守卫 = (plane, round_num);
    并存驱动天然幂等,重入不重复计数)。"""
    bs = _bs_with_node(plane=1, round_num=3)
    sess = StrategySession()
    drive_intention(bs, sess)
    st = strategy_state_of(sess)
    key_first = st.v3_intention_key
    drive_intention(bs, sess)
    assert st.v3_intention_key == key_first, '同轮键不换'
    assert st.v3_intention_key == (1, 4), 'BOSS 简报腿已推进 +1:(1,3)→(1,4)'


def test_drive_intention_key_follows_node_readout(
        strategy_state_factory) -> None:
    """驱动键 = (plane_of, round_num_of) 现读(键面跟随节点读口);
    同序重观察被派生腿去重(node 不再变)→ 键不变(幂等窗 = 节点读口)。"""
    bs = _bs_with_node(plane=1, round_num=3)
    sess = StrategySession()
    drive_intention(bs, sess)
    st = strategy_state_of(sess)
    assert st.v3_intention_key == (1, 4)
    # 同序 BOSS 简报重进:派生腿去重(去重键已占),node 读口不变 → 键不变
    bs.observe_screen_context(SCREEN_BOSS_BRIEFING, sig=_sig())
    drive_intention(bs, sess)
    assert st.v3_intention_key == (1, 4), '去重保证同节点不二次计数'
    # 新节点读口(跨位面状态)→ 新键面
    bs_p2 = _bs_with_node(plane=2, round_num=1)
    drive_intention(bs_p2, sess)
    assert st.v3_intention_key != (1, 4), '新轮读口 = 新键面'


def test_drive_intention_without_factory_skips() -> None:
    """工厂未注册(第三方策略面)→ 保守跳过(kernel 不代建,零异常)。"""
    bs = _bs_with_node()
    sess = StrategySession()
    drive_intention(bs, sess)
    assert strategy_state_of(sess) is None


# ============================================================ §3 committed 权威序

def test_committed_authority_authority_order() -> None:
    """权威序(任一成立即 True):
    ① 位面≥2 恒定型(P2 起严于文档口径);
    ② 意向状态机 phase=locked;
    ③ p1_pair 配方锁已立。"""
    bs_p2 = _bs_with_node(plane=2, round_num=1)
    assert committed_authority(bs_p2, StrategySession()) is True, \
        '位面≥2 恒定型(无意向供给也 True)'

    bs_p1 = _bs_with_node(plane=1, round_num=3)
    sess = StrategySession()
    assert committed_authority(bs_p1, sess) is False, 'P1 无锁 = 双轨期'

    ist_holder = SimpleNamespace(v3_intention=IntentionState())
    ist_holder.v3_intention.phase = 'locked'
    sess_locked = SimpleNamespace(strategy_state=ist_holder)
    assert committed_authority(bs_p1, sess_locked) is True, '锁线即定型'

    ist_pair = SimpleNamespace(v3_intention=IntentionState())
    ist_pair.v3_intention.p1_pair = ('A', 'B')
    sess_pair = SimpleNamespace(strategy_state=ist_pair)
    assert committed_authority(bs_p1, sess_pair) is True, '配方锁已立'


def test_committed_authority_missing_supply_is_conservative_false() -> None:
    """缺供给帧 = 保守侧 False(供给点 D2:ist 不可得时禁缺省 True——
    True=激进侧,攒息门/双轨买门全开)。"""
    assert committed_authority(None, None) is False
    bare = SimpleNamespace()
    assert committed_authority(None, bare) is False


def test_committed_consumes_board_state_singleton() -> None:
    """state 形态 = 容器单例(board_state_of);session 容器经唯一读端
    取现读帧。"""
    sess = StrategySession()
    bs = board_state_of(sess)
    assert committed_authority(bs, sess) is False, 'P1 未观察 = 双轨期'


# ============================================================ §4 锁定帧约束基准

def test_locked_buy_scope_empty_window_none() -> None:
    """空窗/弱意向/降格终局 → None(无锁定帧不约束——空窗期全集是方向,
    不存在「非目标件」)。"""
    assert locked_buy_scope(None) is None
    assert locked_buy_scope(IntentionState()) is None


def test_plane_round_read_mirrors_legacy_defaults() -> None:
    """决策面公共读口:未观察帧镜像旧 CwSimFrame 缺省(plane=1/round=1),
    禁各消费点自写兜底造成第二源。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    assert plane_of(bs) == 1 and round_num_of(bs) == 1

