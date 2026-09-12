"""T-131 投资环境迭代 3.6 品质改写型结构与分派 · 预注册单帧锁(Q1-Q6)。

锁面出处 = docs/develop/sr_od/application/currency_war/changes/2026-09-12-invest-env/
landing.md §3.6 + details/env-value-models.md §2.2(§2.2.1 语义盘点/§2.2.2 两层
拆分/§2.2.3 难度腿辖域/§2.2.4 数量通道/§2.2.5 结构与落码面/§2.2.6 Q 组锁表)。

机器单一源:
- 结构 = ``cw_investments.ENV_POOL_REWRITE``(恰 7 条白名单,构建闸
  _validate_env_pool_rewrite:孤儿键/三表互斥收全/结构完备/pending 必填);
- 层 E = ``cw_env_economy.env_economy_value`` 单一入口分派 →
  _pool_rewrite_value(ΔV 公式,读 STRAT_POOL_ECON_MEANS/OFFER_QUALITY_DIST/
  _STRAT_PICK_HORIZONS,任一缺参 fail-closed,v1 恒然——受限通道 μ_E 非单调
  (银>金实测),转正须过准入门,详设 §2.2.2 裁决);
- 层 Q = 环境裸分维持(ENV_PICK_VALUE 零改动),两层从不相加。

fixture 直调核验(模块导入即验;注册表漂移先红于此,漂移 = 修库后重核咬合面,
不是改断言保绿):7 条环境 plaza id/裸分/faction/无经济通道(design §2.2.6 Q1
行括号值 + §2.2.1 表 id 对账)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel import cw_env_economy as eco
from sr_od.application.currency_war.kernel import cw_investments as inv
from sr_od.application.currency_war.kernel.cw_env_economy import (
    EconomyEstimate,
    env_economy_value,
)
from sr_od.application.currency_war.kernel.cw_events import decide_event
from sr_od.application.currency_war.kernel.cw_game_state import (
    GameState,
    board_state_bridge,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_ECONOMY,
    ENV_GIFTS,
    ENV_PICK_VALUE,
    ENV_POOL_REWRITE,
    get_env,
)
from sr_od.application.currency_war.kernel.cw_vocab import CwWorkFrame, PickEvent

# ===== fixture 前提直调核验(锁语义依赖的注册表事实;漂移先红于此)=====

#: 7 条品质改写环境(名, plaza id, 裸分)——§2.2.1 表 id 对账 + §2.2.2 层 Q
#: 裸分括号值(ENV_PICK_VALUE 零改动前提的直调锚)
_POOL_FIXTURE: tuple[tuple[str, int, int], ...] = (
    ('彩虹时代', 110, 72), ('黄金时代', 111, 55), ('白银时代', 112, 35),
    ('头彩', 123, 55), ('尾彩', 124, 52), ('银·金·彩', 135, 62),
    ('联席决策', 122, 50),
)

assert {n for n, _id, _pv in _POOL_FIXTURE} == set(ENV_POOL_REWRITE), (
    f'品质改写白名单漂移(§2.2.1 恰 7 条),实得 {sorted(ENV_POOL_REWRITE)}')
for _n, _id, _pv in _POOL_FIXTURE:
    _e = get_env(_n)
    assert _e is not None and _e.source == f'plaza:{_id}', (
        f'{_n} plaza id 漂移:期望 plaza:{_id},实得 {_e.source if _e else None}')
    assert _e.pick_value == _pv == ENV_PICK_VALUE.get(_n), (
        f'{_n} 裸分漂移(层 Q = 裸分维持,禁动 ENV_PICK_VALUE):期望 {_pv}')
    assert _e.faction == '' and _e.economy is None, (
        f'{_n} 应为 faction 空且无经济通道的阵容无关型,实得 {_e!r}')


def _est(value: float, lo: float, hi: float) -> EconomyEstimate:
    """注入用估算参数(CI = [lo, hi];source/cutoff 为测试申报占位)。"""
    return EconomyEstimate(value=value, ci=(lo, hi),
                           source='test-inject', cutoff='1970-01-01')


def _bs() -> GameState:
    """开局裸桩帧(node 缺读 = 局首语义;层 E v1 用全局先验视界,帧无关)。"""
    return GameState(schema_version=1)


def _cfg(**overrides) -> SimpleNamespace:
    base: dict = {'strategy_priority': [], 'strategy_forbid': []}
    base.update(overrides)
    return SimpleNamespace(**base)


_STATE = CwWorkFrame(board={}, hp=100, hp_readable=True)


def _pick(options: list[str], cfg=None, **kw) -> PickEvent:
    """kernel 纯函数直调(空板帧:无 D* 信号/无 DoT 惩罚;容器桥沿 universe 先例)。"""
    return decide_event(options, cfg if cfg is not None else _cfg(),
                        board_state_bridge(_STATE), **kw)


# ===== Q1 结构表(§2.2.6 行 1;§2.2.1/§2.2.5)=====


def test_q1_registry_structure() -> None:
    """Q1:恰 7 条 + 逐条字段 = §2.2.1 改写事实直读;pending 歧义三条 notes
    必填。红 = 效果原文变(实采定谳)或登记错装,对账源 = plaza id。"""
    assert set(ENV_POOL_REWRITE) == {
        '彩虹时代', '黄金时代', '白银时代', '头彩', '尾彩', '银·金·彩', '联席决策'}
    _r = ENV_POOL_REWRITE
    # 时代 ×3:全改写型(quality + picks=(1,2,3));白银带难度腿登记(§2.2.3:
    # 数值在册不折金,字段只如实登记不产生分值)
    assert _r['彩虹时代'].rewrite_quality == '棱彩'
    assert _r['黄金时代'].rewrite_quality == '金'
    assert _r['白银时代'].rewrite_quality == '银'
    for _n in ('彩虹时代', '黄金时代', '白银时代'):
        assert _r[_n].rewrite_picks == (1, 2, 3), f'{_n} 全改写 picks'
        assert not _r[_n].offer_structure and _r[_n].extra_pick_refreshes == 0
        assert _r[_n].extra_pick_node_range is None
    assert _r['白银时代'].difficulty_exempt is True
    assert not _r['彩虹时代'].difficulty_exempt and not _r['黄金时代'].difficulty_exempt
    # 单张改写型:头彩=(1,)/尾彩=(3,);效果原文歧义(三卡全改还是仅点名张)
    # 挂账 → pending_notes 必填
    assert _r['头彩'].rewrite_quality == '棱彩' and _r['头彩'].rewrite_picks == (1,)
    assert _r['尾彩'].rewrite_quality == '棱彩' and _r['尾彩'].rewrite_picks == (3,)
    for _n in ('头彩', '尾彩'):
        assert _r[_n].pending_notes, f'{_n} offer 覆盖面歧义须挂账 notes'
    # 银·金·彩:offer 结构改写 + 刷新 +2(数量通道登记,§2.2.4 无消费端)
    assert _r['银·金·彩'].offer_structure == 'silver_gold_prism_slots'
    assert _r['银·金·彩'].extra_pick_refreshes == 2
    assert _r['银·金·彩'].rewrite_quality == '' and _r['银·金·彩'].rewrite_picks == ()
    assert _r['银·金·彩'].pending_notes, '银·金·彩 槽位语义歧义须挂账 notes'
    # 联席决策:数量通道(额外取卡节点范围 (2,6) 全局节点序 1 基含两端)
    assert _r['联席决策'].extra_pick_node_range == (2, 6)
    assert _r['联席决策'].rewrite_quality == '' and _r['联席决策'].extra_pick_refreshes == 0


# ===== Q2 fail-closed(§2.2.6 行 2;§2.2.2 裁决)=====


def test_q2_v1_fail_closed_all_seven() -> None:
    """Q2:v1 恒 (0.0, False)——机制锁(注入空参数表,不依赖注册表现值,层 E
    落参后照常可跑)+ 现值锁(v1 两表空 → 恒然;层 E 转正数据批落参后本断言
    随批重立)。半值禁出:fail-closed 返回点值恒 0.0。"""
    _frame = _bs()
    # 现值:v1 两参数表空 → 7 条恒然
    assert eco.STRAT_POOL_ECON_MEANS == {} and eco.OFFER_QUALITY_DIST == {}, (
        'v1 层 E 参数表应空(落参 = 转正数据批义务);非空 = 转正已发生,'
        '本锁须随批重立')
    for _n in ENV_POOL_REWRITE:
        assert env_economy_value(_n, _frame) == (0.0, False), f'{_n} v1 恒 fail-closed'
    # 机制锁:即使参数表被注入,清空任一表即全量 fail-closed(缺参门)
    monkey_full_means = {('棱彩', 24): _est(10, 9, 11), ('金', 24): _est(6, 5, 7),
                         ('银', 24): _est(4, 3, 5)}
    monkey_full_pi = {1: {'银': _est(0.5, 0.4, 0.6), '金': _est(0.3, 0.2, 0.4),
                          '棱彩': _est(0.2, 0.1, 0.3)}}
    orig_means, orig_pi = eco.STRAT_POOL_ECON_MEANS, eco.OFFER_QUALITY_DIST
    try:
        eco.STRAT_POOL_ECON_MEANS = {}
        eco.OFFER_QUALITY_DIST = dict(monkey_full_pi)
        assert env_economy_value('头彩', _frame) == (0.0, False), 'μ 表缺 → fail-closed'
        eco.STRAT_POOL_ECON_MEANS = dict(monkey_full_means)
        eco.OFFER_QUALITY_DIST = {}
        assert env_economy_value('头彩', _frame) == (0.0, False), 'π 表缺 → fail-closed'
    finally:
        eco.STRAT_POOL_ECON_MEANS, eco.OFFER_QUALITY_DIST = orig_means, orig_pi


def test_q2_decide_event_bare_score_regression() -> None:
    """Q2 裸分回归帧:分派接线后 decide_event 全帧行为不变(fail-closed 恒走
    裸分,胜者/归因与无分派时逐位一致)。

    帧选型申报:详设 §2.2.6 原帧 {彩虹时代 72, 增发货币 48, 深井角斗场 42}
    的「增发货币 48 裸分」前提已被后续交付演化取代(3.3 数据批后增发货币
    resolved=True,3.5 域带接线后必走 env-econ 胜出)——本锁辖域 = 品质改写
    分派零扰动,故取 3.5 前后行为稳定的无经济通道帧,锁核心语义
    (品质改写环境 fail-closed 时维持裸分序 + env-eval 归因)不变。
    蓝海(A 类零参数通道)直调回归 = 分派不扰动 ENV_ECONOMY 既有通道。
    """
    p = _pick(['彩虹时代', '深井角斗场', '火药味'])
    assert p.option_idx == 0, f'fail-closed 下彩虹时代(72)裸分胜出,实得 {p.reason}'
    assert 'env-eval' in p.reason, f'胜出应来自 env 裸分支,实得 {p.reason}'
    assert env_economy_value('蓝海', _bs()) == (6.0, True), (
        '分派接线不得扰动既有 A 类精确通道')


# ===== Q3 公式算术(§2.2.6 行 3;§2.2.2)=====


def _inject_formula_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    """注入非真实参数的 μ_E/π_offer/H 全套 fixture(层 E 转正前的公式锁面;
    键型/结构 = 生产注册表同构)。"""
    monkeypatch.setattr(eco, '_STRAT_PICK_HORIZONS', {1: 24, 2: 20, 3: 16})
    monkeypatch.setattr(eco, 'STRAT_POOL_ECON_MEANS', {
        ('棱彩', 24): _est(10.0, 9.5, 10.5), ('金', 24): _est(6.0, 5.5, 6.5),
        ('银', 24): _est(4.0, 3.5, 4.5),
        ('棱彩', 20): _est(9.0, 8.5, 9.5), ('金', 20): _est(5.0, 4.5, 5.5),
        ('银', 20): _est(3.0, 2.5, 3.5),
        ('棱彩', 16): _est(8.0, 7.5, 8.5), ('金', 16): _est(4.0, 3.5, 4.5),
        ('银', 16): _est(2.0, 1.5, 2.5),
    })
    def _pi() -> dict[str, EconomyEstimate]:
        return {'银': _est(0.5, 0.45, 0.55), '金': _est(0.3, 0.25, 0.35),
                '棱彩': _est(0.2, 0.15, 0.25)}

    monkeypatch.setattr(eco, 'OFFER_QUALITY_DIST', {1: _pi(), 2: _pi(), 3: _pi()})


def test_q3_delta_v_formula_full_rewrite(monkeypatch: pytest.MonkeyPatch) -> None:
    """Q3 全改写 3 张:彩虹时代 ΔV 按公式逐位——

    ΔV = Σ_{k=1..3} [μ(棱彩,H_k) − Σ_q π_k(q)·μ(q,H_k)],H_k 视界入参化
    (k=1,2,3 → H=24,20,16 各自带 μ 表条目);期望值在测试内按公式独立
    现算(不抄实现),CI 低端 > 0 构造使 resolved=True 可断言点值。
    """
    _inject_formula_fixtures(monkeypatch)
    _h = {1: 24, 2: 20, 3: 16}
    _mu = {'棱彩': {24: 10.0, 20: 9.0, 16: 8.0},
           '金': {24: 6.0, 20: 5.0, 16: 4.0},
           '银': {24: 4.0, 20: 3.0, 16: 2.0}}
    # π:银 0.5/金 0.3/棱彩 0.2(三 k 同分布,fixture 构造)
    _expect = sum(
        _mu['棱彩'][_h[_k]]
        - (0.5 * _mu['银'][_h[_k]] + 0.3 * _mu['金'][_h[_k]]
           + 0.2 * _mu['棱彩'][_h[_k]])
        for _k in (1, 2, 3))
    _v, _ok = env_economy_value('彩虹时代', _bs())
    assert _ok is True
    assert _v == pytest.approx(_expect)
    assert _expect == pytest.approx(12.6)   # 4.2 + 4.2 + 4.2(算术锚点)


def test_q3_delta_v_formula_single_pick(monkeypatch: pytest.MonkeyPatch) -> None:
    """Q3 单张 1 张:头彩(picks=(1,))只计入 k=1 项;尾彩(picks=(3,))只计
    k=3 项——单张改写与全改写逐位同公式、仅 picks 辖域差。"""
    _inject_formula_fixtures(monkeypatch)
    _mu = {'棱彩': {24: 10.0, 16: 8.0}, '金': {24: 6.0, 16: 4.0},
           '银': {24: 4.0, 16: 2.0}}
    _k1 = 10.0 - (0.5 * 4.0 + 0.3 * 6.0 + 0.2 * 10.0)
    _k3 = 8.0 - (0.5 * 2.0 + 0.3 * 4.0 + 0.2 * 8.0)
    _v1, _ok1 = env_economy_value('头彩', _bs())
    assert _ok1 is True and _v1 == pytest.approx(_k1)
    _v3, _ok3 = env_economy_value('尾彩', _bs())
    assert _ok3 is True and _v3 == pytest.approx(_k3)


def test_q3_missing_pi_for_pick_fails_closed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Q3 缺参分型:π_offer 缺该 k → resolved=False;H_k 视界缺 → False;
    μ_E 缺该 (品质, H) → False。逐型独立注入验证 fail-closed 半值禁出。"""
    _inject_formula_fixtures(monkeypatch)
    # π 缺 k=1(头彩辖 k=1 → miss;尾彩辖 k=3 不受)
    _pi = dict(eco.OFFER_QUALITY_DIST)
    del _pi[1]
    monkeypatch.setattr(eco, 'OFFER_QUALITY_DIST', _pi)
    assert env_economy_value('头彩', _bs()) == (0.0, False)
    _v, _ok = env_economy_value('尾彩', _bs())
    assert _ok is True and _v == pytest.approx(
        8.0 - (0.5 * 2.0 + 0.3 * 4.0 + 0.2 * 8.0))
    # H 缺 k=3(尾彩 miss;头彩不受)——先重注满参 fixture 再删 H,防上一
    # 分型的 π 缺参状态泄入本分型(分型间互不污染)
    _inject_formula_fixtures(monkeypatch)
    monkeypatch.setattr(eco, '_STRAT_PICK_HORIZONS', {1: 24, 2: 20})
    assert env_economy_value('尾彩', _bs()) == (0.0, False)
    _v, _ok = env_economy_value('头彩', _bs())
    assert _ok is True
    # μ 缺基线品质条目(π 含银/金/棱彩,μ 表删 ('银',24) → 基线项不可算)
    _inject_formula_fixtures(monkeypatch)
    _mu = dict(eco.STRAT_POOL_ECON_MEANS)
    del _mu[('银', 24)]
    monkeypatch.setattr(eco, 'STRAT_POOL_ECON_MEANS', _mu)
    assert env_economy_value('头彩', _bs()) == (0.0, False)


# ===== Q4 准入方向(§2.2.6 行 4;§2.2.2/§2.2.5)=====


def test_q4_negative_delta_v_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Q4:注入参数使 ΔV(白银)≤0(基线 offer 全棱彩、改写目标银的受限均值
    更低)→ expected_gold ≤ 0 → fail-closed,白银时代不进经济域带、落裸分
    35(方向自洽:消费端 design §2.3 门 3 的 resolved ∧ expected_gold > 0
    自动承载准入门第 2 条)。decide_event 帧当前锚裸分行为(域带消费面 =
    3.5 接线,落地后本帧语义自动完整:白银 resolved=False 恒不进带,42 裸分
    胜)。"""
    monkeypatch.setattr(eco, '_STRAT_PICK_HORIZONS', {1: 24})
    monkeypatch.setattr(eco, 'STRAT_POOL_ECON_MEANS', {
        ('银', 24): _est(5.0, 4.8, 5.2), ('棱彩', 24): _est(8.0, 7.8, 8.2)})
    monkeypatch.setattr(eco, 'OFFER_QUALITY_DIST', {1: {'棱彩': _est(1.0, 1.0, 1.0)}})
    # ΔV = [4.8−8.2, 5.2−7.8] = [−3.4, −2.6]:CI 任一端点 ≤ 0 → (0.0, False)
    assert env_economy_value('白银时代', _bs()) == (0.0, False)
    p = _pick(['白银时代', '深井角斗场', '火药味'])
    assert p.option_idx == 1, (
        f'ΔV≤0 fail-closed 下白银时代(35)应落裸分,深井角斗场(42)胜出,'
        f'实得 {p.reason}')
    assert 'env-eval' in p.reason, f'胜出应来自裸分支,实得 {p.reason}'


# ===== Q5 数量通道(§2.2.6 行 5;§2.2.4)=====


def test_q5_quantity_channel_no_econ_band(monkeypatch: pytest.MonkeyPatch) -> None:
    """Q5:联席决策/银·金·彩 = 数量通道/结构改写型(rewrite_quality 空)→
    无层 E 语义,即使参数表全满也结构性 fail-closed(非缺参 False——数量
    通道不折金与 A 类策略大师同口径);decide_event 帧行为与现版一致
    (裸分承载:银·金·彩 62 > 联席 50)。"""
    _inject_formula_fixtures(monkeypatch)   # 参数全满亦然
    assert env_economy_value('联席决策', _bs()) == (0.0, False)
    assert env_economy_value('银·金·彩', _bs()) == (0.0, False)
    p = _pick(['联席决策', '银·金·彩', '火药味'])
    assert p.option_idx == 1, f'银·金·彩(62)裸分胜出,实得 {p.reason}'
    assert 'env-eval' in p.reason, f'胜出应来自裸分支(数量通道不折金),实得 {p.reason}'


# ===== Q6 结构互斥(§2.2.6 行 6;§2.1.3/§2.2.5;G8 半边收全)=====


def test_q6_cross_registry_mutex() -> None:
    """Q6:ENV_POOL_REWRITE ∩ ENV_GIFTS = ∅ ∧ ∩ ENV_ECONOMY = ∅(构建期断言
    的可读红面;与 test_cw_env_gift G8 半边合看 = 三表两两互斥收全——单一
    环境只落一个估值结构,防双通道叠加)。"""
    assert not (set(ENV_POOL_REWRITE) & set(ENV_GIFTS)), '品质改写与送卡注册表必须互斥'
    assert not (set(ENV_POOL_REWRITE) & set(ENV_ECONOMY)), '品质改写与经济通道注册表必须互斥'


def test_q6_validator_fires(monkeypatch: pytest.MonkeyPatch) -> None:
    """Q6:构建校验闸逐闸可炸(孤儿键/∩GIFTS/∩ECONOMY/结构半残/pending 缺失)。

    构建闸炸 import(模块级 _validate_env_pool_rewrite 调用),本锁逐闸给
    可读红:monkeypatch 注入坏条目后直调 validator,断言 ValueError 带对账
    语义(G8 validator-firing 同款手法)。
    """
    _rw = inv.StrategyPoolRewrite
    # ① 孤儿键(ENV_ECONOMY/ENV_GIFTS 先例同款)
    monkeypatch.setitem(inv.ENV_POOL_REWRITE, '不存在的环境', _rw(rewrite_quality='棱彩'))
    with pytest.raises(ValueError, match='孤儿键'):
        inv._validate_env_pool_rewrite()
    monkeypatch.undo()
    # ② ∩ ENV_GIFTS(双通道叠加拒绝)
    monkeypatch.setitem(inv.ENV_POOL_REWRITE, '持续伤害契约',
                        _rw(rewrite_quality='棱彩', rewrite_picks=(1, 2, 3)))
    with pytest.raises(ValueError, match='ENV_GIFTS'):
        inv._validate_env_pool_rewrite()
    monkeypatch.undo()
    # ②' ∩ ENV_ECONOMY(双通道叠加拒绝)
    monkeypatch.setitem(inv.ENV_POOL_REWRITE, '增发货币',
                        _rw(rewrite_quality='棱彩', rewrite_picks=(1, 2, 3)))
    with pytest.raises(ValueError, match='ENV_ECONOMY'):
        inv._validate_env_pool_rewrite()
    monkeypatch.undo()
    # ③ 结构半残(quality 与 picks 同有同无,层 E 公式不可算)
    monkeypatch.setitem(inv.ENV_POOL_REWRITE, '彩虹时代', _rw(rewrite_quality='棱彩'))
    with pytest.raises(ValueError, match='结构半残'):
        inv._validate_env_pool_rewrite()
    monkeypatch.undo()
    # ④ pending 必填(单张改写型 offer 覆盖面歧义)
    monkeypatch.setitem(inv.ENV_POOL_REWRITE, '头彩', _rw(rewrite_quality='棱彩',
                                                          rewrite_picks=(1,)))
    with pytest.raises(ValueError, match='保守支 notes'):
        inv._validate_env_pool_rewrite()
    monkeypatch.undo()
    # ④' pending 必填(offer 结构改写型槽位语义歧义)
    monkeypatch.setitem(inv.ENV_POOL_REWRITE, '银·金·彩',
                        _rw(offer_structure='silver_gold_prism_slots'))
    with pytest.raises(ValueError, match='保守支 notes'):
        inv._validate_env_pool_rewrite()
    monkeypatch.undo()
