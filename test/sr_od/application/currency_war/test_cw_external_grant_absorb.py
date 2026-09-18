"""外部随机备战席授予·精确吸收回归锁(2026-09-18 reconcile 事故修复批)。

病理(实机局 run_20260918_012509 journal 实录,安灯 hook:reconcile_mismatch
停局):投资策略「武装支援」(官方卡文 = 获得1件随机简易装备和2个随机3费
角色)确认后游戏向备战席授予 2 个随机单位;随机身份按效果域写入归属判据
不建逻辑写端(effect-domain.md §6.3 概率随机分支/§6.4 随机资产面观察收口,
用户裁定)。journal 时序:确认(01:28:04,先于开店)→游戏自动开店
(01:28:12)→买牌投影逐张改写 bench 逻辑态 = 已知 2 追踪 + 买入 5 = 7
(授予单位不在容器,投影基线缺员)→关店后下一备战帧实读 9 单位对逻辑态
7 必然失配 → 安灯当推算 bug 停机。分歧显形点 = 投影以授予盲基线改写
逻辑态:确认时字段在观察态,授予本身不触发失配(观察盖观察静默吸收)。
机制本身(实读多于逻辑)不是推算 bug,是申报盲区:豁免注册表的三维键
(screen×field×写端前缀)表达不了「外部授予」形状(授予不写逻辑,失配
时写端证据 = 买牌投影),故修法 = 申报表(EXTERNAL_BENCH_GRANTS)+
待吸收计数 + observe() 失配分支「纯超集+差额≤计数」精确吸收。

锁依据 = cw_mismatch_policy.EXTERNAL_BENCH_GRANTS 申报注释的吸收语义
(数量确定、身份不可推算、「只多不少」形状确定)+ GameState._absorb_
external_grant docstring 命中条件全列。改锁先重推语义:本锁钉的是
「申报形状内吸收、形状外照停」两向,禁为保绿机械跟绿。

同批姊妹锁:test_finalize_empty_ledger(空账关店审计不崩)驻本文件尾,
同属本事故两根因的回归面。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_game_state as _gs_mod
from sr_od.application.currency_war.kernel import (
    cw_mismatch_policy as _policy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    consume_defect_sink,
    game_state_of,
    register_sig_actors,
    set_defect_sink,
)

register_sig_actors('TestGrantWriter')

# ===== 事故帧实录(对局日志 01:28:35 失配行;语义对帧,禁引 .debug 路径)=====

#: 买牌投影写入的逻辑态 7 单位(已知 2 追踪 + 确认后买入 5;授予单位
#: 不在容器,投影基线缺员——时序见文件头 journal 实录)。
_LOGIC_UNITS: tuple[tuple[str, int], ...] = (
    ('爻光', 1), ('缇宝', 1), ('三月七', 1), ('艾丝妲', 1),
    ('乱破', 1), ('远坂凛', 1), ('飞霄', 1),
)
#: 实读 9 单位 = 授予的 娜塔莎/镜流(首两空槽)+ 既有 7 单位(槽位平移)。
_READ_UNITS: tuple[tuple[str, int], ...] = (
    ('娜塔莎', 1), ('镜流', 1), ('三月七', 1), ('艾丝妲', 1),
    ('爻光', 1), ('缇宝', 1), ('乱破', 1), ('远坂凛', 1), ('飞霄', 1),
)


def _bench_view(units: tuple[tuple[str, int], ...],
                capacity: int = 9) -> BenchView:
    """(名, 星) 序列 → BenchView(前缀占槽,余槽 empty;单帧构造专用)。"""
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=name, star=star, slot=i + 1))
             for i, (name, star) in enumerate(units)]
    while len(slots) < capacity:
        slots.append(BenchSlot(kind='empty'))
    return BenchView(slots=slots, capacity=capacity)


def _logic_sig() -> ChannelSig:
    return ChannelSig(family='logic_action', actor='TestGrantWriter',
                      mode='compute')


def _obs_sig() -> ChannelSig:
    return ChannelSig(family='obs', actor='CwScreenPrep',
                      screen='货币战争-备战', mode='read',
                      quality={'bench': 'real_read'})


def _observe_capture(gs: GameState, value: BenchView) -> list[dict]:
    """观察写入 + 缺陷行捕获(sink 挂载/卸载成对;安灯钩子由调用方
    monkeypatch 注入 _policy._ANDON_HOOK)。"""
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.bench, value, sig=_obs_sig())
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    return rows


# ============================================================ 吸收主锁


def test_external_grant_superset_absorbed(monkeypatch) -> None:
    """事故主形态:申报(待吸收 2)+ 实读纯超集差额 2 → 吸收不停机。

    锁:无 observe_vs_logic_mismatch 行、安灯不被调、
    external_grant_absorbed 行在案(豁免 ≠ 消失)、待吸收数清零、
    覆盖照常(观察赢,bench = 实读 9 单位)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.bench, _bench_view(_LOGIC_UNITS),
                   produced_by='TestGrantWriter',
                   evidence='proj_buy_place', sig=_logic_sig())
    gs.exec_books.external_bench_grant_pending = 2

    rows = _observe_capture(gs, _bench_view(_READ_UNITS))

    assert gs.bench.value == _bench_view(_READ_UNITS), '观察赢覆盖照常'
    assert gs.exec_books.external_bench_grant_pending == 0, '吸收后待吸收数清零'
    assert [r['kind'] for r in rows] == ['external_grant_absorbed'], \
        '落 external_grant_absorbed 台账行(无真失配行,可审计)'
    assert fired == [], '申报形状内:安灯不触发(不无脑停机)'


# ===== 事故帧实录(2026-09-18 run_074040 失配行语义;未投影族第 10 例)=====

#: 骇客专家:银狼确认后买牌前后的逻辑态 7 单位(对局日志 07:45:31 失配行)。
_WOLF_LOGIC_UNITS: tuple[tuple[str, int], ...] = (
    ('乱破', 1), ('卡芙卡', 1), ('大丽花', 1), ('藿藿', 1),
    ('椒丘', 1), ('爻光', 1), ('灵砂', 1),
)
#: 实读 9 单位 = 逻辑 7 单位 + 授予的 2×银狼(槽 2/4,卡双腿各一)。
_WOLF_READ_UNITS: tuple[tuple[str, int], ...] = (
    ('乱破', 1), ('银狼', 1), ('大丽花', 1), ('银狼', 1), ('椒丘', 1),
    ('卡芙卡', 1), ('藿藿', 1), ('爻光', 1), ('灵砂', 1),
)


def test_hacker_expert_silverwolf_bench_leg_absorbed(monkeypatch) -> None:
    """第 10 例事故形态:骇客专家:银狼确认(置闩 bench 2)+ 实读恰多
    2×银狼 → 精确吸收不停机。

    病理:该卡仅装备腿在册(EXTERNAL_EQUIP_GRANTS=1),bench 双腿
    (专家顾问银狼 + 加入商店银狼,实机证实均落备战席)未申报,安灯当
    推算 bug 停局。锁:置闩定额 = 表值 (2,1);吸收落台账行、安灯零触发;
    装备腿闩独立存续(同卡双腿分账)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    n_bench, n_equip = _gs_mod.latch_external_grants(
        gs, '骇客专家:银狼', actor='TestGrantWriter')
    assert (n_bench, n_equip) == (2, 1), '置闩定额 = 双表申报 (bench 2, equips 1)'
    gs.write_logic(gs.bench, _bench_view(_WOLF_LOGIC_UNITS),
                   produced_by='TestGrantWriter',
                   evidence='proj_buy_place', sig=_logic_sig())

    rows = _observe_capture(gs, _bench_view(_WOLF_READ_UNITS))

    assert gs.bench.value == _bench_view(_WOLF_READ_UNITS), '观察赢覆盖照常'
    assert gs.exec_books.external_bench_grant_pending == 0, 'bench 腿吸收清零'
    assert gs.exec_books.external_equip_grant_pending == 1, '装备腿闩独立存续'
    assert [r['kind'] for r in rows] == ['external_grant_absorbed'], \
        '落 external_grant_absorbed 台账行(无真失配行)'
    assert fired == [], '申报形状内:安灯不触发'


def test_external_grant_without_declaration_still_stops(monkeypatch) -> None:
    """反腿:未申报(待吸收 0)时同形状实读 → 真失配照落照停。

    锁:吸收只认申报表,非全局放水——bench 失配的默认处置不变。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.bench, _bench_view(_LOGIC_UNITS),
                   produced_by='TestGrantWriter',
                   evidence='proj_buy_place', sig=_logic_sig())
    assert gs.exec_books.external_bench_grant_pending == 0

    rows = _observe_capture(gs, _bench_view(_READ_UNITS))

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '未申报的真失配安灯照触发'


def test_external_grant_shape_guard_missing_unit(monkeypatch) -> None:
    """形状守卫·缺员腿:待吸收 2 但实读丢了一个逻辑态已有单位
    (非纯超集)→ 真失配照落照停(吸收不吞真投影 bug)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.bench, _bench_view(_LOGIC_UNITS),
                   produced_by='TestGrantWriter',
                   evidence='proj_buy_place', sig=_logic_sig())
    gs.exec_books.external_bench_grant_pending = 2
    # 实读 = 授予 2 单位 + 逻辑 7 单位缺『飞霄』(卖牌投影漏写类病灶形态)
    read_units = (('娜塔莎', 1), ('镜流', 1)) + _LOGIC_UNITS[:-1]

    rows = _observe_capture(gs, _bench_view(read_units))

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '形状不符(缺员)交回三分流照停'
    assert gs.exec_books.external_bench_grant_pending == 2, \
        '未吸收:待吸收数不动'


def test_external_grant_shape_guard_slot_shift_only(monkeypatch) -> None:
    """形状守卫·差额 0 腿:多重集相等仅槽位错位(授予没发生,纯投影
    错位病灶形态)→ 真失配照落照停(差额 0 不在 (0, 待吸收] 域)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.bench, _bench_view(_LOGIC_UNITS),
                   produced_by='TestGrantWriter',
                   evidence='proj_buy_place', sig=_logic_sig())
    gs.exec_books.external_bench_grant_pending = 2
    # 同多重集、整体右移一槽(槽 1 空):值不等(槽位号入 Unit)但
    # (char_id, star) 多重集相等 → 差额 0。
    shifted_slots = [BenchSlot(kind='empty')]
    shifted_slots += [BenchSlot(kind='unit',
                                unit=Unit(char_id=name, star=star, slot=i + 2))
                      for i, (name, star) in enumerate(_LOGIC_UNITS)]
    while len(shifted_slots) < 9:
        shifted_slots.append(BenchSlot(kind='empty'))
    shifted_view = BenchView(slots=shifted_slots, capacity=9)

    rows = _observe_capture(gs, shifted_view)

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '差额 0(纯槽位错位)不吸收'


def test_external_grant_surplus_over_declaration(monkeypatch) -> None:
    """形状守卫·超额腿:待吸收 1 但实读多出 2 个新单位 → 真失配照落
    (差额超申报 = 异常增益,不是本卡授予)。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.bench, _bench_view(_LOGIC_UNITS),
                   produced_by='TestGrantWriter',
                   evidence='proj_buy_place', sig=_logic_sig())
    gs.exec_books.external_bench_grant_pending = 1
    read_units = (('娜塔莎', 1), ('镜流', 1)) + _LOGIC_UNITS

    rows = _observe_capture(gs, _bench_view(read_units))

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch']
    assert len(fired) == 1, '差额超申报照停'


# ============================================================ 申报表一致性


def test_external_bench_grants_match_official_text() -> None:
    """申报表数值对官方卡文(data/cw_invest_data.py PLAZA_AUGMENTS,值
    唯一源):数量必须与卡文「N个随机N费角色」一致,防申报与游戏规则
    漂移。"""
    from sr_od.application.currency_war.data.cw_invest_data import (
        PLAZA_AUGMENTS,
    )
    official = {a.id: a for a in PLAZA_AUGMENTS}
    assert official['102501'].name == '武装支援'
    assert official['102502'].name == '武装支援+'
    assert '2个随机3费角色' in official['102501'].effect
    assert '1个随机4费角色' in official['102502'].effect
    assert _policy.EXTERNAL_BENCH_GRANTS['武装支援'] == 2
    assert _policy.EXTERNAL_BENCH_GRANTS['武装支援+'] == 1

    # 骇客专家:银狼(253401,未投影族第 10 例):两表双腿一致性——
    # bench 双腿(专家顾问银狼 + 加入商店银狼,实机证实均落备战席)= 2,
    # 装备腿(随机4费骇客改件)= 1;卡文数值为唯一源。
    assert official['253401'].name == '骇客专家:银狼'
    wolf_effect = official['253401'].effect
    assert '专家顾问【银狼】' in wolf_effect
    assert '加入商店' in wolf_effect
    assert '1个随机4费骇客改件' in wolf_effect
    assert _policy.EXTERNAL_BENCH_GRANTS['骇客专家:银狼'] == 2
    assert _policy.EXTERNAL_EQUIP_GRANTS['骇客专家:银狼'] == 1
    assert _policy.external_grant_totals('骇客专家:银狼') == (2, 1)


# ============================================================ 姊妹锁:空账审计


def test_finalize_empty_ledger_no_crash() -> None:
    """空账(全零 ledger)关店审计不崩(事故根因一回归锁)。

    病理:finalize_buy_phase 的消费块(_expected/冲突检查)曾被账本迁移
    挪出 `if total_buy or ...` 守卫,零动作 visit(策略首帧 CwActionCloseShopParam,
    实证 = 残局恢复局空店 [empty×5])守卫不执行 → _spend/_final_gold
    UnboundLocalError → CwActionOpenShopParam 执行异常。修复语义 = 零账无动作账可
    对拍,整段审计(读金+对拍)随守卫跳过(守卫 = 原意图,消费与读金
    同在守卫内)。锁依据 = finalize_buy_phase 守卫注释「空账早退语义」。"""
    from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
        ShopVisitLedger,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        finalize_buy_phase,
    )

    session = SimpleNamespace()
    game_state_of(session)   # 建容器(summary 读 gold/lv/plane 消费)
    match = SimpleNamespace(session=session)
    op = SimpleNamespace(ctx=None)   # 零账路径不触 op(读金在守卫内)

    summary = finalize_buy_phase(op, match, ShopVisitLedger(), None)

    assert isinstance(summary, str), '空账 visit 返回摘要串不崩'
    assert '买0张' in summary and '卖0张' in summary, \
        '摘要 = 全零动作账(审计对象为空的显式形态)'
