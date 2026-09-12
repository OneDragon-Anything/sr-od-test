"""配方底线门「锁定线语境豁免」回归锁(ADR-0564)。

设计出处:docs/develop/currency_war/decisions/0564-recipe-floor-lock-line-exempt.md
(设计稿 = fix_recipe_floor/方案-v3.md §5,8 条)。

覆盖面(五处消费点 + 遥测 + 缺省逐位同旧):
- 1  非锁定语境仍拦(既有锚的同型保绿 + 桥对帧 scope 误开门回归锚);
- 2  锁定线放行(修复本体;缺省 False 仍拦 = 向后兼容锁);
- 3  有效仙舟供给保留条款(armed ∧ 有真供给 → 门照拦,供给先上);
- 4  三类死供给换形全豁免(同名拷贝/item_slot/列车主籍双籍件防御排除);
- 5  op 适配器与 kernel 判定对账 + filter 纯函数 + spy 实参归因
     (op 主循环/P24 两消费点经同一判定函数的存在性证据);
- 6  swap 转型臂复活(ctx 武装 → post_sell_held 消失 → arm='transition');
- 7  发射侧帧级去重三键 + 执行侧 held/skip 分桶键;
- 8  装配段武装锁(CP2′:拦截 kwargs 豁免实参 + up 序含列车 core)。

纪律:单帧直调(锁语义不锁牌面);spy 断言按调用实参归因,禁平面计数
(kernel 计划层在同一次 execute 内也被同一包装拦截);红证 = 临时去
豁免武装,锁定线用例必须红。
"""
from __future__ import annotations

from types import SimpleNamespace

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel import cw_deploy_logic as dl
from sr_od.application.currency_war.kernel.cw_board_state import (
    board_state_bridge,
)
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    RECIPE_FLOOR_TRAIN_CAP,
    SwapPlanContext,
    assemble_swap_plan_inputs,
    can_deploy_single,
    deployed_bond_counts,
    has_deployable,
    recipe_floor_holds,
    select_deployments,
    select_deployments_reasoned,
    select_swap_plan,
    xianzhou_supply_exists,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    locked_faction_scope,
    locked_line_recipe_floor_conflict,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.operations.cw_op import cw_op_deploy as db
from sr_od.application.currency_war.strategies.impl.mandate_v1 import mandate
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

# ===== 测试基建 =====


def _bc(name: str, slot: int, star: int = 1) -> BenchChar:
    """注册表直读构造(ch.position_pref/主阵营单一源)。"""
    ch = CHARACTERS.get(name)
    return BenchChar(slot=slot, char_id=name, star=star,
                     faction=(ch.factions[0] if ch and ch.factions else '?'),
                     position_pref=(ch.position_pref() if ch else 'back'))


def _ist(locked_comp: str = '') -> IntentionState:
    return IntentionState(locked_comp=locked_comp)


def _armed(locked_comp: str = '列车同行') -> bool:
    """武装布尔单源直调(helper 判真前提自证,不拍布尔)。"""
    val = locked_line_recipe_floor_conflict(_ist(locked_comp))
    assert val is True, f'锁前提失效:{locked_comp} 应构成锁定线语境'
    return val


def _session(counters: dict | None = None,
             locked_comp: str = '',
             board: dict | None = None) -> SimpleNamespace:
    """直驱桩 op 的 session 桩(策略状态 = SimpleNamespace,字段面 =
    _deploy_deterministic 直接解引用的最小集)。``board`` 非空时构造
    last_state(op 的计划构造 board 输入 = last_state.board,None 时
    last_state=None → board 空 → 配对判定关闭)。"""
    last_state = (SimpleNamespace(board=dict(board), level=3)
                  if board is not None else None)
    return SimpleNamespace(
        last_state=last_state,
        strategy_state=SimpleNamespace(
            v3_intention=_ist(locked_comp),
            target_comp=None,
            transition_framework='',
            cw4_counters=counters if counters is not None else {}))


def _make_rf_op(monkeypatch, *, sess: SimpleNamespace,
                bench_read: list[BenchChar],
                deployed_read: list[BenchChar],
                cap: int = 6, front_occ: int = 1, back_occ: int = 2,
                paddle_x: int | None = None):
    """直驱 _deploy_deterministic 的桩 op(形态先例 =
    test_cw_deploy_battle_chain._make_gate_op;身份读面 monkeypatch
    ——templates 直传非 None 哨兵,read_*_chars 桩出身份,templates=None
    时身份空集走 fail-open,武装锁无从验证)。

    采样后 slot_occupied 按坐标分流:bench 排(y≥800)的源槽 fresh 复查
    返占用(放行拖拽,主循环/P24 fill 循环同语义);front/back 排返空
    (P24 段 _scr_fill 重采两排全空 → fill 计划可达)。
    """
    calls = {'n': 0}
    _paddle = paddle_x if paddle_x is not None else front_occ + back_occ

    def _fake_occ(scr, x, y):
        i = calls['n']
        calls['n'] += 1
        if i < 9:                      # bench 9 槽:前 len(bench_read) 占用
            return i < len(bench_read)
        if i < 13:                     # 前排 4 槽
            return (i - 9) < front_occ
        if i < 19:                     # 后排 6 槽
            return (i - 13) < back_occ
        return int(y) >= 800           # 采样后:bench 复查占用/前后排空

    monkeypatch.setattr(db, 'slot_occupied', _fake_occ)
    monkeypatch.setattr(db, 'read_deploy_cap_debounced',
                        lambda ctx, scr, level: cap)
    monkeypatch.setattr(db, 'read_deployed_count',
                        lambda ctx, scr: _paddle)
    # 身份读面 monkeypatch(B3/F2②:templates 直驱时身份空集 → 装配段
    # 无从判列车 core;按用例构造桩出 bench 列车 core 件与在场名集)
    monkeypatch.setattr(db, 'read_bench_chars',
                        lambda ctx, scr, tpl: list(bench_read))
    monkeypatch.setattr(db, 'read_deployed_chars',
                        lambda ctx, scr, tpl: list(deployed_read))
    from sr_od.application.currency_war.obs import cw_back_layout
    monkeypatch.setattr(cw_back_layout, 'select_back_layout',
                        lambda ctx, scr, level=None, cap=None,
                        level_trusted=None: (6, ''))
    monkeypatch.setattr(db.time, 'sleep', lambda s: None)
    drags: list[float] = []
    monkeypatch.setattr(
        db.DragCwChar, 'drag_char',
        lambda op, src, dst: drags.append(src.x) or True)

    class _Op(db.CwOpDeploy):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            pass

        def screenshot(self):
            return object()

        def _wait_slot_occupied(self, pt, budget):
            return True

        def _decision_overlay_screen(self, scr):
            return None   # T-277 遮蔽探测桩化(无 screen_loader 面)

    op = _Op()
    op.ctx = SimpleNamespace(cw_match=SimpleNamespace(session=sess))
    bench_pts = [Point(100 + 30 * i, 900) for i in range(9)]
    front_pts = [Point(500 + 30 * i, 400) for i in range(4)]
    back_pts = [Point(500 + 30 * i, 650) for i in range(6)]
    return op, bench_pts, front_pts, back_pts, drags


def _drive(op, bench_pts, front_pts, back_pts):
    placed, plan_empty, gate_fail = op._deploy_deterministic(
        bench_pts, front_pts, back_pts,
        object())   # templates 哨兵:非 None 走身份读
    # T-164 批A 契约扩 3 元组:本文件锁面不辖 D2 失配闸,剥第三元返回;
    # 守护断言防场景漂移后静默吞掉失配闸命中(命中 = 本文件场景失真)。
    assert gate_fail is None, f'本文件场景不应命中 D2 失配闸,实得 {gate_fail!r}'
    return placed, plan_empty


def _identity(bench_names: list[str], deployed_names: list[str]):
    """身份读桩产物(bench/deployed 同构 BenchChar 列表;slot 1-based)。"""
    return ([_bc(n, i + 1) for i, n in enumerate(bench_names)],
            [_bc(n, i + 1) for i, n in enumerate(deployed_names)])


# 局64 精确形态共用底料:deployed 饮月+三月七+3 非引擎(列车2/仙舟1),
# bench 姬子·启行(列车同行 core;注册表 cw_chars 主阵营列车同行)。
_G64_DEP = ['丹恒·饮月', '三月七', '阿格莱雅', '乱破', '大丽花']
_G64_TRAIN = '姬子·启行'


# ==================== 1 非锁定语境仍拦(保绿 + I3 锚)====================

def test_floor_gate_holds_non_lock_context() -> None:
    """非锁定语境仍拦。①局64 精确形态(本文件自持锚;test_cw_deploy_ops
    的原同型锚已删,其头部处置注记回指本文件——豁免不得误开);
    ②桥对帧变体(I3 锚):真 IntentionState 置 p1_pair 非空、
    locked_comp='' → helper False → 仍拦——scope 成员判会把门在过渡期
    误开(桥池列车目标档=2 = 门封顶,无冲突,过渡纪律应全额生效)。"""
    # ① 局64 精确形态
    fac = deployed_bond_counts(set(_G64_DEP))
    bench = [_bc(_G64_TRAIN, 1), _bc(_G64_TRAIN, 2)]
    up, held = select_deployments(
        bench, deployed_cids=set(_G64_DEP), deployed_fac=fac,
        board=dict(fac), cap=7)
    assert not up, '非锁定语境列车件应被 r288 门拦(豁免不得误开)'
    assert len(held) == 2

    # ② 桥对帧变体:p1_pair 非空 + locked_comp='' → 豁免关
    ist_bridge = IntentionState(p1_pair=('仙舟', '持续伤害'))
    assert locked_line_recipe_floor_conflict(ist_bridge) is False
    assert locked_faction_scope(ist_bridge), '锁前提:scope 非空'
    bench3 = [_bc(_G64_TRAIN, 1), _bc('彦卿', 2)]   # 彦卿 = 有效仙舟供给
    up3, _held3, reasons3 = select_deployments_reasoned(
        bench3, deployed_cids=set(_G64_DEP), deployed_fac=fac,
        board=dict(fac), cap=7,
        recipe_floor_lock_exempt=locked_line_recipe_floor_conflict(ist_bridge))
    up_names = {bench3[i].char_id for i in up3}
    assert _G64_TRAIN not in up_names, (
        '桥对帧(locked_comp 空)豁免必须关:scope 误开门 = r288 暴露面重开')
    assert '彦卿' in up_names, '有效供给件照常上(帧内优先语义)'
    assert 'recipe_floor' in set(reasons3.values())


# ==================== 2 锁定线放行(修复本体)====================

def test_lock_line_exempt_releases_train_core() -> None:
    """锁定线放行:locked_comp='列车同行'(form_tiers 列车 4 > 封顶 2)、
    列车 3 档/仙舟 < 基础线、bench 列车 core(姬子·启行)且无仙舟供给
    → 豁免开火:up 含该件 ∧ has_deployable True;同输入缺省(False)
    仍拦(reason='recipe_floor');「龙丹战技点」双档 comp 自动覆盖。"""
    dep = ['三月七', '瓦尔特', '姬子', '阿格莱雅']   # 列车3/仙舟0
    fac = deployed_bond_counts(set(dep))
    assert fac.get('列车同行', 0) >= RECIPE_FLOOR_TRAIN_CAP
    bench = [_bc(_G64_TRAIN, 1)]
    armed = _armed('列车同行')
    assert xianzhou_supply_exists(bench, set(dep)) is False, \
        '锁前提:bench 无有效仙舟供给(供给保留条款不触发)'

    up, held, _reasons = select_deployments_reasoned(
        bench, deployed_cids=set(dep), deployed_fac=fac, board=dict(fac),
        cap=8, recipe_floor_lock_exempt=armed)
    assert [bench[i].char_id for i in up] == [_G64_TRAIN], '豁免开火:列车 core 上场'
    assert not held
    assert has_deployable(
        bench, deployed_cids=set(dep), deployed_fac=fac, board=dict(fac),
        cap=8, recipe_floor_lock_exempt=armed) is True
    # has_deployable_reasoned armed 面经第 7 节武装发射帧的生产链
    # (mandate._deployable → 本函数)覆盖,不重复直调。

    # 同输入缺省(False)仍拦 = 逐位同旧(向后兼容锚)
    up_d, held_d, reasons_d = select_deployments_reasoned(
        bench, deployed_cids=set(dep), deployed_fac=fac, board=dict(fac),
        cap=8)
    assert not up_d and held_d
    assert reasons_d[held_d[0]] == 'recipe_floor'

    # 双档 comp(战技点 4 + 列车同行 4)自动覆盖
    assert locked_line_recipe_floor_conflict(_ist('龙丹战技点')) is True
    up2, _held2, _r2 = select_deployments_reasoned(
        bench, deployed_cids=set(dep), deployed_fac=fac, board=dict(fac),
        cap=8, recipe_floor_lock_exempt=locked_line_recipe_floor_conflict(
            _ist('龙丹战技点')))
    assert [bench[i].char_id for i in up2] == [_G64_TRAIN]


# ==================== 3 有效供给保留条款 ====================

def test_lock_line_with_valid_supply_still_holds() -> None:
    """锁定线 ∧ bench 有**有效**仙舟供给(主阵营仙舟件,不在场)→ 仍拦
    (reason='recipe_floor'),且同帧 up 含供给件——门的供给保留条款:
    有真供给竞争帧门不让位,供给先上(仙舟档 +1)后豁免自动闭合。"""
    dep = ['三月七', '瓦尔特', '姬子']   # 列车3/仙舟0
    fac = deployed_bond_counts(set(dep))
    bench = [_bc(_G64_TRAIN, 1), _bc('彦卿', 2)]
    assert xianzhou_supply_exists(bench, set(dep)) is True
    up, held, reasons = select_deployments_reasoned(
        bench, deployed_cids=set(dep), deployed_fac=fac, board=dict(fac),
        cap=8, recipe_floor_lock_exempt=_armed())
    up_names = {bench[i].char_id for i in up}
    assert _G64_TRAIN not in up_names, '有有效供给:列车 core 仍拦'
    assert '彦卿' in up_names, '帧内优先:供给件先上'
    train_reason = next(v for k, v in reasons.items()
                        if bench[k].char_id == _G64_TRAIN)
    assert train_reason == 'recipe_floor'


# ==================== 4 死供给换形全豁免(I2 复发洞锁)====================

def _dead_supply_case(monkeypatch, bench: list[BenchChar],
                      synthetic_name: str = ''):
    """死供给变体公共断言:锁定线 ∧ bench 只有死供给 → 豁免开、列车
    core 上场(按名义供给计数时任一死供给形态在场 = 豁免恒闭 = 死锁
    换形复发,即本锁的靶)。"""
    dep = ['三月七', '瓦尔特', '姬子']
    fac = deployed_bond_counts(set(dep))
    if synthetic_name:
        # 条件④防御性排除(当前注册表无实例):合成「主阵营列车同行 +
        # flows 仙舟」件——其自身被本门拦,永远轮不到它贡献仙舟档。
        synth = SimpleNamespace(factions=('列车同行',), flows=('仙舟',))
        monkeypatch.setattr(dl, 'CHARACTERS',
                            {**CHARACTERS, synthetic_name: synth})
    assert xianzhou_supply_exists(bench, set(dep)) is False, \
        '死供给必须被判无效(谓词四条判据的靶面)'
    up, held, _reasons = select_deployments_reasoned(
        bench, deployed_cids=set(dep), deployed_fac=fac, board=dict(fac),
        cap=8, recipe_floor_lock_exempt=_armed())
    assert _G64_TRAIN in {bench[i].char_id for i in up}, \
        '死供给形态:豁免应开火、列车 core 上场'


def test_dead_supply_same_name_copy_exempt(monkeypatch) -> None:
    """死供给①同名拷贝:三月七已在场,bench 第二张同名 = 恒 held 的
    死供给,不计作有效供给。"""
    _dead_supply_case(
        monkeypatch, [_bc(_G64_TRAIN, 1), _bc('三月七', 2)])


def test_dead_supply_item_slot_exempt(monkeypatch) -> None:
    """死供给②item_slot:占槽物品恒拒、永不上场(身份可读 + 标记形态
    ——装配点 assemble_bench_list 的显式 is_item_slot 形态,非仅
    char_id='' 推断形态)。"""
    item = BenchChar(slot=2, char_id='彦卿', faction='仙舟',
                     position_pref='back', is_item_slot=True)
    _dead_supply_case(monkeypatch, [_bc(_G64_TRAIN, 1), item])


def test_dead_supply_train_main_dual_faction_exempt(monkeypatch) -> None:
    """死供给③列车主籍双籍件(条件④防御性排除;当前注册表无实例,
    合成注册表项验证谓词分支本身)。"""
    synth = '合成列车仙舟件'
    item = BenchChar(slot=2, char_id=synth, faction='列车同行',
                     position_pref='back')
    _dead_supply_case(monkeypatch, [_bc(_G64_TRAIN, 1), item],
                      synthetic_name=synth)


# ==================== 5 op 适配器与接线 ====================

def test_op_gate_adapter_matches_kernel() -> None:
    """适配器对账锁(形态先例 = test_cw_deploy_ops op 与纯函数对账):
    r288_hold_now 与 kernel.recipe_floor_holds(+供给谓词)同输入同输出,
    armed/disarmed 双语境 + 门自开/非列车件边界。"""
    cases = [
        # (main_fac, deployed_fac, bench, lock_conflict)
        ('列车同行', {'列车同行': 2, '仙舟': 1}, [_bc(_G64_TRAIN, 1)], False),
        ('列车同行', {'列车同行': 2, '仙舟': 1}, [_bc(_G64_TRAIN, 1)], True),
        ('列车同行', {'列车同行': 3, '仙舟': 0}, [_bc('彦卿', 1)], True),
        ('仙舟', {'列车同行': 2, '仙舟': 1}, [_bc('彦卿', 1)], False),
        ('列车同行', {'列车同行': 2, '仙舟': 3}, [_bc(_G64_TRAIN, 1)], False),
    ]
    for main_fac, dfac, bench, lc in cases:
        expect = recipe_floor_holds(
            main_fac, dfac.get('列车同行', 0), dfac.get('仙舟', 0), lc,
            xianzhou_supply_exists(bench, set()) if lc else False)
        got = db.r288_hold_now(main_fac, dfac, set(), bench, lc)
        assert got is expect, (main_fac, dfac, lc)


def test_fill_plan_filter_and_wiring(monkeypatch) -> None:
    """P24 fill 过滤纯函数 + spy 实参归因(op 主循环/P24 两消费点经
    同一判定函数的存在性证据;断言按调用实参归因,禁平面计数——
    kernel 计划层在同一次 execute 内也被同一包装拦截)。

    armed 帧:存在实参组 (列车同行, 3, 0, True)——增量现值(列车档 2→3)
    在门调用实参中出现,证明 op 侧运行时档值经共享判定函数喂入。
    ⚠️ 该组不可按站点归因:kernel 计划层逐件评估(第一件 up 后 _fac_run
    同步 +1,第二件在计划层即以 train=3 被评估)与主循环均可能产出同组
    ——两者都经同一判定函数,存在性证据成立但站点不可区分。主循环
    消费点的**行为证据** = placed==2 ∧ drags 非空(列车件被拖拽上场 =
    未被主循环门 skip);该帧全部门调用的武装布尔与装配段同值。

    disarmed 帧:主循环对列车件零 gate 调用(非列车件在适配器前短路),
    kernel 计划层恰 1 次(单列车件一次评估)+ P24 过滤恰 1 次 = 同实参
    组恰 2 次——P24 消费点经同一判定函数的存在性证据;列车件不出拖拽。
    """
    dep = ['三月七', '瓦尔特']   # 列车2/仙舟0
    # ---- 纯函数面:豁免开时列车件不被剔除 ----
    plan = [(0, 'front', 1)]
    bench1 = [_bc(_G64_TRAIN, 1)]
    fac12 = {'列车同行': 2, '仙舟': 1}
    assert db.filter_fill_plan_by_floor(
        plan, {0: '列车同行'}, fac12, set(), bench1,
        lock_conflict=False) == []
    assert db.filter_fill_plan_by_floor(
        plan, {0: '列车同行'}, fac12, set(), bench1,
        lock_conflict=True) == plan
    assert db.filter_fill_plan_by_floor(
        plan, {0: '仙舟'}, fac12, set(), bench1, lock_conflict=False) == plan

    # ---- spy 面 ----
    real_holds = dl.recipe_floor_holds
    gate_calls: list[tuple] = []

    def _spy_holds(main_fac, train_now, xz_now, lock_exempt_armed,
                   supply_exists):
        gate_calls.append((main_fac, train_now, xz_now, lock_exempt_armed))
        return real_holds(main_fac, train_now, xz_now, lock_exempt_armed,
                          supply_exists)

    monkeypatch.setattr(dl, 'recipe_floor_holds', _spy_holds)

    # armed 帧 双列车件:先上件吃掉门值,后件以 train=3 被评估
    #(计划层逐件增量与主循环增量同值——站点不可区分,见 docstring)
    sess_a = _session(locked_comp='列车同行')
    bench_read_a, deployed_read_a = _identity([_G64_TRAIN, '姬子'], dep)
    op_a, bp, fp, bk, drags_a = _make_rf_op(
        monkeypatch, sess=sess_a, bench_read=bench_read_a,
        deployed_read=deployed_read_a, cap=6)
    placed_a, plan_empty_a = _drive(op_a, bp, fp, bk)
    assert placed_a == 2 and drags_a, \
        'armed 帧:列车件应被拖拽上场(不进 skip;主循环消费点行为证据)'
    assert plan_empty_a is False
    train_groups_a = [g for g in gate_calls if g[0] == '列车同行']
    assert train_groups_a, 'armed 帧:列车件的门判定必须经共享判定函数'
    assert all(g[3] is True for g in train_groups_a), \
        'armed 帧全部门调用的武装布尔与装配段同值'
    assert ('列车同行', 3, 0, True) in train_groups_a, (
        '增量现值(train=3)在门实参中出现 = op 侧运行时档值经共享判定'
        f'函数喂入(计划层第二件/主循环均可能产出,站点不可区分),'
        f'实得 {sorted(set(train_groups_a))}')

    # disarmed 帧:列车件 kernel held → P24 计划 → filter 经同一判定剔除
    gate_calls.clear()
    sess_b = _session()   # locked_comp='' → 武装关
    bench_read_b, deployed_read_b = _identity(['彦卿', _G64_TRAIN], dep)
    op_b, bp, fp, bk, drags_b = _make_rf_op(
        monkeypatch, sess=sess_b, bench_read=bench_read_b,
        deployed_read=deployed_read_b, cap=6)
    placed_b, plan_empty_b = _drive(op_b, bp, fp, bk)
    assert placed_b == 1, '仅彦卿(非列车件)上场'
    assert drags_b == [bp[0].x], '列车件不得被拖拽(kernel held → P24 剔除)'
    assert plan_empty_b is False
    train_groups_b = [g for g in gate_calls if g[0] == '列车同行']
    assert len(train_groups_b) == 2, (
        'disarmed 帧同实参组恰 2 次:kernel 计划层 1(单列车件)+ '
        f'P24 过滤 1(主循环对列车件零调用),实得 {train_groups_b}')
    assert all(g[3] is False for g in train_groups_b)


# ==================== 6 swap 转型臂复活 ====================

def test_swap_transition_arm_revived_on_lock_line() -> None:
    """swap 复活:锁定线语境 ctx(recipe_floor_lock_exempt=True、locked、
    fp<1.00、板满、victim=fenced 过渡件、bench 列车 core)→ plan.nonempty
    ∧ arm='transition'——ADR-0534 转型臂此前被 recipe_floor 经
    post_sell_held 闷死,豁免复活它;对照:ctx 缺省 False 同输入 →
    post_sell_held(既有 test_cw_swap_plan 锁语义,该 fixture 不动)。"""
    victim = '艾丝妲'   # 持续伤害主阵营 = fenced off-target(注册表事实)
    deployed = [_bc(victim, 1), _bc('三月七', 2), _bc('瓦尔特', 3),
                _bc('阿格莱雅', 4), _bc('飞霄', 5), _bc('乱破', 6)]
    bench = [_bc(_G64_TRAIN, 1)]   # 列车 core;卖后假想态列车 2/仙舟 0
    base = {
        'target_factions': frozenset({'仙舟', '列车同行'}),
        'target_cores': frozenset({_G64_TRAIN}), 'fw_carry': frozenset(),
        'locked_factions': frozenset(), 'protect_names': frozenset(),
        'membership': frozenset(), 'fresh_buys': frozenset(), 'board': {},
        'deployed': deployed, 'bench': bench, 'cap': 6, 'fenced_on': False,
        'fp': 0.5, 'locked': True, 'board_full': True}
    ctx_armed = SwapPlanContext(**base, recipe_floor_lock_exempt=True)
    plan = select_swap_plan(ctx_armed)
    assert plan.nonempty and plan.arm == 'transition', plan
    assert plan.sell_names == [victim]
    assert {bench[i].char_id for i in plan.up_bench} == {_G64_TRAIN}

    # 对照:同输入缺省(豁免关)→ post_sell_held(白卖不可达语义保持)
    reasons_off: dict[str, str] = {}
    plan_off = select_swap_plan(
        SwapPlanContext(**base), reasons_out=reasons_off)
    assert not plan_off.nonempty
    assert reasons_off.get(_G64_TRAIN) == 'post_sell_held'
    assert _G64_TRAIN not in {bench[i].char_id for i in plan_off.up_bench}

    # CP4 装配武装锁:锁定 session 经生产装配函数 → ctx 新字段 True
    #(assemble_swap_plan_inputs→SwapPlanContext 接线;装配断链时红)
    sess_locked = SimpleNamespace(
        last_state=None,
        strategy_state=SimpleNamespace(
            v3_intention=_ist('列车同行'), target_comp=None,
            transition_framework=''))
    ctx_asm = assemble_swap_plan_inputs(
        sess_locked, state=board_state_bridge(GameState(plane=2, round_num=3)),
        deployed=deployed, bench=bench, cap=6)
    assert ctx_asm is not None
    assert ctx_asm.recipe_floor_lock_exempt is True, \
        '装配函数未把锁定线语境武装进 ctx(CP4 接线断链)'
    sess_plain = SimpleNamespace(
        last_state=None,
        strategy_state=SimpleNamespace(
            v3_intention=_ist(), target_comp=None, transition_framework=''))
    ctx_plain = assemble_swap_plan_inputs(
        sess_plain, state=board_state_bridge(GameState(plane=2, round_num=3)),
        deployed=deployed, bench=bench, cap=6)
    assert ctx_plain is not None and ctx_plain.recipe_floor_lock_exempt is False


# ==================== 7 遥测:发射侧三键 + 执行侧分桶 ====================

def _tele_frame(round_num: int = 3) -> mandate.MandateFrame:
    return mandate.MandateFrame(
        gold=20, level=3, bench=[_bc(_G64_TRAIN, 1)],
        deployed=[_bc('三月七', 1), _bc('瓦尔特', 2)],
        deploy_cap=8, node_type=None, stop_flag=False, k_members=(),
        round_num=round_num)


def test_emission_frame_dedup_union_and_hold_key() -> None:
    """发射侧拦帧:计划空帧(列车 core 被门拦)连调 3 次(M5/M1/M1′
    帧内最多次数)→ deploy_emit_held_recipe_floor 只 +1(并集语义,
    帧级去重载体 phase 翻转自动重置)。"""
    sess = SimpleNamespace()
    state_of(sess).cw4_counters = {}
    state_of(sess).v3_intention = _ist()   # 未锁 → 豁免关
    frame = _tele_frame()
    for _ in range(3):
        assert mandate._deployable(frame, sess, GameState()) is False
    c = state_of(sess).cw4_counters
    assert c.get('deploy_emit_held_recipe_floor') == 1, c
    assert 'deploy_emit_floor_ctx_open' not in c
    assert 'deploy_emit_floor_exempt_open' not in c
    # 轮次推进 = 新帧,键重新可计(去重载体 phase 键式)
    frame2 = _tele_frame(round_num=4)
    assert mandate._deployable(frame2, sess, GameState()) is False
    assert state_of(sess).cw4_counters.get(
        'deploy_emit_held_recipe_floor') == 2


def test_emission_armed_release_and_exempt_fire_keys() -> None:
    """发射侧放行帧:armed 帧豁免开火 → deploy_emit_held_recipe_floor
    不增(拒因消失)、deploy_emit_floor_ctx_open +1(分母,帧级去重)、
    deploy_emit_floor_exempt_open +1(开火验证:armed 帧无豁免对照补跑,
    对照拒因消失 = 本帧开过火;G1 生效门读数)。"""
    sess = SimpleNamespace()
    state_of(sess).cw4_counters = {}
    state_of(sess).v3_intention = _ist('列车同行')
    frame = _tele_frame()
    for _ in range(2):
        assert mandate._deployable(frame, sess, GameState()) is True
    c = state_of(sess).cw4_counters
    assert 'deploy_emit_held_recipe_floor' not in c, c
    assert c.get('deploy_emit_floor_ctx_open') == 1
    assert c.get('deploy_emit_floor_exempt_open') == 1


def test_exec_telemetry_held_and_skip_buckets(monkeypatch) -> None:
    """执行侧键:deploy_exec_held_<reason> 每 execute 一次(计划拒因,
    与发射侧同粒度对读);deploy_exec_r288_skip_ctx_open/closed 分桶
    正确(P24 过滤剔除按帧武装布尔分桶)。构造:8 在场(列车2/仙舟0,
    vacancy=2 → 供给件彦卿 rest_capacity held、供给保活)∧ bench
    [列车core, 彦卿] → 列车件计划层 r288 held;P24 fill 计划含两件 →
    filter 剔除列车件(armed 帧供给在场 hold=True 计 ctx_open;disarmed
    帧同形计 ctx_closed),彦卿经 fill 上场。既有
    fuel_filler_stall_held_postbuy 行为不回归(无买入登记 → 键不出现)。"""
    dep = ['三月七', '瓦尔特', '阿格莱雅', '乱破', '大丽花', '飞霄',
           '娜塔莎', '万敌']   # 列车2/仙舟0(注册表直选,无仙舟羁绊件)
    fac_probe = deployed_bond_counts(set(dep))
    assert fac_probe.get('列车同行') == 2 and '仙舟' not in fac_probe, \
        '锁前提失效:8 在场形态必须构成 列车2/仙舟0'
    # armed 帧:列车件计划层 held(供给彦卿在 bench 保活),P24 剔除 → ctx_open
    counters_a: dict = {}
    sess_a = _session(counters=counters_a, locked_comp='列车同行',
                      board=fac_probe)
    bench_a, deployed_a = _identity([_G64_TRAIN, '彦卿'], dep)
    op_a, bp, fp, bk, drags_a = _make_rf_op(
        monkeypatch, sess=sess_a, bench_read=bench_a,
        deployed_read=deployed_a, cap=9, front_occ=2, back_occ=4,
        paddle_x=6)
    placed_a, _pe_a = _drive(op_a, bp, fp, bk)
    assert placed_a == 1 and drags_a == [bp[1].x], '仅供给件(彦卿)经 fill 上场'
    assert counters_a.get('deploy_exec_held_recipe_floor') == 1, counters_a
    assert counters_a.get('deploy_exec_held_rest_capacity') == 1
    assert counters_a.get('deploy_exec_r288_skip_ctx_open') == 1, counters_a
    assert 'deploy_exec_r288_skip_ctx_closed' not in counters_a
    assert 'fuel_filler_stall_held_postbuy' not in counters_a

    # disarmed 帧:同形构造 → 剔除计 ctx_closed
    counters_b: dict = {}
    sess_b = _session(counters=counters_b, board=fac_probe)
    bench_b, deployed_b = _identity([_G64_TRAIN, '彦卿'], dep)
    op_b, bp, fp, bk, drags_b = _make_rf_op(
        monkeypatch, sess=sess_b, bench_read=bench_b,
        deployed_read=deployed_b, cap=9, front_occ=2, back_occ=4,
        paddle_x=6)
    placed_b, _pe_b = _drive(op_b, bp, fp, bk)
    assert placed_b == 1 and drags_b == [bp[1].x]
    assert counters_b.get('deploy_exec_held_recipe_floor') == 1
    assert counters_b.get('deploy_exec_r288_skip_ctx_closed') == 1, counters_b
    assert 'deploy_exec_r288_skip_ctx_open' not in counters_b


# ==================== 8 装配段武装锁(CP2′)====================

def test_assembly_wiring_armed_plan_includes_train_core(monkeypatch) -> None:
    """装配段武装锁(N1 回归锚:CP2′ 接线存在且语义正确)。armed 变体:
    monkeypatch select_deployments_reasoned 为记录包装(透传真函数;
    拦截生效依据 = op 内函数级惰性 import 调用时解析模块属性)→
    断言①拦截 kwargs recipe_floor_lock_exempt is True;②真函数返回的
    up 序映射回 bench 后含列车 core(姬子·启行)∧ order 非空(拖拽发生)。
    disarmed 变体:locked_comp 置空 → 豁免实参 False ∧ 同输入 up 不含
    该件(reasons 拒因 'recipe_floor')。"""
    dep = ['三月七', '瓦尔特']

    # ---- armed 变体 ----
    calls: list[dict] = []
    real_reasoned = dl.select_deployments_reasoned

    def _spy_reasoned(bench, deployed_cids, **kwargs):
        result = real_reasoned(bench, deployed_cids=deployed_cids, **kwargs)
        calls.append({'kwargs': dict(kwargs), 'bench': bench,
                      'result': result})
        return result

    monkeypatch.setattr(dl, 'select_deployments_reasoned', _spy_reasoned)

    sess_a = _session(locked_comp='列车同行')
    bench_read_a, deployed_read_a = _identity([_G64_TRAIN], dep)
    op_a, bp, fp, bk, drags_a = _make_rf_op(
        monkeypatch, sess=sess_a, bench_read=bench_read_a,
        deployed_read=deployed_read_a, cap=6)
    placed_a, plan_empty_a = _drive(op_a, bp, fp, bk)
    assert calls, '装配段计划构造必须被拦截(spy 生效)'
    kw = calls[0]['kwargs']
    assert kw.get('recipe_floor_lock_exempt') is True, (
        f'装配段豁免实参未武装:实得 {kw.get("recipe_floor_lock_exempt")}')
    up_a, _held_a, _r_a = calls[0]['result']
    assert {calls[0]['bench'][i].char_id for i in up_a} == {_G64_TRAIN}, \
        'armed 帧:kernel 计划 up 序应含列车 core(装配段漏武装 = 原病)'
    assert placed_a >= 1 and drags_a and plan_empty_a is False

    # ---- disarmed 变体 ----
    calls.clear()
    sess_b = _session()   # locked_comp=''
    bench_read_b, deployed_read_b = _identity([_G64_TRAIN], dep)
    op_b, bp, fp, bk, drags_b = _make_rf_op(
        monkeypatch, sess=sess_b, bench_read=bench_read_b,
        deployed_read=deployed_read_b, cap=6)
    placed_b, _pe_b = _drive(op_b, bp, fp, bk)
    assert calls
    kw_b = calls[0]['kwargs']
    assert kw_b.get('recipe_floor_lock_exempt') is False
    up_b, _held_b, reasons_b = calls[0]['result']
    assert up_b == [], 'disarmed 帧:列车 core 被 kernel 门留 bench'
    assert reasons_b.get(0) == 'recipe_floor'
    assert drags_b == [] and placed_b == 0


# can_deploy_single 家族穿参烟测(shop 预检两调用点的判定面;缺省逐位同旧)
def test_can_deploy_single_family_passthrough() -> None:
    """can_deploy_single 新参透传:armed 帧列车 core 假想查询可落板,
    缺省仍拒(recipe_floor)——shop.py 两处预检接线的判定面(接线义务
    本体在 shop 调用侧,本锁钉 kernel API 家族语义)。"""
    dep = ['三月七', '瓦尔特', '姬子']
    fac = deployed_bond_counts(set(dep))
    bench: list[BenchChar] = []
    ok, why = can_deploy_single(
        _bc(_G64_TRAIN, 1), bench, deployed_cids=set(dep),
        deployed_fac=fac, board=dict(fac), cap=8,
        recipe_floor_lock_exempt=True)
    assert ok is True and why == ''
    ok2, why2 = can_deploy_single(
        _bc(_G64_TRAIN, 1), bench, deployed_cids=set(dep),
        deployed_fac=fac, board=dict(fac), cap=8)
    assert ok2 is False and why2 == 'recipe_floor'
