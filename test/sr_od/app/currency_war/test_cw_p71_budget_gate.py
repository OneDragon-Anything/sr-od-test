"""P72 全段预算闸落码锁(ADR-0576;证明 =
docs/develop/currency_war/proofs/p72-full-band-budget-gate.md;
上位 = P71-b 溢余段闸 ADR-0560,本文件随全段化落码批整体重推,
旧 P71-b 语义锁的处置随条目 docstring 记录)。

锁清单(T-63 落码批 + T-79 修复批验收):
- 判据式锁:溢余段退化(73002 形)/全段中间段拦(签名 A 真洞形
  s110 r6 同参)/开局追级畅通(防恒拒,证明 §3 帧 A)/贴线边界
  (τ 单一源)/必花域生效/整批推迟语义;
- ALL IN 豁免锁(纯函数 P2 r7 boss + sim 检查器镜像);
- 支A 兑现链锁(纯函数 + sim 检查器镜像,schedule_upgrade ①臂
  同步锚对);
- 检查器三处对齐锁:g* 单一源(state.cap 部署 cap 禁读,D1)、
  决策帧金重放(先花后潜形态,D2)、ρ 过渡配方名册解析(D3)、
  合法批零违规双向;
- 三发射位同步:prep/shop(M3+必花域)/posture 镜像全链拒因与
  豁免一致(单点判据本体,分键面逐位锁)。
锁结构/回显,不锁分布数值(sr-od-test README 第 11 条)。
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
from sr_od.application.currency_war.sim.checks.ledger import (
    check_levelup_budget_gate,
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
                           active_strategies=[])


class TestRhoPublicSource:
    """ρ 公共源零漂移(P71-b 批承继;r2 测试既有 4 键不改断言的同源
    证据 = test_cw_r2_interest_floor.py 直跑,本类锁别名/注册面)。"""

    def test_shop_alias_same_value_as_single_source(self):
        """shop._r2_card_reserve 接线烟雾(本文件唯一 1 条,README 第 8
        条容忍档):别名 = 单一源 criteria/refresh.r2_card_reserve 的
        重导出委托(生产别名保留使 test_cw_r2_interest_floor 私名
        直引与调用点零漂移)。对比帧扫(2★ 出集经 bench/deployed 两
        路 + level 显式传参)防委托走样成第二实现——单点同值对包装
        漂移零判别力。ρ 值语义(注册表派生/过滤面)由
        test_cw_r2_interest_floor.test_card_reserve_is_registry_derived
        经同一别名辖,此处不重复锁值。"""
        km = tuple(_km())
        assert '三月七' in km   # 1费 min-cost 成员(注册表现读,下扫面对比锚)
        st = _state(0, 3)
        cases = [([], []),
                 ([_bc('三月七', star=2, slot=1)], []),
                 ([], [_bc('三月七', star=2, slot=1)]),
                 ([_bc('三月七', star=1, slot=1)], [])]
        for bench, deployed in cases:
            assert shop._r2_card_reserve(km, bench, deployed, st) == \
                crit_refresh.r2_card_reserve(km, bench, deployed, st)
        # level 过滤口径转发(包装签名/默认参漂移即断)
        assert shop._r2_card_reserve(km, [], [], st, level=6) == \
            crit_refresh.r2_card_reserve(km, [], [], st, level=6)

    def test_contracts_registered(self):
        """闸契约锚文本登记门:P72 全段闸契约锚必须指向 P72 证明与
        ADR-0576——锚漂移即闸出处断链,红时登记新出处。键存在性
        (criteria 全公开函数注册完备性)由 test_cw4_contracts
        .test_covers_all_criteria_public_functions 辖(亲读复核:
        各守边界成立),此处缺键经 KeyError 自然红,不重复断言。"""
        anchor = contracts.CONTRACTS[
            ('levelup', 'levelup_budget_gate')].anchor
        assert 'p72-full-band-budget-gate' in anchor
        assert 'ADR-0576' in anchor


class TestGatePure:
    """闸判据纯函数(P72 (3a) 全段式;判据单一源对拍)。"""

    def test_reject_73002_form(self):
        """73002 同参复刻(g=82, lv8, 批 72 金 = 18 击×4):τ(82)=5,
        floor = 50+2ρ ≥ 50,花后 10 金深穿 ⇒ 拒 + 拒因
        levelup_budget_gate_blocked。溢余段退化一致性(证明 §1):
        与 P71-b (3) 同判,已落码行为零漂移。"""
        st = _state(82, 8, xp=(12, 72))
        ok, why = crit_levelup.levelup_budget_gate(
            st, None, 82, 5, tuple(_km()), [], [], 18, 4)
        assert ok is False
        assert why == 'levelup_budget_gate_blocked'

    def test_pass_rich(self):
        """闸过形态:g 充分(花后 128 ≥ 50+2ρ 任取 ρ≤39)⇒ 放行。"""
        st = _state(200, 8, xp=(12, 72))
        ok, why = crit_levelup.levelup_budget_gate(
            st, None, 200, 5, tuple(_km()), [], [], 18, 4)
        assert ok is True
        assert why == ''

    def test_midband_dive_rejected(self):
        """T-93 签名 A 真洞同参复刻(s110 r6 形):义务买牌把金花到
        49 后逐击发射,批余 20 金(5 击×4)——τ(49)=4,floor =
        40+2ρ ≥ 40,花后 29 ⇒ 拒。旧 P71-b 在该帧 vacuous 空过
        (49 ≤ 50)= 真洞本体;全段化后中间段逐帧管账。"""
        st = _state(49, 7, xp=(40, 52))
        ok, why = crit_levelup.levelup_budget_gate(
            st, None, 49, 5, tuple(_km()), [], [], 5, 4)
        assert ok is False
        assert why == 'levelup_budget_gate_blocked'

    def test_early_game_chase_passes(self):
        """开局追级畅通(证明 §3 帧 A:P1 r2 lv3 g=8 批 4 金):
        τ(8)=0,floor = 0+2ρ ≤ 2,花后 4 ⇒ 放行。ADR-0560 §4 的
        防恒拒顾虑在 (3a) 全段式下不复发(τ 随金位自适应缩为零);
        旧「g ≤ g* vacuous 放行」锁已被本语义取代(锁重推:辖域
        vacuous → 全段判据,开局结论不变)。"""
        st = _state(8, 3, xp=(0, 4))
        ok, why = crit_levelup.levelup_budget_gate(
            st, None, 8, 5, tuple(_km()), [], [], 1, 4)
        assert ok is True and why == ''

    def test_components_single_source(self):
        """分量单一源对拍:τ = kernel interest() 直消费(息档数分量,
        禁第二实现);ρ 与 r2_card_reserve 同参同值;贴线边界一对
        (恰过/差 1 拒,数值不锁死只锁方向)。"""
        from sr_od.application.currency_war.kernel.cw_economy import interest
        km = tuple(_km())
        st = _state(100, 5, bench=[_bc('瓦尔特', star=1, slot=1)])
        assert interest(59, 5) == min(59 // 10, 5) == 5
        assert saturation_line(5) == 50
        rho = crit_refresh.r2_card_reserve(km, list(st.bench), [], st)
        assert rho == min(1, 5)   # 三月七(1费)在集且未 2★
        # 贴线边界:τ(60)=5,floor = 50+2ρ;花后恰 = floor ⇒ 放行
        s = 8
        ok, _ = crit_levelup.levelup_budget_gate(
            st, None, 50 + 2 * rho + s, 5, km, list(st.bench), [], 2, 4)
        assert ok is True
        # 差 1 金(59 同 τ=5,floor 不变)⇒ 拒(闸界贴线敏感)
        ok2, _ = crit_levelup.levelup_budget_gate(
            st, None, 50 + 2 * rho + s - 1, 5, km, list(st.bench), [],
            2, 4)
        assert ok2 is False

    def test_zero_batch_passes(self):
        """s ≤ 0(无批可发)恒可行:闸辖「升级支出的量」,不制造支出。"""
        st = _state(10, 3)
        ok, why = crit_levelup.levelup_budget_gate(
            st, None, 10, 5, tuple(_km()), [], [], 0, 4)
        assert ok is True and why == ''


class TestAllInExempt:
    """ALL IN 豁免支(P72 §2.5 新增交互;plane_last_battle 单一源)。"""

    def test_plane_last_boss_exempt(self):
        """P2 r7 boss 位面末战(R=0 机会成本恒零):深穿量也放行。
        session 携 plane_node_table(7 槽)⇒ plane_last_battle 判真;
        同参非 boss 帧不豁免——豁免谓词同帧判定,禁把豁免读成常开。"""
        km = tuple(_km())
        st_boss = _state(45, 7, xp=(48, 52))
        st_boss.plane = 2
        st_boss.node_type = 'boss'
        st_boss.round_num = 7
        sess_p2 = SimpleNamespace(plane_node_table=list(range(7)))
        ok, why = crit_levelup.levelup_budget_gate(
            st_boss, sess_p2, 45, 5, km, [], [], 10, 4)
        assert ok is True and why == ''
        # 同帧非 boss:量闸照判(45−40=5 < 40+2ρ)
        st_norm = _state(45, 7, xp=(48, 52))
        ok2, why2 = crit_levelup.levelup_budget_gate(
            st_norm, sess_p2, 45, 5, km, [], [], 10, 4)
        assert ok2 is False and why2 == 'levelup_budget_gate_blocked'


class TestRealizeChain:
    """支A 兑现链放行(P72 (3b) 构造谓词承担项;同步锚对谓词)。"""

    def test_board_full_with_two_star_bench_passes(self):
        """板满 ∧ bench 有 2★ 等待件:人口位增量当帧可兑现 ⇒ 放行
        (P39 ② 骨架义务不被量闸否决存在性;量闸深穿同帧也放)。"""
        km = _km()
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km)]
        bench = [_bc('阮·梅', star=2, slot=1)]
        st = _state(30, 4, xp=(0, 6), bench=bench, deployed=deployed)
        # 板满前置:cap = lv4 → max_units 4,deployed 4 ✓
        assert crit_levelup._realize_chain_ready(st, bench, deployed)
        ok, why = crit_levelup.levelup_budget_gate(
            st, None, 30, 5, tuple(km), bench, deployed, 2, 4)
        assert ok is True and why == ''

    def test_one_star_bench_not_enough(self):
        """bench 全 1★:①支不触发(证明帧 B 同形——bench 候补全 1★
        未过兑现链),量闸照判拒 = 推迟;病灶帧不得经支A 潜行。"""
        km = _km()
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km)]
        bench = [_bc('三月七', star=1, slot=1)]
        st = _state(30, 4, xp=(0, 6), bench=bench, deployed=deployed)
        assert not crit_levelup._realize_chain_ready(st, bench, deployed)
        ok, why = crit_levelup.levelup_budget_gate(
            st, None, 30, 5, tuple(km), bench, deployed, 2, 4)
        assert ok is False and why == 'levelup_budget_gate_blocked'

    def test_not_full_board_no_realize(self):
        """未板满:人口位增量不存在,C_realize 构造性零(普通 M1 部署
        辖,量闸语义回到 (3a))。"""
        km = _km()
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km[:2])]
        bench = [_bc('阮·梅', star=2, slot=1)]
        st = _state(30, 4, xp=(0, 6), bench=bench, deployed=deployed)
        assert not crit_levelup._realize_chain_ready(st, bench, deployed)


class TestPrepDefer:
    """prep 位:发射前过闸,拒 = 整批推迟(禁部分买)。"""

    def test_gate_reject_defers_whole_batch(self):
        """域内帧(g=56, lv4 满编线,批 8 金,τ(56)=5 → 花后 48 < 50)
        ⇒ 零 LevelUp 发射 + 独立分键(整批推迟:spend_unified 已保
        整批,闸拒即整批不出,无「按闸值截断击数」形态可存在)。"""
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
        """链路锁(v2 确认点 A 承继):prep 闸拒帧「M6」= emit OpenShop
        可发,转店后 shop 帧 M3 重过闸再拒——prep 不重复挂起(防双闸),
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
    """商店 M3 位过闸 + 闸拒同帧 M6 挂起(ADR-0576 承继 ADR-0560)。"""

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
    """必花域 L3 位:闸在域内生效(P72 承继「要花 ≠ 花在哪」)。"""

    def test_zone_gate_defers_with_key(self):
        """域内帧(g=65, 批 20 金,τ(65)=5 → 花后 45 < 50)⇒ 闸拒改道:
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
        (bench_free=0)+ g=57(τ(57)=5,花后 49 < 50,ρ=0 闸拒)。"""
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


class TestAllInEmissionSync:
    """三发射位 ALL IN 豁免同步锁(P72 §2.5 合取序:(2) 豁免了 (3)
    不得还拦——shop M3 位同帧放行花光;血预算 (2) 支的 ALL IN 让位
    与量闸 (3) 支豁免同谓词同帧,发射照达)。"""

    def test_shop_m3_allin_emits(self):
        """shop M3 位:位面末 boss 帧闸豁免 ⇒ LevelUpShop 照发
        (arm1 触发 + 血预算 ALL IN 让位 + 量闸豁免,同谓词同帧)。"""
        km = _km()
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km)]
        bench = [_bc('瓦尔特', star=1, slot=1)]
        st = _state(60, 5, xp=(0, 20), hp=90, bench=bench,
                    deployed=deployed)
        st.plane = 2
        st.node_type = 'boss'
        st.round_num = 7
        sess = _sess()
        sess.plane_node_table = list(range(7))
        _ms = state_of(sess)
        _ms.target_comp = _comp()
        _ms.v3_intention = IntentionState()
        act = shop.decide_shop_action(st, sess,
                                      SimpleNamespace(ev_arm='full'))
        assert isinstance(act, LevelUpShop), \
            '位面末 boss 帧 M3 位闸豁免后应照发(ALL IN 花光时机)'


class TestPostureMirror:
    """posture 对账镜像哨兵(v2 测试面承继):闸拒归因 = budget_gate 族。"""

    def test_gate_reject_attributed_not_contract_other(self, monkeypatch):
        """闸拒帧 posture 未兑现原因 = levelup_budget_gate_blocked,
        禁落 contract_other 兜底桶(entry.py 兜底,漏接即错)。"""
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
        # g 决策帧 59:τ=5,floor=50+2ρ ≥ 52,批 8 金,花后 51 < 52
        # ⇒ 闸拒)
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
    """sim m3_batch 检查器双向 + 三处口径对齐锁(P72 全段镜像)。"""

    @staticmethod
    def _row(rn: int, level: int, *, gold0=None, s=0, auth=None,
             node='battle', cap=None, bench=None, deployed=None,
             plane=1, actions=None, target=None):
        lv_actions = ([{'__type__': 'LevelUp', 'cost': s, 'auth': auth}]
                      if auth else [])
        return {
            'plane': plane, 'round_num': rn,
            'gold': (gold0 or 0) - s,
            'target_comp': target if target is not None else _COMP,
            'state': {'level': level, 'cap': cap if cap is not None else level,
                      'bench': bench or [], 'deployed': deployed or []},
            'sim': {'node': node, 'shop_waves': ([{'gold': gold0}]
                                                 if gold0 is not None else []),
                    'spend': {'levelup': s}},
            'actions': actions if actions is not None else lv_actions,
        }

    def test_legal_batch_zero_violation(self):
        """闸过批(决策帧金 200,批 20,息档充裕)⇒ 零违规。"""
        rows = [self._row(5, 5),
                self._row(6, 6, gold0=200, s=20, auth='m3_batch:arm1')]
        assert check_levelup_budget_gate(rows) == []

    def test_bypass_flagged(self):
        """绕闸形态(决策帧金 60,批 36 穿线:τ(60)=5,floor ≥ 50,
        花后 24)⇒ 违规在案,回显携批金额与闸值分量。"""
        rows = [self._row(5, 5),
                self._row(6, 6, gold0=60, s=36, auth='m3_batch:arm0')]
        out = check_levelup_budget_gate(rows)
        assert len(out) == 1
        assert '绕闸' in out[0] and '36' in out[0]

    def test_reward_node_bypass_flagged_non_m3_ignored(self):
        """T-115 对齐(ADR-0580;锁重推):奖励节点豁免([16]②)已随
        [16]② 删除退役——奖励节点 = 升级抑制对象,其 m3_batch 绕闸形态
        = 违规可见(生产闸判据节点无关,镜像删除 skip 后更忠实);非
        m3_batch 授权照旧不辖(白名单外或非 m3 批与本镜像无关)。"""
        rows = [self._row(5, 5),
                self._row(6, 6, gold0=60, s=36, auth='m3_batch:pop',
                          node='reward'),
                self._row(7, 7, gold0=60, s=36, auth='pop_slot')]
        out = check_levelup_budget_gate(rows)
        assert len(out) == 1
        assert '绕闸' in out[0] and '36' in out[0]

    def test_early_game_low_gold_zero_violation(self):
        """开局低金合法批零违规(锁重推:旧「g ≤ g* skip」辖域镜像已
        随全段化作废,开局结论由 (3a) 本身承载——lv3/g0=8/批 4 金,
        τ(8)=0,floor=0+2ρ ≤ 2,花后 4 ≥ floor 零违规)。"""
        rows = [self._row(5, 3),
                self._row(6, 3, gold0=8, s=4, auth='m3_batch:arm1')]
        assert check_levelup_budget_gate(rows) == []

    def test_dive_after_spend_flagged(self):
        """T-93 签名 A 真洞观测面锁(D2 决策帧金重放):g0=53 先义务
        买牌 3 金 → 决策帧金 50 → 2 击×4=8 批潜到 42——g0 口径下
        53−8=45 贴线可漏,重放后 τ(50)=5,floor ≥ 50,42 < floor
        ⇒ 违规在案(先花后潜形态结构性不再漏报)。"""
        rows = [self._row(5, 5),
                self._row(6, 6, gold0=53, cap=6,
                          actions=[{'__type__': 'BuyCard',
                                    'card': {'name': 'x', 'cost': 3},
                                    'reason': 'r'},
                                   {'__type__': 'LevelUp', 'cost': 4,
                                    'auth': 'm3_batch:arm1'},
                                   {'__type__': 'LevelUp', 'cost': 4,
                                    'auth': 'm3_batch:arm1'}],
                          s=8)]
        out = check_levelup_budget_gate(rows)
        assert len(out) == 1
        assert '决策帧金 50' in out[0]

    def test_g_star_single_source_ignores_deploy_cap(self):
        """g* 单一源锁(D1 修复):state.cap=7 是部署人口 cap(同名
        异义),禁当息帽推 g*=70——g0=75/批 20,息帽口径 τ(75)=5
        floor=50+2ρ ≤ 52,花后 55 ≥ floor 零违规(旧读 state.cap
        口径 g*=70 会误报)。"""
        rows = [self._row(5, 5),
                self._row(6, 6, gold0=75, s=20, auth='m3_batch:arm1',
                          cap=7)]
        assert check_levelup_budget_gate(rows) == []

    def test_allin_boss_exempt(self):
        """ALL IN 镜像锁(P72 §2.5):位面末 boss 节(本 run rows 现推
        位面长 9,P1 r9 boss)豁免;同量批在位面中段照报。"""
        rows = [self._row(r, 5) for r in range(1, 9)]
        rows.append(self._row(9, 5, gold0=60, s=36, auth='m3_batch:arm0',
                              node='boss'))
        assert check_levelup_budget_gate(rows) == []
        # 对照:同参非 boss(位面中段)→ 照报
        rows_mid = [self._row(5, 5),
                    self._row(6, 6, gold0=60, s=36, auth='m3_batch:arm0',
                              node='battle')]
        assert len(check_levelup_budget_gate(rows_mid)) == 1

    def test_realize_chain_exempt(self):
        """支A 镜像锁:板满(cap 回退后)∧ bench 2★ ⇒ 豁免;bench 无
        2★ 同帧照报(镜像与生产同步锚对谓词一致)。T-135 起本锁 rows
        不携披露键 = 辖**无披露键账本的回退分支**(携键按击判据另见
        test_realize_chain_disclosure_branch)。"""
        dep = [{'char_id': m, 'star': 2} for m in _km()[:4]]
        rows = [self._row(5, 4),
                self._row(6, 4, gold0=40, s=8, auth='m3_batch:arm1',
                          cap=4, deployed=dep,
                          bench=[{'char_id': '阮·梅', 'star': 2}])]
        assert check_levelup_budget_gate(rows) == []
        rows_b1 = [self._row(5, 4),
                   self._row(6, 4, gold0=40, s=8, auth='m3_batch:arm1',
                             cap=4, deployed=dep,
                             bench=[{'char_id': '三月七', 'star': 1}])]
        assert len(check_levelup_budget_gate(rows_b1)) == 1

    def test_realize_chain_disclosure_branch(self):
        """支A 披露键消费分支锁(T-135):携键账本按击读披露真值,行末
        近似不参与——行末 bench 无 2★(当帧上板形态,即 t133 假阳形态)
        + 披露 ready ⇒ 豁免;披露 not-ready ⇒ 照报(键存在不放宽豁免)。"""
        dep = [{'char_id': m, 'star': 2} for m in _km()[:4]]

        def _lv(full: bool, two: bool) -> dict:
            return {'__type__': 'LevelUp', 'cost': 8,
                    'auth': 'm3_batch:arm1',
                    'dec_board_full': full, 'dec_bench_2star': two}

        ready = [self._row(5, 4),
                 self._row(6, 4, gold0=40, s=8, cap=4, deployed=dep,
                           bench=[{'char_id': '三月七', 'star': 1}],
                           actions=[_lv(True, True)])]
        assert check_levelup_budget_gate(ready) == []
        shut = [self._row(5, 4),
                self._row(6, 4, gold0=40, s=8, cap=4, deployed=dep,
                          bench=[{'char_id': '阮·梅', 'star': 2}],
                          actions=[_lv(False, True)])]
        assert len(check_levelup_budget_gate(shut)) == 1

    def test_transition_pair_roster_resolved(self):
        """ρ 名册 D3 锁:过渡配方标签经 pair_target_comp + line_members
        解析非空(旧 _roster 段名查 COMP_LIBRARY 落空名册 ρ 恒 0);
        检查器对过渡配方锁帧正常判定(深穿批照报)。"""
        from sr_od.application.currency_war.kernel.cw_intention import (
            pair_target_comp,
        )
        km = line_members(pair_target_comp(('仙舟', '持续伤害')))
        assert len(km) > 0, '过渡配方体系对名册解析不得为空'
        rows = [self._row(5, 7),
                self._row(6, 7, gold0=60, s=36, auth='m3_batch:arm0',
                          target='过渡配方·仙舟+持续伤害')]
        out = check_levelup_budget_gate(rows)
        assert len(out) == 1 and '绕闸' in out[0]
