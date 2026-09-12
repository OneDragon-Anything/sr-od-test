"""店开帧 node_type 台账制回归锁(ADR-0587;C2 缺陷修复批)。

病理(ADR-0587,归层 = 流程组装层):店开帧(``prep_shop_open``)节点行
被遮,node_type 结构性恒 None;旧组装代码无条件拷 ``session.last_node_type``
——该值唯一写点(备战环 heavy 观察,shop 关态才可读)正常节拍晚于本轮
店开,拷到的恒为上一轮值。实机案件形态:上一轮 = 奖励、本轮 = 普通战斗,
滞后 'reward' 落进战斗帧 → ②(b) ``dead_gold_press_buy`` 在战斗节点误发射,
且 M3 规则①把战斗帧升级错误抑制(同根双病灶)。

修复 = 拷贝改 ``ledger_node_type(session, state.plane, state.round_num)``
查表(与关店帧 prep_clean 台账优先链同构,键查表结构上不可能滞后);
查不到 → 保持 None fail-open(②(b) 不发射,ADR-0580 None 语义;死金域
义务由节点无关的 ②(a) 备战凑息承载)。

验证边界(方案审定稿):本修属执行层帧组装,sim 决策核自行装配帧——
缺陷与修复对 sim 双重结构性不可见,禁 sim A/B 作验收;本锁为验收面之一,
相邻参照 = test_cw_op_journal / test_cw_dispatch_wrapper。

离线宿主手法 = test_cw_budget_disclosure 同款(读屏/帧留证/决策源/遥测
单例全替身,零真实副作用);真核直调形态 = test_cw_realizable_interest_floor 同款。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    board_state_bridge as _bridge,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    node_kind_of,
)
from sr_od.application.currency_war.kernel.cw_reward_node import (
    reward_node_suppressed,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BuyCard,
    CloseShop,
    CwWorkFrame,
    ShopCard,
    ledger_update_plane,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CurrencyWarMatch,
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bs,
)

# ===== 测试基建 =====


def _card(name: str = '廉价杂件', cost: int = 1) -> ShopCard:
    """1★ 1 费燃料形候选(p56 ②(b) 锁同款名:线外 1★ 全额退形)。"""
    return ShopCard(x=100, name=name, cost=cost, star=1)


def _shop_frame(gold: int, cards: list[ShopCard]) -> CwWorkFrame:
    """店开帧合成(p1r3 案件形态:gold=11 < g*,bench 空有席)。"""
    st = CwWorkFrame(gold=gold, level=7, hp=80, plane=1, round_num=3)
    st.shop = list(cards)
    return st


class _ProbeCloseStrategy:
    """替身决策源:捕获店开组装容器 + 真核试算,随即 CloseShop 终结。

    试算结果只记录不返回——动作执行层不进本锁辖域;断言面 = 组装容器
    内容 + 真决策核对组装帧的反应(②(b)/M3),即「生产组装 → 决策核」
    全链,禁自抄复刻组装逻辑(测试纪律第 10 条)。
    """

    def __init__(self) -> None:
        self.frames: list[object] = []
        self.actions: list[object] = []

    def decide_shop_action(self, session: StrategySession,
                           config: object) -> CloseShop:
        # 店开组装的决策载体 = session 容器单例(shop_state_frame 黑板槽
        # 已随波 4 退役,组装喂入 = 合成口容器直写);组装断裂检测 =
        # 容器店 payload 缺席,节点判读经容器 node 读口。
        from sr_od.application.currency_war.kernel.cw_game_state import (
            board_state_of,
        )
        bs = board_state_of(session)
        assert bs.shop.value is not None, '店开帧未落黑板(组装断裂)'
        self.frames.append(bs)
        self.actions.append(
            shop.decide_shop_action(bs, session,
                                    SimpleNamespace(ev_arm='full')))
        return CloseShop()


def _drive_run_buy_waves(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                         session: StrategySession,
                         strategy: _ProbeCloseStrategy,
                         seed_ledger=None) -> None:
    """最小替身面驱动 ``run_buy_waves`` 段顶组装段(budget_disclosure 同款)。

    段顶读屏替身产出 p1r3 形态帧(gold=11 非零跳过金救援支;shop 含
    1 费候选;bench 空 = 有席);遥测单例隔离 → 零真实 .debug 写入。
    ``seed_ledger`` = 局容器构造后的台账预置回调(生产时序 = 局容器先建、
    局中写入;ExecState 载体绑定单一调用点 = CurrencyWarMatch.__post_init__
    幂等覆写,先于构造的懒建载体写入会被孤儿化,禁先写后建)。
    """
    import sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards as buy_mod
    from sr_od.application.currency_war.telemetry import recorder as rec_mod
    from sr_od.application.currency_war.telemetry import state as tel_state

    monkeypatch.setattr(tel_state, '_RECORDER',
                        rec_mod.TelemetryRecorder(enabled=True,
                                                  replay_dir=tmp_path))
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 'node_type_ledger')
    monkeypatch.setattr(tel_state, '_defect_seen', {})
    monkeypatch.setattr(tel_state, '_defect_seen_run', '')

    match = CurrencyWarMatch(strategy, session)
    if seed_ledger is not None:
        seed_ledger()
    # (删除波 1:_CTX_MATCH_REF 暂存槽桩已移除——决策行 session 读通道随
    #  decisions 写入端退役;台账读链经 exec_state_of(session) 直读,
    #  seed_ledger() 即覆盖台账注入面。)

    class _Op:
        """离线宿主替身:run_buy_waves 消费面仅 ctx/screenshot/park_cursor。"""

        ctx = SimpleNamespace(current_instance_idx=1)

        def screenshot(self) -> bytes:
            return b''

        def park_cursor(self, after_wait: float = 0.0) -> None:
            pass

    monkeypatch.setattr(buy_mod, 'read_game_state',
                        lambda *a, **k: _shop_frame(11, [_card()]))
    monkeypatch.setattr(buy_mod, 'save_decision_frame', lambda *a, **k: None)
    monkeypatch.setattr(buy_mod, 'shop_card_click_points', lambda ctx: [])
    monkeypatch.setattr(buy_mod, 'area_center', lambda *a, **k: (0, 0))
    monkeypatch.setattr(buy_mod.time, 'sleep', lambda s: None)
    monkeypatch.setattr(buy_mod, 'CurrencyWarConfig',
                        lambda idx: SimpleNamespace(strategy_id='mandate_v1',
                                                    ev_arm=''))
    _rr, _outcome = buy_mod.run_buy_waves(_Op(), match, None, False, False)
    assert _rr is None, 'run_buy_waves 异常收工(替身面不完备,先修夹具)'


# ===== 锁 1:单帧锁·滞后形态(C2 病灶本体)=====


def test_battle_frame_stale_reward_not_copied_no_press_buy_no_m3_defer(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """战斗轮店开帧 + 滞后 'reward' + 台账无本轮档 → 三断言(ADR-0587)。

    红证 = 旧无条件拷贝实现下三断言全翻:帧 node_type='reward'、
    ``reward_node_suppressed`` 为 True(战斗帧被 M3 规则①误抑制)、
    ②(b) ``dead_gold_press_buy`` 在战斗帧发射(C2 病灶)。锁的承重点 =
    组装段不再拷会话滞后值,查不到台账 → 保持 None fail-open。
    """
    session = StrategySession()
    # 上一轮残留值:唯一写点(备战环 heavy 观察)节拍晚于本轮店开,
    # 案件帧拿到的是它而非本轮真值(ADR-0587 背景节)。
    session.last_node_type = 'reward'
    strategy = _ProbeCloseStrategy()
    _drive_run_buy_waves(monkeypatch, tmp_path, session, strategy)
    frame = strategy.frames[0]
    assert node_kind_of(frame) is None, '滞后值被拷入店开帧(C2 病灶复发)'
    assert reward_node_suppressed(frame) is False, 'M3 规则①在战斗帧被误抑制'
    act = strategy.actions[0]
    assert not (isinstance(act, BuyCard)
                and act.reason == 'dead_gold_press_buy'), '②(b) 在战斗帧发射'
    counters = state_of(session).cw4_counters
    assert 'reward_node_defer' not in counters, 'M3 误抑制计数出现(应 fail-open)'
    assert 'dead_gold_press_buy_hit' not in counters, '②(b) 命中计数出现'


# ===== 锁 2:单帧锁·台账命中形态 =====


def test_ledger_hit_enters_shop_frame_and_rewards_press_buy_legally(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """台账含本轮 (1,3)='reward' → 查表值进店开帧(ADR-0587)。

    session.last_node_type 预置与台账冲突的滞后值,证明供值优先级 =
    台账压过会话残留(旧实现恰好相反)。下游全链:真核在组装帧上合法
    发射 ②(b)(奖励帧 ∧ 死金域 ∧ 席位 ∧ 1 费候选,合法奖励帧行为)。"""
    session = StrategySession()
    session.last_node_type = 'battle'
    strategy = _ProbeCloseStrategy()

    def _seed() -> None:
        # 键语义 = seq 下标 i(0-based)= 第 i+1 轮(cw_state.PlaneNodeLedger);
        # 第 3 轮 = seq[2] = 'reward',写入端通道标 plane_detail(位面详情全量)。
        # 写入时点 = 局容器构造后(载体绑定单一调用点先于局中写入,生产同序)。
        ledger_update_plane(session, 1, ['battle', 'reward', 'reward'],
                            'plane_detail')

    _drive_run_buy_waves(monkeypatch, tmp_path, session, strategy,
                         seed_ledger=_seed)
    frame = strategy.frames[0]
    assert node_kind_of(frame) == 'reward', '台账查表值未进店开帧'
    act = strategy.actions[0]
    assert isinstance(act, BuyCard) and act.reason == 'dead_gold_press_buy', \
        '台账背书的合法奖励帧上 ②(b) 未发射'
    assert state_of(session).cw4_counters.get('dead_gold_press_buy_hit') == 1


# ===== 锁 3:单帧锁·None 帧形态(②(b) 沉默;②(a) 义务臂存活面在 p56 主题位)=====


def test_none_frame_press_buy_silent() -> None:
    """None 帧上 ②(b) 沉默(ADR-0587 fail-open;None 语义权威 = ADR-0580)。

    None 帧直调决策核 → ``reward_node_suppressed`` 取 False → 压库臂
    关门,零命中计数。None 帧的死金域「禁死囤」义务仍由 ②(a) 备战凑息
    承载——该存活面的等价断言单点承载于 test_cw_realizable_interest_floor::
    test_pullback_success_closes_press_arm 前半(同输入帧型 + 同
    sorted(sells)==[1,2] 断言,跨文件等价择一,本侧原重复腿已删)。"""
    st = CwWorkFrame(gold=11, level=7, hp=80, plane=1, round_num=3)
    st.shop = [_card()]
    sess = StrategySession()
    act = shop.decide_shop_action(cw4_bs(st, sess), sess, SimpleNamespace(ev_arm='full'))
    assert not (isinstance(act, BuyCard)
                and act.reason == 'dead_gold_press_buy'), \
        'None 帧上 ②(b) 发射(fail-open 失守)'
    assert 'dead_gold_press_buy_hit' not in state_of(sess).cw4_counters
