"""overlay 注册表一致性测试(设计终版 §二 8 断言首锁;Phase 2 子批 1-2)。

注册表 = ``sr_od.application.currency_war.kernel.cw_overlay_registry.OVERLAY_REGISTRY``
(单一枚举点)。本测试锁的是**声明层的结构一致性**;A 面(P0 清场)与
B 面(director bail)已切换为派生消费,对应锁随切换批改写为「切换后 +
行为断言门」;C/D(battle_loop 派发 / 退出链)未切换,零行为锁仍钉住。

C1 红线(断言 3):``decision ⇒ closable is False`` ∧ 派生清场集不含
decision 条目。吸收 Phase 1 临时哨(「遭遇节点 ∉ ENTRY_OVERLAY_CLOSE」,
test_cw_w609_phase_field_spec.py)后成为唯一红线锁——临时哨在其全绿的同
commit 删除(设计定案 5)。
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import pytest
import yaml

from sr_od.application.currency_war.kernel import cw_overlay_registry as reg

REPO = Path(__file__).resolve().parents[5]
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
    """按类名在 handler / run_node 承载包的各子模块中 import。

    类不经包 ``__init__`` 导出(项目约定 ``__init__`` 默认不暴露模块),
    须逐子模块 getattr;两包全找不到即 AssertionError。
    """
    last_err: Exception | None = None
    for pkg_name in (
        'sr_od.application.currency_war.operations.handlers',
        'sr_od.application.currency_war.operations.run_nodes',
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
#: event_overlay bail → 0i 选卡 / RunSupplyNode 消化。
_GOLDEN_CLEAR_MAP: dict[str, str] = {
    '货币战争-积分奖励': '按钮-关闭',
    '货币战争-中断挑战弹窗': '按钮-关闭',
    '货币战争-武装箱弹窗': '按钮-关闭',
}


def test_aface_clear_set_switched_to_registry() -> None:
    """A 面已切换:清场表 = 注册表派生桥接,手写 5 条 dict 删除。

    接线锁三件:① gate 清场映射逐条等于派生黄金值(含两处 decision 化
    成员收缩——星徽秘典/补给不再可被环入口一键关);② gate 源码消费
    ``derive_clearable`` 且不再含手写清场条目字面量(单一源收拢);
    ③ 被移出的两屏仍在 decision 派生集(退出路径=bail→handler,不是
    裸消失)。
    """
    import inspect

    from sr_od.application.currency_war.obs.cw_observation_gate import (
        ENTRY_OVERLAY_CLOSE,
    )
    # ① 派生值 = 黄金(成员收缩锁)
    assert ENTRY_OVERLAY_CLOSE == _GOLDEN_CLEAR_MAP, (
        f'清场派生集漂移: 实际={ENTRY_OVERLAY_CLOSE} 黄金={_GOLDEN_CLEAR_MAP}')
    # ② 接线锁:源码走 derive_clearable,手写条目不回流
    from sr_od.application.currency_war.obs import cw_observation_gate
    src = inspect.getsource(cw_observation_gate)
    assert 'derive_clearable()' in src, '清场表未接线 derive_clearable()'
    for _scr, _area in _GOLDEN_CLEAR_MAP.items():
        assert f"'{_scr}': '{_area}'" not in src, (
            f'清场手写条目 {_scr} 仍在 gate(单一源未收拢)')
    # ③ 移出成员的退出路径存在性:两屏 ∈ decision 派生集(bail→handler)
    decision_names = {s.screen_name for s in reg.derive_decision()}
    assert '货币战争-星徽秘典弹窗' in decision_names
    assert '货币战争-补给' in decision_names


def test_aface_clear_judgment_per_fixture_frame() -> None:
    """变更语义 fixture 断言锁:对「单 overlay 在场」的 mock 帧剧本,
    环入口清场段(``PrepDirector._clear_entry_overlays``,消费循环未改、
    判定源换成注册表派生)的点击行为逐帧锁定:

    - 星徽秘典弹窗在场 → **不点**其关闭钮(A 面行为变化 1:移出清场,
      改走 0i 选卡;旧行为会点「按钮-关闭」丢选卡内容);
    - 补给在场 → **不点**「按钮-返回备战界面」(行为变化 2:移出清场,
      改走 bail → RunSupplyNode 消化);
    - 武装箱弹窗在场 → 仍点「按钮-关闭」(清场留存成员,防过度收缩)。

    帧模型:monkeypatch ``screen_utils.get_match_screen_name`` 只对剧本
    屏命中(其余屏全部 miss),点击经替身记录——纯离线,零真实 IO。
    """
    from types import SimpleNamespace

    from one_dragon.base.screen import screen_utils
    from sr_od.application.currency_war import prep_director

    def _run_clear(visible: str) -> list[tuple[str, str]]:
        d = prep_director.PrepDirector.__new__(prep_director.PrepDirector)
        d.ctx = SimpleNamespace(current_instance_idx=99)
        d.screenshot = lambda: object()   # 帧本体不被消费(锚判定全桩)
        clicks: list[tuple[str, str]] = []

        def _fake_click(_frame, screen, area, **_kw):
            clicks.append((screen, area))
        d.round_by_find_and_click_area = _fake_click

        def _fake_match(*, ctx, screen, screen_name_list, crop_first=False):
            return visible if visible in screen_name_list else None

        mp = pytest.MonkeyPatch()
        try:
            mp.setattr(screen_utils, 'get_match_screen_name', _fake_match)
            mp.setattr(prep_director.time, 'sleep', lambda _s: None)
            d._clear_entry_overlays()
        finally:
            mp.undo()
        return clicks

    # 行为变化 1:星徽秘典不再被清场关闭(旧行为会点 按钮-关闭)
    clicks = _run_clear('货币战争-星徽秘典弹窗')
    assert clicks == [], (
        f'星徽秘典弹窗仍被环入口清场关闭(应走 0i 选卡消化): {clicks}')
    # 行为变化 2:补给不再被「返回备战界面」一键离场(应走 RunSupplyNode)
    clicks = _run_clear('货币战争-补给')
    assert clicks == [], (
        f'补给 modal 仍被环入口一键离场(应走 bail→RunSupplyNode): {clicks}')
    # 留存成员仍清:武装箱弹窗在场 → 点「按钮-关闭」(mock 帧不随点击变化,
    # 每轮清场轮重复命中同屏 → 断言每次点击都是该关闭钮,无其它屏混入)
    clicks = _run_clear('货币战争-武装箱弹窗')
    assert clicks and set(clicks) == {('货币战争-武装箱弹窗', '按钮-关闭')}, (
        f'武装箱弹窗清场行为漂移: {clicks}')


#: B 面切换前的手写 bail 清单黄金集(切换批零漂移对拍基准;单一源收拢后
#: 本常量只存在于测试,作为历史黄金基准防接线漂移)。
_GOLDEN_BAIL_LIST: tuple[tuple[str, str, str], ...] = (
    ('货币战争-盛会之星', '标识-盛会之星', 'megastar'),
    ('货币战争-选择伙伴', '标识-选择伙伴', 'partner'),
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

    接线锁三件:① 源码不再含手写 (screen, area, tag) 元组字面量(单一源收拢);
    ② 源码含 derive_decision 消费;③ 派生集 (screen, anchor, bail_tag) 三元组
    与切换前手写黄金集逐条一致(零成员/零锚名/零 tag 漂移)。
    """
    import inspect

    from sr_od.application.currency_war import prep_director
    src = inspect.getsource(prep_director)
    assert 'derive_decision' in src, 'bail 扫描未接线 derive_decision()'
    for _scr, _area, _tag in _GOLDEN_BAIL_LIST:
        assert f"('{_scr}', '{_area}', '{_tag}')" not in src, (
            f'bail 手写清单条目 {_tag} 仍在 prep_director(单一源未收拢)')
    derived = {(s.screen_name, s.anchor_area, s.bail_tag)
               for s in reg.derive_decision()}
    assert derived == _golden_bail_set(), (
        f'派生集与切换前手写黄金集漂移: '
        f'多={derived - _golden_bail_set()} 少={_golden_bail_set() - derived}')


def test_zero_drift_bail_judgment_per_frame_fixture() -> None:
    """零漂移门(fixture 帧组对拍):对 9 张「单 overlay 在场」fixture 帧,
    手写清单序与 registry 派生序的判定(event_overlay tag)逐帧一致。

    帧模型:每帧恰好一个锚命中(round_by_find_area 对该 screen 返 success)——
    decision overlay 是全屏顶层弹窗,单帧锚互斥(历史帧组 ≤1 命中)。
    两套判定序在同一帧上都只可能命中这唯一锚 → tag 逐帧相等;若未来出现
    多锚帧,本测试的互斥前提破裂,须升级为显式序语义裁决(不得静默跟绿)。
    """
    golden_order = [tag for _s, _a, tag in _GOLDEN_BAIL_LIST]
    derived_order = [s.bail_tag for s in reg.derive_decision()]

    def _scan(order: list[tuple[str, str, str]], visible: str) -> str | None:
        for _scr, _area, tag in order:
            if _scr == visible:
                return tag
        return None

    for scr, _area, tag in _GOLDEN_BAIL_LIST:
        g = _scan(_GOLDEN_BAIL_LIST, scr)
        d = _scan([(s.screen_name, s.anchor_area, s.bail_tag)
                   for s in reg.derive_decision()], scr)
        assert g == tag and d == tag, (
            f'fixture 帧 {scr}:手写判定 {g} / 派生判定 {d} / 黄金 {tag} 漂移')
    # 序差异显式化:两序不同是已论证的行为无关差异(见 prep_director 扫描段注释),
    # 锁住差异事实本身,防止「以为序相同」的误读
    assert golden_order != derived_order
    assert set(golden_order) == set(derived_order)


def test_zero_behavior_upper_screens_golden() -> None:
    """UPPER_SCREENS 成员集与迁移前手写常量(黄金名单)完全一致。

    顺序注:两段式派生(派生段在前、残余段在后)相对迁移前手写常量存在
    段内交错位的顺序变化(位面过渡等残余屏从段内移到段尾)——逐屏判定的
    布尔结果与命中短路语义与顺序无关,成员集一致 = 行为一致;逐位派生
    一致由断言 8 锁定。
    """
    from sr_od.application.currency_war.kernel import cw_obs_core
    assert set(cw_obs_core.UPPER_SCREENS) == {
        '货币战争-选择伙伴',
        '货币战争-祈愿试炼',
        '货币战争-遭遇节点',
        '货币战争-投资策略',
        '货币战争-投资环境',
        '货币战争-盛会之星',
        '货币战争-位面过渡',
        '货币战争-积分奖励',
        '货币战争-简报',
        '货币战争-中断挑战弹窗',
        '货币战争-未达上限警告',
        '货币战争-提示-前台无角色',
        '货币战争-武装箱弹窗',
        '货币战争-商店刷新概率表',
        '货币战争-攻略码输入弹窗',
        '货币战争-备战-角色详情',
        '货币战争-备战-装备详情浮窗',
        '货币战争-备战-角色信息提示',
        '货币战争-星徽详情',
        '货币战争-星徽秘典弹窗',
        '货币战争-备战-专家邀请函',
        '货币战争-补给',
        '货币战争-难度确认',
        '货币战争-阵容编辑',
        '货币战争-模式选择',
    }


def test_zero_behavior_bail_scan_matches_registry_decision_set() -> None:
    """B 面预备核对:现 bail 清单成员 = registry decision 派生集(切换日零漂移前提)。"""
    assert {s.bail_tag for s in reg.derive_decision()} == {
        'megastar', 'partner', 'wish_trial', 'star_tome', 'bookcard',
        'encounter', 'invest_strategy', 'invest_env', 'supply',
    }
