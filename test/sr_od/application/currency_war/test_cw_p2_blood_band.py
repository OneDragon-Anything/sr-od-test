"""P2 低血带授权域统一件落码锁组(fail-closed 落码)。

设计出处(纯语义索引;原设计稿存于本机工作区归档,未入 git):§1.2
(统一授权域单点 + 判定面/消费面分层正交合成)/§2.1(面①消费让位 +
解锁包三件同构移植 + fail-closed 只落观测分键)/§2.3-5(a)(面③出辖观察件
lock_gen_feasibility_obs_* 族)/§4-8(分键族零交集对账);裁定条目定稿 =
「P2 低血带授权域统一裁定」(覆①消费让位 + 覆②濒死定向豁免 + 覆③出辖
注记位,唯一权威);l3_pregate 分键四元合取与位面维分列 = R3-低3 兑付。
单一语义权威现状 = 生产符号:谓词/授权闩 = statefn.predicates,分键写入端
= flow.bump_lock_gen_feasibility_obs 与 mandate l3 前置短路。

锁三类事(存续面):
1. 判据结构——p2_blood_floor 域谓词真值表(plane≥2 域/信任门/阈值
   单一源 = HP_BAND_NEAR_DEATH,边界随常量走);
2. 危机带停付面——产线在产 p2_crisis_band 对 P2 濒死帧全额管辖:
   M3 停付照常/保底金门照查(花后下界不豁免)/凑息不进 p2_blood_floor
   禁令支(P1 域 'blood_floor' 原键在册语义零改,分键禁并);
3. 观测分键——形态⑥两键(terminal_targetless_idle / l3_pregate_
   targetless_neardeath_p1|p2 分域)+ 面③ lock_gen_feasibility_obs_*
   (锁开率分子/分母 + boss 濒死死区)只计数零行为。

纪律:锁结构/回显不锁分布数值。

锁面组织(极限合并):域真值表+P1 互补并一;三条观测键(形态⑥
terminal_targetless_idle / 锁开率分子分母 / boss 死区)参数化并一;
停付面与 l3 前置分键分列保留。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _bsb,
)
from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.kernel import cw_intention as ci
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    mandate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    predicates as preds,
)


def _st2(hp: int | None = 10, plane: int = 2, gold: int = 30,
         round_num: int = 2, level: int = 7,
         node_type: str | None = None) -> dict:
    """P2 濒死带场景种子轴(hp 缺省 10 ⊂ ≤15 带;返回 = ``_bsb`` kwargs,
    消费位逐次装箱取容器,hp=None = 域未观察)。"""
    axes: dict = {'hp': hp, 'plane': plane, 'gold': gold,
                  'round_num': round_num, 'level': level}
    if node_type is not None:
        axes['node'] = node_type   # 终态契约 §A′:node 单一源 = gs
    return axes


# ===== 1. 判据结构:域谓词 + 授权闩合成 =====


class TestP2BloodFloorPredicate:

    def test_domain_truth_table_and_p1_complement(self):
        """域真值表 + 位面域互补并一。
        [真值表] p2_blood_floor:plane≥2 ∧ hp≤15 ∧ 可信 ⇒ True;
        hp>15 / hp None / 不可信帧 fail 向 ⇒ False(与 p1_blood_floor
        逐行同构,设计稿 §2.1)。阈值单一源(设计稿 §1.1「禁任何第二份
        字面量 15」):谓词边界 = HP_BAND_NEAR_DEATH 读数(≤15 族含
        边界),非本地第二份——改常量即改边界,无第二值可漂。
        [互补] 位面域互补且不交(设计稿 §2.1「同构不同域,禁搭车」):
        P1 帧不得开 P2 域谓词(P1 半边 = p1_blood_floor 在册授权,零改);
        P3 帧属 P2+ 域(谓词 plane≥2 口径)。"""
        # [真值表]
        st = _st2(hp=10)
        assert preds.p2_blood_floor(_bsb(**st)) is True
        st['hp'] = 16
        assert preds.p2_blood_floor(_bsb(**st)) is False
        st['hp'] = 15   # ≤15 族含边界(p1_blood_floor 同款)
        assert preds.p2_blood_floor(_bsb(**st)) is True
        st['hp'] = None
        assert preds.p2_blood_floor(_bsb(**st)) is False
        st['hp'] = None   # 不可读 = 域未观察(无可信值可桥,fail 向)
        assert preds.p2_blood_floor(_bsb(**st)) is False
        # 阈值单一源:边界随常量走
        from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.lambda_death import (
            HP_BAND_NEAR_DEATH,
        )
        assert preds.p2_blood_floor(_bsb(**_st2(hp=HP_BAND_NEAR_DEATH))) is True
        assert preds.p2_blood_floor(
            _bsb(**_st2(hp=HP_BAND_NEAR_DEATH + 1))) is False
        # [互补]
        st = _st2(hp=10, plane=1)
        assert preds.p1_blood_floor(_bsb(**st)) is True
        assert preds.p2_blood_floor(_bsb(**st)) is False, 'P1 帧禁开 P2 域谓词'
        st3 = _st2(hp=10, plane=3)
        assert preds.p2_blood_floor(_bsb(**st3)) is True


# ===== 2. 危机带停付面(在产 p2_crisis_band 全额管辖)=====


class TestUnlockPackageFailClosed:

    def test_m3_spend_still_blocked_while_latch_off(self):
        """危机带停付面:实锁 = 产线在产 p2_crisis_band 对 P2 濒死帧
        (hp≤15 ⊂ 危机带 41)全额管辖——停付照常;保底金门照查(花后
        下界不豁免;血线地板解锁让位支已随血线地板删除链退役——迭代
        2026-10-12-prep-shop-workflow-redesign 批 3.4,line_and_upgrade
        §2.3 血线地板解锁行:替代语义 = 濒死响应走修经济/阵容本身);
        凑息不受血线辖(凑息禁令位已随同链退役,凑息行为由金位缺口
        驱动)。"""
        from sr_od.application.currency_war.kernel.cw_registry import (
            DEFAULT_REGISTRY,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.levelup import (
            guarantee_floor_gate,
            level_spend_blocked,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.sell import (
            sell_for_interest,
        )
        sess = SimpleNamespace(node_type_current='normal')
        assert level_spend_blocked(_bsb(**_st2(hp=10)), sess,
                                   DEFAULT_REGISTRY) is True, (
            'P2 濒死帧停付照常(危机带管辖)')
        # 保底金门照查(血线让位支已退役:无豁免,花后下界照设)
        assert guarantee_floor_gate(
            _bsb(**_st2(hp=10)), sess, 5, 1, 4, 5) is False
        # 凑息不受血线辖(血线拒因键退役:两域帧的拒因键族里血线键
        # 不复存在——空板守卫等金位/板面键照常,P1/P2 域同判)
        for _st in (_st2(hp=10), _st2(hp=10, plane=1)):
            slots_k, key_k = sell_for_interest(
                30, [], 4, (), state=_bsb(**_st))
            assert slots_k == []
            assert key_k not in ('blood_floor', 'p2_blood_floor'), (
                '血线拒因键已随凑息禁令位退役')
# ===== 3. 观测分键(纯观测零行为)=====


# (l3_pregate_targetless_neardeath_p1|p2 观测分键类已随 mandate M3 段
# 退役消亡——迭代 2026-10-12-prep-shop-workflow-redesign 批 3.4:升级
# 判据内核收拢为 entry 备战第 3 步(criteria/levelup.upgrade_trigger
# 五臂),M3 前置短路形态不复存在,该分键无触发面;替代语义考古走
# git 历史。观测族的存续成员〔形态⑥ terminal_targetless_idle /
# lock_gen_feasibility_obs_*〕由 TestLockGenObservationKeys 承载。)
class TestLockGenObservationKeys:
    """面③出辖观察件(载体 = flow.bump_lock_gen_feasibility_obs,strategies
    侧消费位;kernel 观察位禁反向 import strategies,布局依赖矩阵)。

    「切阵后 N 轮内亡率」(771014 型)不在本载体:策略层结构性不可见 hp0
    (结算 drain 跳过 hp_after=0 帧 + hp0 即局终),归档案层离线派生,
    申报义务在案(helper docstring 与交付报告承载)。

    三条观测键(形态⑥ terminal_targetless_idle / 锁开率分子分母 /
    boss 濒死死区)参数化并一:只计数零行为,逐键独立会话。"""

    _OBS_CASES = ('terminal-targetless-idle', 'lock-open-rate',
                  'boss-deadzone')

    def _sess(self) -> SimpleNamespace:
        from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
        _s = SimpleNamespace(cw4_counters={})
        game_state_of(_s).node_books.plane_node_table = [1] * 7   # 终态契约 §A′
        return _s

    def _flow(self):
        from sr_od.application.currency_war.strategies.impl.flow import (
            CwFlowStrategy,
        )
        # abstract 桩子类(CwFlowStrategy 的 decide_prep_screen 为 abstract;
        # 本组只驱动方向节拍 _refresh_direction,备战主流程不触达)
        class _Flow(CwFlowStrategy):
            def decide_prep_screen(self, *a, **kw):
                raise NotImplementedError

        from types import SimpleNamespace as _NS
        return _Flow(object(), _NS(strategy_seed=None))   # 终态契约:构造注入

    @pytest.mark.parametrize('obs_case', _OBS_CASES)
    def test_observation_key_count_only(self, obs_case, monkeypatch):
        _OBS_KEY_CASES[obs_case](self, monkeypatch)

    def _case_terminal_targetless_idle(self, monkeypatch):
        """形态⑥观测键(241 §5.1 键名,不分位面):target 空窗 ∧ 濒死带
        ∧ 域外 ∧ 持金 ∧ 本帧零金消费 ⇒ terminal_targetless_idle 计 1;
        域外帧(g>g* 且必花域判定真)与非濒死帧(hp=60)零显影。纯观测:
        计数不改发射序列。
        (九段工序重排对账:观测载体辖域 = 到达第 7 步之后的帧——帧构造
        需打 shop_handled 标记〔商店会话已处理〕,否则第 4 步开店命中
        提前返回不入键;monkeypatch run_mandate 桩随 emit 不再调用骨架
        pass 自然失效,保留无害。)"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            ChannelSig,
            game_state_of,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            session_scope as _ss,
        )

        def _mk_frame(gold: int, hp: int) -> dict:
            # 容器化段 2:局内事实喂 session 容器(观察源契约),黑板帧
            # 只载视觉/占用域。
            return {'gold': gold, 'level': 6, 'round_num': 2, 'hp': hp,
                    'plane': 2, 'node': '战斗'}

        def _mk_sess(st: dict) -> SimpleNamespace:
            _sess = SimpleNamespace(cw4_counters={},
                                    v3_intention=IntentionState())
            _gs = cw4_gs(_sess, **st)
            # 生效序位写端(node_pos;标记判定 = effective_node_pos 读口,
            # 未观察 None 不当真)+ 商店会话标记(第 4 步跳过 → 帧到达
            # 第 7/8 步,观测辖域内)。
            _gs.observe(_gs.node_pos, (int(st['plane']), int(st['round_num'])),
                        sig=ChannelSig(family='obs', actor='cw4_seed',
                                       mode='synthesized'))
            _ss.mark_shop_handled(game_state_of(_sess))
            return _sess

        sess = _mk_sess(_mk_frame(40, 10))
        out = entry.emit(sess, None)
        assert state_of(sess).cw4_counters.get('terminal_targetless_idle') == 1
        assert not any(isinstance(e.action, mandate.CwActionLevelUpParam) for e in out), (
            '观测零行为:形态⑥帧发射序列不变(无动作 ⇒ 出战路径)')
        # 域外对照:同帧 g>g* ⇒ 不计
        sess_z = _mk_sess(_mk_frame(80, 10))
        entry.emit(sess_z, None)
        assert 'terminal_targetless_idle' not in state_of(sess_z).cw4_counters
        # 负对照:非濒死帧(hp=60)不计(键只辖濒死带形态,与既有
        # advisor 计数面零交集)
        sess_h = _mk_sess(_mk_frame(40, 60))
        entry.emit(sess_h, None)
        assert 'terminal_targetless_idle' not in state_of(sess_h).cw4_counters

    def _case_lock_open_rate(self, monkeypatch):
        """低血带新开 lock 开启率载体(wiring 锁:经 _refresh_direction
        生产驱动面触发):分母 = 锁开事件总数,分子 = λ 低血带帧锁开
        (带判定 = 血带结构锚单一源,统一设计稿 §5-F4);率由读端按两键
        比值派生,禁写进计数(只记不判)。非低血带帧只进分母;分母只辖
        锁开事件——保持锁帧零重复计数(率读数不被保持帧稀释)。
        (终态契约 §2.5 impl 桶:_refresh_direction 状态宿主 = 显式
        _ms 形参。帧种上阵核心件 = 移交候选可达前置:total_remaining_
        nodes 场字段修正(P2 视界封顶 modeled planes)后遭遇窗门按真值
        判可达,空手帧核心全部不可达 = 候选空帧;核心在显即可达,
        与视界无关。"""
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        monkeypatch.setattr(ci, 'detect_signals', lambda s: [])
        monkeypatch.setattr(ci, 'line_completion_feasibility',
                            lambda *a, **k: 0.5)   # 移交候选可行 → 帧即锁
        strategy = self._flow()
        sess_lo = self._sess()
        ms_lo = state_of(sess_lo)
        ms_lo.cw4_counters = {}
        strategy._refresh_direction(
            _bsb(front_row=[Unit(char_id='姬子·启行', star=1)],
                 **_st2(hp=10, gold=0)), ms_lo)
        ct_lo = ms_lo.cw4_counters
        assert ct_lo.get('lock_gen_feasibility_obs_lock_open_total') == 1
        assert ct_lo.get('lock_gen_feasibility_obs_lock_open_lowband') == 1
        sess_hi = self._sess()
        ms_hi = state_of(sess_hi)
        ms_hi.cw4_counters = {}
        strategy._refresh_direction(
            _bsb(front_row=[Unit(char_id='姬子·启行', star=1)],
                 **_st2(hp=40, gold=0)), ms_hi)
        ct_hi = ms_hi.cw4_counters
        assert ct_hi.get('lock_gen_feasibility_obs_lock_open_total') == 1
        assert 'lock_gen_feasibility_obs_lock_open_lowband' not in ct_hi
        # 保持锁帧(帧2同 session,已锁不转移)不分母重复计
        strategy._refresh_direction(
            _bsb(**_st2(hp=40, gold=0, round_num=2)), ms_hi)
        assert ct_hi.get('lock_gen_feasibility_obs_lock_open_total') == 1, (
            '帧2保持锁非锁开事件,分母不重复计')

    def _case_boss_deadzone(self, monkeypatch):
        """死区面计数(R1 存疑-1 兑付:boss 窗濒死帧恒闭死区不留白):
        boss 节点 ∧ 濒死带域内帧按授权域分列(_p1/_p2);域外帧不入键。
        直调 helper(帧级观测,不依赖锁开;终态契约 §2.5:计数宿主 =
        显式 _ms 形参)。"""
        from sr_od.application.currency_war.strategies.impl.flow import (
            bump_lock_gen_feasibility_obs,
        )
        sess = self._sess()
        ms = state_of(sess)
        ms.cw4_counters = {}
        # node 单一源 = gs(终态契约 §A′):'boss' 经帧喂入 gs.node,不再挂 session
        bump_lock_gen_feasibility_obs(ms, _bsb(**_st2(hp=10, gold=0,
                                                    node_type='boss')),
                                      IntentionState(), 'lock:旧事件')
        assert ms.cw4_counters.get(
            'lock_gen_feasibility_obs_boss_neardeath_p2') == 1
        assert 'lock_gen_feasibility_obs_lock_open_total' \
            not in ms.cw4_counters, '无锁开转移 ⇒ 分母不计'
        # 域外对照(hp=40):零计数
        sess2 = self._sess()
        ms2 = state_of(sess2)
        ms2.cw4_counters = {}
        bump_lock_gen_feasibility_obs(ms2, _bsb(**_st2(hp=40, gold=0,
                                                     node_type='boss')),
                                      IntentionState(), 'lock:旧事件')
        assert 'lock_gen_feasibility_obs_boss_neardeath_p2' \
            not in ms2.cw4_counters


_OBS_KEY_CASES = {
    'terminal-targetless-idle': (
        TestLockGenObservationKeys._case_terminal_targetless_idle),
    'lock-open-rate': TestLockGenObservationKeys._case_lock_open_rate,
    'boss-deadzone': TestLockGenObservationKeys._case_boss_deadzone,
}
