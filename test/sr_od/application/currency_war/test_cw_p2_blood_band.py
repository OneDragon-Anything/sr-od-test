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

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _bsb,
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
