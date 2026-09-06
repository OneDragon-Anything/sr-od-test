"""P71-b 溢余段预算闸落码锁(ADR-0560;证明 =
docs/develop/currency_war/proofs/p71-levelup-channel-budget-gate.md;
方案单一源 = .debug/temp/currency_war/p71_gate_landing/方案审.md v1+v2)。

锁清单(方案审两轮汇总 + v2 确认节③):
- 零漂移:ρ 公共源提升(criteria/refresh.r2_card_reserve)后
  shop._r2_card_reserve 别名与单一源同参同值;
- 闸拒形态(73002 同参复刻)/闸过形态/三分量取值(单一源对拍);
- 必花域内生效 + 金滞留死角观测分键;
- M6 同帧挂起(shop 侧零压库)+ prep 闸拒 OpenShop 转店 shop 再拒链路;
- posture 镜像哨兵(闸拒归因 = budget_gate 族,禁落 contract_other);
- sim 检查器双向(合法批零违规 / 绕闸违规);
- 整批推迟语义(禁部分买)。
锁结构/回显,不锁分布数值(sr-od-test README 第 8 条)。
"""
from __future__ import annotations
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import state_of

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    LevelUp,
    OpenShop,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    LevelUpShop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    contracts,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    levelup as crit_levelup,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    refresh as crit_refresh,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.interest import (
    saturation_line,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)

_COMP = '列车同行'


def _comp():
    return get_comp(_COMP)


def _km() -> list[str]:
    return list(line_members(_comp()))


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _state(gold: int, level: int, *, xp: tuple[int, int] = (0, 6),
           hp: int = 60, bench: list | None = None,
           deployed: list | None = None) -> GameState:
    st = GameState(gold=gold, level=level, round_num=2, hp=hp)
    st.level_readable = True
    st.plane = 2
    st.node_type = 'battle'
    st.xp_progress = xp
    st.level_up_cost = 4
    st.shop = []
    st.bench = list(bench) if bench is not None else []
    st.deployed = list(deployed) if deployed is not None else []
    st.refresh_probs = {5: 0}
    return st


def _sess():
    return SimpleNamespace(cw4_counters={}, target_comp=_comp(),
                           v3_intention=IntentionState(),
                           cw4_cap_override=None)


class TestRhoPublicSource:
    """ρ 公共源提升零漂移(方案审 v2 ①/v1 B1;r2 测试既有 4 键不改断言
    的同源证据 = test_cw_r2_interest_floor.py 直跑,本类锁别名/注册面)。"""

    def test_shop_alias_same_value_as_single_source(self):
        """shop._r2_card_reserve 别名与 criteria/refresh.r2_card_reserve
        同参同值(测试面既有私名 import 不断链 + 零漂移)。"""
        km = tuple(_km())
        bench = [_bc('瓦尔特', star=1, slot=1)]
        st = _state(0, 3)
        assert shop._r2_card_reserve(km, bench, [], st) == \
            crit_refresh.r2_card_reserve(km, bench, [], st)
        assert shop._r2_card_reserve(km, bench, [], st) > 0   # 1★ 瓦尔特在集

    def test_contracts_registered(self):
        """契约注册完备:新公开判据函数已登记(CONTRACTS 键集与 criteria
        全公开函数对拍,漏登记 = 静态完备性测试红)。"""
        assert ('refresh', 'r2_card_reserve') in contracts.CONTRACTS
        assert ('levelup', 'levelup_budget_gate') in contracts.CONTRACTS


class TestGatePure:
    """闸判据纯函数(P71-b (3);判据单一源对拍)。"""

    def test_reject_73002_form(self):
        """73002 同参复刻(g=82, lv8, 批 72 金 = 15 击×4):花后 10 金
        深穿息线 ⇒ 拒 + 拒因 levelup_budget_gate_blocked(ρ≥0 任取,
        溢余段 32 < 72,与证明 §P71-c 批账一致)。"""
        st = _state(82, 8, xp=(12, 72))
        ok, why = crit_levelup.levelup_budget_gate(
            st, 82, 5, tuple(_km()), [], [], 18, 4)
        assert ok is False
        assert why == 'levelup_budget_gate_blocked'

    def test_pass_rich(self):
        """闸过形态:g 充分(花后 128 ≥ g*+2ρ 任取 ρ≤39)⇒ 放行。"""
        st = _state(200, 8, xp=(12, 72))
        ok, why = crit_levelup.levelup_budget_gate(
            st, 200, 5, tuple(_km()), [], [], 18, 4)
        assert ok is True
        assert why == ''

    def test_components_single_source(self):
        """三分量取值:g* = saturation_floor(cap_resolved)(息线单一源);
        ρ 与 r2_card_reserve 同参同值(闸消费同一函数,非第二实现);
        B_L 语义 = 单比较(方案审 §8:min 形态退化声明)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.refresh import (
            r2_card_reserve,
        )
        km = tuple(_km())
        st = _state(100, 5, bench=[_bc('瓦尔特', star=1, slot=1)])
        g_star = crit_levelup.saturation_floor(5)
        assert g_star == saturation_line(5) == 50
        rho = r2_card_reserve(km, list(st.bench), [], st)
        assert rho == min(1, 5)   # 三月七(1费)在集且未 2★
        # 闸边界构造:B_L 恰好容下批(花后 = g*+2ρ)⇒ 放行
        s = 8
        ok, _ = crit_levelup.levelup_budget_gate(
            st, 50 + 2 * rho + s, 5, km, list(st.bench), [], 2, 4)
        assert ok is True
        # 差 1 金 ⇒ 拒(闸界贴线敏感,数值不锁死只锁方向)
        ok2, _ = crit_levelup.levelup_budget_gate(
            st, 50 + 2 * rho + s - 1, 5, km, list(st.bench), [], 2, 4)
        assert ok2 is False

    def test_zero_batch_passes(self):
        """s ≤ 0(无批可发)恒可行:闸辖「升级支出的量」,不制造支出。"""
        st = _state(10, 3)
        ok, why = crit_levelup.levelup_budget_gate(
            st, 10, 5, tuple(_km()), [], [], 0, 4)
        assert ok is True and why == ''

    def test_below_floor_vacuous(self):
        """辖域限定:g ≤ g* 帧闸不辖(ADR-0560 §4)——非溢余段帧不存在
        可保护预算(息律零档),负闸值 = 预算不存在,禁读成「恒拒」
        (封死开局追级 = arm0/arm1 语义断层);开局形态(g=8, lv3,
        批 4 金)闸过,升级量归 P48 可负担性+P39/P21 既有门。"""
        st = _state(8, 3, xp=(0, 4))
        ok, why = crit_levelup.levelup_budget_gate(
            st, 8, 5, tuple(_km()), [], [], 1, 4)
        assert ok is True and why == ''


class TestPrepDefer:
    """prep 位:发射前过闸,拒 = 整批推迟(禁部分买)。"""

    def test_gate_reject_defers_whole_batch(self):
        """域内帧(g=56, lv4 满编线,批 8 金,花后 48 < g*+2ρ)⇒ 零
        LevelUp 发射 + 独立分键(整批推迟:spend_unified 已保整批,
        闸拒即整批不出,无「按闸值截断击数」形态可存在)。"""
        km = _km()
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km)]
        frame = mandate.MandateFrame(
            gold=56, level=4, bench=[], deployed=deployed,
            deploy_cap=4, node_type='battle', stop_flag=True,
            k_members=tuple(km), round_num=2)
        st = _state(56, 4, xp=(0, 6), hp=80, deployed=deployed)
        sess = _sess()
        out = mandate.run_mandate(frame, sess, state=st)
        assert not [e for e in out if isinstance(e.action, LevelUp)]
        assert state_of(sess).cw4_counters.get('levelup_budget_gate_blocked') == 1

    def test_prep_openshop_then_shop_regate(self):
        """链路锁(v2 确认点 A):prep 闸拒帧「M6」= emit OpenShop 可发,
        转店后 shop 帧 M3 重过闸再拒——prep 不重复挂起(防双闸),
        shop 侧兜住。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import (
            provisional,
        )
        km = _km()
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km)]
        frame = mandate.MandateFrame(
            gold=56, level=4, bench=[], deployed=deployed,
            deploy_cap=4, node_type='battle', stop_flag=True,
            k_members=tuple(km), round_num=2)
        st = _state(56, 4, xp=(0, 6), hp=80, deployed=deployed)
        provisional.inject('T_SEARCH_A', 1)
        try:
            out = mandate.run_mandate(frame, _sess(), state=st)
        finally:
            provisional.reset('T_SEARCH_A')
        assert not [e for e in out if isinstance(e.action, LevelUp)]
        assert any(isinstance(e.action, OpenShop) for e in out), \
            'prep 闸拒不挂起 OpenShop(转店后 shop 重过闸兜住)'
        # 转店后:同参商店帧 M3 重过闸再拒(域内拒因独立分键)
        st2 = _state(56, 4, xp=(0, 6), hp=80, deployed=deployed)
        sess2 = _sess()
        act = shop.decide_shop_action(st2, sess2,
                                      SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, LevelUpShop)
        assert state_of(sess2).cw4_counters.get('budget_gate_must_spend_defer') == 1


class TestShopM3M6:
    """商店 M3 位过闸 + 闸拒同帧 M6 挂起(ADR-0560;shop 侧辖域)。"""

    def test_gate_reject_m6_suspended(self):
        """arm1 帧闸拒 ⇒ 零 LevelUpShop/零压库发射 + levelup_budget_gate_
        blocked 与 m6_budget_gate_suspend 双分键(闸刚护住的预留金不被
        同帧压库击穿;店面空帧压库本无可买,挂起分键 = 挂起分支到达的
        结构证据)。"""
        km = _km()
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km)]
        deployed.append(_bc('姬子', star=1, slot=5))
        bench = [_bc('瓦尔特', star=1, slot=1)]
        st = _state(60, 5, xp=(0, 20), bench=bench, deployed=deployed)
        sess = _sess()
        # 策略器状态迁 MandateState:target_comp/v3_intention 经 state_of
        # 附着(与旧 session 直挂语义等价;stop_flag 推导依赖 target_comp)
        _ms = state_of(sess)
        _ms.target_comp = _comp()
        _ms.v3_intention = IntentionState()
        act = shop.decide_shop_action(st, sess,
                                      SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, LevelUpShop)
        assert not isinstance(act, BuyCard)
        assert state_of(sess).cw4_counters.get('levelup_budget_gate_blocked') == 1
        assert state_of(sess).cw4_counters.get('m6_budget_gate_suspend') == 1


class TestMustSpendGate:
    """必花域 L3 位:闸在域内生效(方案审 v2 采纳 3;「要花 ≠ 花在哪」)。"""

    def test_zone_gate_defers_with_key(self):
        """域内帧(g=65, 批 20 金,花后 45 < g*+2ρ)⇒ 闸拒改道:
        budget_gate_must_spend_defer 独立分键(与域外分键分开,归因可辨),
        零 LevelUpShop。"""
        st = _state(65, 5, xp=(0, 20))
        sess = _sess()
        act = shop.decide_shop_action(st, sess,
                                      SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, LevelUpShop)
        assert state_of(sess).cw4_counters.get('budget_gate_must_spend_defer') == 1
        assert 'levelup_budget_gate_blocked' not in state_of(sess).cw4_counters

    def test_zone_gate_deadend_observed(self):
        """金滞留死角观测:闸拒 ∧ bench 无空席(义务无处安放)⇒
        budget_gate_must_spend_deadend 观测分键在案(纯观察,不降档)。
        帧构造:满编全 2★ 线(无 M2 缺口/M4 腾席干扰)+ bench 9 垫
        (bench_free=0)+ g=57(花后 49 贴 g*=50 下侧,ρ=0 闸拒)。"""
        km = _km()
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km)]
        pad_bench = [_bc(f'垫{i}', star=1, slot=i + 1) for i in range(9)]
        st = _state(57, 4, xp=(0, 6), bench=pad_bench, deployed=deployed)
        sess = _sess()
        act = shop.decide_shop_action(st, sess,
                                      SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, LevelUpShop)
        assert state_of(sess).cw4_counters.get('budget_gate_must_spend_defer') == 1
        assert state_of(sess).cw4_counters.get('budget_gate_must_spend_deadend') == 1


class TestPostureMirror:
    """posture 对账镜像哨兵(v2 测试面):闸拒归因 = budget_gate 族。"""

    def test_gate_reject_attributed_not_contract_other(self, monkeypatch):
        """闸拒帧 posture 未兑现原因 = levelup_budget_gate_blocked,
        禁落 contract_other 兜底桶(entry.py:599 现状兜底,漏接即错)。"""
        from sr_od.application.currency_war.kernel import cw_economy
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            entry,
        )
        monkeypatch.setattr(
            cw_economy, 'get_node_goal',
            lambda *a, **k: SimpleNamespace(spend_mode='level'))
        km = _km()
        # ρ 合格集构造:板上三线件 2★ 出集,bench 三月七(1费)1★ 在集
        #(瓦尔特 5 费在 lv4 出牌面概率 0,不可追不进 ρ——注册表过滤语义;
        # g*=cap_resolved 口径 50,批 8 金,花后 51 < 52 = g*+2ρ ⇒ 闸拒)
        deployed = [_bc('姬子·启行', star=2, slot=1),
                    _bc('花火', star=2, slot=2),
                    _bc('姬子', star=1, slot=3),
                    _bc('银狼', star=1, slot=4)]
        bench = [_bc('三月七', star=1, slot=1)]
        st = _state(59, 4, xp=(0, 6), bench=bench, deployed=deployed)
        sess = _sess()
        un = entry._reconcile_posture_authorization(
            sess, st, [], tuple(km))
        assert un is not None
        assert un['reason'] == 'levelup_budget_gate_blocked'
        assert un['reason'] != 'contract_other'
        assert state_of(sess).cw4_counters.get('posture_unfulfilled_level') == 1


class TestSimChecker:
    """sim m3_batch 检查器双向(v2 测试面):合法批零违规 / 绕闸违规。"""

    @staticmethod
    def _row(rn: int, level: int, *, gold0=None, s=0, auth=None,
             node='battle'):
        return {
            'plane': 1, 'round_num': rn,
            'gold': (gold0 or 0) - s,
            'target_comp': _COMP,
            'state': {'level': level, 'cap': level, 'bench': [],
                      'deployed': []},
            'sim': {'node': node, 'shop_waves': ([{'gold': gold0}]
                                                 if gold0 is not None else []),
                    'spend': {'levelup': s}},
            'actions': ([{'__type__': 'LevelUp', 'auth': auth}]
                        if auth else []),
        }

    def test_legal_batch_zero_violation(self):
        """闸过批(时点金 200,批 20,溢余段充裕)⇒ 零违规。"""
        from sr_od.application.currency_war.sim.checks.ledger import (
            check_levelup_budget_gate,
        )
        rows = [self._row(5, 5),
                self._row(6, 6, gold0=200, s=20, auth='m3_batch:arm1')]
        assert check_levelup_budget_gate(rows) == []

    def test_bypass_flagged(self):
        """绕闸形态(时点金 60,批 36 穿线,g*+2ρ=42 头寸 18)⇒ 违规
        在案,回显携批金额与闸值分量。"""
        from sr_od.application.currency_war.sim.checks.ledger import (
            check_levelup_budget_gate,
        )
        rows = [self._row(5, 5),
                self._row(6, 6, gold0=60, s=36, auth='m3_batch:arm0')]
        out = check_levelup_budget_gate(rows)
        assert len(out) == 1
        assert '绕闸' in out[0] and '36' in out[0]

    def test_reward_node_exempt_and_non_m3_ignored(self):
        """奖励节点豁免([16]② 同款)+ 非 m3_batch 授权不辖。"""
        from sr_od.application.currency_war.sim.checks.ledger import (
            check_levelup_budget_gate,
        )
        rows = [self._row(5, 5),
                self._row(6, 6, gold0=60, s=36, auth='m3_batch:pop',
                          node='reward'),
                self._row(7, 7, gold0=60, s=36, auth='pop_slot')]
        assert check_levelup_budget_gate(rows) == []

    def test_below_floor_batch_zero_violation(self):
        """辖域镜像(ADR-0560 §4;落地审 B1):g ≤ g* 帧生产闸合法豁免,
        检查器同条件 skip——开局低金合法批(lv3/g0=8/批 4 金,
        g*+2ρ 口径 headroom 为负)零违规,镜像缺口即假违规复现形态。"""
        from sr_od.application.currency_war.sim.checks.ledger import (
            check_levelup_budget_gate,
        )
        rows = [self._row(5, 5),
                self._row(6, 6, gold0=8, s=4, auth='m3_batch:arm1')]
        assert check_levelup_budget_gate(rows) == []
