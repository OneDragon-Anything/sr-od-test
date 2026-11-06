"""策略卡羁绊档位条件发放 sim 状态副本链测试(镜像 src = sim/cw_sim_backend.py
的 _resolve_battle 结算腿族槽调用点;kernel 触发函数单元面 = kernel/
cw_gain_chain/test_check_strategy_bond_tier_grants.py,本文件锁 sim 接入调用
与状态副本里的值落地面)。

测试面依据 = 迭代设计 designs/T-271-mengjing-dawutai.md §4 锁 8
(驱动与断言形态先例 = 同目录 test_strategy_bond_battle_grant_sim_
chain.py;触发-发放单拍制 = 结算拍直接发放,无节点窗交付拍):

- 结算拍发放:持卡 + 3 激活板(盛会之星 2 gate + 治疗 2 + 护盾 2 +
  贝洛伯格 2)战斗结算 → equips 恰 +1 盛会之星星徽(``strategy_bond_
  tier:<卡名>@3`` 前缀 evidence 笔——**断言用前缀匹配禁精确匹配**,
  gain_equipment 原语内追加 #equip 后缀;sig 组 'sim:strategy';确定
  通道零随机)+ 一次性标志位 '<卡名>#3' 落域;
- 胜负无关:败局存活局同样发放(卡面无「胜利」限定,胜败两态共同
  路径);
- 幂等回归 = 既有守卫(同节点战斗重放 _settled_key 整段跳过,零二次
  发放);
- 死亡局不发放(调用点在死亡提前 return 之后,局终不见发放);
- 板面直构双源同喂(board 状态容器 = 左面板口径 + deployed 行域注入 =
  身份口径,两源同值;构成式:花火+知更鸟 = 盛会之星 2 gate,娜塔莎+
  藿藿 = 治疗 2,杰帕德+砂金 = 护盾 2,娜塔莎+杰帕德 = 贝洛伯格 2 →
  激活非独立 4 ≥ 3 触 tier 3,追击 2 未达 tiers[0] 不计)。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
    _backend,
    _close_shop_feed,
    _drive_env_grant_step,
    _force_settle,
    _start_battle_feed,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    DeployedView,
    Unit,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_LOBBY,
    SCREEN_PREP,
    SCREEN_SETTLE,
    SimBackend,
    uninstall_backend,
)

_CARD = '梦境大舞台'
_EQUIP = '盛会之星星徽'
_EVIDENCE_PREFIX = f'strategy_bond_tier:{_CARD}@3'
_LATCH_KEY = f'{_CARD}#3'

#: 3+ 激活直构板(构成式见模块 docstring;6 单位全前排)。
_BOARD_UNITS: tuple[str, ...] = (
    '花火', '知更鸟', '娜塔莎', '藿藿', '杰帕德', '砂金',
)
#: 板面状态容器直写值 = 行域身份聚合同值(双源同喂,左面板真值口径)。
_BOARD_DICT: dict[str, int] = {
    '盛会之星': 2, '战技点': 1, '量子同频': 1, '追击': 2,
    '贝洛伯格': 2, '治疗': 2, '仙舟': 1, '能量': 1, '护盾': 2,
    '公司': 1,
}


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(沿同目录同名 fixture 先例,fixture 不可跨文件
    import 故本文件自带同语义副本)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        consume_defect_sink,
        set_defect_sink,
    )
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def _prep_backend(seed: int) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;先例 = 同目录
    test_strategy_bond_battle_grant_sim_chain._prep_backend 形)。"""
    b = _backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP, '前置:未达 P1r1 备战屏'
    return b


def _hold_card(gs, *, card: str = _CARD) -> None:
    """持卡直置(注册状态容器直写 = 持卡事实单一源;不经 pick 链)。"""
    gs.write_logic(gs.active_strategies, [card],
                   produced_by='test-seed', evidence='t:card', sig=_SIG)


def _inject_board(gs) -> None:
    """羁绊板直构(双源同喂:deployed 行域注入 = 身份口径 + board 状态容器
    直写 = 左面板口径,两源同值——与实机「board = 左面板真值、身份 =
    行域聚合」同构;单喂 deployed 则 board 状态容器 miss,单喂 board 则身份
    miss,双源 max 融合下直构须两源同值)。"""
    front = [Unit(char_id=n, star=1) for n in _BOARD_UNITS]
    gs.observe(gs.deployed,
               DeployedView(front_slots=front, back_slots=[]),
               sig=_SIG_OBS)
    gs.observe(gs.board, dict(_BOARD_DICT), sig=_SIG_OBS)


def _record_world_writes(gs, monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """包装 write_logic/write_logic_rand/observe 记录
    (通道, 字段名, evidence, sig, value, produced_by) 写序(透传真实现
    零行为变化;债文件禁追加故本文件自带副本,先例 =
    test_strategy_bond_battle_grant_sim_chain._record_world_writes)。"""
    calls: list[tuple] = []

    def _wrap_logic(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            calls.append((channel, gs._field_name(target), evidence, sig,
                          value, produced_by))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    def _wrap_obs(real):
        def rec(target, value, *, evidence=None, sig, note=''):
            calls.append(('obs', gs._field_name(target), evidence, sig,
                          value, None))
            real(target, value, evidence=evidence, sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic',
                        _wrap_logic(gs.write_logic, 'logic'))
    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap_logic(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'observe', _wrap_obs(gs.observe))
    return calls


def _grant_rows(calls: list[tuple]) -> list[tuple]:
    """本腿装备写行(strategy_bond_tier 前缀)。"""
    return [c for c in calls
            if c[1] == 'equips'
            and str(c[2] or '').startswith(_EVIDENCE_PREFIX)]


def _latch_rows(calls: list[tuple]) -> list[tuple]:
    """一次性标志位域写行(strategy_bond_tier_fired 字段)。"""
    return [c for c in calls if c[1] == 'strategy_bond_tier_fired']


def test_settle_grants_on_win(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """锁 8 主条(胜局):持卡 + 3 激活板 → P1r1 战斗结算拍 equips 恰
    +1 星徽(evidence 前缀笔、'sim:strategy' 组、确定通道)+ 落一次性标志位。"""
    b = _prep_backend(91)
    try:
        gs = b.gs
        _hold_card(gs)
        _inject_board(gs)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE, '结算后应泊结算屏'
        rows = _grant_rows(calls)
        assert len(rows) == 1, f'结算拍发放笔数漂移: {[c[:3] for c in rows]}'
        assert str(rows[0][2]) == f'{_EVIDENCE_PREFIX}#equip', \
            f'evidence 漂移: {rows[0][2]!r}'
        # 通道断言不设:sim 状态副本未锚定期确定发放走随机态通道是链级既定
        # 约定(gain-chain §5,箱腿同款),确定面 source 锁归 kernel 单元面
        #(test_check_strategy_bond_tier_grants 首达主条 prep_anchored 置一次性标志位)。
        assert rows[0][3].family == 'logic_action' \
            and rows[0][3].group_id == 'sim:strategy', \
            f'sig 组漂移: {rows[0][3]}'
        assert rows[0][4][-1] == _EQUIP, f'发放物漂移: {rows[0][4]!r}'
        assert gs.equips.value == [_EQUIP], f'入栏漂移: {gs.equips.value!r}'
        latches = _latch_rows(calls)
        assert len(latches) == 1 and latches[0][4] == (_LATCH_KEY,), \
            f'一次性标志位写漂移: {[c[:5] for c in latches]}'
        assert gs.strategy_bond_tier_fired.value == (_LATCH_KEY,), '一次性标志位值漂移'
    finally:
        uninstall_backend()


def test_settle_grants_on_loss_alive(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """胜负无关锁(败局存活):败局(hp 未清零)结算 → 同样发放(卡面
    无「胜利」限定,胜败两态共同路径;与实机「战斗中达成即发」平读
    一致)。"""
    b = _prep_backend(92)
    try:
        gs = b.gs
        _hold_card(gs)
        _inject_board(gs)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE, '败局存活应泊结算屏'
        assert len(_grant_rows(calls)) == 1, '败局存活局未发放'
        assert gs.equips.value == [_EQUIP], '败局存活局入栏漂移'
        assert gs.strategy_bond_tier_fired.value == (_LATCH_KEY,), '未落一次性标志位'
    finally:
        uninstall_backend()


def test_settled_replay_no_regrant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """幂等回归锁:同节点战斗重放(battle_resolve 重入)→ _settled_key
    既有守卫整段跳过,零二次发放零新增一次性标志位写笔(防本腿绕过)。"""
    b = _prep_backend(93)
    try:
        gs = b.gs
        _hold_card(gs)
        _inject_board(gs)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert gs.equips.value == [_EQUIP], '前置:首战未发放'
        calls = _record_world_writes(gs, monkeypatch)
        _start_battle_feed(gs)
        assert b.screen_identity() == SCREEN_SETTLE, '重放应泊原结算屏'
        assert _grant_rows(calls) == [], '重入误发放'
        assert _latch_rows(calls) == [], '重入误置一次性标志位'
        assert gs.equips.value == [_EQUIP], '重入入栏漂移'
    finally:
        uninstall_backend()


def test_dead_battle_no_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """死亡局锁:保底已用 + 濒死局 boss 战败 → hp 归零死亡提前 return
    在发放调用点之前,零发放直接进终局(局终不见发放,与实机一致;boss
    位伤害可击穿 1 hp 濒死,普通战斗位伤害不必然致死)。"""
    b = _prep_backend(94)
    try:
        gs = b.gs
        _hold_card(gs)
        _inject_board(gs)
        node = gs.node.value
        for _ in range(80):
            node = gs.node.value
            screen = b.screen_identity()
            if screen == SCREEN_PREP and node is not None \
                    and node.kind == 'boss':
                break
            if screen in (SCREEN_SETTLE, '货币战争-位面过渡',
                          '货币战争-投资策略', '货币战争-补给',
                          '货币战争-遭遇节点', '货币战争-BOSS简报',
                          '货币战争-盛会之星', '货币战争-银狼升星'):
                _drive_env_grant_step(b)
            elif screen == '货币战争-备战-开商店':
                # 备战开店形态(窗起发牌后自动弹店):关店动作单轨回备战
                _close_shop_feed(b)
            elif screen == SCREEN_PREP:
                _force_settle(monkeypatch, won=True)
                _start_battle_feed(gs)
            else:
                raise AssertionError(f'未预期屏 {screen!r}(target=boss)')
        else:
            raise AssertionError('驱动步数超限:未达 boss 备战窗')
        gs.observe(gs.hp_floor_triggered, True, sig=_SIG_OBS)
        gs.observe(gs.hp, 1, sig=_SIG_OBS)
        calls = _record_world_writes(gs, monkeypatch)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert b.done and b.screen_identity() == SCREEN_LOBBY, \
            '败局致死应进终局'
        assert _grant_rows(calls) == [], '死亡局误发放'
        assert _latch_rows(calls) == [], '死亡局误置一次性标志位'
    finally:
        uninstall_backend()
