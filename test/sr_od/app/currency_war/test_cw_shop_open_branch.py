"""外循环「开商店」分支(0n,备战子态族)锁:判定/商店访问转交/序位。

背景(实机事故,2026-09-06 进度流水「外循环开商店分支批」):商店浮层不遮
备战双锚锚区,双锚判据在商店开着时穿透命中 → 备战分支内的达标臂发射面把
部署/出战点击打在浮层上被挡。治本 = 分支序新增 0n(先于备战双锚),判据 =
cw_loop._shop_open_anchors_hit 三 id_mark(idmark 审计批定稿,互斥依据 =
干净备战帧「按钮-收起」不存在)。

锁语义重推(ADR-0562,用户裁定 2026-09-06):分支处理由「硬编码点收起交回
重判」改为「转交商店访问路径」——委托 CwScreenPrep.visit_open_shop(入口
观察 → 策略器逐动作决策 → CloseShop 终结收店)。「收不收」由策略器基于
期望态决定(CloseShop = 商店画面 op 的一等终结动作),路由层不越权。行为锁
随之由「收起点击+分键」重推为「商店访问被调用+关店终结发生」;判定互斥锁
与序位锁语义不变。

分层声明:本文件管「0n 分支路由与转交」;序位全局矩阵(先于备战双锚)
单一源 = test_cw_dispatch_order_matrix.py(本分支已登记其矩阵);商店访问
编排与策略器决策路径锁单一源 = test_cw_shop_open_visit.py,两文件
不重复锁同一语义。
"""
import inspect

import pytest

from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.operations.sr_operation import SrOperation
from test.conftest import SrTestContext

# --------------------------------------------------------------------------- #
# fixture 判定锁(真 screen_info + 真 OCR,离线配对验证的测试侧固化)
# --------------------------------------------------------------------------- #

class _ProbeOp(SrOperation):
    """真锚判定探针:真 SrOperation(test_context 离线装配,手法同
    test_cw_shop_refresh._BuyPhaseHostOp)——round_by_find_area 判定链
    与生产同源(真 screen_loader + 真 OCR)。"""

    def __init__(self, ctx):
        SrOperation.__init__(self, ctx, op_name='cw-0n判定探针')


def _shop_open_hit(test_context: SrTestContext, screen) -> bool:
    """0n 分支判据单一源直调(生产 _shop_open_anchors_hit)。"""
    from sr_od.application.currency_war.operations.cw_loop import (
        _shop_open_anchors_hit,
    )
    return _shop_open_anchors_hit(_ProbeOp(test_context), screen)


def _load(test_context: SrTestContext, screen_name: str, state: str):
    if not test_context.has_screen(screen_name, state):
        pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')
    return test_context.load_screen(screen_name, state)


@pytest.mark.parametrize('anchor', ['备战标识-购买经验', '按钮-收起',
                                    '标识-备战阶段'])
def test_shop_open_frame_each_anchor_hits(test_context: SrTestContext,
                                          anchor: str) -> None:
    """开商店 fixture 帧:三 id_mark 锚逐个命中(idmark 审计批离线验证
    shop_open is_precise 的测试侧固化)。"""
    screen = _load(test_context, '货币战争-备战-开商店', 'shop_open')
    r = _ProbeOp(test_context).round_by_find_area(
        screen, '货币战争-备战-开商店', anchor, crop_first=False)
    assert r.is_success, (
        f'开商店帧锚 {anchor} 未命中(建档漂移信号:对照 idmark 审计表 §三)')


def test_shop_open_branch_judgment_hits_on_shop_frame(
        test_context: SrTestContext) -> None:
    """分支判定锁(正):开商店 fixture 帧 → 三锚全命中 → 0n 分支命中。"""
    screen = _load(test_context, '货币战争-备战-开商店', 'shop_open')
    assert _shop_open_hit(test_context, screen), (
        '开商店帧 0n 判据未命中——分支将漏派,商店穿透事故复发面')


def test_shop_open_branch_judgment_clean_on_closed_prep_frame(
        test_context: SrTestContext) -> None:
    """分支判定锁(反,互斥):干净备战帧(shop_closed)→ 0n 判据零命中
    (「按钮-收起」不存在;idmark 审计表 §三 离线配对验证的固化)。"""
    screen = _load(test_context, '货币战争-备战', 'shop_closed')
    assert not _shop_open_hit(test_context, screen), (
        '干净备战帧误命中 0n——互斥破缺,正常备战会被误收店')


# --------------------------------------------------------------------------- #
# 行为锁:loop 驱动 → 转交商店访问路径 + 命中/结果分键(ADR-0562 重推)
# --------------------------------------------------------------------------- #

class _Res:
    def __init__(self, ok: bool):
        self.is_success = ok


def _drive_loop_shop_open(monkeypatch, *, shop_hit: bool):
    """桩 loop 驱动:商店三锚按 shop_hit 命中/全 miss,备战双锚恒命中
    (穿透形态——事故形态:商店开 ∧ 双锚透出)。
    返回 (clicks, counters, visits):visits = CwScreenPrep.visit_open_shop
    的调用记录 [(返回 ok, detail)]。"""
    from sr_od.application.currency_war.operations import cw_loop

    visits: list[tuple[bool, str]] = []

    class _FakePrep:
        def __init__(self, ctx):
            pass

        def visit_open_shop(self, *a, **k):
            visits.append((True, '买牌 测试'))
            return visits[-1]

        def execute(self):
            return None   # 负例落穿 0 系进备战分支(与本锁无关,桩化)

    monkeypatch.setattr(cw_loop, 'CwScreenPrep', _FakePrep)
    # 负例路径落穿 0 系进备战分支后的节点探针(收益耗尽臂 supply 排除读)
    # 与本锁无关:桩化为空序列(否则需补 screen_loader 全链离线装配)。
    monkeypatch.setattr(cw_loop, 'read_node_sequence', lambda ctx, screen: [])
    # 备战分支策略失活检查走遥测(test 进程默认 enabled)→ 关掉,免
    # read_phase_round 的 screen_loader 离线装配;本锁不辖失活判据。
    from sr_od.application.currency_war.telemetry import state as _tel_state
    monkeypatch.setattr(_tel_state, 'get_recorder',
                        lambda: type('R', (), {'enabled': False})())
    # 备战环前清场(试用揭示卡/书册卡)的槽位读需 screen_loader 离线装配:
    # 桩空槽位 → 清场环零迭代,直落 CwScreenPrep(桩)。本锁不辖清场链。
    from sr_od.application.currency_war.obs import cw_identity_obs as _cio
    monkeypatch.setattr(_cio, '_ctx_slots', lambda *a, **k: [])
    monkeypatch.setattr(_cio, 'find_trial_reveal_cards', lambda *a, **k: [])
    monkeypatch.setattr(_cio, 'find_bookcards', lambda *a, **k: [])
    clicks: list[tuple[str, str]] = []

    class _Loop(cw_loop.CwLoop):
        _iter = 2
        _is_new_match = False
        _cw_locked_resume = False
        _cw_back_btn_count = 0
        _battle_ts = None
        _cw_resume_candidate = False   # 恢复局检测不进(与本锁无关)
        _max_rounds = None             # 可控轮数停点不进(与本锁无关)

        def __init__(self):  # noqa: D107 桩:bypass SrOperation.__init__
            pass

        @property
        def last_screenshot(self):
            return self._screen

        @last_screenshot.setter
        def last_screenshot(self, v):
            pass

        def _stall_watch_tick(self, screen):
            pass

        def screenshot(self):
            return self._screen

        def round_by_find_area(self, screen, s1, s2, **kw):
            if s1 == '货币战争-备战-开商店' and s2 in (
                    '备战标识-购买经验', '按钮-收起', '标识-备战阶段'):
                return _Res(shop_hit)
            if s1 == '货币战争-备战' and s2 in ('备战标识-购买经验',
                                                '按钮-出战'):
                return _Res(True)   # 双锚穿透形态(事故形态)
            return _Res(False)

        def round_by_ocr(self, *a, **kw):
            return _Res(False)

        def round_by_ocr_and_click(self, *a, **kw):
            return _Res(False)

        def round_by_find(self, *a, **kw):
            return _Res(False)

        def round_by_find_and_click_area(self, screen, s1, s2, **kw):
            clicks.append((s1, s2))
            return _Res(True)

        def round_wait(self, wait=1.0, status=''):
            return ('wait', status)

    op = _Loop()
    op._screen = object()
    sess = type('S', (), {})()
    state_of(sess).target_comp = None
    sess.last_state = None
    sess.last_prep_action_sig = None
    state_of(sess).cw4_counters = {}
    match = type('M', (), {})()
    match.session = sess
    ctx = type('C', (), {})()
    ctx.cw_match = match
    # 0p BOSS 简报 OCR 链(负例路径落穿 0 系到 boss 排他读)用:空文本
    ctx.ocr_service = type('O', (), {})()
    ctx.ocr_service.get_ocr_result_list = lambda **kw: []
    op.ctx = ctx
    op.loop()
    return clicks, state_of(sess).cw4_counters, visits


def test_loop_shop_open_delegates_to_shop_visit(monkeypatch) -> None:
    """转交锁(ADR-0562 重推):商店态穿透帧 → visit_open_shop 恰被调用
    一次(商店访问被调用)+ 路由层零「按钮-收起」点击(收不收由策略器
    决定,CloseShop 终结在访问编排内)+ 命中/结果分键零静默。"""
    clicks, counters, visits = _drive_loop_shop_open(monkeypatch, shop_hit=True)
    assert len(visits) == 1 and visits[0][0] is True, (
        f'商店态须转交商店访问路径(visit_open_shop):{visits}')
    assert ('货币战争-备战-开商店', '按钮-收起') not in clicks, (
        '路由层禁硬编码收店点击(收不收归策略器/CloseShop 终结,ADR-0562)')
    assert counters.get('branch_shop_open_hit') == 1, (
        '分支命中分键零静默(branch_shop_open_hit)')
    assert counters.get('branch_shop_open_visit_ok') == 1, (
        '商店访问结果分键零静默(branch_shop_open_visit_ok)')


def test_clean_prep_frame_zero_shop_branch(monkeypatch) -> None:
    """反例行为锁:干净备战形态(商店锚全 miss ∧ 双锚命中)→ 零转交、
    分键零命中。fixture 帧侧互斥已由判定锁钉死,此处锁 loop 路由面。"""
    clicks, counters, visits = _drive_loop_shop_open(monkeypatch, shop_hit=False)
    assert visits == [], '干净备战帧不得转交商店访问路径'
    assert 'branch_shop_open_hit' not in counters, (
        '未命中不得写分键(零静默 = 分键只记真命中)')


# --------------------------------------------------------------------------- #
# 序位锁:0n 相邻 0m(备战子态族同段)、先于 0j 与备战双锚
# --------------------------------------------------------------------------- #

def test_shop_open_branch_position_adjacent_to_dark_lock() -> None:
    """序位锁(源码级):0n 分支判定位于 0m 暗色锁定分支之后、0j 之前、
    备战双锚判定之前——「备战子态族」同段语义的序位声明(设计裁定:
    与 0m 相邻放置;互斥依据与穿透机制写在 0n 分支注释,写给无会话
    历史的读者)。"""
    from sr_od.application.currency_war.operations import cw_loop
    src = inspect.getsource(cw_loop)
    # 锚定串取分支体独有文本(DISPATCH_AREA_ANCHORS 枚举行在文件更早处
    # 含同名锚,find 首中会落表行,锁不到分支位置)。
    i_shop = src.find('if _shop_open_anchors_hit(self, screen):')
    i_0m = src.find('for _lock_screen, _lock_area in (')
    i_0j = src.find('前台无角色重部署')
    i_prep = src.find("if (self.round_by_find_area(screen, '货币战争-备战', "
                      "'备战标识-购买经验')")
    for name, i in (('0n 开商店分支', i_shop), ('0m 暗色锁定', i_0m),
                    ('0j 前台无角色', i_0j), ('备战双锚', i_prep)):
        assert i >= 0, f'{name} 判定行未找到(源码结构变更,本锁须同步)'
    assert i_0m < i_shop < i_0j, (
        '0n 须与 0m 暗色锁定分支相邻同段(备战子态族序位原则)')
    assert i_shop < i_prep, (
        '0n 必须先于备战双锚判定(浮层穿透事故的序位治本点)')


# --------------------------------------------------------------------------- #
# N1 补(落地审 0e0a3077):判据单一源的三锚成员与画面档 id_mark 定稿一致
# --------------------------------------------------------------------------- #

def test_shop_open_anchors_members_match_screen_file() -> None:
    """判据单一源 `_shop_open_anchors_hit` 引用的 (画面, 锚) 对恰好等于
    idmark 审计批定稿的三锚(购买经验+按钮-收起+标识-备战阶段)——防判据
    私加/改名漂移与画面档脱钩(源码级:提取函数体内全部 round_by_find_area
    引用对,集合严格相等)。"""
    import inspect
    import re

    from sr_od.application.currency_war.operations import cw_loop
    fn_src = inspect.getsource(cw_loop._shop_open_anchors_hit)
    pairs = set(re.findall(
        r"round_by_find_area\(\s*screen,\s*'([^']+)'\s*,\s*'([^']+)'",
        fn_src))
    expected = {
        ('货币战争-备战-开商店', '备战标识-购买经验'),
        ('货币战争-备战-开商店', '按钮-收起'),
        ('货币战争-备战-开商店', '标识-备战阶段'),
    }
    assert pairs == expected, (
        f'开商店判据锚集漂移:多余={pairs - expected} '
        f'缺失={expected - pairs}(id_mark 定稿见 '
        f'idmark_audit/审计表.md;改锚集须先过画面档审计)')
