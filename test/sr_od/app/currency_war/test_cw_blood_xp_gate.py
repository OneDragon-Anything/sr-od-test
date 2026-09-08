"""T-99② [40]② 血本位 XP 购买支付能力闸锁(blood_xp_gate;ADR-0578)。

- 判据 = 裁定字面「血余额 ≥ 下一级血成本(⌈need/4⌉×6)才买经验,否则停」
  (user_playstyle.md L274,2026-08-31 OPEN-6 + 同日三次简化「不留安全量」);
  阈值口径 = **全量击数** ⌈XP_TO_NEXT_LEVEL[level]/XP_PER_BUY⌉(N1 拍板,
  先例 = cw_plane_table.clicks_to_level;剩余口径 ⌈(need−cur)/4⌉ 恒向放行、
  与「否则停」反向,禁用)。
- 落点:cw_economy.blood_xp_gate(纯函数)+ blood_xp_gate_for(消费适配)+
  prep_actions._level_up(批入口闸 + 逐击地板/过冲 fail-closed,血模式限定;
  金模式零改动)+ cw4 M3 三消费位串联。
- 锁契约:锁结构语义不锁分布数值;数值期望从 XP_TO_NEXT_LEVEL/XP_PER_BUY
  推导式声明,非手抄口径锁。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_economy import (
    blood_xp_full_clicks,
    blood_xp_gate,
    blood_xp_gate_for,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    blood_xp_mode,
)
from sr_od.application.currency_war.kernel.cw_state import (
    XP_PER_BUY,
    XP_TO_NEXT_LEVEL,
    GameState,
)
from sr_od.application.currency_war.prep_actions import PrepActionExecutor
from sr_od.application.currency_war.telemetry import recorder as cw_recorder

# ===== 共用桩 =====


@pytest.fixture()
def captured_exo(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """捕获 record_exogenous 调用(写点经模块属性消费,patch 即全捕;
    手法 = test_cw_t100_hp_pay 同款)。"""
    rows: list[dict] = []

    def _cap(round_num, kind, detail='', state=None, choice=None):
        rows.append({'kind': kind, 'choice': choice})

    monkeypatch.setattr(cw_recorder, 'record_exogenous', _cap)
    return rows


def _blood_session(active: list[str] | None = None, **state_kw) -> SimpleNamespace:
    """血闸消费面依赖桩:active_strategies + last_state(其余无关)。"""
    return SimpleNamespace(
        active_strategies=list(active or ['奋斗协议']),
        last_state=GameState(**state_kw),
    )


# ===== T6/T6b/T7/T10:纯函数阈值 =====


def test_blood_xp_gate_threshold() -> None:
    """T6 阈值边界逐点红证(全量口径帧;ADR-0578):
    lv3(XP_TO_NEXT_LEVEL[3]=4 → 全量 ⌈4/4⌉=1 击)cost=6:hp=6 → True / hp=5 → False;
    lv7(need=52 → 全量 13 击):hp=78 → True(78≥78)/ hp=77 → False。
    红证语义:移除闸 → False 案例放行。"""
    assert XP_TO_NEXT_LEVEL[3] == 4 and XP_TO_NEXT_LEVEL[7] == 52
    assert blood_xp_full_clicks(3) == 1 and blood_xp_full_clicks(7) == 13
    assert blood_xp_gate(6, True, 3, 6) is True    # 6 ≥ 1×6
    assert blood_xp_gate(5, True, 3, 6) is False   # 5 < 6
    assert blood_xp_gate(78, True, 7, 6) is True   # 78 ≥ 13×6
    assert blood_xp_gate(77, True, 7, 6) is False  # 77 < 78


def test_blood_xp_gate_full_clicks_with_carryover() -> None:
    """T6b cur>0 结转专锁(N1 全量口径;ADR-0578):lv5 + xp_progress=(12,20)
    (买牌 XP 结转常态),cost=6 → 全量 ⌈20/4⌉=5 击×6=30:hp=13 → False /
    hp=30 → True。红证语义:误用剩余口径 ⌈(20−12)/4⌉=2 击×6=12 ≤ 13 →
    hp=13 帧放行、本锁红——判别帧 12 < 13 < 30 具完全判别力(锁钉死
    「cur>0 仍按全量判」)。"""
    st = GameState(level=5, xp_progress=(12, 20), hp=13)
    assert XP_TO_NEXT_LEVEL[5] == 20 and XP_PER_BUY == 4
    sess = _blood_session(plane=1, round_num=3, hp=13)
    # hp=13 帧:全量门槛 30 → 拒(剩余口径会放行)
    assert blood_xp_gate_for(st, sess) is False
    # 下边界:hp=30 恰达门槛 → 放行
    st_ok = GameState(level=5, xp_progress=(12, 20), hp=30)
    assert blood_xp_gate_for(st_ok, sess) is True
    # 口径自检:模式解析与击数推导单一源(非手抄)
    assert blood_xp_mode(sess) == ('奋斗协议', 6)
    assert blood_xp_full_clicks(5) == -(-XP_TO_NEXT_LEVEL[5] // XP_PER_BUY)


def test_blood_xp_gate_untrusted_hp_fail_closed() -> None:
    """T7 hp 不可信帧 fail-closed(P21 blood_budget_levelup_blocked 同面同论证:
    误放=血线内追级、误拦=少升一级,非对称);消费面 state 缺席同向;
    金本位(无 active 血本位卡)恒 True 直通(零改动面)。"""
    assert blood_xp_gate(None, True, 3, 6) is False    # hp 无真值
    assert blood_xp_gate(100, False, 3, 6) is False    # 可信位 False
    assert blood_xp_gate(None, False, 3, 6) is False
    # 消费适配面:state 缺席 fail-closed;金本位直通
    assert blood_xp_gate_for(None, _blood_session()) is False
    assert blood_xp_gate_for(GameState(hp=100, hp_readable=True),
                             SimpleNamespace(active_strategies=[])) is True
    # 不可信帧经消费适配面同样拒(兜底 100 帧语义 = ADR-0282:两位皆 False,
    # 由读取端显式写;GameState 构造缺省 hp_readable=True 是 sim 恒真读帧约定)
    st_ghost = GameState(level=3, hp=100, hp_readable=False)
    assert blood_xp_gate_for(st_ghost, _blood_session()) is False


def test_blood_xp_gate_max_level_pass() -> None:
    """R1 满级分支(ADR-0578):lv≥10 → 0 击恒放行(与 cw_state.xp_apply_clicks
    / clicks_to_next_level 满级返 0 同语义)——分支必须在公式本体,字面公式
    ⌈兜底4/4⌉=1 击会产出 6 血门槛拒付,与申报语义分叉。"""
    assert blood_xp_full_clicks(10) == 0
    assert blood_xp_gate(5, True, 10, 6) is True
    assert blood_xp_gate(5, True, 12, 6) is True


def test_blood_xp_gate_high_level_expected_stop() -> None:
    """T10 lv≥8 观测域内不可满足预期行为锁(F2c+N4 口径;ADR-0578):lv8
    (XP_TO_NEXT_LEVEL[8]=72 → 全量 18 击×6=108;hp=100 观测域内实采合法帧)
    → 闸拒。判读语义 = 设计而非故障([40]②「只看下一级所需…升级走买牌送的
    自然 XP」自带后果);lv7→8=78 ≤ 100 临界可达,结构性不可满足自 lv≥8 起。"""
    assert XP_TO_NEXT_LEVEL[8] == 72
    assert blood_xp_full_clicks(8) == 18
    assert blood_xp_gate(100, True, 8, 6) is False   # 108 > 100
    # 临界可达面:lv7→8 全量 78 血 ≤ 100,hp≥78 帧闸放行(R3 措辞锚)
    assert blood_xp_gate(90, True, 7, 6) is True


# ===== T8/T9:prep 连点循环(执行通道)=====


def _level_up_env(session, monkeypatch: pytest.MonkeyPatch,
                  level_reads: list, gold: int | None = 100):
    """PrepActionExecutor._level_up 离线桩(手法 = test_cw_t100_hp_pay 同款):
    ctx/op 全 SimpleNamespace,level 验证读序列与 gold 现读可控。"""
    import sr_od.application.currency_war.prep_actions as pa
    ex = object.__new__(PrepActionExecutor)
    ex._ctx = SimpleNamespace(
        cw_match=SimpleNamespace(session=session),
        controller=SimpleNamespace(mouse_move=lambda p: None,
                                   click=lambda p: None))
    ex._op = SimpleNamespace(screenshot=lambda: None,
                             park_cursor=lambda **kw: None)
    reads = iter(level_reads)
    monkeypatch.setattr(pa, '_read_level_raw',
                        lambda ctx, screen: next(reads))
    monkeypatch.setattr(pa, 'read_gold', lambda ctx, screen: gold)
    monkeypatch.setattr(pa, 'area_center', lambda ctx, name: None)
    return ex, pa


def test_level_up_gold_mode_unchanged(
        monkeypatch: pytest.MonkeyPatch,
        captured_exo: list[dict]) -> None:
    """T8 金模式零漂移(ADR-0578):无血本位卡 active → 批入口闸/逐击地板/
    过冲检全不激活——低 hp(hp=3,若血检误激活第 1 击即停)同样点满 12 击,
    hp_pay 零行(金本位回执 no-op)。"""
    sess = _blood_session(active=['淘金客'],    # 在册但非血本位 → 金模式
                          plane=2, round_num=1, hp=3)
    sess.effect_inventory = SimpleNamespace(on_level_up=lambda: None)
    sess.last_level_obs = None
    ex, pa = _level_up_env(sess, monkeypatch,
                           [5] + [None] * PrepActionExecutor.LEVEL_MAX_CLICKS)
    clicks = []
    monkeypatch.setattr(
        ex._ctx.controller, 'click',
        lambda p: clicks.append(1))
    ok, detail = ex._level_up()
    assert ok is False
    assert len(clicks) == PrepActionExecutor.LEVEL_MAX_CLICKS, \
        f'金模式点击序列不得被血检截断,实得 {len(clicks)}'
    assert f'点{PrepActionExecutor.LEVEL_MAX_CLICKS}次经验' in detail
    assert all(r['kind'] != 'hp_pay' for r in captured_exo)


def test_level_up_blood_mode_overshoot_cap(
        monkeypatch: pytest.MonkeyPatch,
        captured_exo: list[dict]) -> None:
    """T9 过冲上界(ADR-0578;§5.2 申报行:cur>0 帧验级成功路径实付 =
    剩余击数×单价 < 授权血成本 = 正常省钱路径,过冲上界只在验级恒失败帧兑现):
    血模式 lv3(全量 1 击)、hp_trusted=24、验级 OCR 恒失败 → 实击数=1、
    modeled 实付=6(= 授权血成本;现状无过冲检同 stub 点满 12 击 = 72 血的
    过冲同型消灭)。"""
    sess = _blood_session(active=['奋斗协议'],
                          plane=1, round_num=2, hp=24)
    sess.effect_inventory = SimpleNamespace(on_level_up=lambda: None)
    sess.last_level_obs = None
    ex, _pa = _level_up_env(
        sess, monkeypatch,
        [3] + [None] * PrepActionExecutor.LEVEL_MAX_CLICKS)   # 基线 3,验证恒失败
    clicks = []
    monkeypatch.setattr(
        ex._ctx.controller, 'click',
        lambda p: clicks.append(1))
    ok, detail = ex._level_up()
    assert ok is False
    assert len(clicks) == 1, f'过冲 fail-closed:实击数须 = 入口授权 1 击,实得 {len(clicks)}'
    assert '点1次经验' in detail
    rows = [r for r in captured_exo if r['kind'] == 'hp_pay']
    assert len(rows) == 1 and rows[0]['choice']['hp_delta'] == -6
    # modeled 实付 6 = 入口授权血成本(全量 1 击×6),非 LEVEL_MAX_CLICKS×6=72
    assert blood_xp_full_clicks(3) * 6 == 6


def test_level_up_blood_mode_entry_gate_reject(
        monkeypatch: pytest.MonkeyPatch,
        captured_exo: list[dict]) -> None:
    """批入口闸拒路径(ADR-0578;与「level 基线读不到」同返回路径):
    血模式 lv8(全量 108 血)> hp=100 → 零点击零回执,拒因回显。"""
    sess = _blood_session(active=['奋斗协议'],
                          plane=2, round_num=1, hp=100)
    sess.last_level_obs = None
    ex, pa = _level_up_env(sess, monkeypatch, [8, None])   # 基线 lv8
    clicks = []
    monkeypatch.setattr(
        ex._ctx.controller, 'click',
        lambda p: clicks.append(1))
    ok, detail = ex._level_up()
    assert ok is False and clicks == []
    assert '血闸拒' in detail and '108' in detail, f'拒因回显缺失:{detail}'
    assert all(r['kind'] != 'hp_pay' for r in captured_exo)
