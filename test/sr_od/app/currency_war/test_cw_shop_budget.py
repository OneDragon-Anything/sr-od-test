"""CW 商店/备战预算闸测试(#9):spend_unified 锁 + P72 全段预算闸代表
(上位 = P71-b 溢余段闸 ADR-0560;证明 =
docs/develop/currency_war/proofs/p72-full-band-budget-gate.md,ADR-0576)。

覆盖面:
- spend_unified 直测(D-BUYNOTE 整买纪律三分支:散买拦截/整批放行/
  零剩余 click 守卫;原 test_cw_shop_line::test_d_buynote_embedded 承载,
  must_spend_zone 侧等价锁删后全仓唯一载体,D7 消费);
- 闸判据纯函数分支代表:73002 深穿拒(P71-b 同判承继)/ T-93 中段
  真洞拒(旧 P71-b vacuous 空过的事故本体)/ 开局追级畅通(防恒拒)/
  分量单一源对拍(τ=kernel interest + ρ 同参 + 贴线一对);
- ρ 公共源零漂移(shop._r2_card_reserve 别名 = criteria 单一源委托,
  P71-b 批承继);
- ALL IN 豁免支(位面末 boss 豁免、同帧非 boss 不豁免;T-149/ADR-0603
  重推定稿);
- prep 位整批推迟(闸拒即整批不出,spend_unified 已保整批)+ 契约锚
  文本登记门(p72 锚漂移红)。

来源:shop_line 之 spend_unified 段 + budget_gate 核(2026-09-09 套件
重建批 A,#9;两来源文件已分别按 #8/#5 重建退役)。其余历史锁已退役
(git 可复活)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_prep_actions import LevelUp
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
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.interest import (
    saturation_line,
)
from test.sr_od.app.currency_war._cw_helpers import (
    battle_state as _state,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_comp as _comp_single_source,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_km as _km_of,
)
from test.sr_od.app.currency_war._cw_helpers import (
    ns_session as _ns_session,
)

_COMP = '列车同行'


def _comp():
    """本文件锚定具名套(``列车同行``;血线族共用锚)。"""
    return _comp_single_source(_COMP)


def _km() -> list[str]:
    return _km_of(_comp())


def _sess():
    return _ns_session(_comp())


# ==================== spend_unified 锁(自 test_cw_shop_line 段并入) ====================


def test_spend_unified_whole_batch_discipline():
    """D-BUYNOTE:P48 整买纪律作为常量判据内嵌(spend_unified 直测;
    must_spend_zone 侧等价锁删后本文件为全仓唯一载体,D7 消费)。
    三分支:散买拦截/整批放行/零剩余 click 守卫(clicks_to_next≤0
    ⇒ False,防 0×cost=0 恒过把「无级可升」当「可整批支付」)。"""
    assert not crit_levelup.spend_unified(2, 4, 4)   # 散买拦截
    assert crit_levelup.spend_unified(2, 8, 4)       # 整批放行
    assert not crit_levelup.spend_unified(0, 8, 4)   # 零剩余 click 守卫


# ==================== 闸判据纯函数代表行(自 test_cw_budget_gate 并入) ====================


class TestGatePure:
    """闸判据纯函数(P72 (3a) 全段式;判据单一源对拍)。本文件保留四
    分支代表(深穿拒/中段真洞拒/开局畅通/分量单一源);富金放行与
    零批恒可行两行退役 git 可复活。"""

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


class TestRhoPublicSource:
    """ρ 公共源零漂移(P71-b 批承继;r2 测试既有 4 键不改断言的同源
    证据 = test_cw_economy.py R2 息线 floor 直跑,本类锁别名/注册面)。"""

    def test_shop_alias_same_value_as_single_source(self):
        """shop._r2_card_reserve 接线烟雾(README 第 8 条容忍档):
        别名 = 单一源 criteria/refresh.r2_card_reserve 的重导出委托
        (生产别名保留使息线 floor 私名直引与调用点零漂移)。对比帧扫
        (2★ 出集经 bench/deployed 两路 + level 显式传参)防委托走样成
        第二实现——单点同值对包装漂移零判别力。ρ 值语义(注册表派生/
        过滤面)由 test_cw_economy 的 floor 组合同一别名辖,此处不重复
        锁值。"""
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
        (criteria 全公开函数注册完备性)由 test_cw_contracts
        .test_covers_all_criteria_public_functions 辖(各守边界成立),
        此处缺键经 KeyError 自然红,不重复断言。"""
        anchor = contracts.CONTRACTS[
            ('levelup', 'levelup_budget_gate')].anchor
        assert 'p72-full-band-budget-gate' in anchor
        assert 'ADR-0576' in anchor


class TestAllInExempt:
    """ALL IN 豁免支(P72 §2.5 交互;plane_last_battle 单一源)。

    锁重推记录(T-149,ADR-0603):位面末 boss 帧从「花光」改「花至
    1 息档」(域③ P83 全局轴);终局域(末位面末战)维持花光原语义;
    花后 <10 的推迟行为锁在 test_cw_guarantee_floor.py。
    """

    def test_plane_last_boss_exempt(self):
        """P2 r7 boss 位面末战:豁免支维持(花后 15 ≥ 1 息档 ⇒ 放行);
        同参非 boss 帧不豁免——豁免谓词同帧判定,禁把豁免读成常开。
        旧断言场景(g=45 批 40 花后 5)在保底门下改判推迟,见
        test_cw_guarantee_floor.TestGuaranteeFloorExemptionBranches。"""
        km = tuple(_km())
        st_boss = _state(55, 7, xp=(48, 52))
        st_boss.plane = 2
        st_boss.node_type = 'boss'
        st_boss.round_num = 7
        sess_p2 = SimpleNamespace(plane_node_table=list(range(7)))
        ok, why = crit_levelup.levelup_budget_gate(
            st_boss, sess_p2, 55, 5, km, [], [], 10, 4)
        assert ok is True and why == ''
        # 同帧非 boss:量闸照判(45−40=5 < 40+2ρ)
        st_norm = _state(45, 7, xp=(48, 52))
        ok2, why2 = crit_levelup.levelup_budget_gate(
            st_norm, sess_p2, 45, 5, km, [], [], 10, 4)
        assert ok2 is False and why2 == 'levelup_budget_gate_blocked'


class TestPrepDefer:
    """prep 位:发射前过闸,拒 = 整批推迟(禁部分买)。本文件保留域内
    闸拒行(与 spend_unified 整批语义同面);prep→shop 链路行退役
    git 可复活。"""

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
