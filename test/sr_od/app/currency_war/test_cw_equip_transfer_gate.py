"""M7 装备转移发射门回归(dd-027;2026-09-03 实机 RunEquip 备战环活锁)。

事故链:mandate 旧发射谓词「last_owned_equips 非空即发 RunEquip」,而
owned 快照按 ADR-0387 全量含工具件(不可穿)——工具-only 库存谓词永真 ⇒
每帧重发 RunEquip 且执行侧 0 穿 ⇒ 空批出口(StartBattle)永不可达,备战
环活锁(实机 1-6 卡死,哨兵签名「序列完成(RunEquip)」零推进)。

修法(dd-027)= 变换可能性两件套,锁钉行为语义而非实现细节:
门① 可穿存在性(注册表已登记 ∧ 非工具类)——持有面谓词换变换面谓词;
门② 备战期闩(cw4_m7_equipped_phase)——同 (plane, round) 只消费一次,
闩置位在执行位(mandate.mark_equip_pass_executed;发射位只读不写)、
推进自动失效;与备战期开店闩(cw4_shopped_phase)同构且独立(键不同,
互不遮蔽)。

dd-027 修订(实机局 g_20260904_010335 漏发定谳,2026-09-04):同帧
「开店意图 ∧ 可穿件」形态下,M7 末位评估的 RunEquip 落在 OpenShop
(截断点)之后被截断器静默丢弃,闩已被消耗 ⇒ 装备滞留整个备战期
(1-6/1-7 漏发,1-8 无开店面才首穿)。修法 = 发射序回排(RunEquip
插到首个截断点/终点之前),TestM7EmissionOrder 锁此形态;复盘批的
「快照依赖环」假设被帧数据证伪(1-6 决策帧 state.equips 已含轮滑鞋,
快照经 overlay 确认链及时推进)。
"""
from __future__ import annotations
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import state_of

from sr_od.application.currency_war.kernel.cw_prep_actions import (
    OpenShop,
    RunDeploy,
    RunEquip,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import mandate

# 工具件/穿戴件取注册表真实规范名(锁语义不锁牌面;名字变动时改此处,
# 谓词走 EQUIPMENTS 注册表现查,不依赖测试桩)
_TOOLS = ['拆装扳手', '冶金炉']          # 注册表 category='工具'
_WEARABLE = ['和平手枪', '轮滑鞋']       # 注册表非工具类(历史 fixture 常用件)


def _frame(round_num: int = 3, stop: bool = True) -> mandate.MandateFrame:
    """最小备战帧:stop=True 压掉 M2/dominance/M6 的开店发射面,本批只看 M7。"""
    return mandate.MandateFrame(
        gold=0, level=3, bench=[], deployed=[], deploy_cap=4,
        node_type='战斗', stop_flag=stop, k_members=(),
        round_num=round_num)


def _session(owned: list[str]) -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    s.last_owned_equips = list(owned)
    return s


def _m7_actions(out: list) -> list:
    return [e for e in out if isinstance(e.action, RunEquip)]


class TestM7WearableGate:
    """门①:可穿存在性(变换面谓词,替持有面谓词)。"""

    def test_tools_only_owned_never_fires(self):
        """事故回归帧:owned 全工具件 → 不发 RunEquip(旧码永真重发=活锁根)。"""
        out = mandate.run_mandate(_frame(), _session(_TOOLS))
        assert _m7_actions(out) == []

    def test_wearable_owned_fires(self):
        """owned 有穿戴类件 → 正常发射(门不误杀常态转移)。"""
        out = mandate.run_mandate(_frame(), _session(_WEARABLE))
        assert len(_m7_actions(out)) == 1

    def test_mixed_owned_fires(self):
        """穿戴件+工具件混装 → 发射(工具不遮蔽可穿件)。"""
        out = mandate.run_mandate(_frame(), _session(_TOOLS + _WEARABLE))
        assert len(_m7_actions(out)) == 1

    def test_unregistered_name_not_wearable(self):
        """未登记名按不可穿保守侧(与执行侧 wearable 过滤同口径)。"""
        out = mandate.run_mandate(_frame(), _session(['语料未知名']))
        assert _m7_actions(out) == []


class TestM7PhaseLatch:
    """门②:备战期闩(置位=执行位;非时间冷却)。

    语义演进(C3 同型残留修复):闩置位从发射位移到 RunEquip 执行位
    (mandate.mark_equip_pass_executed,唯一写点 = prep_actions 执行
    入口在组合 op 成功返回时调用)——发射位只读不写。闩未置时同期
    重发由执行成功后的闩拦下;发射永不落地的残值由 DD-030 环级守卫
    兜底。
    """

    def test_same_phase_fires_once(self):
        """执行成功置闩后,同 (plane, round) 后续帧不再发,计数
        equip_latch_skip_m7=1;闩未置时同帧重跑照常重发(发射不烧闩)。"""
        s = _session(_WEARABLE)
        st = GameState(round_num=3)
        assert len(_m7_actions(mandate.run_mandate(_frame(), s, state=st))) == 1
        # 闩未置(发射≠执行):重跑照常发射
        assert len(_m7_actions(mandate.run_mandate(_frame(), s, state=st))) == 1
        # 穿戴 pass 执行成功(执行位置位)→ 同期后续帧不再发
        mandate.mark_equip_pass_executed(s, st)
        out3 = mandate.run_mandate(_frame(), s, state=st)
        assert _m7_actions(out3) == []
        assert state_of(s).cw4_counters['equip_latch_skip_m7'] == 1

    def test_phase_advance_relatches(self):
        """位面/轮次推进 = 新键自动失效,新发放件重评(闩不是局级开关)。"""
        s = _session(_WEARABLE)
        st3, st4 = GameState(round_num=3), GameState(round_num=4)
        assert len(_m7_actions(mandate.run_mandate(_frame(3), s, state=st3))) == 1
        mandate.mark_equip_pass_executed(s, st3)
        assert _m7_actions(mandate.run_mandate(_frame(3), s, state=st3)) == []
        # 轮次推进:重新武装
        assert len(_m7_actions(mandate.run_mandate(_frame(4), s, state=st4))) == 1
    # 「发射不置闩 / 门①拦下不置闩」面由 TestM7LatchAtExecution::
    # test_deploy_termination_does_not_burn_latch(发射后闩仍 None)与
    # test_cw_mandate_v1.py::TestShopPhaseLatch::
    # test_emit_does_not_set_latch_and_rerun_reemits(发射后开店闩为 None)
    # 承载,此处不再重复立锁。


class TestM7ShopLatchCoexistence:
    """闩语义共存:装备闩与开店闩(cw4_shopped_phase)独立互不遮蔽。"""

    def test_shop_latch_does_not_block_m7(self):
        s = _session(_WEARABLE)
        state_of(s).cw4_shopped_phase = (None, 3)      # 开店闩已置(同期已开过店)
        assert len(_m7_actions(mandate.run_mandate(_frame(), s))) == 1

    def test_equip_latch_does_not_block_shop(self):
        """反向:装备闩置位后,M6 溢余开店面不被装备闩拦(分站键)。"""
        s = _session(_WEARABLE)
        st = GameState(gold=60, plane=1, round_num=3)
        # 同 (plane, round)=(1,3) 首帧:发射 RunEquip 并在执行位记账置闩
        mandate.run_mandate(_frame(), s, state=st)
        mandate.mark_equip_pass_executed(s, st)
        # 帧:金 > 息饱和线(cap 4 → 50),stop_flag=True → M6 开店面可达
        f = mandate.MandateFrame(
            gold=60, level=3, bench=[], deployed=[], deploy_cap=4,
            node_type='战斗', stop_flag=True, k_members=(), round_num=3)
        out = mandate.run_mandate(f, s, state=st)
        assert any(isinstance(e.action, RunEquip) for e in out) is False
        assert any(isinstance(e.action, type(out[0].action)) for e in out)
        shop_emitted = any(
            getattr(e.action, 'read_only', True) is False for e in out)
        assert shop_emitted, f'M6 开店面被装备闩误拦: {[type(e.action).__name__ for e in out]}'


class TestM7EmissionOrder:
    """dd-027 修订:同帧「开店 ∧ 可穿件」的发射序回排(事故形态回归)。

    事故(g_20260904_010335 1-6/1-7):M7 末位发射的 RunEquip 落在
    OpenShop(截断点)后被 truncate_frame_stable 丢弃,闩已消耗 ⇒
    整个备战期装备滞留。

    覆盖分工(重复断言择一保留,超集在 mandate_v1 侧):发射序面
    ([RunEquip, OpenShop] 回排序)由 test_cw_mandate_v1.py::
    TestShopPhaseLatch::test_emit_does_not_set_latch_and_rerun_reemits
    承载(同断言面且多锁开店闩语义);本类只留 truncate 端到端存活——
    真实发射列表经 truncate_frame_stable 两动作均存活(事故里 RunEquip
    被截断器静默丢弃,别处无此组合面)。
    """

    def _frame_shop_intent(self) -> mandate.MandateFrame:
        """可穿件在场 + M2 买面意图(线成员缺,bench 空,金足)→ 同帧双意图。"""
        return mandate.MandateFrame(
            gold=10, level=3, bench=[], deployed=[], deploy_cap=4,
            node_type='战斗', stop_flag=False, k_members=('希儿',),
            round_num=3)

    def test_truncation_keeps_both_actions(self):
        """端到端:经帧稳定截断器后两动作均存活(事故里 RunEquip 被丢)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.entry import (
            truncate_frame_stable,
        )
        s = _session(_WEARABLE)
        actions = [e.action for e in
                   mandate.run_mandate(self._frame_shop_intent(), s)]
        kept = truncate_frame_stable(actions, s)
        assert [type(a) for a in kept] == [RunEquip, OpenShop]


class TestM7LatchAtExecution:
    """C3 同型残留回归锁:闩置位在执行位(2026-09-05 双修对抗审计)。

    事故形态:[RunDeploy(可续), RunEquip] 无截断点发射帧(部署空位 ∧
    可穿件同时成立,如补给发装备 + 场上有空位)——单动作备战环第 1 环
    执行 RunDeploy 即「投影未建模,访问终结交回外循环重观察」,
    RunEquip 意图未执行;旧实现发射即置闩 ⇒ 第 2 环 equip_latch_skip
    ⇒ 空批 StartBattle,装备整个备战期滞留。修法 = 置位时机移执行位,
    与开店闩(mandate_v1/shop.decide_shop_action 入口置位)同批同型。

    覆盖分工:本类留「发射不烧闩」回归锁(C3 形态全序 + 闩仍 None);
    「执行成功置闩 → 同期跳过 + 轮次推进重武装」正向面与普通帧共路
    (同一门读同一写点),由 TestM7PhaseLatch::test_same_phase_fires_once
    与 test_phase_advance_relatches 承载,不在此重复。
    """

    def _deploy_equip_frame(self, round_num: int = 3) -> mandate.MandateFrame:
        """无开店意图的「部署空位 ∧ 可穿件」帧:金 0 压掉 M2/dominance/M6
        开店面,stop=True;bench 1 可部署件 + 板空 ⇒ M1 发 RunDeploy。
        闩相位键取 frame.round_num(与 run_mandate phase 同式)。"""
        return mandate.MandateFrame(
            gold=0, level=3,
            bench=[BenchChar(slot=1, char_id='彦卿', star=1)],
            deployed=[], deploy_cap=4,
            node_type='战斗', stop_flag=True, k_members=(),
            round_num=round_num)

    def test_deploy_termination_does_not_burn_latch(self):
        """回归锁:同帧 [RunDeploy, RunEquip] 发射,环被 RunDeploy 先
        终结(RunEquip 未执行)——下一环 mandate 重跑 RunEquip 重新发射
        (闩未烧)。"""
        s = _session(_WEARABLE)
        out1 = mandate.run_mandate(self._deploy_equip_frame(), s)
        kinds = [type(e.action) for e in out1]
        assert kinds == [RunDeploy, RunEquip]       # 可续双动作,无截断点
        assert getattr(s, 'cw4_m7_equipped_phase', None) is None  # 发射不置闩
        out2 = mandate.run_mandate(self._deploy_equip_frame(), s)
        assert len(_m7_actions(out2)) == 1          # 闩未烧,重发
        assert state_of(s).cw4_counters.get('equip_latch_skip_m7', 0) == 0
