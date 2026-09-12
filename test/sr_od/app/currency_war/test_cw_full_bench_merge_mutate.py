"""T-182 满栏合成买双账同构锁(2026-09-09 05:52 运行局双响事故回归)。

事故形态(证据 = ADR-0617 §根因证据链;原始日志链 = .log/mcp_server.log
05:52:01/05:52:25 两 Traceback + op_journal gold/bench_used 回执行):bench 满栏(9/9,含同名同星副本对
——T-59 同名同星可同场,建模须兼容)下,m2 合成完成买(own=2 = bench
素材 + 场上素材)经 merge_mechanics §2.5 满栏例外自动合成:游戏真实
行为 = 接受买入(金照扣)、消费 bench 素材(槽位腾出)、场上载体升星。
投影侧(``simulate``)正确建模了这一切;旧 tracked ``mutate_bench_
deployed`` 满栏丢件 → 只见 2 份不合成 → 槽位不动 → 两账结构性分叉。
守卫的满栏豁免按投影侧占用数判定,同 visit 下一动作(投影侧已腾槽、
占用 8 < 9)逃出豁免,对拍两本已分叉的账 → AssertionError 误炸
(expected=阿格莱雅@slot1 / 三月七@slot2,tracked=陈旧素材名)。

修复:``mutate_bench_deployed`` 带 shop 视图,满栏合成买与 ``simulate``
共用 ``_apply_full_bench_merge_buy`` 单一源(分支同构 = 写端治本)。

锁面(六件):
- 事故帧重放 ×2(05:52:01 椒丘帧 / 05:52:25 丹恒·饮月帧,载荷取自
  守卫 Traceback 原文 + journal gold/bench_used)——两动作序列后双账
  签名逐槽一致 + 守卫静默(不炸也不降级告警);
- 变异自检:本地复刻旧丢件增量,断言①事故世界守卫必炸(场景有牙,
  旧形态可复现事故)②生产 mutate 结果与旧形态不同(修复被回退时本
  断言变红);
- k=2 自动多买(own=1 + 店内 2 张)双账同构;
- 非合成满栏买(merge_buy_completes=False)零漂移:tracked 维持拒收
  不动、simulate no-op、两账一致(ADR-0283 拒买语义);
- own=0 门(T-184,ADR-0619):own=0 + 店内同名同星 3 张的
  满栏帧,合成买不成立(merge_buy_completes own≥1 门,语义锚 =
  merge_mechanics §2.5 例外以已有素材/载体在场为前提)→ 按满栏非
  合成买拒收:金不扣、店侧 3 张不下架、双账零漂移一致(摘门变异
  红点 = 金被扣 k×单价 + 店侧被下架,旧形态合成载体被截删凭空消失);
- shop=None 兼容面:旧调用形态零漂移(满栏丢件维持,无 shop 视图的
  调用方行为不变)。
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    CwWorkFrame,
    ShopCard,
    _card_to_bench,
    _merge_bench,
    bench_place,
    mutate_bench_deployed,
    pad_bench,
    pad_deployed,
    simulate,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)

# ===== 事故帧载荷(取自 2026-09-09 05:52 运行局,禁改动语义)=====

#: 05:51:51 起各入口 seed 一致的 bench 真值(绯英×2/花火×2 副本同场 = T-59)
BENCH_INCIDENT_NAMES = ['椒丘', '丹恒·饮月', '花火', '艾丝妲', '绯英',
                        '阮·梅', '绯英', '花火', '希儿']


def _sig(bench) -> list[tuple[str, int]]:
    """守卫同口径占用签名(逐槽 (char_id, star);None 跳过)。"""
    return [(b.char_id, b.star or 1) for b in (bench or []) if b is not None]


def _seed_bench() -> list[BenchChar | None]:
    """事故 bench(槽 1-9 全占,全 1★)。"""
    return [BenchChar(slot=i + 1, char_id=n, star=1)
            for i, n in enumerate(BENCH_INCIDENT_NAMES)]


def _session(bench=None, deployed=None) -> StrategySession:
    sess = StrategySession()
    exec_state_of(sess).tracked_bench_chars = (
        bench if bench is not None else _seed_bench())
    exec_state_of(sess).tracked_deployed = (
        deployed if deployed is not None else [])
    return sess


def _state(gold: int, shop: list[ShopCard],
           deployed: list[BenchChar]) -> CwWorkFrame:
    st = CwWorkFrame(gold=gold, level=5, round_num=9, hp=35)
    st.shop = shop
    st.bench = _seed_bench()
    st.deployed = deployed
    return st


def _legacy_drop_mutate(bench, deployed, action) -> None:
    """事故形态旧增量复刻(满栏丢件+无合成分支)。

    用途有二:①证明本测试场景对旧形态有牙(守卫必炸 = 事故可复现);
    ②与生产 mutate 对拍——修复被回退(生产行为重合本复刻)时,
    「生产 ≠ 旧形态」断言变红。"""
    pad_bench(bench)
    pad_deployed(deployed)
    bench_place(bench, _card_to_bench(action.card))
    _merge_bench(bench, deployed)


# ===== 事故帧重放(修复后守卫必须静默)=====

class TestIncidentFrameReplay:

    #: 双响两帧参数(载荷取自守卫 Traceback 原文 + op_journal gold/bench_used
    #: 回执行,禁改动语义):同形体帧合并为参数化(判定分支相同,差异全在
    #: 数据面——合成卡 cost 1/2、腾出槽位、journal 金锚)。
    _FRAMES = [
        pytest.param(
            '椒丘',
            ShopCard(x=1007, name='椒丘', faction='狼狩', cost=1, star=1),
            ShopCard(x=501, name='阿格莱雅', faction='昼之半神', cost=1, star=1),
            61, 60,
            [('阿格莱雅', 1), ('丹恒·饮月', 1), ('花火', 1), ('艾丝妲', 1),
             ('绯英', 1), ('阮·梅', 1), ('绯英', 1), ('花火', 1), ('希儿', 1)],
            id='055201_jiaochiu_merge_buy_then_aglaea'),
        pytest.param(
            '丹恒·饮月',
            ShopCard(x=754, name='丹恒·饮月', faction='仙舟', cost=2, star=1),
            ShopCard(x=1514, name='三月七', faction='列车同行', cost=1, star=1),
            51, 49,
            [('椒丘', 1), ('三月七', 1), ('花火', 1), ('艾丝妲', 1),
             ('绯英', 1), ('阮·梅', 1), ('绯英', 1), ('花火', 1), ('希儿', 1)],
            id='055225_danhen_merge_buy_then_march7th'),
    ]

    @pytest.mark.parametrize(
        'deployed_char, merge_card, second_card, gold_before, '
        'gold_after_first, expected_final', _FRAMES)
    def test_incident_frame_dual_ledger_isomorphic_and_guard_silent(
            self, monkeypatch, deployed_char, merge_card, second_card,
            gold_before, gold_after_first, expected_final):
        """事故帧重放:满栏 9/9 + 场上<deployed_char>@1,买同名@1(合成,
        k=1)→ 买第二张(落腾出槽)。修复后:两动作后双账签名逐槽一致、
        场上载体 2★(投影与 tracked 两侧)、守卫静默(不炸/无降级告警
        ——事故现场 = 修复前守卫点 AssertionError 误炸)。"""
        from sr_od.application.currency_war.operations.cw_op import (
            cw_shop_action_ops,
        )
        warnings: list[tuple] = []
        monkeypatch.setattr(
            cw_shop_action_ops, 'log',
            type('W', (), {'warning': staticmethod(
                lambda *a, **k: warnings.append(a))})())
        deployed = [BenchChar(slot=1, char_id=deployed_char, star=1,
                              position_pref='front')]
        sess = _session(deployed=deepcopy(deployed))
        # 生产同构:mutate 直接作用于 session 台账列表(guard 读同一列表)
        tracked = exec_state_of(sess).tracked_bench_chars
        tracked_deployed = exec_state_of(sess).tracked_deployed
        st = _state(gold=gold_before, shop=[second_card, merge_card],
                    deployed=deepcopy(deployed))
        act1 = BuyCard(card=deepcopy(merge_card))
        proj1 = simulate(st, act1)
        mutate_bench_deployed(tracked, tracked_deployed, act1, shop=st.shop)
        # 动作1 后:素材槽腾出,场上载体升 2★,双账一致
        after_merge = [e for e in expected_final
                       if e != (second_card.name, 1)]
        assert _sig(proj1.bench) == after_merge, _sig(proj1.bench)
        assert _sig(tracked) == after_merge, _sig(tracked)
        assert proj1.gold == gold_after_first   # journal 回执:bench_used=8
        assert any(d.char_id == deployed_char and d.star == 2
                   for d in proj1.deployed if d is not None)
        assert any(d.char_id == deployed_char and d.star == 2
                   for d in tracked_deployed if d is not None)
        # 动作2:第二张落腾出槽(两侧首个空位规则同位)
        act2 = BuyCard(card=deepcopy(second_card))
        proj2 = simulate(proj1, act2)
        mutate_bench_deployed(tracked, tracked_deployed, act2,
                              shop=proj1.shop)
        assert _sig(proj2.bench) == expected_final, _sig(proj2.bench)
        assert _sig(tracked) == expected_final, _sig(tracked)
        # 事故守卫点:修复前此处 AssertionError(误炸);修复后静默
        cw_shop_action_ops.guard_expected_vs_tracked(proj2, sess)
        assert warnings == [], warnings


# ===== 变异自检(旧形态可复现事故 + 修复在位证明)=====

class TestMutationSelfCheck:

    def _run_legacy_world(self, sess, st, acts):
        """旧丢件增量跑同一动作序列,返回 (legacy_tracked, 末帧投影)。"""
        tracked = deepcopy(exec_state_of(sess).tracked_bench_chars)
        tracked_deployed = deepcopy(exec_state_of(sess).tracked_deployed)
        proj = st
        for act in acts:
            proj = simulate(proj, act)
            _legacy_drop_mutate(tracked, tracked_deployed, act)
        return tracked, tracked_deployed, proj

    def test_legacy_shape_reproduces_incident_and_fix_differs(self):
        """变异自检双断言:①旧形态世界 = 事故复现(守卫必炸「双账分离」
        ——场景有牙,锁不是恒绿);②生产 mutate 与旧形态结果不同
        (修复被回退 → 生产行为重合旧形态 → 本断言变红)。"""
        from sr_od.application.currency_war.operations.cw_op import (
            cw_shop_action_ops,
        )
        deployed = [BenchChar(slot=1, char_id='椒丘', star=1,
                              position_pref='front')]
        sess = _session(deployed=deepcopy(deployed))
        st = _state(gold=61,
                    shop=[ShopCard(x=501, name='阿格莱雅', faction='昼之半神',
                                   cost=1, star=1),
                          ShopCard(x=1007, name='椒丘', faction='狼狩',
                                   cost=1, star=1)],
                    deployed=deepcopy(deployed))
        acts = [BuyCard(card=ShopCard(x=1007, name='椒丘', faction='狼狩',
                                      cost=1, star=1)),
                BuyCard(card=ShopCard(x=501, name='阿格莱雅',
                                      faction='昼之半神', cost=1, star=1))]
        legacy_tracked, _legacy_dep, proj = self._run_legacy_world(
            sess, st, acts)
        # ①旧形态 = 事故复现:tracked 漏记合成(椒丘@1 仍在槽1、无阿格莱雅)
        assert ('椒丘', 1) in _sig(legacy_tracked)
        assert not any(c.char_id == '阿格莱雅'
                       for c in legacy_tracked if c is not None)
        with pytest.raises(AssertionError, match='双账分离'):
            cw_shop_action_ops.guard_expected_vs_tracked(proj, sess)
        # ②生产(修复后)与旧形态分道:同序列逐步跑生产 mutate
        #(动作1 用动作前店面 st.shop,动作2 用动作1 投影后的店面)
        fixed_tracked = deepcopy(exec_state_of(sess).tracked_bench_chars)
        fixed_deployed = deepcopy(exec_state_of(sess).tracked_deployed)
        proj1 = simulate(st, acts[0])
        mutate_bench_deployed(fixed_tracked, fixed_deployed, acts[0],
                              shop=st.shop)
        mutate_bench_deployed(fixed_tracked, fixed_deployed, acts[1],
                              shop=proj1.shop)
        assert _sig(fixed_tracked) != _sig(legacy_tracked)
        assert fixed_tracked[0] is not None \
            and fixed_tracked[0].char_id == '阿格莱雅'


# ===== 分支面锁(k=2 多买 / 非合成拒买零漂移 / shop=None 兼容)=====

class TestBranchFaces:

    @staticmethod
    def _flat_full_bench(name_at_merge: str) -> list[BenchChar | None]:
        """满栏 bench:9 个互异名(name_at_merge 占槽1,其余填充)。"""
        names = [name_at_merge] + [f'填充{i}' for i in range(8)]
        return [BenchChar(slot=i + 1, char_id=n, star=1)
                for i, n in enumerate(names)]

    def test_k2_auto_multibuy_both_ledgers_isomorphic(self):
        """k=2 自动多买(own=1 + 店内 2 张同名@1):一次点击买 2 张,
        own+k=3 触发合成。两账同走分支 → 签名一致、载体 2★ 落原槽。"""
        deployed: list[BenchChar] = []
        sess = _session(bench=self._flat_full_bench('椒丘'),
                        deployed=deepcopy(deployed))
        tracked = deepcopy(exec_state_of(sess).tracked_bench_chars)
        st = CwWorkFrame(gold=30, level=5, round_num=9, hp=35)
        st.shop = [ShopCard(x=1, name='椒丘', cost=1, star=1),
                   ShopCard(x=2, name='椒丘', cost=1, star=1)]
        st.bench = self._flat_full_bench('椒丘')
        st.deployed = []
        act = BuyCard(card=ShopCard(x=1, name='椒丘', cost=1, star=1))
        proj = simulate(st, act)
        mutate_bench_deployed(tracked,
                              exec_state_of(sess).tracked_deployed,
                              act, shop=st.shop)
        assert proj.gold == 28   # k=2,单价 1
        assert _sig(proj.bench) == _sig(tracked)
        assert sum(1 for b in proj.bench if b is not None) == BENCH_CAPACITY
        assert any(b.char_id == '椒丘' and b.star == 2
                   for b in proj.bench if b is not None)
        assert any(b.char_id == '椒丘' and b.star == 2
                   for b in tracked if b is not None)

    def test_non_merge_full_bench_buy_rejected_zero_drift(self):
        """非合成满栏买(own=0,不满足 merge_buy_completes)零漂移:
        simulate no-op(不扣金)、tracked 拒收不动,两账一致
        (ADR-0283 拒买语义;游戏侧该点击被拒,像素差检出为执行层面)。"""
        deployed: list[BenchChar] = []
        sess = _session(bench=self._flat_full_bench('甲'),
                        deployed=deepcopy(deployed))
        tracked = deepcopy(exec_state_of(sess).tracked_bench_chars)
        st = CwWorkFrame(gold=30, level=5, round_num=9, hp=35)
        st.shop = [ShopCard(x=1, name='乙', cost=1, star=1)]
        st.bench = self._flat_full_bench('甲')
        st.deployed = []
        act = BuyCard(card=ShopCard(x=1, name='乙', cost=1, star=1))
        before_sig = _sig(st.bench)
        proj = simulate(st, act)
        mutate_bench_deployed(tracked,
                              exec_state_of(sess).tracked_deployed,
                              act, shop=st.shop)
        assert proj.gold == 30   # 拒买不扣金
        assert _sig(proj.bench) == before_sig
        assert _sig(tracked) == before_sig   # 丢件 = 拒收(与游戏拒绝一致)

    def test_own0_shop3_full_bench_buy_rejected_gold_unchanged(self):
        """own=0 + 店内同名同星 3 张满栏帧:合成买不成立(own≥1 门,
        T-184,ADR-0619)→ 按满栏非合成买拒收——金不扣、店侧 3 张不下架、
        双账零漂移一致。摘门变异时本锁红:金被扣 3×单价(30→27)、
        店侧 3 张被下架(旧形态 k=3 全为尾挂张,合成载体落 idx9 被
        ``del bench[9:]`` 截删,买下的 2★ 凭空消失)。"""
        deployed: list[BenchChar] = []
        sess = _session(bench=self._flat_full_bench('甲'),
                        deployed=deepcopy(deployed))
        tracked = deepcopy(exec_state_of(sess).tracked_bench_chars)
        st = CwWorkFrame(gold=30, level=5, round_num=9, hp=35)
        st.shop = [ShopCard(x=1, name='丙', cost=1, star=1),
                   ShopCard(x=2, name='丙', cost=1, star=1),
                   ShopCard(x=3, name='丙', cost=1, star=1)]
        st.bench = self._flat_full_bench('甲')
        st.deployed = []
        act = BuyCard(card=ShopCard(x=1, name='丙', cost=1, star=1))
        before_sig = _sig(st.bench)
        proj = simulate(st, act)
        mutate_bench_deployed(tracked,
                              exec_state_of(sess).tracked_deployed,
                              act, shop=st.shop)
        assert proj.gold == 30   # 拒买不扣金(摘门变异红点:30→27)
        assert _sig(proj.bench) == before_sig   # 账面无截删凭空消失
        assert _sig(tracked) == before_sig   # tracked 拒收不动
        assert sum(1 for c in proj.shop
                   if c.name == '丙') == 3   # 拒买店侧不下架(变异红点:0)
        assert _sig(proj.bench) == _sig(tracked)   # 双账一致

    def test_shop_none_keeps_legacy_drop_face(self):
        """shop=None 兼容面锁:无店面语境的既有调用方(部署/备战域)
        满栏时维持旧丢件行为——签名不变、不触发合成分支(零漂移)。"""
        sess = _session(bench=self._flat_full_bench('椒丘'))
        deployed = [BenchChar(slot=1, char_id='椒丘', star=1,
                              position_pref='front')]
        exec_state_of(sess).tracked_deployed = deepcopy(deployed)
        tracked = deepcopy(exec_state_of(sess).tracked_bench_chars)
        before_sig = _sig(tracked)
        act = BuyCard(card=ShopCard(x=1, name='椒丘', cost=1, star=1))
        mutate_bench_deployed(tracked,
                              exec_state_of(sess).tracked_deployed, act)
        assert _sig(tracked) == before_sig, \
            'shop=None 时满栏买必须维持旧丢件行为(零漂移兼容面)'
