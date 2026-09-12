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
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    board_state_of,
    gold_of,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    reserve_cap as kernel_reserve_cap,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BuyCard,
    CwWorkFrame,
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
# (adapter.decision_state 已随 T-116 段 2 缝收敛退役删除——原 import 与其
#  独立重算腿同批改读容器单一源,语义 = 重算输入与装配同容器,不变。)
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
from test.sr_od.app.currency_war._cw_helpers import cw4_feed

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


def _cur(plane: int, round_num: int, gold: int = 53,
         node_type: str | None = None) -> CwWorkFrame:
    """帧构造(node_type = 喂容器时的节点轴载体,直调帧轴读属性不经容器)。"""
    return CwWorkFrame(gold=gold, level=5, plane=plane, round_num=round_num,
                     hp=100, node_type=node_type)


def _run_buy_waves_offline_host(monkeypatch: pytest.MonkeyPatch,
                                tmp_path: Path, disclose_impl) -> tuple[
        list, object, object]:
    """锁 F 行为腿共用离线宿主(零真实副作用;离线手法同
    test_cw_shop_refresh)。替身面 = run_buy_waves 段顶消费面(读屏/帧
    留证/决策源/遥测单例全替身):决策源首动作即 CloseShop 终结,循环
    只走入口观察组装段一次;段顶读屏 gold=10 非零(跳过 gold 救援重读
    支),shop/bench 默认空 → 停机钩子/占槽对拍支不可达,帧留证不落盘。
    返回 (warned, rr, outcome);disclose_impl 替换店开帧披露写点
    (接线点为函数内 lazy import,每次调用取模块属性,monkeypatch 即
    生效)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards as buy_mod
    from sr_od.application.currency_war.kernel.cw_vocab import CloseShop
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        CurrencyWarMatch,
        StrategySession,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        assembly as assembly_mod,
    )
    from sr_od.application.currency_war.telemetry import recorder as rec_mod
    from sr_od.application.currency_war.telemetry import state as tel_state

    # 遥测单例隔离(shop_snapshots 行写入端已随删除波 1 退役;缺陷台账行
    # 落 tmp_path)。
    monkeypatch.setattr(tel_state, '_RECORDER',
                        rec_mod.TelemetryRecorder(enabled=True,
                                                  replay_dir=tmp_path))
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 't1host')
    monkeypatch.setattr(tel_state, '_defect_seen', {})
    monkeypatch.setattr(tel_state, '_defect_seen_run', '')

    class _CloseShopStrategy:
        """替身决策源:首动作即 CloseShop 终结(段顶接线段后立即收工)。"""

        def decide_shop_action(self, session, config) -> CloseShop:
            return CloseShop()

    match = CurrencyWarMatch(_CloseShopStrategy(), StrategySession())

    class _Op:
        """离线宿主替身:run_buy_waves 消费面仅 ctx/screenshot/park_cursor。"""

        ctx = SimpleNamespace(current_instance_idx=1)

        def screenshot(self) -> bytes:
            return b''

        def park_cursor(self, after_wait: float = 0.0) -> None:
            pass

    monkeypatch.setattr(buy_mod, 'read_game_state',
                        lambda *a, **k: _cur(1, 8, 10))
    monkeypatch.setattr(buy_mod, 'save_decision_frame', lambda *a, **k: None)
    monkeypatch.setattr(buy_mod, 'shop_card_click_points', lambda ctx: [])
    monkeypatch.setattr(buy_mod, 'area_center', lambda *a, **k: (0, 0))
    monkeypatch.setattr(buy_mod.time, 'sleep', lambda s: None)
    monkeypatch.setattr(buy_mod, 'CurrencyWarConfig',
                        lambda idx: SimpleNamespace(strategy_id='mandate_v1',
                                                    ev_arm=''))
    monkeypatch.setattr(assembly_mod, 'disclose_budget_at_shop_frame',
                        disclose_impl)
    warned: list = []
    monkeypatch.setattr(buy_mod.log, 'warning',
                        lambda *a, **k: warned.append(a))
    rr, outcome = buy_mod.run_buy_waves(_Op(), match, None, False, False)
    return warned, rr, outcome


# ===== 锁 C:写读闭环锁(主锁)=====

class TestBudgetDisclosureWriteRead:

    def test_state_fields_equal_same_frame_computed_values(self):
        """装配后状态四字段 == 同帧独立现算值(R*/溢余/义务)。红证 =
        现码恒 0(52 行全零实证);本腿断的是「值对」,非「非零」。
        W6 波 4:预算接缝读 session 容器单例,喂入先于装配(生产同路 =
        观察漏斗,测试同路 = cw4_feed 合成口)。"""
        sess = StrategySession()
        snap = _snap(1, 8, 53)
        cw4_feed(sess, _cur(1, 8, 53, node_type='prep'))
        turn = assemble(snap, sess)
        st = state_of(sess)
        # 独立重算:同输入投影确定 ⇒ 与 _budget 内部同值(非转抄 turn);
        # 重算输入 = 同一容器实例(键戳/轮轴的单一来源)。
        # (原经 adapter.decision_state——T-116 段 2 缝收敛后改读容器,
        #  金值单一源 = 容器 gold 读口,值流不变。)
        state = board_state_of(sess)
        expected_cap = kernel_reserve_cap(board_state_of(sess), sess)
        assert st.v3_reserve_cap == turn.budget.reserve_cap
        assert st.v3_reserve_cap == expected_cap
        assert st.v3_reserve_overflow == max(
            0, int(gold_of(state) or 0) - int(turn.budget.reserve_cap))
        assert st.v3_release_budget == turn.budget.obligation
        assert st.v3_disclosure_key == (1, 8)
        # 构造帧结构性非退化(gold 高于息线 ⇒ 溢余/义务应非零;恒 0 =
        # 写点断裂的病理签名回归)
        assert st.v3_reserve_overflow > 0
        assert st.v3_release_budget > 0

    def test_disclosure_fields_non_none_and_match_state(
            self, monkeypatch: pytest.MonkeyPatch):
        """预算披露状态面(删除波 1 重写:sess_* 五键的 decisions 行组装
        写端已随 decisions 流写入端退役,行族归属策略侧决策行接线批):
        assemble 装配点 + accrue 执行回执后,策略态五字段与预算构式一致
        且非 None(读链写点两端对齐;T-84 修的读口在本锁钉「有真值可读」)。
        W6 波 4:键戳轴读 session 容器,装配前先喂入(生产同路 = 观察漏斗)。"""
        sess = StrategySession()
        cw4_feed(sess, _cur(1, 8, 53, node_type='prep'))
        assemble(_snap(1, 8, 53), sess)
        accrue_release_spent(_StubMatch(sess), RefreshShop(cost=2), True,
                             _cur(1, 8))
        st = state_of(sess)

        assert st.v3_disclosure_key == (1, 8)
        assert st.v3_reserve_overflow is not None
        assert st.v3_release_budget is not None
        assert st.v3_release_spent is not None
        assert st.v3_release_spent >= 2   # RefreshShop(cost=2) 执行回执已计
        assert st.v3_release_reason is not None
        # None 语义边界:default 栈帧(无写点)读端保持 None,非 0 假数据
        assert all(getattr(st, k) is not None for k in (
            'v3_reserve_cap', 'v3_reserve_overflow', 'v3_release_budget',
            'v3_release_spent'))


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
        独占);下轮 prep 关店帧 ⇒ 披露 = 容器现值重算(W6 波 4 语义
        变更,见④注;键戳翻轮清零断言面 = 锁 D 主锁,此处不重复)。"""
        sess = StrategySession()
        # ① prep 关店帧(轮入口装配;容器金缺席 = 关店不采金,首读无前值
        # 不 carry ⇒「金未采」0 语义保持)
        assemble(self._closed_snap(1, 8, 64), sess)
        st = state_of(sess)
        assert st.v3_reserve_overflow == 0
        # ② 店开帧覆写(帧现值):金源切容器(W6 波 4),店开帧经喂入口写
        # 容器(生产同路 = 观察漏斗;测试同路 = cw4_feed 合成口),披露读
        # 容器现值
        shop_state = CwWorkFrame(gold=64, level=5, plane=1, round_num=8,
                               hp=100, node_type='prep')
        cw4_feed(sess, shop_state)
        disclose_budget_at_shop_frame(shop_state, sess)
        assert st.v3_reserve_overflow == 64 - st.v3_reserve_cap
        assert st.v3_reserve_overflow > 0
        assert st.v3_release_budget > 0
        # ③ 同轮重复覆写不清 spent
        st.v3_release_spent = 4
        disclose_budget_at_shop_frame(shop_state, sess)
        assert st.v3_release_spent == 4
        # ④ 下轮 prep 关店帧(金失读 → 容器 carry 沿用店开金,funnel 同
        # 口径):装配披露 = 容器现值重算。「陈旧店开溢余复位 0」旧语义随
        # 金源切容器消亡——失读沿用下披露恒按沿用金重算,不存在复位面;
        # F1 新会话构造测不到「覆写后再披露」面(翻轮清零语义归锁 D)。
        cw4_feed(sess, CwWorkFrame(gold=0, gold_readable=False, level=5,
                                 plane=1, round_num=9, hp=100,
                                 node_type='prep'))
        assemble(self._closed_snap(1, 9, 64), sess)
        assert st.v3_reserve_overflow == 64 - st.v3_reserve_cap
        assert st.v3_reserve_overflow > 0


# ===== 锁 D:轮界清零锁 =====

class TestRoundBoundaryReset:

    def test_new_round_clears_spent_and_reason_and_renews_key(self):
        """同 session 连续两轮(p1r8→p1r9)装配:新轮首帧 spent==0、
        reason==''(F5 裁决①:reason 并入键戳清零块,杜绝跨轮陈读)、
        键戳已翻新。键戳轴 = session 容器(W6 波 4),每轮装配前喂入。"""
        sess = StrategySession()
        cw4_feed(sess, _cur(1, 8, 53, node_type='prep'))
        assemble(_snap(1, 8, 53), sess)
        st = state_of(sess)
        st.v3_release_spent = 7
        st.v3_release_reason = 'must_spend'
        cw4_feed(sess, _cur(1, 9, 53, node_type='prep'))
        assemble(_snap(1, 9, 53), sess)
        assert st.v3_release_spent == 0
        assert st.v3_release_reason == ''
        assert st.v3_disclosure_key == (1, 9)

    def test_same_round_reassembly_keeps_accumulation(self):
        """同轮重装配(幂等重入)不清账:键戳同值 ⇒ 只覆写三预算字段,
        spent 存活期 = 本轮装配后至下一轮键戳变更(与「轮内截至采样时点
        累计」语义一致)。键戳轴 = session 容器(W6 波 4),装配前喂入。"""
        sess = StrategySession()
        cw4_feed(sess, _cur(1, 8, 53, node_type='prep'))
        assemble(_snap(1, 8, 53), sess)
        st = state_of(sess)
        accrue_release_spent(_StubMatch(sess), RefreshShop(cost=2), True,
                             _cur(1, 8))
        cw4_feed(sess, _cur(1, 8, 51, node_type='prep'))
        assemble(_snap(1, 8, 51), sess)   # 同轮重入(刷新后金位变化)
        assert st.v3_release_spent == 2
        assert st.v3_disclosure_key == (1, 8)


# ===== 锁 E:spent 累计锁(含 F4 栈守卫探针)=====

class TestReleaseSpentAccrual:

    def test_two_refreshes_accumulate_per_receipt(self):
        """执行一次 RefreshShop(cost=2) ⇒ spent==2;同 visit 第二笔 ⇒ 4
        (执行回执位逐笔累计)。键戳轴 = session 容器(W6 波 4),装配前
        喂入使键戳成文。"""
        sess = StrategySession()
        cw4_feed(sess, _cur(1, 8, 53, node_type='prep'))
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


def test_shop_frame_disclosure_wired_after_blackboard_write(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """接线存在锁(T-88 店开帧第二写点;原「黑板写点后位次」腿随黑板槽
    退役消亡——T-116 prep 链段 2 删 session.shop_state_frame 载体,spy
    位次判据前提(黑板帧非 None)结构性不成立,波 5b 收口为接线存在 +
    循环收工两腿;黑板容器化后的喂入位次语义归 T-116 重放件)。"""
    seen_calls: list = []

    def _spy(state, session, registry=None) -> None:
        seen_calls.append(1)

    _warned, rr, outcome = _run_buy_waves_offline_host(monkeypatch, tmp_path,
                                                       _spy)
    assert len(seen_calls) == 1, \
        f'店开帧披露写点调用次数异常({len(seen_calls)}):接线断裂/漂移'
    assert rr is None and outcome is not None, '商店循环未正常收工'


def test_shop_frame_disclosure_failure_degrades_with_warning(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """行为锁(原④字面串锁整形,三审 T1④):披露覆写失败 → log.warning
    降级留痕、不外抛中断商店循环(遥测 best-effort 契约;锚⑤缺陷无声
    复发防线)。触发法 = 薄壳符号 monkeypatch 成抛错,经共用离线宿主
    驱动 ``run_buy_waves`` 段顶接线段,断言 warning 被调且循环正常收工
    ——log 措辞/写法漂移不再假红。"""

    def _boom(*a, **k):
        raise RuntimeError('t1 注入:披露覆写失败')

    warned, rr, outcome = _run_buy_waves_offline_host(monkeypatch, tmp_path,
                                                      _boom)
    assert warned, '披露覆写失败未走 log.warning 降级(静默 no-op 回归)'
    assert rr is None and outcome is not None, \
        '降级未收工:披露失败不应中断商店循环'


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
