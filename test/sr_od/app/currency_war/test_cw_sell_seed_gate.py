"""T-126 批 5 种子年龄豁免·锁面(P78-7;ADR-0633)。

出处(锁纪律:新锁必引设计出处):
- docs/develop/sr_od/application/currency_war/proofs/math_proofs.md **P78-7**(种子年龄
  豁免命题:窗口 ≤2 轮全通道禁卖 / 账闭合三事件 / 1★ 星辖域边界);
- ADR-0633(本批架构:种子簿三件套 + 装配接线 + 发射位注册);
- ADR-0289(判据表「种子 ≥2 轮不回卖 0 容忍」设计正本——本锁面是其
  生产落地的回归资产;窗口常量 SEED_WINDOW_ROUNDS 同源);
- ADR-0593 §4.1 L3(D5 检测器机械窗 ≤2 行,窗口同值互证);
- ADR-0625(候裁 5 编排者裁决 + §4 过渡窗加重面——seed_acquired
  计数显影即该申报的闭合载体);
- ADR-0611(同轮形态归 L1 fresh_buys;本文件窗界锁与 L1 无交叠)。

红证形态:通道覆盖锁以「无 A 时种子穿过燃料物理谓词」的直调实证为
红证(开拓者·记忆 1★ 线外件在排除前是合法燃料候选,探针在案);锁红
≠ 改动错,先按 ADR-0633 重推锁语义再动手。
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_card_identity import (
    is_engine_piece,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    board_state_bridge as _bsb,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BenchChar,
    CwWorkFrame,
)
from sr_od.application.currency_war.sim.checks import selfcalc
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
    sell_gate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    shop as shop_mod,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from test.sr_od.app.currency_war._cw_helpers import cw4_feed

# ===== 测试基建(与 test_cw_sell_window_launch 同构)=====

#: 种子代表(注册表实名;引擎件 ∧ 非静态持有集,探针在案:D5 证据同名)。
_SEED = '开拓者·记忆'
#: 第二种子名(位面闭合/覆盖语义锁用;D5 证据同名)。
_SEED2 = '开拓者·欢愉'
#: 非引擎件代表(希儿;registry_core 档,is_engine_piece=False 实测)。
_NON_ENGINE = '希儿'
#: 引擎件非种子代表(青雀;引擎件但未获取登记 = 合法燃料)。
_FUEL = '青雀'

_SELL_CHANNELS = ('interest', 'funding', 'm4_fuel', 'line_switch',
                  'projection')


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _sess() -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = SimpleNamespace(
        name='测试线', core_chars=('目标件',), shared_chars=())
    state_of(s).v3_intention = IntentionState()
    return s


def _state(bench: list[BenchChar], *, plane: int = 2,
           round_num: int = 3) -> CwWorkFrame:
    st = CwWorkFrame(gold=50, level=7, round_num=round_num, hp=60)
    st.plane = plane
    st.bench = list(bench)
    # 非空板前置(T-32 空板止损守卫):守卫钉「待卖后 deployed 为空 ⇒
    # 拒卖」,卖出判据/发射位直调环境须 ≥1 上场件,否则 fail-closed
    # 拒帧——与被测语义无关的红按环境前置补齐,非跟绿。
    st.deployed = [_bc('板上件锚', slot=1)]
    st.shop = []
    return st


def _seed_registry(sess: StrategySession) -> dict:
    return getattr(state_of(sess), sell_gate.SEED_ACQUISITIONS_ATTR, {})


# ===== 获取资格谓词(P78-7 种子定义四腿)=====


class TestSeedAcquisitionPredicate:
    """seed_acquisition_eligible 单一源锁(ADR-0633 §3;写端与测试同消费)。"""

    def test_eligible_positive_engine_1star_not_held(self):
        """正格:1★ 引擎件 ∧ 购买时未持有 = 种子(P78-7 种子定义;
        开拓者·记忆 = findprob_20260910_005622 D5 证据同名)。"""
        assert sell_gate.seed_acquisition_eligible(
            _SEED, 1, [_bc(_FUEL)], []) is True

    def test_star_leg_2star_out_of_scope(self):
        """星辖域腿:2★/3★ 获取不入种子账(P78-7 星辖域边界:往返非净 0
        [P76 甲 cost≥2 恒 −1]且无 1★ 燃料通道可达,归 P41② 主不等式)。"""
        assert sell_gate.seed_acquisition_eligible(
            _SEED, 2, [], []) is False
        assert sell_gate.seed_acquisition_eligible(
            _SEED, None, [], []) is False

    def test_identity_leg_non_engine_rejected(self):
        """身份腿:非引擎件(含注册表外名)不立种子账(P78-7 引擎件
        合取;单一源 = kernel cw_card_identity.is_engine_piece)。"""
        assert is_engine_piece(_NON_ENGINE) is False
        assert sell_gate.seed_acquisition_eligible(
            _NON_ENGINE, 1, [], []) is False
        assert sell_gate.seed_acquisition_eligible(
            '', 1, [], []) is False

    def test_held_leg_bench_and_deployed_rejected(self):
        """持有腿:购买时已持有(bench 或 deployed 有同名)不立种子账
        (P78-7「购买时未持有」合取;发射时点等价读法,与 D5/selfcalc
        held_names_upto 同口径)。"""
        assert sell_gate.seed_acquisition_eligible(
            _SEED, 1, [_bc(_SEED)], []) is False
        assert sell_gate.seed_acquisition_eligible(
            _SEED, 1, [], [_bc(_SEED)]) is False


# ===== 种子簿:载体/写端/显影 =====


class TestSeedRegistry:
    """种子登记簿载体与写端锁(ADR-0633 §3;与发射登记簿载体分离)。"""

    def test_carrier_separate_from_launch_registry(self):
        """载体分离:种子簿 ≠ 发射登记簿属性(两簿语义不同源——发射
        簿辖买因账期,种子簿辖卡牌身份账期;同属性 = 双源互染)。"""
        assert (sell_gate.SEED_ACQUISITIONS_ATTR
                != sell_gate.LAUNCH_REGISTRY_ATTR)
        assert sell_gate.SEED_ACQUISITIONS_ATTR == 'cw4_seed_acquisitions'

    def test_register_and_overwrite_latest_wins(self):
        """写端:登记落账 + 同名重登记覆盖(最新获取胜,与发射登记簿
        同语义;轮戳随覆盖更新)。"""
        sess = _sess()
        assert sell_gate.register_seed_acquisition(
            sess, _SEED, plane=2, round_num=3)
        assert sell_gate.register_seed_acquisition(
            sess, _SEED, plane=2, round_num=5)
        assert _seed_registry(sess)[_SEED] == (2, 5)

    def test_register_empty_name_rejected(self):
        """空名拒登记(与 register_launch 同卫生纪律)。"""
        assert sell_gate.register_seed_acquisition(
            _sess(), '', plane=2, round_num=3) is False

    def test_register_bumps_seed_acquired_counter(self):
        """显影:登记即 seed_acquired 计数(ADR-0625 候裁 5「种子过渡窗
        无显影」申报的闭合载体;计数容器缺省不炸)。"""
        sess = _sess()
        sell_gate.register_seed_acquisition(sess, _SEED, plane=2,
                                            round_num=3)
        assert state_of(sess).cw4_counters['seed_acquired'] == 1


# ===== 读端三重闭合(P78-7 账闭合语义)=====


class TestSeedExclusionClosures:
    """seed_exclusions 三重闭合锁(位面/窗界/活性;ADR-0633 §3)。"""

    def test_window_active_through_two_rounds_then_expiry(self):
        """窗界闭合:获取轮 b 起 b/b+1/b+2 保护,b+3 过期就地销
        (ADR-0289「≥2 轮内不回卖」+D5 机械窗 ≤2 行同值;过期 = 账
        销毁非过滤,防陈旧账复活)。"""
        sess = _sess()
        cw4_feed(sess, _state([_bc(_SEED)], round_num=3))
        sell_gate.register_seed_acquisition(sess, _SEED, plane=2,
                                            round_num=3)
        assert sell_gate.seed_exclusions(sess, 3) == {_SEED}
        assert sell_gate.seed_exclusions(sess, 4) == {_SEED}
        assert sell_gate.seed_exclusions(sess, 5) == {_SEED}
        assert sell_gate.seed_exclusions(sess, 6) == frozenset()
        assert _SEED not in _seed_registry(sess)

    def test_plane_closure_p2_swap_freedom(self):
        """位面闭合:过渡阶段(P1)种子账在 P2 全部终结——P2 换血自由
        由发展优先不变量(01_math_framework §8-2)要求该闭合存在
        (P78-7 账闭合③;D5 行序跨面紧邻不漏报是检测器过近似,非生产
        闭合语义)。同位面内 pivot 随窗界自然过期(有界,不设读点)。"""
        sess = _sess()
        cw4_feed(sess, _state([_bc(_SEED)], plane=2, round_num=4))
        sell_gate.register_seed_acquisition(sess, _SEED, plane=1,
                                            round_num=3)
        assert sell_gate.seed_exclusions(sess, 4) == frozenset()
        assert _SEED not in _seed_registry(sess)

    def test_liveness_closure_piece_left_bench(self):
        """活性闭合:名不在当前 bench = 件离场(卖出/部署/合成的机械判,
        P78-7 账闭合①②)——账就地销,防同名再获取前误保。"""
        sess = _sess()
        cw4_feed(sess, _state([_bc(_FUEL)], plane=2, round_num=4))
        sell_gate.register_seed_acquisition(sess, _SEED, plane=2,
                                            round_num=3)
        assert sell_gate.seed_exclusions(sess, 4) == frozenset()
        assert _SEED not in _seed_registry(sess)

    def test_fail_closed_keeps_protection_without_frames(self):
        """帧缺 fail-closed:黑板帧全缺时保持保护面(过度禁卖有界:
        账随写端覆盖与活性闭合自然收敛;方向与 L1 读端自治一致,
        ADR-0611 C2)。"""
        sess = _sess()
        sell_gate.register_seed_acquisition(sess, _SEED, plane=2,
                                            round_num=3)
        assert sell_gate.seed_exclusions(sess) == {_SEED}

    def test_second_seed_name_independent(self):
        """多名独立:两种子名各账各闭(覆盖语义只对同名)。"""
        sess = _sess()
        cw4_feed(sess, _state([_bc(_SEED), _bc(_SEED2, slot=2)],
                              plane=2, round_num=4))
        sell_gate.register_seed_acquisition(sess, _SEED, plane=2,
                                            round_num=4)
        sell_gate.register_seed_acquisition(sess, _SEED2, plane=2,
                                            round_num=3)
        assert sell_gate.seed_exclusions(sess, 4) == {_SEED, _SEED2}


# ===== 装配 A 接线(全通道生效;消费位零改)=====


class TestAssemblyWiring:
    """sell_exclusions 种子段接线锁(P78-7;ADR-0633 §3 装配接线)。"""

    def _seed_sess(self) -> StrategySession:
        sess = _sess()
        cw4_feed(sess, _state([_bc(_SEED), _bc(_FUEL, slot=2)],
                              plane=2, round_num=3))
        sell_gate.register_seed_acquisition(sess, _SEED, plane=2,
                                            round_num=3)
        return sess

    def test_all_channels_exclude_active_seed(self):
        """全通道生效:五种卖出通道视图都含活跃种子(P78-7「全卖出通道
        禁卖」;经装配 A 单一入口,消费位零改)。"""
        sess = self._seed_sess()
        for ch in _SELL_CHANNELS:
            excl = sell_gate.sell_exclusions(sess, (), channel=ch,
                                             current_round=3)
            assert _SEED in excl, ch

    def test_projection_view_equals_interest_face_with_seed(self):
        """读端同源(P78-6 继承):projection 投影视图 = interest 全资格
        面——种子入 interest 即入投影,防 liquid_refund 高估。"""
        sess = self._seed_sess()
        interest = sell_gate.sell_exclusions(sess, (), channel='interest',
                                             current_round=3)
        projection = sell_gate.sell_exclusions(sess, (),
                                               channel='projection',
                                               current_round=3)
        assert _SEED in interest
        assert interest == projection

    def test_expired_seed_released_on_all_channels(self):
        """窗界过期满通道放行:过期种子不再出现在任何通道排除集
        (保护有界性;过度禁卖 ≤2 轮)。"""
        sess = self._seed_sess()
        for ch in _SELL_CHANNELS:
            excl = sell_gate.sell_exclusions(sess, (), channel=ch,
                                             current_round=6)
            assert _SEED not in excl, ch

    def test_seed_face_yields_only_to_switch_orphans(self):
        """种子面 carve 按账闭合事件分界(对抗审发现 2 修订,ADR-0633 §3):
        ①垫保同轮转化不让位:种子账活跃(无账闭合事件)时同名活跃垫保
        登记不放行卖出——同 visit 买种卖种 = P78-1 定义性抵消(对兜底
        豁免同样构成上界),P78-5′ 两腿皆不成立(桥建账同帧作废+退款
        净 0 不达成义务账);非种子垫保件的 defer 转化放行语义零改
        (走 L1 carve,本锁不动 L1 面)。
        ②换线孤儿让位:本轮义务买入出基座 = 线账闭合(P78-2a),塌缩
        清算卖照常发射(ADR-0591 §4 打标制;集成面实证 =
        test_cw_sell_reason_matrix TestLineSwitchOrphanSeed18)。"""
        sess = _sess()
        cw4_feed(sess, _state([_bc(_SEED)], plane=2, round_num=3))
        sell_gate.register_seed_acquisition(sess, _SEED, plane=2,
                                            round_num=3)
        # ①垫保语境:同名活跃垫保登记 → 种子仍受保护(发现 2 修订形态)。
        assert sell_gate.register_launch(sess, _SEED, cause='stall_protect',
                                         round_num=3)
        excl = sell_gate.sell_exclusions(sess, (), channel='m4_fuel',
                                         current_round=3)
        assert _SEED in excl
        # ②换线孤儿语境:本轮义务买入出基座(基座 = 空)→ 孤儿证明集
        # 命中 → 种子面让位塌缩清算。
        sess2 = _sess()
        cw4_feed(sess2, _state([_bc(_SEED)], plane=2, round_num=3))
        sell_gate.register_seed_acquisition(sess2, _SEED, plane=2,
                                            round_num=3)
        sell_gate.obligation_book_of(sess2)[_SEED] = 3
        excl2 = sell_gate.sell_exclusions(sess2, (), channel='m4_fuel',
                                          current_round=3)
        assert _SEED not in excl2

    def test_production_order_stale_entry_frame_keeps_fresh_seed(self):
        """生产序锁(对抗审发现 1 修复;W6 波 4 容器化重推):获取 visit
        内的新鲜种子账必须存活并进全通道排除面。原双帧载体(last_state
        段入口快照 + shop_state_frame 逐动作投影帧)随黑板槽退役消亡,
        防线由容器活值续承——bench 轴 = bs.bench,visit 内逐动作投影
        直写使新鲜买入即时在席(_seed_frame_axes docstring 申报)。
        本锁喂入形态 = 段入口帧(买前)→ 登记种子 → 投影帧(买后,种
        子在席),钉「新鲜账不被活性闭合在获取 visit 内销毁」。
        守卫移除验证:bench 轴退回滞后快照读时本锁必红。"""
        sess = _sess()
        cw4_feed(sess, _state([_bc(_FUEL)], plane=2,
                              round_num=3))            # 段入口快照(买前)
        sell_gate.register_seed_acquisition(sess, _SEED, plane=2,
                                            round_num=3)
        # visit 内买入投影(买后,种子在席;apply_shop_action_logic bench
        # 域投影直写同形)。
        cw4_feed(sess, _state([_bc(_FUEL, slot=2), _bc(_SEED, slot=3)],
                              plane=2, round_num=3))
        assert sell_gate.seed_exclusions(sess) == {_SEED}
        excl = sell_gate.sell_exclusions(sess, (), channel='m4_fuel',
                                         current_round=3)
        assert _SEED in excl

    def test_liveness_closure_requires_both_frames_absent(self):
        """活性闭合活值证据(W6 波 4 容器化重推:原「双帧并集」双滞后
        方向封口随黑板槽退役消亡,活性闭合改读容器 bench 活值——
        _seed_frame_axes docstring 申报):名在容器 bench = 在席保留;
        名不在(同轮喂入离场帧)= 件离场成立照常销。"""
        sess = _sess()
        # 名在容器 bench → 保留。
        cw4_feed(sess, _state([_bc(_FUEL, slot=2), _bc(_SEED, slot=3)],
                              plane=2, round_num=3))
        sell_gate.register_seed_acquisition(sess, _SEED, plane=2,
                                            round_num=3)
        assert sell_gate.seed_exclusions(sess, 3) == {_SEED}
        # 名不在容器 bench(离场)→ 照常销。
        sess2 = _sess()
        cw4_feed(sess2, _state([_bc(_FUEL, slot=2)], plane=2, round_num=3))
        sell_gate.register_seed_acquisition(sess2, _SEED, plane=2,
                                            round_num=3)
        assert sell_gate.seed_exclusions(sess2, 3) == frozenset()

    def test_register_rejects_plane_none(self):
        """位面缺读拒登记(fail-closed;对抗审发现 4:位面本地轮号跨位面
        重启使窗界算术双向失真,与 hold 类缺读拒纪律一致)。"""
        sess = _sess()
        assert sell_gate.register_seed_acquisition(
            sess, _SEED, plane=None, round_num=3) is False
        assert _SEED not in _seed_registry(sess)

    def test_fuel_candidates_exclude_seed_via_assembly(self):
        """m4 腾席路径:无 A 时种子穿过燃料物理谓词(直调实证红证:
        1★ 线外引擎件是合法燃料候选);注入装配 A 排除集后种子出候选、
        非种子引擎件(青雀)保持候选——窄获取设计实证(引擎件非种子
        仍合法燃料,静态全集排除被否决的形态对照)。"""
        bench = [_bc(_SEED), _bc(_FUEL, slot=2)]
        st = _state(bench, plane=2, round_num=3)
        sess = _sess()
        cw4_feed(sess, st)
        sell_gate.register_seed_acquisition(sess, _SEED, plane=2,
                                            round_num=3)
        raw = mandate.fuel_sell_candidates(bench, (), _bsb(st))
        assert _SEED in [c.char_id for c in raw]
        excl = sell_gate.sell_exclusions(sess, (), channel='m4_fuel',
                                         current_round=3)
        gated = mandate.fuel_sell_candidates(bench, (), _bsb(st),
                                             exclude_names=excl)
        assert _SEED not in [c.char_id for c in gated]
        assert _FUEL in [c.char_id for c in gated]


# ===== 发射位接线与单一源收拢 =====


class TestEmissionAndSingleSource:
    """发射位结构锁与身份单一源收拢锁(ADR-0633 §3)。"""

    def test_emit_buy_source_registers_seed(self):
        """发射位接线结构锁:_emit_buy 源面含种子资格谓词与登记调用
        (inspect.getsource 先例 = 统一state R4 锁①f;漏接线 = 相邻轮
        种子回卖保护整面失效的静默形态,源面结构锁防回归)。"""
        src = inspect.getsource(shop_mod.decide_shop_action)
        assert 'seed_acquisition_eligible' in src
        assert 'register_seed_acquisition' in src

    def test_selfcalc_delegates_to_kernel_single_source(self):
        """身份单一源收拢:selfcalc.is_engine_piece 委托 kernel 判定核
        (消第二实现;判定核同公式,消费方 D5/C7 零改)。行为等价 +
        源面委托双证。"""
        samples = (_SEED, _SEED2, _FUEL, _NON_ENGINE, '', '不存在名')
        for n in samples:
            assert selfcalc.is_engine_piece(n) == is_engine_piece(n), n
        src = inspect.getsource(selfcalc.is_engine_piece)
        assert 'cw_card_identity' in src
