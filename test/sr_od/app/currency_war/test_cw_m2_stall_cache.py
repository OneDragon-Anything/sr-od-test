"""T-82 M2 停摆续段缓存回归锁(必花臂重试风暴;事件粒度计数)。

设计出处:T-82 排查方案 v3 §3(零参数结构命题:失败条件不变时重试
确定性复现同一拒绝 ⇒ 跳过弱支配,跳过条件 = 白名单非变异枚举可判定
谓词,非计数阈值;命题号 P73 待 math_proofs 索引分配)+ ADR-0573。

被锁行为面:
- 商店域(decide_shop_action M4 块)/备战域(run_mandate M2 块)的
  续段缓存命中协议:上帧动作 ∈ 域白名单 ∧ token/闩序号均 == 当前段
  序号 ∧ 闩结论=腾席无候选 ⇒ 跳过扫描/环,发射动作逐位一致(弱支配);
- 事件粒度计数:命中帧 m2_retry_exhausted/bench_full_buy_abandon 不增,
  m2_stall_repeat_frame(+m2_stall_cache_hit)+1;段首/失效帧重推导,
  两事件键 +1 且 m2_stall_cache_rederive +1;
- 跨段/跨调用方失效(T6):残留 token 序号 ≠ 当前段序号 ⇒ 失效重推导,
  残留 token 被读清——伪命中防线承重 = 段标识比较,非读清;
- merge_material_guard_blocked 零变化恒等(T7):帧首 P56 投影位独立
  承载,每帧每素材 +1 不受 M4 缓存影响(方案 §3.4-2 零变化申报的
  行为学锚)。

红证记录(实施批):①monkeypatch 两域白名单为空集(等效禁缓存)→
T1/T4/T5 命中类断言红;②临时去掉命中谓词两处段序号比较 → T6 红
(hit +1 而非重推导)——证明各锁真实辖住缓存路径与段比较防线。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel import cw_intention
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    predicates,
)

# ===== 基建 =====

_LOCK_COMP = '列车同行'


def _cfg():
    return SimpleNamespace(ev_arm='full')


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _card(name: str, cost: int, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _locked_session() -> StrategySession:
    """锁线会话(target_comp + locked 意向):锁定采购集买入义务面。"""
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = get_comp(_LOCK_COMP)
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = _LOCK_COMP
    ist.lock_plane = 2
    state_of(s).v3_intention = ist
    return s


def _storm_state(gold: int = 30, deployed: list[BenchChar] | None = None
                 ) -> GameState:
    """风暴帧构造:bench 9/9 全为锁定采购集成员(经 exclude 排除 ⇒ 腾席
    燃料集空)∧ 缺员核心件不在场 ⇒ M4 腾席无候选停摆形态。"""
    comp = get_comp(_LOCK_COMP)
    core = set(predicates.line_members(comp))
    hoard_chars, _eq = cw_intention._line_hoard(comp)
    hoard_only = sorted(set(hoard_chars) - core)
    assert len(hoard_only) >= BENCH_CAPACITY, '构造前提:采购集 hoard 件须满席'
    st = GameState(gold=gold, level=7, round_num=2, hp=60)
    st.plane = 2
    st.shop = []
    st.bench = [_bc(m, slot=i + 1)
                for i, m in enumerate(hoard_only[:BENCH_CAPACITY])]
    st.deployed = list(deployed or [])
    return st


def _arm_shop_token(sess: StrategySession, action_name: str = 'LevelUpShop'
                    ) -> None:
    """按续段协议模拟执行层写入帧间动作 token(当前段序号)——单测面
    直接置载体,验证决策核的读清+命中协议(执行层写入点接线由生产代码
    承载,zero-drift 锚覆盖)。"""
    st = state_of(sess)
    st.cw4_frame_action_record = (action_name, st.cw4_segment_serial)


# ===== 商店域(M4 块)=====


class TestShopStallCache:
    """decide_shop_action M4 块续段缓存(方案 §3.4-1)。"""

    def test_t1_storm_invariance_hit_skips_scan_identical_action(self):
        """T1 风暴不变性:帧1 重推导(两事件键+rederive)→ 执行层置
        LevelUpShop token → 帧2 命中:两事件键零增量、repeat/hit +1、
        发射动作与无缓存世界逐位一致(弱支配行为恒等锁)。"""
        st = _storm_state()
        sess = _locked_session()
        shop.decide_shop_action(st, sess, _cfg())
        c = state_of(sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 1
        assert c.get('bench_full_buy_abandon', 0) == 1
        assert c.get('m2_stall_cache_rederive', 0) == 1
        assert c.get('m2_stall_cache_hit', 0) == 0
        assert state_of(sess).cw4_m2_stall_latch is not None, '首推导须写闩'
        # 帧间:执行层确认已执行 LevelUpShop(∈ 白名单)→ 置 token
        _arm_shop_token(sess, 'LevelUpShop')
        act2 = shop.decide_shop_action(st, sess, _cfg())
        c = state_of(sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 1, '命中帧事件键不增'
        assert c.get('bench_full_buy_abandon', 0) == 1, '命中帧事件键不增'
        assert c.get('m2_stall_repeat_frame', 0) == 1
        assert c.get('m2_stall_cache_hit', 0) == 1
        assert c.get('m2_stall_cache_rederive', 0) == 1
        # 行为恒等:与无缓存世界的同输入首推导逐位一致
        sess_plain = _locked_session()
        act_plain = shop.decide_shop_action(st, sess_plain, _cfg())
        assert repr(act2) == repr(act_plain), (act2, act_plain)

    def test_t2_variant_action_invalidates_and_rederives(self):
        """T2 变异失效:帧间动作 = BuyCard(白名单外)⇒ 缓存失效 ⇒ 全量
        重推导:两事件键再 +1(新停摆事件)、hit 恒 0。"""
        st = _storm_state()
        sess = _locked_session()
        shop.decide_shop_action(st, sess, _cfg())
        _arm_shop_token(sess, 'BuyCard')
        shop.decide_shop_action(st, sess, _cfg())
        c = state_of(sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 2
        assert c.get('bench_full_buy_abandon', 0) == 2
        assert c.get('m2_stall_cache_rederive', 0) == 2
        assert c.get('m2_stall_cache_hit', 0) == 0
        assert c.get('m2_stall_repeat_frame', 0) == 0

    def test_t2_fuel_recovered_variant_token_allows_sell_emit(self):
        """T2 行为半边:帧间 φ 真变(W 外动作换入燃料件)⇒ token 型外
        重推导 ⇒ 燃料恢复非空时卖出发射(现行为保持,腾席通道未失效)。"""
        comp = get_comp(_LOCK_COMP)
        core = set(predicates.line_members(comp))
        hoard_chars, _eq = cw_intention._line_hoard(comp)
        # 线外 1★ 角色名(∉ 采购集 ⇒ 不被排除,是合法腾席燃料)
        offline = next(n for n in CHARACTERS
                       if n not in hoard_chars and n not in core)
        st = _storm_state()
        # 帧1:末席为 3★ 占位件(非燃料)⇒ 停摆形态
        st.bench[-1] = _bc('placeholder', slot=BENCH_CAPACITY, star=3)
        shop.decide_shop_action(st, sess_placeholder := _locked_session(),
                                _cfg())
        # 帧间:W 外动作(SellBench)卖出占位件 ⇒ offline 入席
        st.bench[-1] = _bc(offline, slot=BENCH_CAPACITY)
        sess = sess_placeholder
        _arm_shop_token(sess, 'SellBench')
        act2 = shop.decide_shop_action(st, sess, _cfg())
        from sr_od.application.currency_war.kernel.cw_state import SellBench
        assert isinstance(act2, SellBench), '重推导须发现恢复的燃料并卖出'
        assert act2.expect == offline

    def test_t3_unknown_action_type_conservative_rederive(self):
        """T3 未知动作型保守端:token 型 = 未登记新动作型 ⇒ 视为变异 ⇒
        重推导(最坏退化 = 现行为,零风险)。"""
        st = _storm_state()
        sess = _locked_session()
        shop.decide_shop_action(st, sess, _cfg())
        _arm_shop_token(sess, 'SomeFutureAction')
        shop.decide_shop_action(st, sess, _cfg())
        c = state_of(sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 2
        assert c.get('m2_stall_cache_hit', 0) == 0

    def test_t5_event_semantics_exact_and_cross_segment_rearm(self):
        """T5 计数语义:同一停摆段事件键恰 +1(首推导);跨段(段序号
        推进后复现)再次 +1;命中帧 repeat 累加而事件键不动。"""
        st = _storm_state()
        sess = _locked_session()
        shop.decide_shop_action(st, sess, _cfg())          # 段内首推导:+1
        _arm_shop_token(sess, 'LevelUpShop')
        shop.decide_shop_action(st, sess, _cfg())          # 命中:不增
        c = state_of(sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 1
        assert c.get('m2_stall_repeat_frame', 0) == 1
        # 跨段:段入口推进(模拟 visit 重新开始)→ 残留 token 序号过期
        state_of(sess).cw4_segment_serial += 1
        shop.decide_shop_action(st, sess, _cfg())          # 重推导:再 +1
        c = state_of(sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 2
        assert c.get('bench_full_buy_abandon', 0) == 2
        assert c.get('m2_stall_cache_rederive', 0) == 2
        assert c.get('m2_stall_cache_hit', 0) == 1

    def test_t5_hit_frame_does_not_touch_sell_channel_keys(self):
        """T5 零静默面:命中帧除观测对外不新增任何计数键(跳过扫描 =
        只少两事件键,其余发射位照常工作——键面形状锁,键集与无缓存
        首推导帧的键集差恰为 {m2_retry_exhausted 事件化} 的设计声明)。"""
        st = _storm_state()
        sess = _locked_session()
        shop.decide_shop_action(st, sess, _cfg())
        keys1 = set(state_of(sess).cw4_counters)
        _arm_shop_token(sess, 'LevelUpShop')
        shop.decide_shop_action(st, sess, _cfg())
        keys2 = set(state_of(sess).cw4_counters)
        new_keys = keys2 - keys1
        assert new_keys == {'m2_stall_cache_hit', 'm2_stall_repeat_frame'}, \
            f'命中帧新增键面超出观测对: {new_keys}'

    def test_t6_cross_caller_stale_token_always_rederives(self):
        """T6 跨调用方失效:商店 visit 末帧 LevelUpShop 置位 token(旧段
        序号)→ 段序号推进(仲裁段/新 visit 入口)→ 首帧必须全量重推导:
        段序号比较失败、残留 token 被读清、rederive 再 +1、hit 恒 0——
        跨战斗伪命中封死锁(防线承重 = 段标识比较,非读清)。"""
        st = _storm_state()
        sess = _locked_session()
        shop.decide_shop_action(st, sess, _cfg())
        _arm_shop_token(sess, 'LevelUpShop')      # visit 末帧动作 ∈ W 残留
        assert state_of(sess).cw4_frame_action_record is not None
        # 新段入口(仲裁段/重进 visit):序号推进
        state_of(sess).cw4_segment_serial += 1
        shop.decide_shop_action(st, sess, _cfg())
        c = state_of(sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 2, '跨段残留须重推导'
        assert c.get('m2_stall_cache_rederive', 0) == 2
        assert c.get('m2_stall_cache_hit', 0) == 0
        assert state_of(sess).cw4_frame_action_record is None, '读清协议'

    def test_t6_latch_serial_guard_independent_of_token(self):
        """T6 两道独立:token 携当前段新序号但闩序号仍为旧段 ⇒ 序号比较
        仍失败 ⇒ 重推导(闩防线不因 token 翻新而旁路)。"""
        st = _storm_state()
        sess = _locked_session()
        shop.decide_shop_action(st, sess, _cfg())
        assert state_of(sess).cw4_m2_stall_latch[1] == 0
        state_of(sess).cw4_segment_serial += 1
        # 模拟残留 token 被同段新动作翻新(序号已是当前段)——闩仍旧段
        _arm_shop_token(sess, 'LevelUpShop')
        shop.decide_shop_action(st, sess, _cfg())
        c = state_of(sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 2
        assert c.get('m2_stall_cache_hit', 0) == 0

    def test_t7_merge_material_guard_blocked_bitwise_identity(self):
        """T7 混合形态恒等锁:bench 含合成素材件(场上同名同星副本)的
        风暴帧——帧2 走缓存路径(cache_hit=1 证明)而
        merge_material_guard_blocked 仍逐帧 +1(== 2):该键由帧首 P56
        投影位独立承载,与本批 M4 缓存正交、行为与本批前现行为逐位一致
        (方案 §3.4-2 零变化申报的行为学锚)。"""
        comp = get_comp(_LOCK_COMP)
        core = set(predicates.line_members(comp))
        hoard_chars, _eq = cw_intention._line_hoard(comp)
        # 线外 1★ 角色作合成素材对(bench 件 + deployed 同名同星副本)
        material = next(n for n in CHARACTERS
                        if n not in hoard_chars and n not in core)
        st = _storm_state(gold=2)
        st.bench[-1] = _bc(material, slot=BENCH_CAPACITY)
        st.deployed = [_bc(material, slot=1)]
        sess = _locked_session()
        shop.decide_shop_action(st, sess, _cfg())     # 帧1:重推导
        _arm_shop_token(sess, 'LevelUpShop')
        shop.decide_shop_action(st, sess, _cfg())     # 帧2:缓存命中
        c = state_of(sess).cw4_counters
        assert c.get('m2_stall_cache_hit', 0) == 1, '帧2 须走缓存路径(锁有效前提)'
        assert c.get('merge_material_guard_blocked', 0) == 2, \
            'P56 投影位每帧首计,不受 M4 缓存影响(零变化恒等)'


# ===== 备战线镜像(mandate.py M2 块)=====


class TestPrepStallCache:
    """run_mandate M2 停摆块续段缓存(T4 备战线镜像;sim 不跑备战栈,
    生产 prep 帧间同构受益)。"""

    def _storm_frame(self) -> mandate.MandateFrame:
        """prep 域风暴帧:bench 9/9 全 3★(燃料集空:1★ 过滤)∧ 线内缺件
        ∧ 席满。"""
        bench = [_bc(f'高价{i}', star=3, slot=i) for i in range(1, 10)]
        return mandate.MandateFrame(
            gold=30, level=3, bench=bench, deployed=[], deploy_cap=4,
            node_type=None, stop_flag=False, k_members=('目标件',),
            round_num=3)

    def test_t4_prep_mirror_hit_identical_emission(self):
        """T4 镜像:帧1 重推导(两事件键+闩)→ token=('LevelUp', 同段)
        → 帧2 命中:两事件键零增量、repeat/hit +1、发射列表逐位一致。"""
        frame = self._storm_frame()
        sess = StrategySession()
        state_of(sess).cw4_counters = {}
        out1 = mandate.run_mandate(frame, sess)
        c = state_of(sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 1
        assert c.get('bench_full_buy_abandon', 0) == 1
        assert c.get('m2_stall_cache_rederive', 0) == 1
        assert state_of(sess).cw4_m2_stall_latch is not None
        _arm_shop_token(sess, 'LevelUp')
        out2 = mandate.run_mandate(frame, sess)
        c = state_of(sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 1, '命中帧事件键不增'
        assert c.get('bench_full_buy_abandon', 0) == 1
        assert c.get('m2_stall_repeat_frame', 0) == 1
        assert c.get('m2_stall_cache_hit', 0) == 1
        assert [repr(e.action) for e in out2] == [repr(e.action) for e in out1]

    def test_t4_prep_variant_token_rederives(self):
        """T4 变异半边:token 型 = SellBench(∉ 备战白名单)⇒ 重推导:
        两事件键再 +1、rederive +1。"""
        frame = self._storm_frame()
        sess = StrategySession()
        state_of(sess).cw4_counters = {}
        mandate.run_mandate(frame, sess)
        _arm_shop_token(sess, 'SellBench')
        mandate.run_mandate(frame, sess)
        c = state_of(sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 2
        assert c.get('bench_full_buy_abandon', 0) == 2
        assert c.get('m2_stall_cache_rederive', 0) == 2
        assert c.get('m2_stall_cache_hit', 0) == 0

    def test_t6_prep_cross_domain_latch_serial_fails(self):
        """T6 跨域封死(备战域):商店 visit 写下的闩(序号 N)在备战期
        开始(序号 N+1)后不可被 prep 帧消费——即使 token 已携当前段新
        序号,闩序号不等 ⇒ 重推导(跨域伪命中被段标识比较拦截)。"""
        st_state = _storm_state()
        shop_sess = _locked_session()
        shop.decide_shop_action(st_state, shop_sess, _cfg())
        assert state_of(shop_sess).cw4_m2_stall_latch is not None
        c = state_of(shop_sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 1    # 商店帧首推导
        state_of(shop_sess).cw4_segment_serial += 1   # 备战期开始:推进
        _arm_shop_token(shop_sess, 'LevelUp')         # prep 帧间动作
        frame = mandate.MandateFrame(
            gold=30, level=3,
            bench=[_bc(f'高价{i}', star=3, slot=i) for i in range(1, 10)],
            deployed=[], deploy_cap=4, node_type=None, stop_flag=False,
            k_members=('目标件',), round_num=3)
        mandate.run_mandate(frame, shop_sess)
        c = state_of(shop_sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 2, '跨域闩失效 ⇒ prep 帧重推导计数'
        assert c.get('m2_stall_cache_rederive', 0) == 2
        assert c.get('m2_stall_cache_hit', 0) == 0
