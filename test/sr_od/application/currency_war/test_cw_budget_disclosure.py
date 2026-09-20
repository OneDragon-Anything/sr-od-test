"""决策环数据流断链修复 · 缺陷②回归锁(遥测四字段全库零赋值)。

病理(ADR-0571):``v3_reserve_cap / v3_reserve_overflow /
v3_release_budget / v3_release_spent`` 在 MandateState 有字段声明、
但全库零写点,预算现算每帧算完即丢。实机局 g_20260907_021326 的 52 行
decisions 切片四字段全 ``(0, 0, 0, 0, '')``,含升级窗口与滞留金轮,
真值应非零。

修复 = 写点 + 键戳轮界(备战决策入口 + 店开观察帧双写,ADR-0571 §2.2):
- ``economy_cycle.disclose_budget``(备战决策入口,bridge 前置发射位
  判定之后调用):三预算字段幂等覆写 + ``v3_disclosure_key``
  (plane, round) 键戳(变更 ⇒ spent/reason 清零);prep 关店帧 gold
  过 F2 门不可得 ⇒ overflow/budget 恒 0 =「金未采」已知语义(实机
  首局 g_20260907_025608 锚⑤定谳);
- ``economy_cycle.disclose_budget_at_shop_frame``(店开观察帧,经
  ``cw_screen_buy_cards`` 段顶 lazy import 调用):overflow/budget
  覆写为帧现值;
- ``cw_screen_buy_cards.accrue_release_spent``(执行回执位):spent 只
  计刷新实花(首版「宁窄勿虚」收窄口径,ADR-0571);轮键 = 容器读口
  现读。

纪律边界:四字段 + 键戳是**遥测披露面**,不入决策输入——决策输入 =
obs(黑板)+ session 容器直读;披露面禁决策消费(语义锚 =
mandate_state.py 披露字段注释与守卫锁);该禁令的防线现役归宿 =
review 与代码规范(源码扫描形态守卫锁按 sr-od-test README「禁止清单」
不进测试网,历史 F8 全子树扫描锁随本文件恢复批摘除)。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.kernel.cw_economy import (
    reserve_cap as kernel_reserve_cap,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    game_state_of,
    gold_of,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
    strategy_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwAction,
    CwActionBuyCardParam,
    CwActionRefreshShopParam,
    ShopCard,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_buy_cards import (
    accrue_release_spent,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.economy_cycle import (
    disclose_budget,
    disclose_budget_at_shop_frame,
    obligation,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

# ===== 测试基建 =====


class _StubMatch:
    """match 替身(执行回执位只消费 .session)。"""

    def __init__(self, session: StrategySession) -> None:
        self.session = session


def _cur(sess: StrategySession, plane: int, round_num: int, gold: int = 53,
         node_type: str | None = None) -> None:
    """容器域种子(node_type = 节点轴;决策面直读容器)。"""
    cw4_gs(sess, gold=gold, level=5, plane=plane, round_num=round_num,
           hp=100, node=node_type)


def _run_buy_waves_offline_host(monkeypatch: pytest.MonkeyPatch,
                                tmp_path: Path, disclose_impl) -> tuple[
        list, object, object]:
    """锁 F 行为腿共用离线宿主(零真实副作用)。替身面 = run_buy_waves
    段顶消费面(读屏/帧留证/种子读链/决策源/遥测单例全替身):决策源
    首动作即 CwActionCloseShopParam 终结,循环只走入口观察组装段一次;入口读屏回执
    gold=10 非零(跳过 gold 救援重读支);种子段读链桩 = 分型的
    「屏幕席真空」合法态(生产 SIFT 读链离线不可用,空账重建出口按
    合法态零写零台账);帧留证不落盘。返回 (warned, rr, ledger);
    disclose_impl 替换店开帧披露写点(接线点为函数内 lazy import,每次
    调用取模块属性,monkeypatch 即生效)。"""
    import sr_od.application.currency_war.operations.cw_screen.cw_screen_buy_cards as buy_mod
    from sr_od.application.currency_war.kernel.cw_vocab import CwActionCloseShopParam
    from sr_od.application.currency_war.obs.cw_observation import (
        GameStateReadReceipt,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        CurrencyWarMatch,
        StrategySession,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        economy_cycle as economy_cycle_mod,
    )
    from sr_od.application.currency_war.telemetry import recorder as rec_mod
    from sr_od.application.currency_war.telemetry import state as tel_state

    # 遥测单例隔离(run 态簇 + 缺陷台账去重键;缺陷台账行落 tmp_path)。
    monkeypatch.setattr(tel_state, '_RECORDER',
                        rec_mod.TelemetryRecorder(enabled=True,
                                                  replay_dir=tmp_path))
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 't1host')
    monkeypatch.setattr(tel_state, '_defect_seen', {})
    monkeypatch.setattr(tel_state, '_defect_seen_run', '')

    class _CloseShopStrategy:
        """替身决策源:首动作即 CwActionCloseShopParam 终结(段顶接线段后立即收工)。"""

        def decide_shop_action(self) -> CwActionCloseShopParam:
            return CwActionCloseShopParam()

    match = CurrencyWarMatch(_CloseShopStrategy(), StrategySession())

    class _Op:
        """离线宿主替身:run_buy_waves 消费面仅 ctx/screenshot/park_cursor。"""

        ctx = SimpleNamespace(current_instance_idx=1)

        def screenshot(self) -> bytes:
            return b''

        def park_cursor(self, after_wait: float = 0.0) -> None:
            pass

    def _entry_receipt(*a, **k) -> GameStateReadReceipt:
        """段顶入口观察回执(gold=10 非零,跳过 gold 救援重读支)。"""
        return GameStateReadReceipt(gold=10, gold_readable=True, hp=100,
                                    hp_readable=True, hp_trusted=True,
                                    level=5, plane=1, round_num=8)

    monkeypatch.setattr(buy_mod, 'read_game_state', _entry_receipt)
    monkeypatch.setattr(buy_mod, 'save_decision_frame', lambda *a, **k: None)
    monkeypatch.setattr(buy_mod, 'shop_card_click_points', lambda ctx: [])
    monkeypatch.setattr(buy_mod, 'area_center', lambda *a, **k: (0, 0))
    monkeypatch.setattr(buy_mod.time, 'sleep', lambda s: None)
    monkeypatch.setattr(buy_mod, 'CurrencyWarConfig',
                        lambda idx: SimpleNamespace(strategy_id='mandate_v1',
                                                    ev_arm=''))
    # (种子段读链工厂替身已移除:原店内读屏重建出口退役,
    #  未观察态改走「策略关店→备战 heavy 观察」链;本宿主观察态缺省可信,
    #  CwActionCloseShopParam 替身策略照常走正常关店收工。)
    monkeypatch.setattr(economy_cycle_mod, 'disclose_budget_at_shop_frame',
                        disclose_impl)
    warned: list = []
    monkeypatch.setattr(buy_mod.log, 'warning',
                        lambda *a, **k: warned.append(a))
    rr, ledger = buy_mod.run_buy_waves(_Op(), match)
    return warned, rr, ledger


# ===== 锁 C:写读闭环锁(主锁)=====

class TestBudgetDisclosureWriteRead:

    def test_state_fields_equal_same_frame_computed_values(self):
        """披露后状态四字段 == 同帧独立现算值(R*/溢余/义务)。红证 =
        现码恒 0(52 行全零实证);本腿断的是「值对」,非「非零」。
        W6 波 4:预算接缝读 session 容器单例,种子先于披露(生产同路 =
        观察漏斗,测试同路 = cw4_gs 容器域种子)。"""
        sess = StrategySession()
        _cur(sess, 1, 8, 53, node_type='prep')
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        # 独立现算 oracle:同输入现算确定 ⇒ 与披露写点内部同值(非转抄
        # 披露字段);重算输入 = 同一容器实例(键戳/轮轴的单一来源)。
        state = game_state_of(sess)
        expected_cap = kernel_reserve_cap(state, sess)
        assert st.v3_reserve_cap == expected_cap
        assert st.v3_reserve_overflow == max(
            0, int(gold_of(state) or 0) - expected_cap)
        assert st.v3_release_budget == obligation(state, sess,
                                                  DEFAULT_REGISTRY)
        assert st.v3_disclosure_key == (1, 8)
        # 构造帧结构性非退化(gold 高于息线 ⇒ 溢余/义务应非零;恒 0 =
        # 写点断裂的病理签名回归)
        assert st.v3_reserve_overflow > 0
        assert st.v3_release_budget > 0

    # (原 test_disclosure_fields_non_none_and_match_state 删:非 None 面
    #  弱于主锁值相等;spent/key/reason 三轴分别由 ReleaseSpentAccrual /
    #  RoundBoundaryReset / refresh_ledger 组辖,子集断言不留。)


# ===== 锁 F:店开帧双写(实机锚⑤补遗)=====

class TestShopOpenFrameDualWrite:

    def test_prep_frame_without_gold_keeps_zero_semantics(self):
        """prep 关店帧 ⇒ overflow/budget 恒 0 =「金未采」已知语义(非
        真 0;实机首局 g_20260907_025608 锚⑤定谳),reserve_cap 不受
        影响(gold 无关)——关店 0 语义由容器金缺席承载(F2 门:gold
        仅店开态可信,关店读空不写容器)。"""
        sess = StrategySession()
        cw4_gs(sess, gold_unread=True, level=5, plane=1, round_num=8,
               hp=100, node='prep')
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        assert st.v3_reserve_cap == kernel_reserve_cap(
            game_state_of(sess), sess)
        assert st.v3_reserve_overflow == 0
        assert st.v3_release_budget == 0

    def test_shop_open_frame_overwrites_with_frame_values(self):
        """店开观察帧覆写:overflow/budget 变帧现值(gold 64 > cap ⇒
        溢余 14/义务 >0);同轮重复覆写不清 spent(轮界清零归 prep 键戳
        独占);下轮 prep 关店帧 ⇒ 披露 = 容器现值重算(W6 波 4 语义
        变更,见④注;键戳翻轮清零断言面 = 锁 D 主锁,此处不重复)。"""
        sess = StrategySession()
        # ① prep 关店帧(轮入口披露;容器金缺席 = 关店不采金,首读无前值
        # 不 carry ⇒「金未采」0 语义保持)
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        assert st.v3_reserve_overflow == 0
        # ② 店开帧覆写(帧现值):金源切容器(W6 波 4),店开帧经种子写
        # 容器(生产同路 = 观察漏斗;测试同路 = cw4_gs 容器域种子),披露读
        # 容器现值
        cw4_gs(sess, gold=64, level=5, plane=1, round_num=8, hp=100,
               node='prep')
        disclose_budget_at_shop_frame(game_state_of(sess), sess)
        assert st.v3_reserve_overflow == 64 - st.v3_reserve_cap
        assert st.v3_reserve_overflow > 0
        assert st.v3_release_budget > 0
        # ③ 同轮重复覆写不清 spent
        st.v3_release_spent = 4
        disclose_budget_at_shop_frame(game_state_of(sess), sess)
        assert st.v3_release_spent == 4
        # ④ 下轮 prep 关店帧(金失读 → 容器 carry 沿用店开金,funnel 同
        # 口径):披露 = 容器现值重算。「陈旧店开溢余复位 0」旧语义随
        # 金源切容器消亡——失读沿用下披露恒按沿用金重算,不存在复位面;
        # F1 新会话构造测不到「覆写后再披露」面(翻轮清零语义归锁 D)。
        cw4_gs(sess, gold_unread=True, level=5, plane=1, round_num=9,
               hp=100, node='prep')
        disclose_budget(game_state_of(sess), sess)
        assert st.v3_reserve_overflow == 64 - st.v3_reserve_cap
        assert st.v3_reserve_overflow > 0


# ===== 锁 D:轮界清零锁 =====

class TestRoundBoundaryReset:

    def test_new_round_clears_spent_and_reason_and_renews_key(self):
        """同 session 连续两轮(p1r8→p1r9)披露:新轮首帧 spent==0、
        reason==''(F5 裁决①:reason 并入键戳清零块,杜绝跨轮陈读)、
        键戳已翻新。键戳轴 = session 容器(W6 波 4),每轮披露前喂入。"""
        sess = StrategySession()
        _cur(sess, 1, 8, 53, node_type='prep')
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        st.v3_release_spent = 7
        st.v3_release_reason = 'must_spend'
        _cur(sess, 1, 9, 53, node_type='prep')
        disclose_budget(game_state_of(sess), sess)
        assert st.v3_release_spent == 0
        assert st.v3_release_reason == ''
        assert st.v3_disclosure_key == (1, 9)

    def test_same_round_redisclosure_keeps_accumulation(self):
        """同轮重披露(幂等重入)不清账:键戳同值 ⇒ 只覆写三预算字段,
        spent 存活期 = 本轮披露后至下一轮键戳变更(与「轮内截至采样时点
        累计」语义一致)。键戳轴 = session 容器(W6 波 4),披露前喂入。"""
        sess = StrategySession()
        _cur(sess, 1, 8, 53, node_type='prep')
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        accrue_release_spent(_StubMatch(sess), CwActionRefreshShopParam(cost=2), True)
        _cur(sess, 1, 8, 51, node_type='prep')
        disclose_budget(game_state_of(sess), sess)   # 同轮重入(刷新后金位变化)
        assert st.v3_release_spent == 2
        assert st.v3_disclosure_key == (1, 8)


# ===== 锁 E:spent 累计锁(含 F4 栈守卫探针)=====

class TestReleaseSpentAccrual:

    def test_two_refreshes_accumulate_per_receipt(self):
        """执行一次 CwActionRefreshShopParam(cost=2) ⇒ spent==2;同 visit 第二笔 ⇒ 4
        (执行回执位逐笔累计)。键戳轴 = session 容器(W6 波 4),披露前
        喂入使键戳成文。"""
        sess = StrategySession()
        _cur(sess, 1, 8, 53, node_type='prep')
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        m = _StubMatch(sess)
        accrue_release_spent(m, CwActionRefreshShopParam(cost=2), True)
        assert st.v3_release_spent == 2
        accrue_release_spent(m, CwActionRefreshShopParam(cost=2), True)
        assert st.v3_release_spent == 4

    def test_failed_execution_not_accrued(self):
        """未落地(_ok=False)不记账——与 apply_action_outcome「两侧都不
        动」同纪律(实花=真执行)。"""
        sess = StrategySession()
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        accrue_release_spent(_StubMatch(sess), CwActionRefreshShopParam(cost=2), False)
        assert st.v3_release_spent == 0

    def test_non_refresh_actions_not_accrued(self):
        """首版口径只计刷新:买牌/升级/关店不进 spent(宁窄勿虚,
        ADR-0571 收窄申报)。"""
        sess = StrategySession()
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        m = _StubMatch(sess)
        accrue_release_spent(m, CwActionBuyCardParam(card=ShopCard(x=1, name='x', cost=3),
                                        reason='t'), True)
        assert st.v3_release_spent == 0

    def test_stale_key_receipt_not_accrued(self):
        """F4 探针①:回执轮次 ≠ 键戳(键戳 r8、回执 r9)⇒ 不累计——
        防「本轮预算披露行混入上轮累计」的键界漂移。轮键现役轴 = 容器
        读口:喂入翻轮即回执轮已翻,键戳仍钉上一轮。"""
        sess = StrategySession()
        _cur(sess, 1, 8, 53, node_type='prep')
        disclose_budget(game_state_of(sess), sess)
        st = state_of(sess)
        _cur(sess, 1, 9, 53, node_type='prep')
        accrue_release_spent(_StubMatch(sess), CwActionRefreshShopParam(cost=2), True)
        assert st.v3_release_spent == 0

    def test_no_key_stamp_session_not_accrued(self):
        """F4 探针②:非 mandate_v1 栈(裸 session 无键戳)⇒ 不累计——
        防「spent>0 而预算三字段=None」混合行形态(recorder None 语义
        声明;异型策略状态对象经防御 getattr 走缺省)。"""
        sess = StrategySession()
        st = state_of(sess)
        assert st.v3_disclosure_key is None
        accrue_release_spent(_StubMatch(sess), CwActionRefreshShopParam(cost=2), True)
        assert st.v3_release_spent == 0
        assert strategy_state_of(sess) is st


# ===== 锁 G:armed 短路帧不披露(披露落点位次单帧锁)=====

def test_armed_shortcircuit_frame_writes_no_disclosure(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """armed 短路帧不披露单帧锁:预算披露落点 = 备战决策入口前置发射位
    判定之后(非 armed 帧才到达),armed 帧在三遍编排前短路 return ⇒
    披露字段零写。发射准入核桩 = armed 单键替身(真 armed 帧需配方完备
    板面,与本锁无关——锁的是落点位次,非 armed 判据本体);替身返回
    缺 quality/quality_eval_error 键 = 常态发射帧。"""
    import sr_od.application.currency_war.kernel.cw_launch_admission as admit_mod
    import sr_od.application.currency_war.strategies.impl.mandate_v1.bridge as bridge_mod
    from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
        MandateV1Strategy,
    )

    sess = StrategySession()
    _cur(sess, 1, 8, 53, node_type='prep')
    # (黑板帧装配已随 gs.prep_obs 退役删除——阶段 3.5:决策输入 = 容器
    #  直读,「观察帧缺失即抛错」入口内务门随黑板消亡;决策核发射缝已桩 =
    #  不可达,本帧内容不在锁面。)
    monkeypatch.setattr(admit_mod, 'readiness_launch_decision',
                        lambda *a, **k: {'armed': True})

    def _no_reach(*a, **k):
        raise AssertionError('armed 帧短路后不得到达三遍编排')

    monkeypatch.setattr(bridge_mod, 'decide_prep_frame', _no_reach)
    from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
    action = MandateV1Strategy(
        game_state_of(sess),
        SimpleNamespace(strategy_seed=None)).decide_prep_screen()   # 终态契约:构造注入
    assert isinstance(action, CwAction), 'armed 帧应短路产出发射意图动作'
    st = state_of(sess)
    assert st.v3_disclosure_key is None, 'armed 短路帧不得盖披露键戳'
    assert st.v3_reserve_cap == 0
    assert st.v3_reserve_overflow == 0
    assert st.v3_release_budget == 0


def test_shop_frame_disclosure_wired_at_shop_entry(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """接线存在锁(店开帧第二写点;原「黑板写点后位次」腿随黑板槽
    退役消亡——迁移批 3.2 删 session.shop_state_frame 载体,spy 位次判据
    前提(黑板帧非 None)结构性不成立,收口为接线存在 + 循环收工两腿;
    黑板容器化后的喂入位次语义归容器化迁移批重放件)。改名申报:原
    ``..._after_blackboard_write`` 名嵌退役载体词,恢复时随接线段现址
    (cw_screen_buy_cards 店开观察帧段顶)正名。"""
    seen_calls: list = []

    def _spy(state, session, registry=None) -> None:
        seen_calls.append(1)

    _warned, rr, ledger = _run_buy_waves_offline_host(monkeypatch, tmp_path,
                                                      _spy)
    assert len(seen_calls) == 1, \
        f'店开帧披露写点调用次数异常({len(seen_calls)}):接线断裂/漂移'
    assert rr is None and ledger is not None, '商店循环未正常收工'


def test_shop_frame_disclosure_failure_degrades_with_warning(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """行为锁(原④字面串锁整形,三审 T1④):披露覆写失败 → log.warning
    降级留痕、不外抛中断商店循环(遥测 best-effort 契约;锚⑤缺陷无声
    复发防线)。触发法 = 薄壳符号 monkeypatch 成抛错,经共用离线宿主
    驱动 ``run_buy_waves`` 段顶接线段,断言 warning 被调且循环正常收工
    ——log 措辞/写法漂移不再假红。"""

    def _boom(*a, **k):
        raise RuntimeError('t1 注入:披露覆写失败')

    warned, rr, ledger = _run_buy_waves_offline_host(monkeypatch, tmp_path,
                                                     _boom)
    assert warned, '披露覆写失败未走 log.warning 降级(静默 no-op 回归)'
    assert rr is None and ledger is not None, \
        '降级未收工:披露失败不应中断商店循环'
