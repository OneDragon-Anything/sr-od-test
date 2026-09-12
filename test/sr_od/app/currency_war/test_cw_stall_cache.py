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
    locked_buy_cap_hold,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    BenchChar,
    CwWorkFrame,
    SellBench,
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
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bs,
    cw4_feed,
)

# ===== 基建 =====

_LOCK_COMP = '列车同行'


def _cfg():
    return SimpleNamespace(ev_arm='full')


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
                 ) -> CwWorkFrame:
    """风暴帧构造:bench 9/9 全为锁定采购集成员(经 exclude 排除 ⇒ 腾席
    燃料集空)∧ 缺员核心件不在场 ⇒ M4 腾席无候选停摆形态。
    T-307/R1(ADR-0647)fixture 口径对齐:占位成员取截断义务集 B' 内
    (lv7 下剔除被截的杰帕德/彦卿——被截成员 R1 后可卖,混入会使风暴
    前提「燃料集空」破,由 test_cw_locked_buy_membership_split 的
    TestSeatDeadlockRelease(2026-09-12 归并批并入)另行承载)。"""
    comp = get_comp(_LOCK_COMP)
    core = set(predicates.line_members(comp))
    hoard_chars, _eq = cw_intention._line_hoard(comp)
    hoard_only = sorted(set(hoard_chars) - core)
    st_probe = CwWorkFrame(gold=gold, level=7, round_num=2, hp=60)
    bp = cw_intention.locked_buy_membership(
        _locked_ist_proxy(), cap_hold=locked_buy_cap_hold(st_probe)) or frozenset()
    hoard_only = [m for m in hoard_only if m in bp]
    assert len(hoard_only) >= BENCH_CAPACITY, '构造前提:B\' 内囤件须满席'
    st = CwWorkFrame(gold=gold, level=7, round_num=2, hp=60)
    st.plane = 2
    st.shop = []
    st.bench = [_bc(m, slot=i + 1)
                for i, m in enumerate(hoard_only[:BENCH_CAPACITY])]
    # 非空板前置(T-32 空板止损守卫):守卫钉「待卖后 deployed 为空 ⇒
    # 拒卖」,卖出判据/发射位直调环境须 ≥1 上场件,否则 fail-closed
    # 拒帧——与被测语义无关的红按环境前置补齐,非跟绿。
    st.deployed = (list(deployed) if deployed is not None
                   else [_bc('板上件锚', slot=1)])
    return st


def _locked_ist_proxy() -> IntentionState:
    """_storm_state 构造期的意向代理(与 _locked_session 同构,独立于
    会话生命周期)。"""
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = _LOCK_COMP
    ist.lock_plane = 2
    return ist


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
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        c = state_of(sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 1
        assert c.get('bench_full_buy_abandon', 0) == 1
        assert c.get('m2_stall_cache_rederive', 0) == 1
        assert c.get('m2_stall_cache_hit', 0) == 0
        assert state_of(sess).cw4_m2_stall_latch is not None, '首推导须写闩'
        # 帧间:执行层确认已执行 LevelUpShop(∈ 白名单)→ 置 token
        _arm_shop_token(sess, 'LevelUpShop')
        act2 = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        c = state_of(sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 1, '命中帧事件键不增'
        assert c.get('bench_full_buy_abandon', 0) == 1, '命中帧事件键不增'
        assert c.get('m2_stall_repeat_frame', 0) == 1
        assert c.get('m2_stall_cache_hit', 0) == 1
        assert c.get('m2_stall_cache_rederive', 0) == 1
        # 行为恒等:与无缓存世界的同输入首推导逐位一致
        sess_plain = _locked_session()
        act_plain = shop.decide_shop_action(cw4_bs(st, sess_plain), sess_plain, _cfg())
        assert repr(act2) == repr(act_plain), (act2, act_plain)

    def test_t2_variant_action_invalidates_and_rederives(self):
        """T2 变异失效:帧间动作 = BuyCard(白名单外)⇒ 缓存失效 ⇒ 全量
        重推导:两事件键再 +1(新停摆事件)、hit 恒 0。"""
        st = _storm_state()
        sess = _locked_session()
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        _arm_shop_token(sess, 'BuyCard')
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
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
        sess = _locked_session()
        # 帧1:末席为 3★ 占位件(非燃料)⇒ 停摆形态
        st.bench[-1] = _bc('placeholder', slot=BENCH_CAPACITY, star=3)
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        # 帧间:W 外动作(SellBench)卖出占位件 ⇒ offline 入席
        st.bench[-1] = _bc(offline, slot=BENCH_CAPACITY)
        _arm_shop_token(sess, 'SellBench')
        act2 = shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert isinstance(act2, SellBench), '重推导须发现恢复的燃料并卖出'
        assert act2.expect == offline

    def test_t3_unknown_action_type_conservative_rederive(self):
        """T3 未知动作型保守端:token 型 = 未登记新动作型 ⇒ 视为变异 ⇒
        重推导(最坏退化 = 现行为,零风险)。"""
        st = _storm_state()
        sess = _locked_session()
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        _arm_shop_token(sess, 'SomeFutureAction')
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        c = state_of(sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 2
        assert c.get('m2_stall_cache_hit', 0) == 0

    def test_t5_hit_frame_does_not_touch_sell_channel_keys(self):
        """T5 零静默面:命中帧除观测对外不新增任何计数键(跳过扫描 =
        只少两事件键,其余发射位照常工作——键面形状锁,键集与无缓存
        首推导帧的键集差恰为 {m2_retry_exhausted 事件化} 的设计声明)。"""
        st = _storm_state()
        sess = _locked_session()
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        keys1 = set(state_of(sess).cw4_counters)
        _arm_shop_token(sess, 'LevelUpShop')
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
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
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        _arm_shop_token(sess, 'LevelUpShop')      # visit 末帧动作 ∈ W 残留
        assert state_of(sess).cw4_frame_action_record is not None
        # 新段入口(仲裁段/重进 visit):序号推进
        state_of(sess).cw4_segment_serial += 1
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
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
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
        assert state_of(sess).cw4_m2_stall_latch[1] == 0
        state_of(sess).cw4_segment_serial += 1
        # 模拟残留 token 被同段新动作翻新(序号已是当前段)——闩仍旧段
        _arm_shop_token(sess, 'LevelUpShop')
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())
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
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())     # 帧1:重推导
        _arm_shop_token(sess, 'LevelUpShop')
        shop.decide_shop_action(cw4_bs(st, sess), sess, _cfg())     # 帧2:缓存命中
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
        shop.decide_shop_action(cw4_bs(st_state, shop_sess), shop_sess, _cfg())
        assert state_of(shop_sess).cw4_m2_stall_latch is not None
        c = state_of(shop_sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 1    # 商店帧首推导
        state_of(shop_sess).cw4_segment_serial += 1   # 备战期开始:推进
        _arm_shop_token(shop_sess, 'LevelUp')         # prep 帧间动作
        frame = self._storm_frame()
        mandate.run_mandate(frame, shop_sess)
        c = state_of(shop_sess).cw4_counters
        assert c.get('m2_retry_exhausted', 0) == 2, '跨域闩失效 ⇒ prep 帧重推导计数'
        assert c.get('m2_stall_cache_rederive', 0) == 2
        assert c.get('m2_stall_cache_hit', 0) == 0

    def test_t7_prep_merge_material_key_event_granularity_mirror(self):
        """T7 prep 域镜像(三审 C1):含合成素材件的席满停摆帧——腾席环
        命中帧跳过 ⇒ 腾席环域素材键零增量(m2_stall_cache_hit=1 钉缓存
        生效);T-115 ②(a) 凑息接线(ADR-0580)新增的每帧资格评估位为
        独立触达点:同帧与腾席环共享 _mm_dedup(每帧每素材至多 1),
        跨帧按帧粒度各计 1(C1 口径 = 拦截事件可见性,凑息臂每帧重新
        评估、拒绝真实发生)。原「素材键全帧零增量」断言随新触达点
        语义升级为「缓存域零增量 + 凑息臂帧粒度可辨」。"""
        comp = get_comp(_LOCK_COMP)
        core = set(predicates.line_members(comp))
        hoard_chars, _eq = cw_intention._line_hoard(comp)
        material = next(n for n in CHARACTERS
                        if n not in hoard_chars and n not in core)
        frame = self._storm_frame()
        frame.bench[-1] = _bc(material, slot=9)     # 末席换成素材件(风暴形态
        frame.deployed = [_bc(material, slot=1)]    # 中唯一非 3★ 件 = 守卫目标)
        # 守卫的 deployed 域查经 run_mandate 的 state 参数现读,必须携带
        # 同名同星副本(与商店域 P56 位同款守卫输入)。
        state = CwWorkFrame()
        state.deployed = [_bc(material, slot=1)]
        sess = StrategySession()
        state_of(sess).cw4_counters = {}
        mandate.run_mandate(frame, sess, state)         # 帧1:重推导
        c = state_of(sess).cw4_counters
        assert c.get('merge_material_guard_blocked', 0) == 1, \
            '首推导:凑息臂首计,腾席环同帧去重不重复计'
        assert c.get('m2_retry_exhausted', 0) == 1
        assert state_of(sess).cw4_m2_stall_latch is not None
        _arm_shop_token(sess, 'LevelUp')
        mandate.run_mandate(frame, sess, state)         # 帧2:命中跳过环
        c = state_of(sess).cw4_counters
        assert c.get('m2_stall_cache_hit', 0) == 1, '帧2 须走缓存路径(锁有效前提)'
        assert c.get('merge_material_guard_blocked', 0) == 2, \
            '帧2 = 凑息臂帧粒度再触达 +1;腾席环缓存域零增量(1+1=2)'


# ===== 写点活性锁(三审 T4):删对应写点 ⇒ 锁红 =====


class TestTokenWritePointLiveness:
    """生产 token 写点活性(删写点 → 载体残留 None → 缓存全失效 = 静默
    丢收益,行为面零漂移故无既有锁可红,本组锁承载活性)。覆盖可便宜
    行为化的两处:bridge 驱动器写点(sim/replay 通道)/ prep 主环写点
    (cw_screen_prep 合流位);run_buy_waves 写点与破墙段写点因执行环境
    mock 成本未立行为锁,挂账申报见 ADR-0573 §5(两处与已锁写点同批
    同形三行,主环锁红时同文件同形写点同步暴露)。"""

    def test_shop_driver_write_point_sets_token(self, monkeypatch):
        """bridge 写点活性:decide_shop_screen 循环采纳动作后 token 载体
        置位 (末动作型名, 当前段序号);写点被删 ⇒ 载体 None ⇒ 红。
        决策首帧桩化为 RefreshShop(终结动作:写点在终结 return 前,token
        保留可断言;真实 CloseShop 终结的序列会被下一帧入口读清=协议
        行为,不适用本断言面)。"""
        from sr_od.application.currency_war.kernel import cw_vocab as cw_state
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        strat = MandateV1Strategy()

        def _stub_first_refresh(session, config):
            if not _stub_first_refresh.fired:
                _stub_first_refresh.fired = True
                return cw_state.RefreshShop(reason='anchor_stub')
            return cw_state.CloseShop()

        _stub_first_refresh.fired = False
        monkeypatch.setattr(strat, 'decide_shop_action', _stub_first_refresh)
        st = CwWorkFrame(gold=30, level=7, round_num=2, hp=60)
        st.plane = 2
        st.shop = []
        st.bench = []
        st.deployed = []
        sess = _locked_session()
        cw4_feed(sess, st)
        acts = strat.decide_shop_screen(sess, _cfg())
        assert len(acts) == 1 and isinstance(acts[0], cw_state.RefreshShop), \
            '桩化首帧刷新终结(前提)'
        tok = state_of(sess).cw4_frame_action_record
        assert tok is not None, '驱动器采纳动作后须写 token(写点活性)'
        assert tok[0] == 'RefreshShop'
        assert tok[1] == state_of(sess).cw4_segment_serial

    def test_prep_op_write_point_sets_token(self, test_context, monkeypatch):
        """prep 主环写点活性:备战单轮 op 执行成功后 token 载体置位;
        写点被删 ⇒ 载体 None ⇒ 红。harness 单一源 =
        _cw_helpers.make_prep_round_director(D22 收敛;与
        test_cw_no_progress_guard 的签名写点锁同源镜像,禁删边留角;
        prewarm_state=True = 预冷建 MandateState 载体,写点消费面)。"""
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            OpenShop,
        )
        from test.harness.fixture_controller import (
            enter_running_state,
            fast_sleep,
            reset_running_state,
        )
        from test.sr_od.app.currency_war._cw_helpers import (
            make_prep_round_director,
        )

        d, _match, session = make_prep_round_director(
            test_context, monkeypatch, [OpenShop(read_only=True)],
            prewarm_state=True)
        with fast_sleep():
            enter_running_state(test_context)
            try:
                d.run()
            finally:
                reset_running_state(test_context, d)
        st = state_of(session)
        assert st.cw4_segment_serial == 1, '备战期入口段序号置位活性'
        assert st.cw4_frame_action_record is not None, \
            '主环执行成功后须写 token(写点活性)'
        assert st.cw4_frame_action_record[0] == 'OpenShop'
        assert st.cw4_frame_action_record[1] == st.cw4_segment_serial
