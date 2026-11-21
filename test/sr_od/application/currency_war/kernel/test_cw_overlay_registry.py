"""OVERLAY_REGISTRY 注册表一致性测试(模块头申报的机器化约束全部落实)。

注册表模块头声明的一致性断言在本文件机器化(此前为悬空引用,本测试即其落点):

1. **active 条目建档在场**:screen_name 必须已建档于 screen_info(active=False
   条目豁免,待实机建档);
2. **handler 可解析**:close_action='handle' 的 active 条目 handler_id 必填,
   且 = cw_screen 包内可导入的类名(悬挂 handler = 分发即崩);
   PENDING_HANDLER_IDS 收拢待办集 ⊆ registry 引用集;
3. **dispatch_priority 全表唯一**(C 面派发序键);
4. **C1 红线**:semantic='decision' ⇒ closable=False(关闭即丢决策内容的
   overlay 禁进清场派生集,遭遇节点被清场误关事故的防线);
5. **closable 条目 close_area 载荷在场**(清场派生集消费的一键关按钮);
6. **close_point 载荷契约**:close_action='point' 的 active 条目必填且界内
   (1080p);
7. **bail_tag 机器化**:decision 条目必填且全表唯(director bail 同因键后缀,
   字段 docstring 申报的一致性断言)。
"""

import importlib
import pkgutil

from sr_od.application.currency_war.kernel.cw_overlay_registry import (
    CLOSE_ACTION_HANDLE,
    CLOSE_ACTION_POINT,
    OVERLAY_REGISTRY,
    PENDING_HANDLER_IDS,
    SEMANTIC_DECISION,
)


def _cw_screen_class_names() -> set[str]:
    """cw_screen 包全子模块导入后的类名集(handler 解析域)。

    运行时 import(非源码扫描):handler_id 的解析语义 = cw_screen 包命名空间
    可导入类,与 cw_loop 分发侧的 import 构造同域。"""
    import sr_od.application.currency_war.operations.cw_screen as pkg
    names: set[str] = set()
    for mod_info in pkgutil.iter_modules(pkg.__path__):
        mod = importlib.import_module(f'{pkg.__name__}.{mod_info.name}')
        names.update(n for n in dir(mod) if isinstance(getattr(mod, n), type))
    return names


def test_active_entries_have_screen_info(test_context) -> None:
    """active 条目 screen_name 已建档(inactive 条目豁免待实机建档)。"""
    missing = [spec.screen_name for spec in OVERLAY_REGISTRY
               if spec.active
               and spec.screen_name not in test_context.screen_loader.screen_info_map]
    assert not missing, f'active 条目未建档:{missing}'


def test_handle_close_action_resolves_handler() -> None:
    """close_action='handle' 的 active 条目 handler_id 必填且可解析;
    PENDING_HANDLER_IDS ⊆ registry 引用集。"""
    class_names = _cw_screen_class_names()
    dangling = []
    for spec in OVERLAY_REGISTRY:
        if not spec.active or spec.close_action != CLOSE_ACTION_HANDLE:
            continue
        if not spec.handler_id:
            dangling.append(f'{spec.screen_name}:handler_id 空')
            continue
        if spec.handler_id in PENDING_HANDLER_IDS:
            continue   # 收拢待办集豁免 import 断言(机制申报见注册表)
        if spec.handler_id not in class_names:
            dangling.append(f'{spec.screen_name}:{spec.handler_id} 不可解析')
    assert not dangling, f'悬挂 handler(分发即崩):{dangling}'
    referenced = {spec.handler_id for spec in OVERLAY_REGISTRY if spec.handler_id}
    assert set(PENDING_HANDLER_IDS) <= referenced, (
        f'PENDING_HANDLER_IDS 存在 registry 引用集外的成员:'
        f'{set(PENDING_HANDLER_IDS) - referenced}')


def test_dispatch_priority_unique() -> None:
    """dispatch_priority 全表唯一(C 面派发序键,撞号 = 派发序不定)。"""
    priorities = [spec.dispatch_priority for spec in OVERLAY_REGISTRY]
    dupes = {p for p in priorities if priorities.count(p) > 1}
    assert not dupes, f'dispatch_priority 撞号:{sorted(dupes)}'


def test_c1_decision_not_closable() -> None:
    """C1 红线:decision 语义 ⇒ closable=False(关闭即丢决策内容禁进清场集)。"""
    violations = [spec.screen_name for spec in OVERLAY_REGISTRY
                  if spec.semantic == SEMANTIC_DECISION and spec.closable]
    assert not violations, f'C1 红线违反(decision 且 closable):{violations}'


def test_closable_entries_have_close_area_payload() -> None:
    """closable 条目(清场派生集成员)必须带 close_area 一键关按钮载荷。"""
    violations = [spec.screen_name for spec in OVERLAY_REGISTRY
                  if spec.active and spec.closable and not spec.close_area]
    assert not violations, f'closable 缺 close_area 载荷:{violations}'


def test_close_point_payload_in_bounds() -> None:
    """close_action='point' 的 active 条目 close_point 必填且 1080p 界内。"""
    violations = []
    for spec in OVERLAY_REGISTRY:
        if not spec.active or spec.close_action != CLOSE_ACTION_POINT:
            continue
        if spec.close_point is None:
            violations.append(f'{spec.screen_name}:close_point 缺')
            continue
        x, y = spec.close_point
        if not (0 <= x < 1920 and 0 <= y < 1080):
            violations.append(f'{spec.screen_name}:close_point 界外 {spec.close_point}')
    assert not violations, f'close_point 载荷契约违反:{violations}'


def test_decision_bail_tag_filled_and_unique() -> None:
    """decision 条目 bail_tag 必填且全表唯一(director bail 同因键)。"""
    filled = [spec.bail_tag for spec in OVERLAY_REGISTRY
              if spec.semantic == SEMANTIC_DECISION and spec.bail_tag]
    missing = [spec.screen_name for spec in OVERLAY_REGISTRY
               if spec.semantic == SEMANTIC_DECISION and not spec.bail_tag]
    assert not missing, f'decision 条目缺 bail_tag:{missing}'
    dupes = {t for t in filled if filled.count(t) > 1}
    assert not dupes, f'bail_tag 撞号:{sorted(dupes)}'
