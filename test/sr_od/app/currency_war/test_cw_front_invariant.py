"""T-174 奖励节点停机根因·部署出口不变量锁面(ADR-0610)。

根因链(方案 v2,方案审放行附必改全落):①执行层 r241 换排纠正与主循环
前排保证对「前排非空」无单一所有权——上阵集合全 pref=back(flex→back)
形态下纠正把前排拖空,op 仍 success 返回;②恢复路由层 0j 重部署被
ADR-0601 板满失配闸短路,r250 场内前排保证永远不可达 → 备战环冻结,
环级无进展守卫停机留证。修复 = F1 出口不变量(禁清空前排守卫[调用内
动态计数] + r250 后置补位 + execute 收尾现读断言)+ F2 板满失配窄豁免
+ F3 0j 预算复位收紧。

设计出处 = ``.debug/temp/currency_war/attacks/t174_reward_node/修复方案.md``
v2(易失工作副本;持久收编 = docs/develop/currency_war/decisions/0610-*.md)。
锁编号 L1/L1b/L2/L2b/L2c/L3/L4/L4b/L5/L6 沿方案 §6.1 清单(L2c = 改动
三审 C1/D1 收口批新增:NO_BENCH 第三出口不变量);L7 回归面 =
既有 test_cw_deploy_battle_chain / test_cw_action_op_compliance
全绿不动(零决策层改动、闸三元组契约不动的界碑)。

变异打红口径(验收亲测记录见交付报告):
- 静态计数变异(守卫判定改对 _scr_fix 帧重复采样)→ L1b 红(L1 对
  静态/动态计数不具判别力,两读法同为 1——落地审 F-B 勘误口径);
- 守卫移除(拦下分支删除)→ L1 红(停机形态复现);
- 守卫检查移回 back_empty 检查之前 → L1c 红;
- 出口断言删除 → L2b 红;豁免门值分叉放开(PLANTOM 也可豁免)→ L4b 红;
- 复位条件回退无条件复位 → L6 红;
- NO_BENCH 早退复验移除 → L2c 红(改动三审 C1 收口批:备战栏槽未建模
  + 板全后排 + 前排空的蒙混 success 形态复现)。
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from one_dragon.base.geometry.point import Point

_ACT = '货币战争-备战'
_TPL = object()   # 模板哨兵(读函数全部桩化,模板对象不消费)

# 布局坐标(自建,绕开 screen_loader):备战栏 9 / 前排 4 / 后排 6。
BENCH = [Point(100 + 30 * i, 900) for i in range(9)]
FRONT = [Point(500 + 30 * i, 400) for i in range(4)]
BACK = [Point(500 + 30 * i, 650) for i in range(6)]


class _FrameTruth:
    """帧语义占用真值模型:screenshot = 捕获快照,slot 采样读快照。

    「静态帧重采样恒旧值」语义是 L1b 判别力的前提——静态读法变异(守卫
    判定改对 _scr_fix 帧重复采样)看到的是捕获时刻快照(前排 2 个占用),
    双放行清空前排;动态计数实现看到拖拽后的真值。模拟游戏侧真相:拖成 =
    源槽清空 + 落点槽占用(与验证是否读出无关)。
    """

    def __init__(self) -> None:
        self.occ: dict[tuple[int, int], bool] = {}
        self.shots: int = 0

    def set(self, pts: list, occupied: bool) -> None:
        for p in pts:
            self.occ[(int(p.x), int(p.y))] = occupied

    def is_occ(self, p: Point) -> bool:
        return self.occ.get((int(p.x), int(p.y)), False)

    def shot(self) -> dict[tuple[int, int], bool]:
        self.shots += 1
        return dict(self.occ)

    @staticmethod
    def slot_occ(scr, x: int, y: int) -> bool:
        return scr.get((int(x), int(y)), False)


def _bc(slot: int, char_id: str, cur_row: str) -> object:
    """BenchChar 快捷构造(cur_row = 现读行 front/back;pref 由注册表查)。"""
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    return BenchChar(slot=slot, char_id=char_id, position_pref=cur_row)


def _counters_ctx(counters: dict) -> SimpleNamespace:
    """带 cw4_counters 载体的 ctx 桩(分键断言用;last_state=None = 无
    决策侧黑板,deploy() 的板面视图腿安全走 None 分支)。"""
    return SimpleNamespace(
        cw_match=SimpleNamespace(session=SimpleNamespace(
            last_state=None,
            strategy_state=SimpleNamespace(cw4_counters=counters))))


def _fake_drag_fn(truth: _FrameTruth, drags: list, drag_ok: bool = True):
    """拖拽桩单一源(rowfix/deploy 两装配共用,复制桩体 = 漂移源头):
    记录 (src, dst);成功时按游戏侧真值改帧占用(源槽清空+落点占用)。"""

    def _drag(op, src, dst):
        drags.append((src, dst))
        if not drag_ok:
            return False
        truth.set([src], False)
        truth.set([dst], True)
        return True

    return _drag


def _mk_rowfix_op(monkeypatch, truth: _FrameTruth, deployed: list,
                  counters: dict | None = None,
                  drag_ok: bool = True) -> tuple[object, list]:
    """直驱 _fix_misplaced_rows 的桩 op(帧语义真值模型)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_deploy as db,
    )
    monkeypatch.setattr(db, 'slot_occupied', _FrameTruth.slot_occ)
    monkeypatch.setattr(db, 'read_deployed_chars',
                        lambda ctx, scr, tpl, level=None: list(deployed))
    monkeypatch.setattr(db.time, 'sleep', lambda s: None)
    drags: list = []
    monkeypatch.setattr(db.DragCwChar, 'drag_char',
                        _fake_drag_fn(truth, drags, drag_ok))

    class _Op(db.CwOpDeploy):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            pass
        def screenshot(self):
            return truth.shot()
        def _reconcile_tracking(self, templates):
            pass

    op = _Op()
    op.ctx = (_counters_ctx(counters) if counters is not None
              else SimpleNamespace(cw_match=None))
    return op, drags


def _mk_deploy_op(monkeypatch, truth: _FrameTruth, deployed: list,
                  counters: dict, *, cap: int, paddle_x: int,
                  drag_ok: bool = True,
                  flip_front_empty_after_first_shot: bool = False,
                  bench_slots: list | None = None,
                  ) -> tuple[object, list]:
    """deploy() 节点级桩(直驱 gate→豁免→出口断言全链)。

    ``flip_front_empty_after_first_shot``:第一次截图后把前排翻转为全空
    (L4b 判别力前提:若实现错误地对 PHANTOM 门值也跑豁免,判定帧看到
    「前排空」会通过 → 错误 success → 锁红;按门值短路则不可达)。
    ``bench_slots``:备战栏槽坐标(缺省 = 9 槽全建模;传 ``[]`` = 备战栏
    槽未建模识别退化态,L2c 场景——NO_BENCH 早退出口)。
    """
    from sr_od.application.currency_war.obs import cw_back_layout
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_deploy as db,
    )
    monkeypatch.setattr(db, 'slot_occupied', _FrameTruth.slot_occ)
    monkeypatch.setattr(db, 'read_deployed_chars',
                        lambda ctx, scr, tpl, level=None: list(deployed))
    monkeypatch.setattr(db, 'read_deploy_cap_debounced',
                        lambda ctx, scr, level: cap)
    monkeypatch.setattr(db, 'read_deployed_count', lambda ctx, scr: paddle_x)
    monkeypatch.setattr(db, 'bench_item_slots', lambda ctx, scr, fuzzy: set())
    monkeypatch.setattr(cw_back_layout, 'select_back_layout',
                        lambda ctx, scr, level=None, cap=None,
                        level_trusted=None: (6, ''))
    monkeypatch.setattr(db, 'save_decision_frame', lambda *a, **k: None)
    monkeypatch.setattr(db.time, 'sleep', lambda s: None)
    drags: list = []
    monkeypatch.setattr(db.DragCwChar, 'drag_char',
                        _fake_drag_fn(truth, drags, drag_ok))

    class _Op(db.CwOpDeploy):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            pass
        def screenshot(self):
            snap = truth.shot()
            # 翻转时点 = 闸帧(shot2,构造帧 shot1 已被 last_screenshot 消费)
            # 返回之后:闸判定帧保持 CV 全占,豁免判定帧(shot3+)见前排全空
            # ——若实现错误地对 PHANTOM 门值也跑豁免,判定会通过 → 错误
            # success → 本锁红(判别力前提;shot() 先自增后快照,故比较 2)。
            if flip_front_empty_after_first_shot and truth.shots == 2:
                truth.set(FRONT, False)
            return snap
        def round_by_find_area(self, screen, s1, s2, **kw):
            return SimpleNamespace(is_success=False)
        def _row_centers(self, prefix):
            bench = list(BENCH) if bench_slots is None else list(bench_slots)
            return {'备战栏': bench, '前排': list(FRONT)}.get(prefix, [])
        def _back_row_centers(self):
            return list(BACK)
        def _get_templates(self):
            return _TPL
        def _session_level(self):
            return None
        def _level_trusted(self):
            return None
        def _reconcile_tracking(self, templates):
            pass
        def _snapshot_equips_into_tracking(self):
            pass

    op = _Op()
    op.last_screenshot = truth.shot()   # deploy() overlay 三锚消费入口帧
    op.ctx = _counters_ctx(counters)
    op.ctx.screen_loader = SimpleNamespace(get_screen=lambda name: object())
    return op, drags


# ==================== L1:r241 禁清空前排守卫(反证锁) ====================

def test_l1_rowfix_guard_spares_last_front_char(monkeypatch) -> None:
    """L1 反证锁(方案 §6.1):上阵 = 前排1(pref=back 黑塔)+ 后排2
    (均 pref=back,钉死——含 pref=front 件时处理序决定分键,锁会顺序
    抖动)。守卫必须拦下把前排拖空的纠正(黑塔留前排);旧实现此帧必
    拖空前排 = T-174 停机形态复现。分键 rowfix_skip_front_invariant 计 1;
    无 counters 载体的退化 ctx 下 best-effort 不炸(缺省零漂移)。"""
    truth = _FrameTruth()
    truth.set(FRONT[:1], True)
    truth.set(BACK[:2], True)
    deployed = [_bc(1, '黑塔', 'front'),
                _bc(1, '翡翠', 'back'),
                _bc(2, '大丽花', 'back')]
    counters: dict = {}
    op, drags = _mk_rowfix_op(monkeypatch, truth, deployed, counters)
    op._fix_misplaced_rows(list(FRONT), list(BACK), _TPL)
    assert truth.is_occ(FRONT[0]), '前排最后一个角色不得被纠正拖空(停机形态复现)'
    assert not any(src.y == FRONT[0].y for src, _ in drags), \
        f'不得发生任何 front→back 拖拽,实得 {drags}'
    assert counters.get('rowfix_skip_front_invariant') == 1, \
        f'守卫拦截必须落分键,实得 {counters}'
    # 缺省零漂移:无状态载体的 ctx 上分键 best-effort 静默跳过,不炸。
    bare, _ = _mk_rowfix_op(monkeypatch, _FrameTruth(), [], counters=None)
    bare._bump_cw4_counter('rowfix_skip_front_invariant')


def test_l1c_backfull_skip_not_counted_as_invariant_guard(monkeypatch) -> None:
    """L1c 负锁(落地审 F-C):前排 1 人(pref=back 想回后排)∧ 后排满
    (无槽可拖)→ 移动因 back-full 不可行,不得计入 rowfix_skip_front_
    invariant 分键(该分键只辖「有槽可拖但会清空前排」的不变量拦截,
    误计 = 判读侧归因噪声);守卫判定位于 back_empty 检查之后。
    变异打红口径:守卫检查移回 back_empty 之前 → 本锁红。"""
    truth = _FrameTruth()
    truth.set(FRONT[:1], True)
    truth.set(BACK, True)          # 后排 6 槽全满
    deployed = [_bc(1, '黑塔', 'front'),
                _bc(1, '翡翠', 'back'),
                _bc(2, '大丽花', 'back'),
                _bc(3, '银狼', 'back')]
    counters: dict = {}
    op, drags = _mk_rowfix_op(monkeypatch, truth, deployed, counters)
    op._fix_misplaced_rows(list(FRONT), list(BACK), _TPL)
    assert truth.is_occ(FRONT[0]), '后排满形态下黑塔本就未被拖动'
    assert 'rowfix_skip_front_invariant' not in counters, \
        f'back-full 跳过不得计入守卫分键,实得 {counters}'


def test_l1b_two_back_pref_front_chars_admit_once(monkeypatch) -> None:
    """L1b 双前角色形态锁(F-1 配套;**静态计数实现唯一能被它抓住的锁**):
    上阵 = 前排 2 个(均 pref=back)+ 后排 1 个(pref=back)。动态计数在
    第一次 front→back 完成 −1 后,第二次移动必须被拦(只放行 1 次,前排
    占用 = 1);按静态读法实现时两次各自看到计数 2 双双放行 → 前排 0,
    本锁必红。帧语义桩(快照重采样恒旧值)是判别力前提。"""
    truth = _FrameTruth()
    truth.set(FRONT[:2], True)
    truth.set(BACK[:1], True)
    deployed = [_bc(1, '黑塔', 'front'),
                _bc(2, '翡翠', 'front'),
                _bc(1, '银狼', 'back')]
    op, drags = _mk_rowfix_op(monkeypatch, truth, deployed)
    op._fix_misplaced_rows(list(FRONT), list(BACK), _TPL)
    fb_drags = [(src, dst) for src, dst in drags if src.y == FRONT[0].y]
    assert len(fb_drags) == 1, \
        f'两次 front→back 只放行 1 次(动态计数 −1 后第二次被拦),实得 {fb_drags}'
    front_left = [p for p in FRONT if truth.is_occ(p)]
    assert len(front_left) == 1, \
        f'前排占用必须 = 1(静态读法实现此处 = 0 → 红),实得 {front_left}'


# ==================== L2/L2b/L2c:r250 后置补位 + 成功出口不变量(NOOP/NO_BENCH) ====================

def test_l2_post_rowfix_backfills_empty_front(monkeypatch) -> None:
    """L2 r250 后置补位(方案 §6.1):上阵 = 前排0 + 后排3(全 pref=back,
    T-174 冻结局形态)。修复后前排占用 = 1 且后排 = 2;出口不变量现读
    过(备战硬要求 > 站位偏好)。"""
    truth = _FrameTruth()
    truth.set(BACK[:3], True)
    deployed = [_bc(1, '翡翠', 'back'),
                _bc(2, '大丽花', 'back'),
                _bc(3, '银狼', 'back')]
    op, drags = _mk_rowfix_op(monkeypatch, truth, deployed)
    op._fix_misplaced_rows(list(FRONT), list(BACK), _TPL)
    assert truth.is_occ(FRONT[0]), '前排必须被补位到 ≥1'
    assert not truth.is_occ(BACK[0]) and truth.is_occ(BACK[1]) \
        and truth.is_occ(BACK[2]), '补位来源 = 后排第一槽(后排 3→2)'
    assert op._front_ok_now(list(FRONT), list(BACK)) is True, '出口断言应过'


def test_l2b_noop_exit_rejected_when_front_unfixable(monkeypatch) -> None:
    """L2b NOOP 出口不变量锁(F-2 配套):bench 空 early-return 路径 ∧
    板上有角色 ∧ 前排空 ∧ 补位修复失败(drag 3 次未动)→ success 出口
    被拒(round_fail 具名状态)——「success ⇒ 前排≥1」承诺覆盖 NOOP,
    禁「板有人而前排空」地以合法稳态蒙混返回。"""
    truth = _FrameTruth()
    truth.set(BACK[:3], True)
    deployed = [_bc(1, '翡翠', 'back'),
                _bc(2, '大丽花', 'back'),
                _bc(3, '银狼', 'back')]
    counters: dict = {}
    op, _ = _mk_deploy_op(monkeypatch, truth, deployed, counters,
                          cap=5, paddle_x=3, drag_ok=False)
    res = op.deploy()
    assert res.result.name == 'FAIL', \
        f'NOOP 出口必须被不变量断言拒绝,实得 {res.result.name}'
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        CwOpDeploy,
    )
    assert CwOpDeploy.STATUS_FRONT_INVARIANT_FAIL in (res.status or ''), \
        f'必须以具名状态 fail,实得 {res.status!r}'


def test_l2c_no_bench_exit_front_invariant(monkeypatch) -> None:
    """L2c NO_BENCH 第三出口不变量锁(改动三审 C1/D1 收口,ADR-0610
    §2.1):备战栏槽未建模(``_row_centers('备战栏')`` 返回空,识别退化
    态)∧ 板上全在后排 ∧ 前排空 → 早退不得以 STATUS_NO_BENCH 蒙混
    success(发射链拿到 success 即出战 → 游戏拒「前台区域无角色」,与
    1-1 冻结同型从另一未覆盖出口复发),必须具名 STATUS_FRONT_INVARIANT_
    FAIL round_fail——「success ⇒ 前排≥1」承诺覆盖第三出口。
    变异打红口径:早退前复验移除 → 本锁红(NO_BENCH success 形态复现)。
    反例半边:板真空时不变量前提不适用,NO_BENCH 合法稳态原样放行
    (修复只堵「板有人而前排空」,不得把合法出口整体堵死)。"""
    truth = _FrameTruth()
    truth.set(BACK[:3], True)
    deployed = [_bc(1, '翡翠', 'back'),
                _bc(2, '大丽花', 'back'),
                _bc(3, '银狼', 'back')]
    counters: dict = {}
    op, _ = _mk_deploy_op(monkeypatch, truth, deployed, counters,
                          cap=5, paddle_x=3, bench_slots=[])
    res = op.deploy()
    assert res.result.name == 'FAIL', \
        f'NO_BENCH 早退必须被不变量复验拒绝,实得 {res.status!r}'
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        CwOpDeploy,
    )
    assert CwOpDeploy.STATUS_FRONT_INVARIANT_FAIL in (res.status or ''), \
        f'必须以具名状态 fail,实得 {res.status!r}'
    assert CwOpDeploy.STATUS_NO_BENCH not in (res.status or ''), \
        '禁以合法稳态蒙混 success'
    # 反例半边:板真空 → 谓词「整板空 = 前提不适用」放行,合法稳态原样。
    truth2 = _FrameTruth()
    op2, _ = _mk_deploy_op(monkeypatch, truth2, [], counters,
                           cap=5, paddle_x=0, bench_slots=[])
    res2 = op2.deploy()
    assert res2.result.name == 'SUCCESS', \
        f'板真空时 NO_BENCH 合法稳态必须放行,实得 {res2.status!r}'
    assert CwOpDeploy.STATUS_NO_BENCH in (res2.status or ''), \
        f'必须保持原具名成功状态,实得 {res2.status!r}'


# ==================== L3:守卫与纠正的收敛二段 ====================

def test_l3_converges_in_two_calls(monkeypatch) -> None:
    """L3 收敛二段锁(方案 §6.1):前排1(pref=back 黑塔)+ 后排1
    (pref=front 飞霄)。第一段:守卫拦黑塔出前排,飞霄入前排(前排 ≥1,
    黑塔未被拖走);第二段(新调用新读数):黑塔归位后排、飞霄留前排
    ——防「被跳角色永不被挪回」回归(两种处理序均 ≤2 次调用收敛)。"""
    truth = _FrameTruth()
    truth.set(FRONT[:1], True)
    truth.set(BACK[:1], True)
    deployed = [_bc(1, '黑塔', 'front'), _bc(1, '飞霄', 'back')]
    op, drags1 = _mk_rowfix_op(monkeypatch, truth, deployed)
    op._fix_misplaced_rows(list(FRONT), list(BACK), _TPL)
    assert truth.is_occ(FRONT[0]) and truth.is_occ(FRONT[1]), \
        '第一段后前排 = 2(黑塔被守卫留下 ∧ 飞霄已入前排)'
    assert truth.is_occ(BACK[0]) is False, '飞霄已离开后排'
    # 第二段:重读后的形态(黑塔 cur=front 槽1,飞霄 cur=front 槽2)。
    deployed2 = [_bc(1, '黑塔', 'front'), _bc(2, '飞霄', 'front')]
    op2, drags2 = _mk_rowfix_op(monkeypatch, truth, deployed2)
    op2._fix_misplaced_rows(list(FRONT), list(BACK), _TPL)
    assert truth.is_occ(FRONT[0]) is False and truth.is_occ(FRONT[1]) is True, \
        '第二段后黑塔归位后排、飞霄留前排(pref 全归位)'
    assert truth.is_occ(BACK[0]) is True


# ==================== L4/L4b/L5:板满失配闸窄豁免 ====================

def test_l4_board_full_front_empty_exempts_to_rowfix(monkeypatch) -> None:
    """L4 豁免正锁(方案 §6.1):满板(仲裁 = cap)+ 前排 4 槽全空 +
    后排有人 → 场内换排修复后返回新具名成功状态(非 STATUS_BOARD_FULL_
    MISMATCH);现读前排 ≥1;分键 board_full_front_empty_rowfix 计 1。
    豁免恰覆盖「恢复需要 ∧ 拖拽可行」形态——0j 恢复链第一次可达 r250。"""
    truth = _FrameTruth()
    truth.set(BENCH[:2], True)   # bench 有角色(0j 无条件派发形态)
    truth.set(FRONT, False)
    truth.set(BACK[:6], True)    # CV 计 6,paddle=3 → 仲裁 3 ≥ cap=3 闸命中
    deployed = [_bc(1, '翡翠', 'back'), _bc(2, '大丽花', 'back'),
                _bc(3, '银狼', 'back')]
    counters: dict = {}
    op, _ = _mk_deploy_op(monkeypatch, truth, deployed, counters,
                          cap=3, paddle_x=3)
    res = op.deploy()
    assert res.result.name == 'SUCCESS', f'豁免修复应成功,实得 {res.status!r}'
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        CwOpDeploy,
    )
    assert CwOpDeploy.STATUS_ROWFIX_RECOVERED in (res.status or ''), \
        f'必须返回新具名成功状态,实得 {res.status!r}'
    assert CwOpDeploy.STATUS_BOARD_FULL_MISMATCH not in (res.status or '')
    assert counters.get('board_full_front_empty_rowfix') == 1, \
        f'豁免必须落分键,实得 {counters}'
    assert truth.is_occ(FRONT[0]), '修复后现读前排 ≥1'


def test_l4b_phantom_gate_never_exempt(monkeypatch) -> None:
    """L4b PHANTOM 门值负锁(F-5):闸值 = 幻影满板矛盾帧 ∧ 豁免判定帧
    现读前排空 → 仍 round_fail(PHANTOM 形态)——豁免按门值分叉的自由度
    被锁死,PHANTOM 永不豁免(CV 全占 ⇒ 前排非空的结构自排除 + 门值
    短路双重防线)。翻转钩使「若实现错误地对 PHANTOM 也跑豁免」时判定
    会通过 → 错误 success → 锁红(判别力前提)。"""
    truth = _FrameTruth()
    truth.set(BENCH[:2], True)
    truth.set(FRONT, True)     # 闸帧:CV 全占(前排4+后排6=10)
    truth.set(BACK[:6], True)
    deployed = [_bc(1, '翡翠', 'back'), _bc(2, '大丽花', 'back'),
                _bc(3, '银狼', 'back')]
    counters: dict = {}
    op, _ = _mk_deploy_op(monkeypatch, truth, deployed, counters,
                          cap=5, paddle_x=3,
                          flip_front_empty_after_first_shot=True)
    res = op.deploy()
    assert res.result.name == 'FAIL', '幻影满板矛盾帧不得以任何形态 success'
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        CwOpDeploy,
    )
    assert CwOpDeploy.STATUS_PHANTOM_FULL_BOARD in (res.status or ''), \
        f'PHANTOM 门值必须原样速报,实得 {res.status!r}'
    assert CwOpDeploy.STATUS_ROWFIX_RECOVERED not in (res.status or '')
    assert 'board_full_front_empty_rowfix' not in counters, \
        '豁免分键不得计数(PHANTOM 永不进豁免)'


def test_l5_exemption_narrow_front_occupied_still_fails(monkeypatch) -> None:
    """L5 豁免窄度负锁(方案 §6.1):满板 + 前排有人 → 仍返
    STATUS_BOARD_FULL_MISMATCH(豁免不扩散;ADR-0601 原语义不动)。"""
    truth = _FrameTruth()
    truth.set(BENCH[:2], True)
    truth.set(FRONT[:2], True)   # 前排有人
    truth.set(BACK[:4], True)
    deployed = [_bc(1, '翡翠', 'front'), _bc(2, '黑塔', 'front'),
                _bc(1, '大丽花', 'back'), _bc(2, '银狼', 'back')]
    counters: dict = {}
    op, _ = _mk_deploy_op(monkeypatch, truth, deployed, counters,
                          cap=3, paddle_x=3)
    res = op.deploy()
    assert res.result.name == 'FAIL'
    from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
        CwOpDeploy,
    )
    assert CwOpDeploy.STATUS_BOARD_FULL_MISMATCH in (res.status or ''), \
        f'满板∧前排有人必须维持原闸 fail 语义,实得 {res.status!r}'
    assert 'board_full_front_empty_rowfix' not in counters


# ==================== L6:0j 预算复位收紧(F3) ====================

def test_l6_frontless_budget_reset_tightened() -> None:
    """L6 0j 预算复位锁(F3,方案 §6.1):复位条件 = 环 success ∧
    (本环未发射 StartBattle ∨ launch_ok)——StartBattle 验证失败的环
    在外循环仍记 round_success(1-1 冻结局实证该形态每环误复位预算,
    两次显示 (1/2)),不得复位;读后即清防跨环残留。写点 = 备战单轮
    执行记账处(StartBattle 是终结动作,每环至多一写)。变异:复位条件
    回退无条件复位 → 本锁红。"""
    from sr_od.application.currency_war.kernel.cw_exec_state import ExecState
    from sr_od.application.currency_war.operations import cw_loop
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep,
    )
    loop_src = inspect.getsource(cw_loop.CwLoop.loop)
    i_read = loop_src.find("last_prep_battle_launch_ok")
    assert i_read > 0, '备战环出口未读发射结果(F3 复位收紧失守)'
    i_cond = loop_src.find('if _launch_ok is not False:', i_read)
    assert i_cond > 0, '复位条件缺失(StartBattle 验证失败帧不得复位)'
    i_reset = loop_src.find('self._frontless_redeploy = 0', i_cond)
    assert 0 < i_reset < loop_src.find('\n', i_cond) + 2000, \
        '预算复位必须在收紧条件之内'
    i_clear = loop_src.find('last_prep_battle_launch_ok = None', i_cond)
    assert i_clear > i_reset, '消费后必须清 None(防跨环残留)'
    prep_src = inspect.getsource(cw_screen_prep.CwScreenPrep.run)
    assert 'isinstance(action, StartBattle)' in prep_src and \
        'last_prep_battle_launch_ok' in prep_src, \
        '备战单轮执行记账处缺发射结果写入端'
    field = ExecState.__dataclass_fields__.get('last_prep_battle_launch_ok')
    assert field is not None and field.default is None, \
        'ExecState 缺 last_prep_battle_launch_ok 字段或缺省非 None(三态约定)'
