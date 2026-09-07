"""T-88 决策环数据流断链修复 · 缺陷②回归锁(遥测四字段全库零赋值)。

病理(ADR-0571):``v3_reserve_cap / v3_reserve_overflow /
v3_release_budget / v3_release_spent`` 在 MandateState 有字段声明、
recorder/engine_p1 有读端,但全库零写点——预算投影(assembly._budget)
每 prep 帧现算后算完即丢。实机局 g_20260907_021326 的 52 行 decisions
切片四字段全 ``(0, 0, 0, 0, '')``,含升级窗口与滞留金轮,真值应非零。

修复 = 写点 + 键戳轮界(prep 装配帧 + 店开观察帧双写,ADR-0571 §2.2):
- ``assembly._disclose_budget``(装配点):三预算字段幂等覆写 +
  ``v3_disclosure_key`` (plane, round) 键戳(变更 ⇒ spent/reason 清零);
  prep 关店帧 gold 过 F2 门不可得 ⇒ overflow/budget 恒 0 =「金未采」
  已知语义(实机首局 g_20260907_025608 锚⑤定谳);
- ``assembly.disclose_budget_at_shop_frame``(店开观察帧,经
  ``cw_op_buy_cards`` 段顶调用):overflow/budget 覆写为帧现值;
- ``cw_op_buy_cards.accrue_release_spent``(执行回执位):spent 只计
  刷新实花(首版「宁窄勿虚」收窄口径,ADR-0571)。

装配纪律边界:四字段 + 键戳是**遥测披露面**,不入决策输入——决策
判据一律消费 TurnState 幂等投影;禁令的可执行化 = 本文件 F8 守卫锁。
红证(修复前亲跑,code_commit=1e7d9a33 工作树):``assemble`` 后状态
四字段恒 0/''(写点不存在),recorder 键非 None 腿修复前即绿、红证由
「状态字段值 == 现算值」腿承重。
"""
from __future__ import annotations

from pathlib import Path

from sr_od.application.currency_war.kernel.cw_economy import (
    reserve_cap as kernel_reserve_cap,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    GameState,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
    strategy_state_of,
)
from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
    accrue_release_spent,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.adapter import (
    decision_state,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.assembly import (
    assemble,
    disclose_budget_at_shop_frame,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.contracts import (
    Snapshot,
    SubstateClassification,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

# ===== 测试基建 =====


def _snap(plane: int, round_num: int, gold: int) -> Snapshot:
    """最小 confident 快照(confident=False 被框架门拒,adapter 契约)。"""
    return Snapshot(plane=plane, round_num=round_num, level=5, gold=gold,
                    gold_trusted=True, hp=100, hp_readable=True,
                    classification=SubstateClassification(name='test',
                                                          confident=True))


class _StubMatch:
    """match 替身(执行回执位只消费 .session)。"""

    def __init__(self, session: StrategySession) -> None:
        self.session = session


def _cur(plane: int, round_num: int, gold: int = 53) -> GameState:
    return GameState(gold=gold, level=5, plane=plane, round_num=round_num,
                     hp=100)


# ===== 锁 C:写读闭环锁(主锁)=====

class TestBudgetDisclosureWriteRead:

    def test_state_fields_equal_same_frame_computed_values(self):
        """装配后状态四字段 == 同帧独立现算值(R*/溢余/义务)。红证 =
        现码恒 0(52 行全零实证);本腿断的是「值对」,非「非零」。"""
        sess = StrategySession()
        snap = _snap(1, 8, 53)
        turn = assemble(snap, sess)
        st = state_of(sess)
        # 独立重算:同输入投影确定 ⇒ 与 _budget 内部同值(非转抄 turn)
        state = decision_state(snap, sess)
        expected_cap = kernel_reserve_cap(state, sess, DEFAULT_REGISTRY)
        assert st.v3_reserve_cap == turn.budget.reserve_cap
        assert st.v3_reserve_cap == expected_cap
        assert st.v3_reserve_overflow == max(
            0, int(state.gold or 0) - int(turn.budget.reserve_cap))
        assert st.v3_release_budget == turn.budget.obligation
        assert st.v3_disclosure_key == (1, 8)
        # 构造帧结构性非退化(gold 高于息线 ⇒ 溢余/义务应非零;恒 0 =
        # 写点断裂的病理签名回归)
        assert st.v3_reserve_overflow > 0
        assert st.v3_release_budget > 0

    def test_recorder_row_keys_non_none_and_match_state(self):
        """recorder 行组装:sess_* 四键非 None 且与状态字段一致(读链
        写点两端对齐;T-84 修的读口在本锁钉「有真值可读」)。tmp 捕获
        _append,零真实 .debug 写入。"""
        from sr_od.application.currency_war.telemetry import recorder as rec_mod
        from sr_od.application.currency_war.telemetry import state as telstate
        from sr_od.application.currency_war.telemetry.recorder import (
            TelemetryRecorder,
        )

        sess = StrategySession()
        assemble(_snap(1, 8, 53), sess)
        accrue_release_spent(_StubMatch(sess), RefreshShop(cost=2), True,
                             _cur(1, 8))
        st = state_of(sess)

        captured: list[tuple[str, dict]] = []
        rec = TelemetryRecorder(replay_dir='unused', enabled=False)
        rec._append = lambda name, payload: captured.append(
            (name, dict(payload)))   # noqa: SLF001 测试捕获替身
        # 模块槽替换 + finally 复原(零真实 .debug 写入;_CTX_MATCH_REF
        # 是 recorder 读 session 的唯一通道,w603 汇点先例)。
        orig_get = telstate.get_recorder
        orig_ref = telstate._CTX_MATCH_REF
        orig_run = telstate._CURRENT_RUN_ID
        try:
            telstate.get_recorder = lambda: rec
            telstate._CTX_MATCH_REF = [_StubMatch(sess)]
            telstate._CURRENT_RUN_ID = 't88-lock-c'
            rec_mod.record_decision(_cur(1, 8), '', {}, {}, [], extra=None)
        finally:
            telstate.get_recorder = orig_get
            telstate._CTX_MATCH_REF = orig_ref
            telstate._CURRENT_RUN_ID = orig_run
        assert captured, 'decisions 行未捕获'
        row = dict(captured[0][1])
        assert row.get('sess_reserve_cap') == st.v3_reserve_cap
        assert row.get('sess_reserve_overflow') == st.v3_reserve_overflow
        assert row.get('sess_release_budget') == st.v3_release_budget
        assert row.get('sess_release_spent') == st.v3_release_spent
        assert row.get('sess_release_reason') == st.v3_release_reason
        # None 语义边界:default 栈帧(无写点)读端保持 None,非 0 假数据
        assert all(row.get(k) is not None for k in (
            'sess_reserve_cap', 'sess_reserve_overflow',
            'sess_release_budget', 'sess_release_spent'))


# ===== 锁 F:店开帧双写(实机锚⑤补遗)=====

class TestShopOpenFrameDualWrite:

    @staticmethod
    def _closed_snap(plane: int, round_num: int, gold: int) -> Snapshot:
        """prep 关店帧形态:gold 可读但 F2 门 untrusted(gold 仅店开态
        可信,cw_screen_prep;decision_state 不采纳 ⇒ 装配态 gold 缺省
        0)——live prep 装配的真实帧型。"""
        return Snapshot(plane=plane, round_num=round_num, level=5,
                        gold=gold, gold_trusted=False, hp=100,
                        hp_readable=True,
                        classification=SubstateClassification(
                            name='test', confident=True))

    def test_prep_closed_frame_keeps_zero_semantics(self):
        """prep 关店帧 ⇒ overflow/budget 恒 0 =「金未采」已知语义(非
        真 0;实机首局 g_20260907_025608 锚⑤定谳),reserve_cap 不受
        影响(gold 无关)——修复不改变关店 0 语义,只增店开帧第二写点。"""
        sess = StrategySession()
        turn = assemble(self._closed_snap(1, 8, 64), sess)
        st = state_of(sess)
        assert st.v3_reserve_cap == turn.budget.reserve_cap
        assert st.v3_reserve_overflow == 0
        assert st.v3_release_budget == 0

    def test_shop_open_frame_overwrites_with_frame_values(self):
        """店开观察帧覆写:overflow/budget 变帧现值(gold 64 > cap ⇒
        溢余 14/义务 >0);同轮重复覆写不清 spent(轮界清零归 prep 键戳
        独占);下轮 prep 关店帧 ⇒ 键戳翻轮清零 + 关店 0 语义恢复
        (decisions 行 sess_* = 最近一次写点值语义)。"""
        sess = StrategySession()
        # ① prep 关店帧(轮入口装配)
        assemble(self._closed_snap(1, 8, 64), sess)
        st = state_of(sess)
        assert st.v3_reserve_overflow == 0
        # ② 店开帧覆写(帧现值)
        shop_state = GameState(gold=64, level=5, plane=1, round_num=8,
                               hp=100)
        disclose_budget_at_shop_frame(shop_state, sess)
        assert st.v3_reserve_overflow == 64 - st.v3_reserve_cap
        assert st.v3_reserve_overflow > 0
        assert st.v3_release_budget > 0
        # ③ 同轮重复覆写不清 spent
        st.v3_release_spent = 4
        disclose_budget_at_shop_frame(shop_state, sess)
        assert st.v3_release_spent == 4
        # ④ 下轮 prep 关店帧:键戳翻轮清零 + 关店 0 语义恢复
        assemble(self._closed_snap(1, 9, 64), sess)
        assert st.v3_release_spent == 0
        assert st.v3_disclosure_key == (1, 9)
        assert st.v3_reserve_overflow == 0


# ===== 锁 D:轮界清零锁 =====

class TestRoundBoundaryReset:

    def test_new_round_clears_spent_and_reason_and_renews_key(self):
        """同 session 连续两轮(p1r8→p1r9)装配:新轮首帧 spent==0、
        reason==''(F5 裁决①:reason 并入键戳清零块,杜绝跨轮陈读)、
        键戳已翻新。"""
        sess = StrategySession()
        assemble(_snap(1, 8, 53), sess)
        st = state_of(sess)
        st.v3_release_spent = 7
        st.v3_release_reason = 'must_spend'
        assemble(_snap(1, 9, 53), sess)
        assert st.v3_release_spent == 0
        assert st.v3_release_reason == ''
        assert st.v3_disclosure_key == (1, 9)

    def test_same_round_reassembly_keeps_accumulation(self):
        """同轮重装配(幂等重入)不清账:键戳同值 ⇒ 只覆写三预算字段,
        spent 存活期 = 本轮装配后至下一轮键戳变更(与「轮内截至采样时点
        累计」语义一致)。"""
        sess = StrategySession()
        assemble(_snap(1, 8, 53), sess)
        st = state_of(sess)
        accrue_release_spent(_StubMatch(sess), RefreshShop(cost=2), True,
                             _cur(1, 8))
        assemble(_snap(1, 8, 51), sess)   # 同轮重入(刷新后金位变化)
        assert st.v3_release_spent == 2
        assert st.v3_disclosure_key == (1, 8)


# ===== 锁 E:spent 累计锁(含 F4 栈守卫探针)=====

class TestReleaseSpentAccrual:

    def test_two_refreshes_accumulate_per_receipt(self):
        """执行一次 RefreshShop(cost=2) ⇒ spent==2;同 visit 第二笔 ⇒ 4
        (执行回执位逐笔累计)。"""
        sess = StrategySession()
        assemble(_snap(1, 8, 53), sess)
        st = state_of(sess)
        m = _StubMatch(sess)
        accrue_release_spent(m, RefreshShop(cost=2), True, _cur(1, 8))
        assert st.v3_release_spent == 2
        accrue_release_spent(m, RefreshShop(cost=2), True, _cur(1, 8))
        assert st.v3_release_spent == 4

    def test_failed_execution_not_accrued(self):
        """未落地(_ok=False)不记账——与 apply_action_outcome「两侧都不
        动」同纪律(实花=真执行)。"""
        sess = StrategySession()
        assemble(_snap(1, 8, 53), sess)
        st = state_of(sess)
        accrue_release_spent(_StubMatch(sess), RefreshShop(cost=2), False,
                             _cur(1, 8))
        assert st.v3_release_spent == 0

    def test_non_refresh_actions_not_accrued(self):
        """首版口径只计刷新:买牌/升级/关店不进 spent(宁窄勿虚,
        ADR-0571 收窄申报)。"""
        sess = StrategySession()
        assemble(_snap(1, 8, 53), sess)
        st = state_of(sess)
        m = _StubMatch(sess)
        accrue_release_spent(m, BuyCard(card=ShopCard(x=1, name='x', cost=3),
                                        reason='t'), True, _cur(1, 8))
        assert st.v3_release_spent == 0

    def test_stale_key_receipt_not_accrued(self):
        """F4 探针①:回执帧轮次 ≠ 键戳(键戳 r8、回执 r9)⇒ 不累计——
        防「本轮预算披露行混入上轮累计」的键界漂移。"""
        sess = StrategySession()
        assemble(_snap(1, 8, 53), sess)
        st = state_of(sess)
        accrue_release_spent(_StubMatch(sess), RefreshShop(cost=2), True,
                             _cur(1, 9))
        assert st.v3_release_spent == 0

    def test_no_key_stamp_session_not_accrued(self):
        """F4 探针②:非 mandate_v1 栈(裸 session 无键戳)⇒ 不累计——
        防「spent>0 而预算三字段=None」混合行形态(recorder None 语义
        声明;异型策略状态对象经防御 getattr 走缺省)。"""
        sess = StrategySession()
        st = state_of(sess)
        assert st.v3_disclosure_key is None
        accrue_release_spent(_StubMatch(sess), RefreshShop(cost=2), True,
                             _cur(1, 8))
        assert st.v3_release_spent == 0
        assert strategy_state_of(sess) is st


def test_shop_frame_disclosure_wired_into_run_buy_waves():
    """接线锁(结构形态,先例 = test_cw_r336_batch4_locks 模块级/体内
    断言):``run_buy_waves`` 段顶必须调用店开帧披露写点——删调用块 =
    本锁红(锁 F 行为腿直调薄壳只证「函数对」,本锁证「接到商店循环」,
    二者合取才是完整接线证明)。钉四件事:①调用在位;②实参形态 =
    state 真值帧 + match.session(防换成无金替身帧);③位次 = 店开帧
    落黑板(shop_state_frame 写点)之后;④降级留痕 = 失败走 log.warning
    非静默 no-op(锚⑤缺陷无声复发防线,P2-1①)。"""
    import inspect
    import re

    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_buy_cards,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        assembly,
    )

    assert hasattr(assembly, 'disclose_budget_at_shop_frame'), \
        '薄壳符号不存在(被改名/拆除)'
    src = inspect.getsource(cw_op_buy_cards.run_buy_waves)
    call = 'disclose_budget_at_shop_frame('
    assert call in src, 'run_buy_waves 未调用店开帧披露写点(接线断裂)'
    assert re.search(
        r'disclose_budget_at_shop_frame\(\s*state\s*,\s*match\.session',
        src), '实参形态漂移:应为 (state 真值帧, match.session)'
    assert src.index('match.session.shop_state_frame = state') \
        < src.index(call), '调用位次漂移:应在店开帧落黑板之后'
    assert '店开帧预算披露覆写失败' in src, \
        '降级留痕缺失:覆写失败须 log.warning 非静默 no-op'


# ===== F8 守卫锁:披露面字段禁决策面消费 =====

#: 披露面字段 + 键戳(守卫集;v3_release_reason 不辖——shop.py 必花域段
#: 是其合法写点)。
_T88_DISCLOSURE_FIELDS: tuple[str, ...] = (
    'v3_reserve_cap',
    'v3_reserve_overflow',
    'v3_release_budget',
    'v3_release_spent',
    'v3_disclosure_key',
)

#: 白名单(相对 strategies/impl 的 posix 路径):写端 / 字段声明 /
#: 纪律声明 docstring。
_DISCLOSURE_SITE_WHITELIST: frozenset[str] = frozenset({
    'mandate_v1/assembly.py',
    'mandate_v1/mandate_state.py',
    'mandate_v1/turn_state.py',
})


def test_disclosure_fields_not_consumed_by_decision_modules():
    """F8 守卫锁:披露面字段禁现于决策面(stategies/impl 全子树扫描,
    白名单外零命中)——ADR-0571「禁决策判据消费」禁令的可执行化(仓内
    先例 = test_cw_session_separation 墓碑锁)。决策判据消费这些字段 =
    决策输入读跨帧旧共享态,正是装配纪律立法目的所禁的污染类缺陷形态;
    守卫判据(ADR-0571):写端只有 assembly._disclose_budget 与执行
    回执位(operations 侧,不在本扫描根),读端只有 recorder/engine_p1
    遥测链(亦在扫描根外)。盲区自检:扫描根失准/文件数异常 = 假绿,
    先证根在且非空;变异自检:字段名对已知坏形必须可检出。"""
    root = (Path(__file__).resolve().parents[5] / 'src' / 'sr_od'
            / 'application' / 'currency_war' / 'strategies' / 'impl')
    sentinel = root / 'mandate_v1' / 'assembly.py'
    assert sentinel.is_file(), f'扫描根解析失准:{root}'
    scanned = list(root.rglob('*.py'))
    assert len(scanned) >= 20, f'扫描文件数异常({len(scanned)}),根可能错位'
    # 变异自检:守卫集每个名字对合成坏形必须可检出(子串判据失效防呆)
    for name in _T88_DISCLOSURE_FIELDS:
        assert name in f'st.{name} = 0', f'变异自检未命中:{name}'
    offenders: dict[str, str] = {}
    for path in scanned:
        rel = path.relative_to(root).as_posix()
        if rel in _DISCLOSURE_SITE_WHITELIST:
            continue
        text = path.read_text(encoding='utf-8')
        for name in _T88_DISCLOSURE_FIELDS:
            if name in text:
                offenders[f'{rel}:{name}'] = name
    assert not offenders, (
        '披露面字段被决策面引用(禁令 = ADR-0571:四字段+键戳不入决策'
        f'输入,决策判据一律走 TurnState 幂等投影):{offenders}')
