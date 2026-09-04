"""M7 装备转移发射门回归(dd-027;2026-09-03 实机 RunEquip 备战环活锁)。

事故链:mandate 旧发射谓词「last_owned_equips 非空即发 RunEquip」,而
owned 快照按 ADR-0387 全量含工具件(不可穿)——工具-only 库存谓词永真 ⇒
每帧重发 RunEquip 且执行侧 0 穿 ⇒ 空批出口(StartBattle)永不可达,备战
环活锁(实机 1-6 卡死,哨兵签名「序列完成(RunEquip)」零推进)。

修法(dd-027)= 变换可能性两件套,锁钉行为语义而非实现细节:
门① 可穿存在性(注册表已登记 ∧ 非工具类)——持有面谓词换变换面谓词;
门② 备战期闩(cw4_m7_equipped_phase)——同 (plane, round) 只发一次,
发射时置闩、推进自动失效;与备战期开店闩(cw4_shopped_phase)同构且
独立(键不同,互不遮蔽)。

dd-027 修订(实机局 g_20260904_010335 漏发定谳,2026-09-04):同帧
「开店意图 ∧ 可穿件」形态下,M7 末位评估的 RunEquip 落在 OpenShop
(截断点)之后被截断器静默丢弃,闩已被消耗 ⇒ 装备滞留整个备战期
(1-6/1-7 漏发,1-8 无开店面才首穿)。修法 = 发射序回排(RunEquip
插到首个截断点/终点之前),TestM7EmissionOrder 锁此形态;复盘批的
「快照依赖环」假设被帧数据证伪(1-6 决策帧 state.equips 已含轮滑鞋,
快照经 overlay 确认链及时推进)。
"""
from __future__ import annotations

from sr_od.application.currency_war.strategies.impl.mandate_v1 import mandate
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    OpenShop,
    RunEquip,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)

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
    s.cw4_counters = {}
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
    """门②:备战期闩(发射后记账防重燃;非时间冷却)。"""

    def test_same_phase_fires_once(self):
        """同 (plane, round) 第二帧不再发,计数 equip_latch_skip_m7=1。"""
        s = _session(_WEARABLE)
        assert len(_m7_actions(mandate.run_mandate(_frame(), s))) == 1
        out2 = mandate.run_mandate(_frame(), s)
        assert _m7_actions(out2) == []
        assert s.cw4_counters['equip_latch_skip_m7'] == 1

    def test_phase_advance_relatches(self):
        """位面/轮次推进 = 新键自动失效,新发放件重评(闩不是局级开关)。"""
        s = _session(_WEARABLE)
        assert len(_m7_actions(mandate.run_mandate(_frame(3), s))) == 1
        # 轮次推进:重新武装
        assert len(_m7_actions(mandate.run_mandate(_frame(4), s))) == 1
        # 位面推进(state.plane 缺席=(None, round) 键,轮次回 1 亦新键)
        assert len(_m7_actions(mandate.run_mandate(_frame(4), s))) == 0

    def test_latch_set_on_emit_only(self):
        """闩发射时才置(本帧无可穿件不置闩)——同开店闩边界语义。"""
        s = _session(_TOOLS)          # 门①拦下,不置闩
        mandate.run_mandate(_frame(), s)
        assert getattr(s, 'cw4_m7_equipped_phase', None) is None
        s.last_owned_equips = list(_WEARABLE)   # 同期拿到可穿件 → 照常发射
        assert len(_m7_actions(mandate.run_mandate(_frame(), s))) == 1


class TestM7ShopLatchCoexistence:
    """闩语义共存:装备闩与开店闩(cw4_shopped_phase)独立互不遮蔽。"""

    def test_shop_latch_does_not_block_m7(self):
        s = _session(_WEARABLE)
        s.cw4_shopped_phase = (None, 3)      # 开店闩已置(同期已开过店)
        assert len(_m7_actions(mandate.run_mandate(_frame(), s))) == 1

    def test_equip_latch_does_not_block_shop(self):
        """反向:装备闩置位后,M6 溢余开店面不被装备闩拦(分站键)。"""
        s = _session(_WEARABLE)
        from sr_od.application.currency_war.kernel.cw_state import GameState
        st = GameState(gold=60, plane=1)
        # 同 (plane, round)=(1,3) 首帧:置装备闩
        mandate.run_mandate(_frame(), s, state=st)
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
    整个备战期装备滞留。锁:回排后 RunEquip 先于截断点发射,截断后
    两动作均保留,闩只被「真实可达截断的发射」消耗一次。
    """

    def _frame_shop_intent(self) -> mandate.MandateFrame:
        """可穿件在场 + M2 买面意图(线成员缺,bench 空,金足)→ 同帧双意图。"""
        return mandate.MandateFrame(
            gold=10, level=3, bench=[], deployed=[], deploy_cap=4,
            node_type='战斗', stop_flag=False, k_members=('希儿',),
            round_num=3)

    def test_runequip_emitted_before_truncation_point(self):
        """事故帧:发射序 = [RunEquip, OpenShop],RunEquip 不落截断点后。"""
        out = mandate.run_mandate(self._frame_shop_intent(), _session(_WEARABLE))
        kinds = [type(e.action) for e in out]
        assert RunEquip in kinds and OpenShop in kinds
        assert kinds.index(RunEquip) < kinds.index(OpenShop)

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

    def test_latch_consumed_once_by_surviving_emission(self):
        """闩语义不回退:回排后发射真实可达截断,同期后续帧恰跳过一次。"""
        s = _session(_WEARABLE)
        actions = [e.action for e in
                   mandate.run_mandate(self._frame_shop_intent(), s)]
        assert any(isinstance(a, RunEquip) for a in actions)
        out2 = mandate.run_mandate(self._frame_shop_intent(), s)
        assert _m7_actions(out2) == []
        assert s.cw4_counters['equip_latch_skip_m7'] == 1
