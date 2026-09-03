"""test_cw_overlay_gates 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- adr0263_overlay_guard: test_cw_adr0263_overlay_guard.py
- overlay_registry: test_cw_overlay_registry.py
- w559_overlay_gates: test_cw_w559_overlay_gates.py
- w721_overlay_b_budget: test_cw_w721_overlay_b_budget.py
- w724_overlay_a_rank: test_cw_w724_overlay_a_rank.py
- test_skip_shop_overlay: test_skip_shop_overlay.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations

# ==================== adr0263_overlay_guard ====================
import numpy as np
import pytest

from one_dragon.base.geometry.rectangle import Rect

# 证据帧(034f8ef3)实测:金币说明面板标题锚 pc_rect (1000,370,1165,435),
# 覆盖带盖备战栏 slot6 (1004,847,1118,978);slot1 (382,845,495,979) 在带外。
_SLOT6 = Rect(1004, 847, 1118, 978)


class _OcrItem:
    """最小 OcrMatchResult 替身(守卫只读 .data)。"""

    def __init__(self, data: str) -> None:
        self.data = data


class _FakeCtx:
    """只喂 cw_obs_core 依赖(_area_rect/_ocr 均被 monkeypatch,不需要真服务)。"""

    run_context = None


@pytest.fixture
def anchor_env(monkeypatch):
    """mock cw_obs_core 的 area/OCR 依赖:锚 area 恒有 rect,OCR 返回锚文本。"""
    from sr_od.application.currency_war.kernel import cw_obs_core

    class _Item:
        data = '金币说明'

    monkeypatch.setattr(cw_obs_core, '_area_rect',
                        lambda ctx, name, screen_name=None: Rect(1000, 370, 1165, 435))
    monkeypatch.setattr(cw_obs_core, '_ocr', lambda ctx, screen, rect: [_Item()])
    return cw_obs_core, monkeypatch


def test_gold_anchor_hit(anchor_env) -> None:
    """金币说明锚 OCR 命中 → overlay 判开(True)。"""
    mod, _ = anchor_env
    ctx = _FakeCtx()
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    assert mod.gold_info_overlay_open(ctx, screen) is True


def test_gold_anchor_miss(anchor_env, monkeypatch) -> None:
    """锚 OCR 未命中(overlay 关)→ False。"""
    mod, _ = anchor_env
    monkeypatch.setattr(mod, '_ocr', lambda ctx, screen, rect: [])
    ctx = _FakeCtx()
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    assert mod.gold_info_overlay_open(ctx, screen) is False


def test_gold_anchor_area_missing(anchor_env, monkeypatch) -> None:
    """锚 area 缺失(screen_info 无档)→ best-effort False(不拦)。"""
    mod, _ = anchor_env
    monkeypatch.setattr(mod, '_area_rect',
                        lambda ctx, name, screen_name=None: None)
    ctx = _FakeCtx()
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    assert mod.gold_info_overlay_open(ctx, screen) is False


def test_overlay_registry_retired() -> None:
    """ADR-0263 Revision:_KNOWN_OVERLAYS / prep_areas_unobstructed 退役删除,
    全仓(src)无引用残留。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    assert not hasattr(cw_obs_core, 'prep_areas_unobstructed')
    assert not hasattr(cw_obs_core, '_KNOWN_OVERLAYS')


# ===== 钩子层:summon 钩子三态(mock OCR/CV,验证排除链接线) =====

class _FakeOcrService:
    def __init__(self, texts: list[str]) -> None:
        self._texts = [_OcrItem(t) for t in texts]

    def get_ocr_result_list(self, **kwargs):   # noqa: ANN003 ARG003 兼容签名
        return list(self._texts)


class _FakeRunContext:
    def __init__(self) -> None:
        self.stops: list[str] = []

    def stop_running(self, reason: str = '') -> None:
        self.stops.append(reason)


class _HookCtx(_FakeCtx):
    def __init__(self, ocr_texts: list[str]) -> None:
        self.ocr_service = _FakeOcrService(ocr_texts)
        self.run_context = _FakeRunContext()


@pytest.fixture
def hook_env(monkeypatch, tmp_path):
    """mock 掉 CV/OCR 依赖,只留 summon 钩子判定链(chdir tmp 防真实 .debug 落盘)。"""
    from sr_od.application.currency_war.kernel import cw_obs_core, cw_observe
    from sr_od.application.currency_war.obs import currency_war_cv, cw_identity_obs
    monkeypatch.chdir(tmp_path)
    # 生产约定:.debug/temp/currency_war/ 已存在(flag/shots 落盘处);tmp 里预建,
    # 否则 flag write_text 抛错被钩子外层 best-effort except 吞掉,测不到停机分支
    (tmp_path / '.debug/temp/currency_war').mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cw_identity_obs, 'identify_slots', lambda *a, **k: [])
    monkeypatch.setattr(cw_identity_obs, '_ctx_slots',
                        lambda ctx, prefix, count: [(6, _SLOT6)])
    monkeypatch.setattr(cw_identity_obs, 'find_supply_boxes', lambda screen, slots: [])
    monkeypatch.setattr(cw_identity_obs, 'find_tomes', lambda screen, slots: [])
    monkeypatch.setattr(cw_identity_obs, 'find_bookcards', lambda screen, slots: [])
    # cw_identity_obs 顶部 `from cw_obs_core import _area_rect` 绑定的是直接引用,
    # 面板守卫(按钮-装备推荐)走它 → 两侧都要 patch(角色详情面板 area 缺 → None)
    monkeypatch.setattr(cw_identity_obs, '_area_rect',
                        lambda ctx, name, screen_name=None: None)
    monkeypatch.setattr(cw_obs_core, 'is_prep_like_frame', lambda ctx, screen: True)
    monkeypatch.setattr(currency_war_cv, 'slot_occupied', lambda screen, x, y: True)
    # 锚接线:标识-金币说明 area 有 rect,OCR 由 per-test 控制
    monkeypatch.setattr(cw_obs_core, '_area_rect',
                        lambda ctx, name, screen_name=None:
                        Rect(1000, 370, 1165, 435) if name == '标识-金币说明' else None)
    shots: list[str] = []

    def _fake_shot(screen, prefix):
        shots.append(prefix)
        return f'{prefix}.png'

    monkeypatch.setattr(cw_observe, 'cw_shot_unique', _fake_shot)
    return cw_identity_obs, cw_obs_core, shots, tmp_path, monkeypatch


def test_summon_hook_skips_when_overlay_open(hook_env) -> None:
    """局69 误触态:slot6 占用未识别 + 金币说明锚命中 → 排除,不停机。"""
    mod, core, shots, tmp_path, monkeypatch = hook_env

    class _Item:
        data = '金币说明'

    monkeypatch.setattr(core, '_ocr', lambda ctx, screen, rect: [_Item()])
    ctx = _HookCtx(['连胜', '金币说明', '2-4'])
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    mod.read_bench_chars(ctx, screen, None)
    assert ctx.run_context.stops == []                     # 不停机
    assert shots == []                                     # 不采证
    assert not (tmp_path / '.debug/temp/currency_war/summon_stop_hook.flag').exists()


def test_summon_hook_stops_when_overlay_closed(hook_env) -> None:
    """对照态:锚 OCR 未命中(overlay 关)→ 正常判定停机 + sentinel flag。"""
    mod, core, shots, tmp_path, monkeypatch = hook_env
    monkeypatch.setattr(core, '_ocr', lambda ctx, screen, rect: [])
    ctx = _HookCtx(['备战阶段', '金币 35'])
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    mod.read_bench_chars(ctx, screen, None)
    assert ctx.run_context.stops == ['hook:summon_unknown']
    assert shots == ['summon_unknown']
    assert (tmp_path / '.debug/temp/currency_war/summon_stop_hook.flag').exists()


def test_summon_hook_skips_when_upper_screen(hook_env) -> None:
    """ADR-0269 两段式:帧态门(上层屏在场)在前,非 prep-like 帧不停机
    (即使金币说明锚也未命中)。"""
    mod, core, shots, tmp_path, monkeypatch = hook_env
    monkeypatch.setattr(core, 'is_prep_like_frame', lambda ctx, screen: False)
    monkeypatch.setattr(core, '_ocr', lambda ctx, screen, rect: [])
    ctx = _HookCtx(['选择伙伴'])
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    mod.read_bench_chars(ctx, screen, None)
    assert ctx.run_context.stops == []
    assert shots == []


# ==================== overlay_registry ====================

import importlib
import pkgutil
from pathlib import Path as _overlay_registry_Path

import pytest as _overlay_registry_pytest
import yaml

from sr_od.application.currency_war.kernel import cw_overlay_registry as reg

REPO = _overlay_registry_Path(__file__).resolve().parents[5]
SCREEN_INFO_DIR = REPO / 'assets' / 'game_data' / 'screen_info'


def _load_screen_areas() -> dict[str, set[str]]:
    """screen_name → 该画面建档 area 名全集(读 screen_info yml 单一源)。"""
    out: dict[str, set[str]] = {}
    for fp in SCREEN_INFO_DIR.glob('*.yml'):
        if fp.name == '_od_merged.yml':
            continue
        data = yaml.safe_load(fp.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not data.get('screen_name'):
            continue
        areas = {a.get('area_name') for a in (data.get('area_list') or [])
                 if isinstance(a, dict)}
        out[data['screen_name']] = areas
    return out


def _import_handler(class_name: str) -> type:
    """按类名在 handler / cw_screen 承载包的各子模块中 import。

    类不经包 ``__init__`` 导出(项目约定 ``__init__`` 默认不暴露模块),
    须逐子模块 getattr;两包全找不到即 AssertionError。
    """
    last_err: Exception | None = None
    for pkg_name in (
        'sr_od.application.currency_war.operations.cw_screen',
        'sr_od.application.currency_war.operations.cw_op',
        'sr_od.application.currency_war.operations.cw_flow',
    ):
        pkg = importlib.import_module(pkg_name)
        for mod in pkgutil.iter_modules(pkg.__path__):
            try:
                obj = getattr(importlib.import_module(f'{pkg_name}.{mod.name}'),
                              class_name)
            except (ImportError, AttributeError) as e:   # noqa: PERF203
                last_err = e
                continue
            return obj
    raise AssertionError(f'handler {class_name!r} 不可 import: {last_err}')


# ── 断言 1:建档完整性 ──

def test_1_onboarding_completeness() -> None:
    """激活条目的 screen/anchor/close_area 均已建档于 screen_info yml。

    未激活条目(0e3/0f,待子批 0 实机建档)豁免——screen_name 本身是
    占位名,建档后置 active=True 时本断言自动接管。
    """
    areas = _load_screen_areas()
    for spec in reg.OVERLAY_REGISTRY:
        if not spec.active:
            assert not spec.anchor_area, \
                f'{spec.screen_name} 未激活却已写锚(建档前锚名会漂移)'
            continue
        assert spec.screen_name in areas, f'{spec.screen_name} 无画面档'
        assert spec.anchor_area in areas[spec.screen_name], (
            f'{spec.screen_name}.{spec.anchor_area} 识别锚未建档')
        if spec.close_area:
            assert spec.close_area in areas[spec.screen_name], (
                f'{spec.screen_name}.{spec.close_area} 关闭按钮未建档')


# ── 断言 2:handler 存在性 ──

def test_2_decision_handler_present_and_importable() -> None:
    """decision 条目 handler 非空且可 import;收拢挂账集须精确对账。"""
    referenced: set[str] = set()
    for spec in reg.OVERLAY_REGISTRY:
        if spec.handler_id:
            referenced.add(spec.handler_id)
        if not spec.active:
            continue
        if spec.semantic == reg.SEMANTIC_DECISION:
            assert spec.handler_id, f'{spec.screen_name} decision 无 handler'
        if spec.handler_id in reg.PENDING_HANDLER_IDS:
            continue   # C 面收拢挂账(当前仅 HandleStarTome),切换批清空
        if not spec.handler_id:
            continue   # display/system 条目 handler_id='' 是合法缺省(无专属 handler),不做 import 检查
        _import_handler(spec.handler_id)
    # 挂账集 ⊆ registry 引用集,且挂账集非空必须有事由(防静默腐化)
    assert referenced >= reg.PENDING_HANDLER_IDS, \
        f'挂账集出现 registry 未引用的 handler: {reg.PENDING_HANDLER_IDS - referenced}'


# ── 断言 3:C1 红线 ──

def test_3_c1_red_line_decision_not_closable() -> None:
    """decision ⇒ closable is False;清场派生集不含 decision 条目。"""
    for spec in reg.OVERLAY_REGISTRY:
        if spec.semantic == reg.SEMANTIC_DECISION:
            assert spec.closable is False, (
                f'{spec.screen_name} 是决策 overlay 却可清场(关闭即丢决策'
                f'内容,C1 事故同型)')
        else:
            assert spec.bail_tag == '', \
                f'{spec.screen_name} 非决策条目却带 bail_tag'
    clear_names = {s.screen_name for s in reg.derive_clearable()}
    for spec in reg.derive_decision():
        assert spec.screen_name not in clear_names, (
            f'清场派生集含 decision 条目 {spec.screen_name}')
    # 红线防回归锚:遭遇节点(C1 事故屏)永不在清场派生集
    assert '货币战争-遭遇节点' not in clear_names


# ── 断言 4:bail_tag 唯一 ──

def test_4_bail_tag_unique() -> None:
    """decision 条目 bail_tag 非空且全表唯一(同因计数键正确性前提)。"""
    tags = [s.bail_tag for s in reg.OVERLAY_REGISTRY if s.bail_tag]
    assert len(tags) == len(set(tags)), f'bail_tag 重复: {tags}'
    for spec in reg.OVERLAY_REGISTRY:
        if spec.active and spec.semantic == reg.SEMANTIC_DECISION:
            assert spec.bail_tag, f'{spec.screen_name} decision 无 bail_tag'


# ── 断言 5:registry 全条目 ∈ UPPER_SCREENS 派生集 ──

def test_5_registry_entries_in_upper_screens() -> None:
    """激活条目全部被帧态门名单覆盖(新增建档即自动排除,防名单孤儿)。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    upper = set(cw_obs_core.UPPER_SCREENS)
    for spec in reg.OVERLAY_REGISTRY:
        if spec.active:
            assert spec.screen_name in upper, (
                f'{spec.screen_name} 在注册表却不在 UPPER_SCREENS(帧态门漏排)')


# ── 断言 6:dispatch_priority 唯一 ──

def test_6_dispatch_priority_unique() -> None:
    """C 面派发优先序全表唯一(含未激活条目,防激活时撞序)。"""
    pris = [s.dispatch_priority for s in reg.OVERLAY_REGISTRY]
    assert len(pris) == len(set(pris)), f'dispatch_priority 重复: {pris}'


# ── 断言 7:close_action 载荷完整性 ──

def test_7_close_action_payload() -> None:
    """退场动作与载荷互斥完整:point 有界内坐标 / close_area 非空 / handle 有 handler。"""
    for spec in reg.OVERLAY_REGISTRY:
        if spec.close_action == reg.CLOSE_ACTION_POINT:
            assert spec.close_point is not None, \
                f'{spec.screen_name} point 动作缺 close_point'
            x, y = spec.close_point
            assert 0 <= x <= 1920 and 0 <= y <= 1080, \
                f'{spec.screen_name} close_point {(x, y)} 越出 1080p 界'
        elif spec.close_action == reg.CLOSE_ACTION_AREA:
            assert spec.close_area, f'{spec.screen_name} close_area 动作缺按钮 area'
        elif spec.close_action == reg.CLOSE_ACTION_HANDLE:
            assert spec.handler_id, f'{spec.screen_name} handle 动作缺 handler'
        # esc 无需载荷(负向校验:不得残留矛盾载荷)
        if spec.close_action == reg.CLOSE_ACTION_ESC:
            assert spec.close_area == '' and spec.close_point is None, \
                f'{spec.screen_name} esc 动作带多余载荷'


# ── 断言 8:常量 = 派生值(防手改绕过派生)──

def test_8_upper_screens_equals_derived() -> None:
    """UPPER_SCREENS 常量逐位等于「registry 派生段 + 非 overlay 残余段」。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    expected = reg.derive_upper_screens() + cw_obs_core.UPPER_SCREENS_NON_OVERLAY
    assert expected == cw_obs_core.UPPER_SCREENS, (
        'UPPER_SCREENS 常量与派生值不一致——名单被手改而未走注册表/残余段')


# ── 残余段问责 ──

def test_residual_segment_disjoint_and_registered() -> None:
    """残余段与 registry 无交集,且每个残余屏名真实建档。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    reg_names = {s.screen_name for s in reg.OVERLAY_REGISTRY}
    yml_names = set(_load_screen_areas())
    for name in cw_obs_core.UPPER_SCREENS_NON_OVERLAY:
        assert name not in reg_names, f'{name} 属残余段却又在注册表(双源)'
        assert name in yml_names, f'残余段屏 {name!r} 未在 screen_info 注册'


# ══ A 面(P0 清场)已切换锁组 ══

#: A 面切换后的清场派生集黄金值(= derive_clearable():激活 ∧ closable,
#: 声明序)。相对迁移前手写 5 条清场表的**两处成员收缩**:星徽秘典弹窗、
#: 补给 decision 化(关闭即丢决策内容,设计定案 5)后退出清场,改走
#: event_overlay bail → 0i 选卡 / CwScreenSupplyNode 消化。
_GOLDEN_CLEAR_MAP: dict[str, str] = {
    '货币战争-积分奖励': '按钮-关闭',
    '货币战争-中断挑战弹窗': '按钮-关闭',
    '货币战争-武装箱弹窗': '按钮-关闭',
}


def test_aface_clear_set_switched_to_registry() -> None:
    """A 面已切换:清场表 = 注册表派生桥接,手写 5 条 dict 删除。

    接线锁两件(2026-09-03 攻击性排查:原 ①「派生值==黄金」冻结钉删除——
    注册表合法演进(新增 overlay)也会红 = change-detector;不变量由
    常驻断言组(唯一性/载荷/常量=派生)辖定):② gate 源码消费
    ``derive_clearable`` 且不再含手写清场条目字面量(单一源收拢,
    黄金表仅作负向扫描枚举源);③ 被移出的两屏仍在 decision 派生集
    (退出路径=bail→handler,不是裸消失)。
    """
    import inspect

    from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        ENTRY_OVERLAY_CLOSE,
    )
    # ② 接线锁(2026-09-03 gate 清尾批:清场表迁址 gate→cw_screen_prep,
    #    锁语义平移):源码走 derive_clearable,手写条目不回流
    src = inspect.getsource(cw_screen_prep)
    assert 'derive_clearable()' in src, '清场表未接线 derive_clearable()'
    for _scr, _area in _GOLDEN_CLEAR_MAP.items():
        assert f"'{_scr}': '{_area}'" not in src, (
            f'清场手写条目 {_scr} 仍在清场表(单一源未收拢)')
    assert ENTRY_OVERLAY_CLOSE, '清场派生集不应为空(接线面失效)'
    # ③ 移出成员的退出路径存在性:两屏 ∈ decision 派生集(bail→handler)
    # (依赖不变量:从清场移出的屏必须有 bail 接管,否则该屏无人处理)
    decision_names = {s.screen_name for s in reg.derive_decision()}
    assert '货币战争-星徽秘典弹窗' in decision_names
    assert '货币战争-补给' in decision_names


def test_aface_clear_judgment_per_fixture_frame() -> None:
    """变更语义 fixture 断言锁:对「单 overlay 在场」的 mock 帧剧本,
    环入口清场段(``CwScreenPrep._clear_entry_overlays``,消费循环未改、
    判定源换成注册表派生)的点击行为逐帧锁定:

    - 星徽秘典弹窗在场 → **不点**其关闭钮(A 面行为变化 1:移出清场,
      改走 0i 选卡;旧行为会点「按钮-关闭」丢选卡内容);
    - 补给在场 → **不点**「按钮-返回备战界面」(行为变化 2:移出清场,
      改走 bail → CwScreenSupplyNode 消化);
    - 武装箱弹窗在场 → 仍点「按钮-关闭」(清场留存成员,防过度收缩)。

    帧模型:monkeypatch ``screen_utils.get_match_screen_name`` 只对剧本
    屏命中(其余屏全部 miss),点击经替身记录——纯离线,零真实 IO。
    """
    from types import SimpleNamespace

    from one_dragon.base.screen import screen_utils
    from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep

    def _run_clear(visible: str) -> list[tuple[str, str]]:
        d = cw_screen_prep.CwScreenPrep.__new__(cw_screen_prep.CwScreenPrep)
        d.ctx = SimpleNamespace(current_instance_idx=99)
        d.screenshot = lambda: object()   # 帧本体不被消费(锚判定全桩)
        clicks: list[tuple[str, str]] = []

        def _fake_click(_frame, screen, area, **_kw):
            clicks.append((screen, area))
        d.round_by_find_and_click_area = _fake_click

        def _fake_match(*, ctx, screen, screen_name_list, crop_first=False):
            return visible if visible in screen_name_list else None

        mp = _overlay_registry_pytest.MonkeyPatch()
        try:
            mp.setattr(screen_utils, 'get_match_screen_name', _fake_match)
            mp.setattr(cw_screen_prep.time, 'sleep', lambda _s: None)
            d._clear_entry_overlays()
        finally:
            mp.undo()
        return clicks

    # 行为变化 1:星徽秘典不再被清场关闭(旧行为会点 按钮-关闭)
    clicks = _run_clear('货币战争-星徽秘典弹窗')
    assert clicks == [], (
        f'星徽秘典弹窗仍被环入口清场关闭(应走 0i 选卡消化): {clicks}')
    # 行为变化 2:补给不再被「返回备战界面」一键离场(应走 CwScreenSupplyNode)
    clicks = _run_clear('货币战争-补给')
    assert clicks == [], (
        f'补给 modal 仍被环入口一键离场(应走 bail→CwScreenSupplyNode): {clicks}')
    # 留存成员仍清:武装箱弹窗在场 → 点「按钮-关闭」(mock 帧不随点击变化,
    # 每轮清场轮重复命中同屏 → 断言每次点击都是该关闭钮,无其它屏混入)
    clicks = _run_clear('货币战争-武装箱弹窗')
    assert clicks and set(clicks) == {('货币战争-武装箱弹窗', '按钮-关闭')}, (
        f'武装箱弹窗清场行为漂移: {clicks}')


#: B 面切换前的手写 bail 清单黄金集(切换批零漂移对拍基准;单一源收拢后
#: 本常量只存在于测试,作为历史黄金基准防接线漂移)。
_GOLDEN_BAIL_LIST: tuple[tuple[str, str, str], ...] = (
    ('货币战争-盛会之星', '标识-盛会之星', 'megastar'),
    ('货币战争-列车同行', '标识-选择伙伴', 'partner'),
    ('货币战争-祈愿试炼', '标识-祈愿试炼', 'wish_trial'),
    ('货币战争-星徽秘典弹窗', '标识-星徽秘典', 'star_tome'),
    ('货币战争-备战-专家邀请函', '标识-专家邀请函', 'bookcard'),
    ('货币战争-遭遇节点', '标识-遭遇节点', 'encounter'),
    ('货币战争-投资策略', '标识-请选择投资策略', 'invest_strategy'),
    ('货币战争-投资环境', '标识-投资环境', 'invest_env'),
    ('货币战争-补给', '标识-补给阶段', 'supply'),
)


def _golden_bail_set() -> set[tuple[str, str, str]]:
    return set(_GOLDEN_BAIL_LIST)


def test_zero_behavior_bail_list_switched_to_registry() -> None:
    """B 面已切换:director bail 扫描消费 derive_decision(),手写 9 条清单删除。

    接线锁两件(2026-09-03 攻击性排查:原 ③「派生集==黄金集」冻结钉删除
    ——注册表合法演进也红,change-detector;不变量由常驻断言组辖定):
    ① 源码含 derive_decision 消费;② 黄金表仅作负向扫描枚举源:手写
    (screen, area, tag) 元组字面量不得回流单一源。
    """
    import inspect

    from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep
    src = inspect.getsource(cw_screen_prep)
    assert 'derive_decision' in src, 'bail 扫描未接线 derive_decision()'
    for _scr, _area, _tag in _GOLDEN_BAIL_LIST:
        assert f"('{_scr}', '{_area}', '{_tag}')" not in src, (
            f'bail 手写清单条目 {_tag} 仍在 cw_screen_prep(单一源未收拢)')


# (2026-09-03 攻击性排查:原 test_zero_drift_bail_judgment_per_frame_fixture、
#  test_zero_behavior_upper_screens_golden、test_zero_behavior_bail_scan_matches_
#  registry_decision_set 三条删除——均为「冻结时刻值」等值断言:黄金序/25 屏
#  手抄集/9 tag 集。注册表合法演进(新增 overlay/屏)即红且需手改黄金 =
#  change-detector;不变量面由常驻断言组(test_4 唯一性/test_5 注册表⊆名单/
#  test_8 常量=派生/残余段问责)辖定。黄金表保留仅作 ② 负向扫描枚举源。)


# ==================== w559_overlay_gates ====================

import pytest as _w559_overlay_gates_pytest

_FLOAT_SCREEN = '货币战争-备战-装备详情浮窗'
_TIP_SCREEN = '货币战争-备战-角色信息提示'


def _load(ctx, screen: str, state: str):
    if not ctx.has_screen(screen, state):
        _w559_overlay_gates_pytest.skip(f'fixture 缺:screens/{screen}/{state}.webp')
    return ctx.load_screen(screen, state)


@_w559_overlay_gates_pytest.mark.parametrize('state', ['equip_detail_roller', 'equip_detail_synth_target'])
def test_float_anchor_hits_fixtures(test_context, state: str) -> None:
    """浮窗锚「可合成列表」在两张真值帧上命中(排除门成立的根)。"""
    from one_dragon.base.screen import screen_utils
    frame = _load(test_context, _FLOAT_SCREEN, state)
    assert screen_utils.get_match_screen_name(
        ctx=test_context, screen=frame,
        screen_name_list=[_FLOAT_SCREEN], crop_first=False) == _FLOAT_SCREEN, (
        f'浮窗锚在 {state} 上失配——两段式将放行该帧(overlay 门漏复发)')


@_w559_overlay_gates_pytest.mark.parametrize('state', ['equip_detail_roller', 'equip_detail_synth_target'])
def test_prep_like_frame_rejects_equip_float(test_context, state: str) -> None:
    """浮窗帧 is_prep_like_frame 必 False(备战 readers/钩子不得在其上跑)。"""
    from sr_od.application.currency_war.kernel.cw_obs_core import is_prep_like_frame
    frame = _load(test_context, _FLOAT_SCREEN, state)
    assert is_prep_like_frame(test_context, frame) is False, (
        f'装备详情浮窗帧 {state} 被判 prep-like(锚失配门漏回归)')


def test_char_tooltip_anchor_hits_fixture(test_context) -> None:
    """提示锚「携带装备」在真值帧上命中。"""
    from one_dragon.base.screen import screen_utils
    frame = _load(test_context, _TIP_SCREEN, 'char_detail')
    assert screen_utils.get_match_screen_name(
        ctx=test_context, screen=frame,
        screen_name_list=[_TIP_SCREEN], crop_first=False) == _TIP_SCREEN, (
        '提示锚在 char_detail 上失配——两段式将放行该帧(overlay 门漏复发)')


def test_prep_like_frame_rejects_char_tooltip(test_context) -> None:
    """tooltip 帧 is_prep_like_frame 必 False。"""
    from sr_od.application.currency_war.kernel.cw_obs_core import is_prep_like_frame
    frame = _load(test_context, _TIP_SCREEN, 'char_detail')
    assert is_prep_like_frame(test_context, frame) is False, (
        '角色信息提示帧被判 prep-like(锚失配门漏回归)')


def test_big_panel_frame_still_rejected(test_context) -> None:
    """大面板形态(信息tab,原 档锚覆盖)仍被排除——拆分不削原有覆盖。"""
    from sr_od.application.currency_war.kernel.cw_obs_core import is_prep_like_frame
    frame = _load(test_context, '货币战争-备战-角色详情', '信息tab')
    assert is_prep_like_frame(test_context, frame) is False, (
        '角色详情大面板帧不再被排除(拆分削了原有覆盖)')


def test_new_anchors_not_hit_clean_prep(test_context) -> None:
    """防过度排除:新锚不得命中干净备战帧(否则备战帧被误判上层屏)。"""
    from one_dragon.base.screen import screen_utils
    frame = _load(test_context, '货币战争-备战', 'r1_idle_stop')
    for screen in (_FLOAT_SCREEN, _TIP_SCREEN):
        assert screen_utils.get_match_screen_name(
            ctx=test_context, screen=frame,
            screen_name_list=[screen], crop_first=False) is None, (
            f'{screen} 锚误命中干净备战帧 → 备战帧被误排除(过度排除)')


def test_prep_positive_sample_not_rejected(test_context) -> None:
    """备战正样本帧仍 True(门语义改动防反向回归)。"""
    from sr_od.application.currency_war.kernel.cw_obs_core import is_prep_like_frame
    frame = _load(test_context, '货币战争-备战', 'r1_idle_stop')
    assert is_prep_like_frame(test_context, frame) is True, (
        '备战正样本帧被判非 prep-like(过度排除)')


# ==================== w721_overlay_b_budget ====================

import dataclasses
import inspect
import math

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_economy import (
    REFRESH_ROLL_CAP,
    refresh_ev_budget,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    intention_core,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import BENCH_CAPACITY, GameState

_REG = DEFAULT_REGISTRY


def _state(*, gold: int = 200, level: int = 5, hp: int = 80) -> GameState:
    """溢余帧工厂(塌缩/帽判据在非应急带常态溢余帧上判)。"""
    return GameState(
        plane=1, round_num=5, gold=gold, level=level, hp=hp,
        shop_refresh_cost=2, deployed=[],
        bench=[None] * BENCH_CAPACITY, shop=[], node_type='battle',
        board={})


def _locked_session(cost_want: int) -> StrategySession:
    """锁定核 session 工厂:意向锁到「意向核心费用档 == cost_want」的
    第一条 comp 线(判据面只依赖核心费档,不依赖具体线)。"""
    for comp in COMP_LIBRARY:
        core = intention_core(comp)
        ch = CHARACTERS.get(core)
        if ch is not None and ch.cost == cost_want:
            sess = StrategySession()
            sess.v3_intention = IntentionState(
                phase='locked', locked_comp=comp.name)
            return sess
    raise AssertionError(f'无费用档 {cost_want} 的意向核心 comp(注册表漂移?)')


# --- 归零腿:塌缩带契约 -------------------------------------------------------


def test_collapse_band_zeroes_budget_on_locked_core() -> None:
    """塌缩带归零锁(ADR-0475):锁定 4 费核 ∧ 当前级 5(比值
    refresh_prob(5,4)/refresh_prob(峰值级,4)≈0.05 < ω=0.1)→ 预算 0
    (合法 0 帧第三类;金量式恒给 6,归零只能来自概率分量)。"""
    st = _state(gold=200, level=5)
    sess = _locked_session(4)
    assert refresh_ev_budget(st, sess) == 0


def test_collapse_judgment_strict_below_threshold() -> None:
    """ω 严格小于判据:比值恰等于阈值不归零(边界取「不归零」侧——
    归零是禁刷,宁松勿误杀;注入 ω=0.05 与比值 0.05 帧 → 不归零)。"""
    st = _state(gold=200, level=5)
    sess = _locked_session(4)
    reg = dataclasses.replace(_REG, omega_collapse_ratio=0.05)
    assert refresh_ev_budget(st, sess, reg) > 0


def test_eval_order_collapse_precedes_cap() -> None:
    """求值次序锁:塌缩带归零与帽取交前先判归零——金量式与帽都远大于 0
    的帧(g=200)预算为 0,只能由归零腿产生(次序颠倒不改变结果,锁钉
    「归零帧不受帽腿豁免」的契约形状)。"""
    st = _state(gold=200, level=5)
    sess = _locked_session(4)
    assert refresh_ev_budget(st, sess) == 0
    # 注入小 q(帽腿收紧)不改变归零结果
    reg = dataclasses.replace(_REG, refresh_find_quantile=0.9)
    assert refresh_ev_budget(st, sess, reg) == 0


# --- 空帧豁免:D1 契约 --------------------------------------------------------


def test_fallback_chain_frame_exempt_from_collapse() -> None:
    """空帧豁免锁(ADR-0475):同一塌缩形态帧(4 费档比值 0.05)在
    未锁定意向帧(兜底链,兜底 2 费非真目标)不归零——对假目标算塌缩比
    会误杀真目标(别的费档)搜索量(D1「空帧不缩供给」契约优先)。"""
    st = _state(gold=200, level=5)
    sess = StrategySession()          # 无锁定意向 → 兜底链空帧
    assert refresh_ev_budget(st, sess) > 0


# --- 帽腿:分位公式手算对拍 ----------------------------------------------------


def test_find_cap_quantile_formula_hand_recalc() -> None:
    """帽公式锁(ADR-0475):预算 = min(6, ⌊溢余/刷价⌋,
    ⌈−ln(1−q)·E_find⌉) 逐项手算对拍——E_find 直接调 cw_shop_odds
    (对拍侧与实现侧同源,公式锁钉的是闭合形状不是数值巧合)。注入
    q=0.05 使帽腿 <6 实际参与 min(默认 q=0.8 的帽在 E_find 放大量级下
    结构性不绑定,SPECS B-v2 §3 已声明)。"""
    from sr_od.application.currency_war.data.cw_shop_odds import (
        expected_refreshes_for_card,
    )
    st = _state(gold=200, level=6)
    sess = StrategySession()          # 兜底链 2 费:非塌缩带
    q = 0.05
    reg = dataclasses.replace(_REG, refresh_find_quantile=q)
    e_find = expected_refreshes_for_card(6, 2, target_star=2, owned=0)
    expect = min(REFRESH_ROLL_CAP, (200 - 50) // 2,
                 math.ceil(-math.log(1.0 - q) * e_find))
    assert expect < REFRESH_ROLL_CAP   # 前置:帽腿确实参与(非恒真锁)
    assert refresh_ev_budget(st, sess, reg) == expect


def test_budget_domain_stays_within_roll_cap() -> None:
    """预算边界锁(ADR-0475):任意 (level, q, ω) 注入组合下预算 ∈
    [0, REFRESH_ROLL_CAP](帽/归零只收紧不放大;6 刷帽单一源不变)。"""
    import itertools
    sess = StrategySession()
    for level, q, omega in itertools.product((4, 6, 8), (0.5, 0.8, 0.9),
                                             (0.05, 0.1, 0.3)):
        reg = dataclasses.replace(_REG, refresh_find_quantile=q,
                                  omega_collapse_ratio=omega)
        st = _state(gold=200, level=level)
        b = refresh_ev_budget(st, sess, reg)
        assert 0 <= b <= REFRESH_ROLL_CAP


# --- 概率单一址:与分配器同源互指 ----------------------------------------------


def test_single_probability_source_no_second_odds_address() -> None:
    """概率单一址锁(ADR-0475;W720 互指条款):两腿都消费
    cw_shop_odds 的既有概率符号,禁第二概率口径——行为证明:把
    expected_refreshes_for_card 换哨兵值,帽腿随之变;把 refresh_prob
    换 0,归零腿随之触发。实现侧若自建概率表,本锁两段都会翻。"""
    import sr_od.application.currency_war.data.cw_shop_odds as odds
    st = _state(gold=200, level=6)
    sess = StrategySession()

    orig_e = odds.expected_refreshes_for_card
    odds.expected_refreshes_for_card = (
        lambda level, cost, target_star, owned=0, non_target_taken=0: 0.5)
    try:
        b = refresh_ev_budget(st, sess, _REG)
        assert b == min(REFRESH_ROLL_CAP, 75, math.ceil(-math.log(0.2) * 0.5))
    finally:
        odds.expected_refreshes_for_card = orig_e

    st5 = _state(gold=200, level=5)
    sess5 = _locked_session(4)
    orig_p = odds.refresh_prob
    odds.refresh_prob = lambda level, cost: 0.0
    try:
        assert refresh_ev_budget(st5, sess5, _REG) == 0
    finally:
        odds.refresh_prob = orig_p


def test_allocator_refresh_estimator_same_odds_source() -> None:
    """分配器互指锁(ADR-0475;W720 统一纪律②):B 的归零腿概率源与
    分配器 Π_refresh 估计器(``allocator._refresh_dpeff_estimate``)同址
    ——两侧都从 cw_shop_odds 取 refresh_prob(结构锁:源码含同一 import
    单一址;行为级同源证明见上锁)。"""
    from sr_od.application.currency_war.decision.decision_v2 import allocator
    src = inspect.getsource(allocator._refresh_dpeff_estimate)
    assert 'cw_shop_odds import refresh_prob' in src
    from sr_od.application.currency_war.kernel import cw_economy
    src_e = inspect.getsource(cw_economy)
    assert 'cw_shop_odds import refresh_prob' in src_e


# ==================== w724_overlay_a_rank ====================

import dataclasses as _w724_overlay_a_rank_dataclasses
import logging

import pytest as _w724_overlay_a_rank_pytest

from sr_od.application.currency_war.decision.cw_strategy import (
    StrategySession as _w724_overlay_a_rank_StrategySession,
)
from sr_od.application.currency_war.decision.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision.decision_v2.ev import RoundPosture
from sr_od.application.currency_war.decision.decision_v2.posture import Posture
from sr_od.application.currency_war.decision.decision_v2.posture_release import (
    ReleaseDirective,
    channel_rank_scope,
    rank_refresh_vs_upgrade,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY as _w724_overlay_a_rank_DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY as _w724_overlay_a_rank_BENCH_CAPACITY,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    LevelUp,
    RefreshShop,
)
from sr_od.application.currency_war.kernel.cw_state import (
    GameState as _w724_overlay_a_rank_GameState,
)


@_w724_overlay_a_rank_pytest.fixture(autouse=True)
def _quiet_logging():
    """本模块测试期间静音日志(测试域收口)。

    进程级 logging.disable 是全局态:pytest 在收集期 import 本模块,模块级
    调用即对整个测试会话生效,会静默饿死其他测试依赖日志落盘的断言
    (判例:test_log_utils_utf8_rollover_continuity 因此 FileNotFoundError)。
    收口为 autouse fixture:进入本模块测试时禁用,退出时还原原级别。
    """
    prev = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(prev)


_w724_overlay_a_rank_REG = _w724_overlay_a_rank_DEFAULT_REGISTRY
# 关行为锁显式注入(危机臂开臂后默认 registry=True,ADR-0503;让位语义
# 锁改注入 False 仍测,不删。同 w611/w633 形态)。
_REG_CRISIS_OFF = _w724_overlay_a_rank_dataclasses.replace(_w724_overlay_a_rank_REG, crisis_release_enabled=False)


def _w724_overlay_a_rank_state(*, gold: int = 80, hp: int = 80, level: int = 6,
           deployed_n: int = 6, bench_n: int = 1,
           plane: int = 1, r: int = 5) -> _w724_overlay_a_rank_GameState:
    """cap 满员(deployed_n=6)溢余帧工厂;deployed_n=5 造第三路径辖区。"""
    return _w724_overlay_a_rank_GameState(
        plane=plane, round_num=r, gold=gold, level=level, hp=hp,
        shop_refresh_cost=2,
        deployed=[BenchChar(slot=20 + i, char_id=f'杂{i}', faction='公司',
                            star=1) for i in range(deployed_n)],
        bench=[BenchChar(slot=i, char_id=f'席{i}', faction='公司', star=1)
               for i in range(bench_n)]
        + [None] * (_w724_overlay_a_rank_BENCH_CAPACITY - bench_n),
        shop=[], node_type='battle', board={})


def _sess_of(state: _w724_overlay_a_rank_GameState) -> _w724_overlay_a_rank_StrategySession:
    """裸 session(release_directive/flip_hit 的 registry 均显式传参)。"""
    return _w724_overlay_a_rank_StrategySession()


def _flip_session(state: _w724_overlay_a_rank_GameState, *, third_path: bool = False,
                  level_up: bool = True) -> _w724_overlay_a_rank_StrategySession:
    """flip 义务帧 session(v3_release=flip 指令 + 包装后 level_up 姿态,
    与生产链 evaluate_release 写入形态同构)。"""
    s = _w724_overlay_a_rank_StrategySession()
    s.v3_release = ReleaseDirective(budget_gold=20, rolls=10,
                                    third_path=third_path, reason='flip')
    s.v3_dp_posture = RoundPosture(
        (state.plane, state.round_num),
        Posture(save=False, level_up=level_up, refresh_budget=6,
                tag='release'))
    return s


# --- ① 排序契约 ---------------------------------------------------------------


def test_rank_upgrade_first_when_saving_covers_fee(monkeypatch) -> None:
    """升级边际覆盖费率锁:省刷金 ≥ 升级费 → 'upgrade_first'(现行固定序
    零漂移;边际口径=省刷金/升级费,单一址两函数输出之比)。"""
    from sr_od.application.currency_war.decision.decision_v2 import ev as _ev
    from sr_od.application.currency_war.kernel import cw_economy
    st = _w724_overlay_a_rank_state()
    monkeypatch.setattr(_ev, 'levelup_refresh_saving',
                        lambda *a, **k: 100.0)
    monkeypatch.setattr(cw_economy, 'upgrade_plan_fee',
                        lambda *a, **k: 10)
    assert rank_refresh_vs_upgrade(st, _flip_session(st), _w724_overlay_a_rank_REG) \
        == 'upgrade_first'


def test_rank_refresh_first_when_saving_below_fee(monkeypatch) -> None:
    """反方向错序修正锁(SPECS A-v2 §3 病灶 1):省刷金 < 升级费 →
    'refresh_first'(刷新先吃溢余残差;峰值级 saving=0 帧即此形态)。"""
    from sr_od.application.currency_war.decision.decision_v2 import ev as _ev
    st = _w724_overlay_a_rank_state()
    monkeypatch.setattr(_ev, 'levelup_refresh_saving',
                        lambda *a, **k: 0.0)   # 峰值级 ΔE≤0 → saving=0
    assert rank_refresh_vs_upgrade(st, _flip_session(st), _w724_overlay_a_rank_REG) \
        == 'refresh_first'


def test_rank_margins_hand_recalc_from_single_addresses() -> None:
    """手算对拍锁:真实查表帧上排序结果 == (saving ≥ fee) 不等式——
    两腿对拍侧与实现侧同源(ev.levelup_refresh_saving 内部消费
    cw_shop_odds.expected_refreshes_for_card;升级费=kernel.upgrade_plan_fee),
    锁钉「比较形状」不锁数值巧合(帧取锁定核 1★ 副本未齐的常态溢余帧)。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.decision.decision_v2.ev import (
        levelup_refresh_saving,
    )
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    from sr_od.application.currency_war.kernel.cw_economy import upgrade_plan_fee
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
        intention_core,
    )
    # 锁定核 comp:bench 放 1★ 核心 1 张(saving 的 owned 输入非退化)
    comp = next(c for c in COMP_LIBRARY
                if CHARACTERS.get(intention_core(c)) is not None
                and (CHARACTERS[intention_core(c)].cost or 0) > 0)
    core = intention_core(comp)
    st = _w724_overlay_a_rank_state(gold=90, bench_n=1)
    st.bench[0] = BenchChar(slot=0, char_id=core,
                            faction=(CHARACTERS[core].factions
                                     or ('?',))[0], star=1)
    s = _w724_overlay_a_rank_StrategySession()
    s.v3_intention = IntentionState(phase='locked', locked_comp=comp.name)
    saving = levelup_refresh_saving(st, s, _w724_overlay_a_rank_REG)
    fee = upgrade_plan_fee(st)
    expect = 'upgrade_first' if saving >= fee else 'refresh_first'
    assert rank_refresh_vs_upgrade(st, s, _w724_overlay_a_rank_REG) == expect


# --- ② flip 谓词辖域(ADR-0445 现语义,W720 修订要点①)--------------------------


def test_scope_requires_flip_release_frame() -> None:
    """辖域=flip 义务帧单一址(session.v3_release.reason=='flip'):
    非 flip 帧无指令不辖(只排其一不辖,行为零漂移);reserve_admission
    指令帧不辖。"""
    st = _w724_overlay_a_rank_state()
    assert not channel_rank_scope(st, _w724_overlay_a_rank_StrategySession())
    s2 = _w724_overlay_a_rank_StrategySession()
    s2.v3_release = ReleaseDirective(budget_gold=0, rolls=0,
                                     reason='reserve_admission')
    assert not channel_rank_scope(st, s2)


def test_scope_excludes_third_path_and_free_slot() -> None:
    """第三路径辖区(deployed<cap,slot 守卫已压 level_up)不辖——人口
    解锁边际本窗=0 由第三路径自辖,排序不得覆写(W720 修订要点①:
    cap 满员使第三路径不先截);third_path 指令帧同不辖。"""
    st_free = _w724_overlay_a_rank_state(deployed_n=5)   # deployed<cap:第三路径辖区
    assert not channel_rank_scope(st_free, _flip_session(st_free))
    st_full = _w724_overlay_a_rank_state()
    assert channel_rank_scope(st_full, _flip_session(st_full))
    s_tp = _flip_session(st_full, third_path=True)
    assert not channel_rank_scope(st_full, s_tp)


def test_scope_requires_wrapped_level_up() -> None:
    """包装后 posture.level_up=False 帧(DP 未说升/第三路径压掉)不辖:
    只辖「升级 ∧ 刷新并存」帧(SPECS A-v2 §1 复合谓词第二枝)。"""
    st = _w724_overlay_a_rank_state()
    assert not channel_rank_scope(st, _flip_session(st, level_up=False))


def test_scope_predicate_uses_adr0445_flip_semantics() -> None:
    """flip 谓词语义对照锁(ADR-0445 纯溢余判定):辖域继承 flip_hit 的
    现语义——经生产链 release_directive 取指令:应急带帧(hp≤25)flip
    让位(指令非 flip,不辖)、息线以内(g≤R*)无 flip 指令不辖;溢余段
    flip 帧辖,且 hp 高低/可信位无关(旧血量复合谓词不得回归)。
    危机臂开臂(ADR-0503)后默认 registry 在应急帧产 crisis 指令,本锁
    的「应急帧无 flip」半边注入 crisis_release_enabled=False 重推钉护
    (让位结构语义,同 w611/w633 形态);默认态下应急帧产 crisis 指令
    属宽辖域另一辖域,由 w917 锁组辖——本测试同时对照两者防语义漂移。"""
    from sr_od.application.currency_war.decision.decision_v2.posture_release import (
        release_directive,
    )
    st_low = _w724_overlay_a_rank_state(gold=80, hp=25)   # 应急辖区,flip 让位
    posture_low = Posture(save=False, level_up=True, refresh_budget=6)
    d = release_directive(st_low, _sess_of(st_low), _w724_overlay_a_rank_REG, 'FORM',
                          posture_low)
    assert d is None or d.reason != 'flip'
    # 关行为半边(注入 OFF):让位结构在关臂时钉死为「无任何指令」。
    assert release_directive(st_low, _sess_of(st_low), _REG_CRISIS_OFF,
                             'FORM', posture_low) is None
    # 默认态对照:该帧确产 crisis 指令(宽辖域,ADR-0503 如实声明)。
    assert d is not None and d.reason == 'crisis'
    st_hp39 = _w724_overlay_a_rank_state(gold=80, hp=39)
    st_hp100 = _w724_overlay_a_rank_state(gold=80, hp=100)
    st_hp100.hp_readable = False
    st_hp100.hp_trusted = False      # 100 兜底假帧也辖(血量维度退场)
    for st in (st_hp39, st_hp100):
        d = release_directive(st, _sess_of(st), _w724_overlay_a_rank_REG, 'FORM',
                              Posture(save=False, level_up=True,
                                      refresh_budget=6))
        assert d is not None and d.reason == 'flip'
        assert channel_rank_scope(st, _flip_session(st))
    st_narrow = _w724_overlay_a_rank_state(gold=48)      # 息线以内:溢余判定不 fire
    d = release_directive(st_narrow, _sess_of(st_narrow), _w724_overlay_a_rank_REG, 'FORM',
                          Posture(save=False, level_up=True,
                                  refresh_budget=6))
    assert d is None or d.reason != 'flip'


# --- ③ 单一址互指(W720 修订要点②)---------------------------------------------


def test_rank_single_address_probability_source(monkeypatch) -> None:
    """概率单一址行为锁:排序两腿只消费既有概率符号——monkeypatch
    cw_shop_odds.expected_refreshes_for_card(级联进 saving)使 saving
    归零 → 排序翻到 refresh_first;实现若自建概率表,本锁翻红(W720
    互指条款:与分配器 Π_refresh 估计器同源,禁第二概率口径)。"""
    import sr_od.application.currency_war.data.cw_shop_odds as odds
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
        intention_core,
    )
    comp = next(c for c in COMP_LIBRARY
                if CHARACTERS.get(intention_core(c)) is not None
                and (CHARACTERS[intention_core(c)].cost or 0) > 0)
    core = intention_core(comp)
    st = _w724_overlay_a_rank_state(gold=90, bench_n=1)
    st.bench[0] = BenchChar(slot=0, char_id=core,
                            faction=(CHARACTERS[core].factions
                                     or ('?',))[0], star=1)
    s = _w724_overlay_a_rank_StrategySession()
    s.v3_intention = IntentionState(phase='locked', locked_comp=comp.name)
    orig = odds.expected_refreshes_for_card
    odds.expected_refreshes_for_card = (
        lambda level, cost, target_star, owned=0, non_target_taken=0: 0.0)
    try:
        # E(L)=E(L+1)=0 → saving=0 < fee → refresh_first(概率源被换即翻;
        # 实现若自建概率表,排序不随本符号变,本锁翻红)
        assert rank_refresh_vs_upgrade(st, s, _w724_overlay_a_rank_REG) == 'refresh_first'
    finally:
        odds.expected_refreshes_for_card = orig


def test_rank_no_second_margin_address_structure() -> None:
    """结构互指锁:排序函数源码只引用 ev.levelup_refresh_saving 与
    kernel.upgrade_plan_fee 两个既有单一址符号,不出现任何本地概率/
    费用查表(W720 修订要点②:刷新边际单一址,禁第二账)。"""
    import inspect

    from sr_od.application.currency_war.decision.decision_v2 import posture_release
    src = inspect.getsource(posture_release.rank_refresh_vs_upgrade)
    assert 'levelup_refresh_saving' in src
    assert 'upgrade_plan_fee' in src
    for banned in ('refresh_prob(', 'SHOP_ODDS', 'PROB_TABLE'):
        assert banned not in src, banned


# --- ④ arbiter 消费点(排序接线)------------------------------------------------


def _lvl_cand(cost: int = 10) -> Candidate:
    return Candidate(action=LevelUp(cost=cost), tag='levelup', source='ui')


def _arbitrate_levelup(st: _w724_overlay_a_rank_GameState, s: _w724_overlay_a_rank_StrategySession,
                       val: float = 1.0):
    return arbitrate([(_lvl_cand(), val, {'int_emb': 0.0})], st, s, _w724_overlay_a_rank_REG)


def test_arbiter_defers_levelup_on_refresh_first_frame(monkeypatch) -> None:
    """消费点锁(提案 A 消费点=arbiter 升级门):排序辖域帧(rank=
    refresh_first)升级候选降级拒,拒因含通道边际排序标注——隐式固定序
    (买/升级恒先于刷新)自此收回显式单一址。"""
    from sr_od.application.currency_war.decision.decision_v2 import ev as _ev
    from sr_od.application.currency_war.kernel import cw_economy
    st = _w724_overlay_a_rank_state(gold=80)
    monkeypatch.setattr(cw_economy, 'schedule_upgrade',
                        lambda *a, **k: True)     # ② DP 授权臂开
    monkeypatch.setattr(_ev, 'levelup_refresh_saving',
                        lambda *a, **k: 0.0)      # refresh_first
    res = _arbitrate_levelup(st, _flip_session(st))
    row = res.log[-1]
    assert row['accepted'] is False, f'refresh_first 帧升级应降级(log={row})'
    assert '通道边际排序' in (row.get('reject') or '')


def test_arbiter_upgrade_first_frame_zero_drift(monkeypatch) -> None:
    """零漂移臂:同帧 rank='upgrade_first'(saving 覆盖费率)→ 升级
    照现行固定序放行(排序不改写 upgrade_first 行为)。"""
    from sr_od.application.currency_war.decision.decision_v2 import ev as _ev
    from sr_od.application.currency_war.kernel import cw_economy
    st = _w724_overlay_a_rank_state(gold=80)
    monkeypatch.setattr(cw_economy, 'schedule_upgrade',
                        lambda *a, **k: True)
    monkeypatch.setattr(_ev, 'levelup_refresh_saving',
                        lambda *a, **k: 999.0)
    res = _arbitrate_levelup(st, _flip_session(st))
    assert res.log[-1]['accepted'] is True, res.log[-1]


def test_arbiter_non_scope_frame_zero_drift(monkeypatch) -> None:
    """零漂移臂(非 flip 帧):无 release 指令的同帧升级照放行——排序
    只辖 flip ∧ level_up ∧ cap 满员帧(SPECS A-v2 §1:非辖帧行为零漂移)。"""
    from sr_od.application.currency_war.decision.decision_v2 import ev as _ev
    from sr_od.application.currency_war.kernel import cw_economy
    st = _w724_overlay_a_rank_state(gold=80)
    monkeypatch.setattr(cw_economy, 'schedule_upgrade',
                        lambda *a, **k: True)
    monkeypatch.setattr(_ev, 'levelup_refresh_saving',
                        lambda *a, **k: 0.0)
    res = _arbitrate_levelup(st, _w724_overlay_a_rank_StrategySession())
    assert res.log[-1]['accepted'] is True, res.log[-1]


def test_arbiter_pop_slot_arm_not_overwritten(monkeypatch) -> None:
    """人口位臂不覆写锁(SPECS A-v2 §1:[33] 当轮兑现,排序不辖①臂)——
    cap 满 ∧ bench 有目标件(pop_slot)帧,即便 rank='refresh_first'
    升级照放行。"""
    from sr_od.application.currency_war.decision.decision_v2 import ev as _ev
    from sr_od.application.currency_war.kernel import cw_economy
    from sr_od.application.currency_war.kernel.cw_intention import (
        HoardTarget,
        IntentionState,
    )
    carry = '姬子·启行'
    st = _w724_overlay_a_rank_state(gold=80)
    st.bench = [BenchChar(slot=0, char_id=carry, faction='贝洛伯格', star=1)] \
        + [None] * (_w724_overlay_a_rank_BENCH_CAPACITY - 1)
    s = _flip_session(st)
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset({carry, '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {carry}
    monkeypatch.setattr(cw_economy, 'schedule_upgrade',
                        lambda *a, **k: True)
    monkeypatch.setattr(_ev, 'levelup_refresh_saving',
                        lambda *a, **k: 0.0)      # refresh_first
    res = _arbitrate_levelup(st, s)
    assert res.log[-1]['accepted'] is True, res.log[-1]
    assert getattr(res.actions[0], 'auth_basis', '') == 'pop_slot'


# --- ⑤ 定向刷新车道塌缩判据接线(ADR-0475 挂账补线,W721 并入)--------------------


def _ma_frame(level: int = 5):
    """M-A 授权帧底座(承 test_cw_w252 形态):P1 末窗 gap>0 ∧ 追名
    peak≥2 ∧ hp 带外(非血预算停付);锁定核=4 费「波提欧」(巡海击破),
    level 参数控塌缩带判定面(lv5 时 refresh_prob(5,4)/refresh_prob(7,4)
    ≈0.05 < ω=0.1,塌缩带;W721 帧族同款)。"""
    from types import SimpleNamespace
    carry = '波提欧'
    st = _w724_overlay_a_rank_GameState(
        plane=1, round_num=8, gold=55, level=level, hp=70,
        board={'击破': 2, '贝洛伯格': 1},
        deployed=[SimpleNamespace(char_id=carry, faction='击破',
                                  star=1, position_pref='back', equips=(),
                                  slot=0),
                  SimpleNamespace(char_id='娜塔莎', faction='贝洛伯格',
                                  star=1, position_pref='back', equips=(),
                                  slot=1)],
        bench=[BenchChar(slot=0, char_id=carry, faction='击破', star=1)],
        shop=[], node_type='battle')
    from sr_od.application.currency_war.kernel.cw_intention import (
        HoardTarget,
        IntentionState,
    )
    s = _w724_overlay_a_rank_StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '巡海击破'
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset({carry}), frozenset(), 'locked')
    s.v3_core_names = {carry}
    s.target_comp = SimpleNamespace(factions=('击破',),
                                    core_chars=(carry,))
    return st, s


def test_ma_lane_stops_on_collapse_frame() -> None:
    """塌缩停付锁(ADR-0475 定向车道同判据辖):塌缩带归零帧
    (锁定核 4 费 @lv5,refresh_prob 比值<ω)M-A 定向车道停付——
    非正分刷新拒,预算零消耗(轮/局计数不动)。"""
    st, s = _ma_frame(level=5)
    from sr_od.application.currency_war.kernel.cw_economy import (
        _omega_collapse_zeroed,
        _target_core_cost,
    )
    _, tc = _target_core_cost(s)
    assert _omega_collapse_zeroed(st, s, _w724_overlay_a_rank_REG, tc), '前置:帧须在塌缩带'
    cand = Candidate(action=RefreshShop(cost=2), tag='refresh', source='shop')
    res = arbitrate([(cand, -2.0, {'int_emb': 0.0})], st, s, _w724_overlay_a_rank_REG)
    assert res.log[-1]['accepted'] is False, res.log[-1]
    assert not any(isinstance(a, RefreshShop) for a in res.actions)
    assert getattr(s, 'v3_dir_refresh_used', 0) == 0
    assert getattr(s, 'v3_dir_refresh_round', 0) == 0


def test_ma_lane_zero_drift_outside_collapse_band() -> None:
    """零漂移臂:非塌缩带同级帧(M-A 授权窗开)定向刷新照常有界放行
    (ADR-0475 接线只辖塌缩带,不缩窗内正常搜索量)。"""
    st, s = _ma_frame(level=8)
    from sr_od.application.currency_war.kernel.cw_economy import (
        _omega_collapse_zeroed,
        _target_core_cost,
    )
    _, tc = _target_core_cost(s)
    assert not _omega_collapse_zeroed(st, s, _w724_overlay_a_rank_REG, tc), '前置:帧须在带外'
    cand = Candidate(action=RefreshShop(cost=2), tag='refresh', source='shop')
    res = arbitrate([(cand, -2.0, {'int_emb': 0.0})], st, s, _w724_overlay_a_rank_REG)
    assert res.log[-1]['accepted'] is True, res.log[-1]
    assert any(isinstance(a, RefreshShop) for a in res.actions)
    assert getattr(s, 'v3_dir_refresh_used', 0) == 1


def test_ma_collapse_single_address_no_reimplementation() -> None:
    """判据单一址结构锁:arbiter 的塌缩停付只引用 kernel.cw_economy
    ._omega_collapse_zeroed(ADR-0475 挂账原文指定单一址),不出现
    第二概率口径(refresh_prob 直调/本地比值)。"""
    import inspect

    from sr_od.application.currency_war.decision.decision_v2 import arbiter
    src = inspect.getsource(arbiter)
    assert '_omega_collapse_zeroed' in src
    # 判据不在 arbiter 本地重算:禁直调概率符号/读判据阈值字段
    assert 'refresh_prob' not in src
    assert 'registry.omega_collapse_ratio' not in src


# ==================== test_skip_shop_overlay ====================

from typing import TYPE_CHECKING

import pytest as _test_skip_shop_overlay_pytest

from one_dragon.base.screen.screen_utils import (
    find_area_in_screen,
    get_match_screen_name,
)

if TYPE_CHECKING:
    from test.conftest import SrTestContext


def test_skip_x_shop_open_overlay_state(test_context: SrTestContext) -> None:
    """叠加态:识别为 备战-开商店(商店牌盖基态 id_mark 前台区域),但「按钮-跳过」(归备战屏)
    的 OCR 文本在叠加帧上仍可命中——验证「跨屏正交元素查找端不锁死单一屏」的必要性。

    fixture 2026-08-17 迁至 screens/货币战争-备战-开商店/(原误归备战目录;叠加帧开商店
    id_mark[购买经验+收起]全中、备战 前台区域 被商店牌盖 → 实属开商店态,r34 id_mark 修复勘定)。
    """
    if not test_context.has_screen('货币战争-备战-开商店', '免战叠加态'):
        _test_skip_shop_overlay_pytest.skip('fixture 缺:screens/货币战争-备战-开商店/免战叠加态.webp')
    img = test_context.load_screen('货币战争-备战-开商店', '免战叠加态')
    # 叠加帧识别为开商店(它盖基态 id_mark → 基态不 is_precise;开商店自己的组合命中)
    assert get_match_screen_name(
        test_context, img, screen_name_list=['货币战争-备战-开商店']) == '货币战争-备战-开商店'
    # 「按钮-跳过」area 归备战屏,但在叠加帧上其 OCR rect 内文本「跳过(1/2)」存在
    si = test_context.screen_loader.get_screen('货币战争-备战')
    skip_area = next((a for a in si.area_list if a.area_name == '按钮-跳过'), None)
    assert skip_area is not None
    assert find_area_in_screen(test_context, img, skip_area).value == 1, (
        '免战×商店开叠加帧上「按钮-跳过」应命中(正交态:两状态同帧共存,'
        '查找端若锁死开商店屏会找不到跳过 → StartBattle 跨屏 fallback 的依据)')
