"""CustomCombineOp shipped 路由完整性测试(纯配置校验,不跑游戏)。

``buy_xianzhou_parcel`` / ``memory_crystal_shard`` / ``trick_snack`` 三个 app 是
``CustomCombineOp`` 薄壳 —— 真实流程在 shipped 路由 yml(``config/custom_combine_op/``),
不在 app 代码。本测试把每条 shipped 路由当**契约**校验:

- 能加载(``existed`` + 有 ``name`` + ``ops`` 非空);
- 每条指令 ``op`` 是合法 ``OpEnum``;
- ``data`` 长度匹配该 op 在 ``CustomCombineOp.run_op`` 各分支实际读取的下标(见
  ``_EXPECTED_ARITY``,与 ``custom_combine_op.py`` 逐分支对照);
- 语义合法:``wait`` 类型 / ``interact`` 类型是合法枚举值,坐标 / 楼层 / 数量可转 int,
  ``buy_store_item`` 的 ``item_id`` 能在 ``StoreItemEnum`` 解析、``synthesize`` 的
  ``item_id`` 能在 ``SynthesizeItemEnum`` 解析(= 运行时 ``run_op`` 真正会做的事)。

不依赖游戏 / 截图 / SrContext —— ``CustomCombineOpConfig`` 只读 yml(``os_utils`` 源码
运行时 work_dir = 项目根,故 ``config/custom_combine_op/`` 可找到)。路由被改坏(漏字段 /
拼错 op / 删了 item 枚举)→ 本测试即暴露。
"""

import pytest

from sr_od.operations.custom_combine_op.custom_combine_op_config import (
    CustomCombineOpConfig,
    CustomCombineOpItem,
)
from sr_od.operations.custom_combine_op.custom_combine_op_const import (
    OpEnum,
    OpInteractTypeEnum,
    OpWaitTypeEnum,
)
from sr_od.operations.store.store_const import StoreItemEnum
from sr_od.operations.synthesize.synthesize_const import SynthesizeItemEnum

# shipped 路由(buy_xianzhou_parcel / memory_crystal_shard / trick_snack 三个 app 实际跑的)
SHIPPED_ROUTES = [
    'buy_xianzhou_parcel',
    'memory_crystal_shard',
    'buy_trick_snack_route_yll6_xzq',
    'buy_trick_snack_route_xzlf_xchzs',
    'synthesize_trick_snack',
]

_VALID_OP_IDS = {op.value for op in OpEnum}


def _expected_arity(op_id: str) -> set[int]:
    """该 op 合法的 ``data`` 长度集合(对照 ``CustomCombineOp.run_op`` 各分支读取的下标)。

    - ``back_to_world_plus``:不读 data → 0。
    - ``transport``:planet / region / floor / tp → 4。
    - ``wait``:wait_type / seconds → 2。
    - ``move`` / ``slow_move``:x / y[, floor] → 2 或 3。
    - ``interact``:type / word[, lcs_percent] → 2 或 3。
    - ``click``:x / y → 2。
    - ``buy_store_item``:item_id / buy_num → 2。
    - ``synthesize``:category / item_id / num → 3(注意 dispatch 只用 item_id / num,
      category 不参与枚举查找,故不在此校验 category 取值)。
    """
    if op_id == OpEnum.BACK_TO_WORLD_PLUS.value:
        return {0}
    if op_id == OpEnum.TRANSPORT.value:
        return {4}
    if op_id == OpEnum.WAIT.value:
        return {2}
    if op_id in (OpEnum.MOVE.value, OpEnum.SLOW_MOVE.value):
        return {2, 3}
    if op_id == OpEnum.INTERACT.value:
        return {2, 3}
    if op_id == OpEnum.CLICK.value:
        return {2}
    if op_id == OpEnum.BUY_STORE_ITEM.value:
        return {2}
    if op_id == OpEnum.SYNTHESIZE.value:
        return {3}
    return set()


def _assert_semantics(route_name: str, idx: int, item: CustomCombineOpItem) -> None:
    """逐 op 语义校验(类型枚举合法 / 数值字段可转 int / item_id 能解析)。"""
    label = f'{route_name} ops[{idx}] op={item.op}'
    data = item.data

    if item.op == OpEnum.WAIT.value:
        assert data[0] in {t.value for t in OpWaitTypeEnum}, (
            f'{label} wait 类型 {data[0]!r} 不合法(应为 in_world / seconds)'
        )
        float(data[1])  # seconds 可转数值

    elif item.op == OpEnum.TRANSPORT.value:
        int(data[2])  # floor 可转 int

    elif item.op in (OpEnum.MOVE.value, OpEnum.SLOW_MOVE.value, OpEnum.CLICK.value):
        int(data[0])  # x 可转 int
        int(data[1])  # y 可转 int

    elif item.op == OpEnum.INTERACT.value:
        assert data[0] in {t.value for t in OpInteractTypeEnum}, (
            f'{label} interact 类型 {data[0]!r} 不合法(应为 world / world_single_line / talk)'
        )

    elif item.op == OpEnum.BUY_STORE_ITEM.value:
        assert data[0].upper() in StoreItemEnum.__members__, (
            f'{label} item_id {data[0]!r} 不在 StoreItemEnum(run_op 会 KeyError)'
        )
        int(data[1])  # buy_num 可转 int

    elif item.op == OpEnum.SYNTHESIZE.value:
        assert data[1].upper() in SynthesizeItemEnum.__members__, (
            f'{label} item_id {data[1]!r} 不在 SynthesizeItemEnum(run_op 会 KeyError)'
        )
        int(data[2])  # num 可转 int


class TestCustomCombineOpConfig:
    """shipped 路由 yml 结构 + 语义完整性。"""

    @pytest.mark.parametrize('route_name', SHIPPED_ROUTES)
    def test_route_loads_and_structure(self, route_name: str) -> None:
        """每条 shipped 路由:能加载 + 每条指令 op / arity / 语义合法。"""
        cfg = CustomCombineOpConfig(route_name)
        assert cfg.existed, f'路由配置缺失: config/custom_combine_op/{route_name}.yml'
        assert cfg.config_name, f'路由 {route_name} 缺 name'
        assert len(cfg.ops) > 0, f'路由 {route_name} ops 为空'

        for idx, item in enumerate(cfg.ops):
            assert item.op in _VALID_OP_IDS, (
                f'{route_name} ops[{idx}] op={item.op!r} 不在 OpEnum'
            )
            arity = _expected_arity(item.op)
            assert len(item.data) in arity, (
                f'{route_name} ops[{idx}] op={item.op} data 长度 {len(item.data)} '
                f'不在合法集合 {arity}'
            )
            _assert_semantics(route_name, idx, item)

    def test_patrol_unused_in_shipped_routes(self) -> None:
        """``patrol`` 在 OpEnum 但 ``run_op`` 无对应分支(会落到 ``op is None`` → round_fail),
        shipped 路由不该用它。"""
        for route_name in SHIPPED_ROUTES:
            cfg = CustomCombineOpConfig(route_name)
            ops = [item.op for item in cfg.ops]
            assert OpEnum.PATROL.value not in ops, (
                f'{route_name} 用了 patrol,但 run_op 不分发它(执行会失败)'
            )

    def test_first_op_returns_to_world_or_synthesize(self) -> None:
        """每条 shipped 路由首指令为 ``back_to_world_plus``(先把 bot 拉回大世界干净起点)。

        synthesize_trick_snack 也是 back_to_world_plus 开头(先回大世界再开合成菜单)。
        """
        for route_name in SHIPPED_ROUTES:
            cfg = CustomCombineOpConfig(route_name)
            assert cfg.ops[0].op == OpEnum.BACK_TO_WORLD_PLUS.value, (
                f'{route_name} 首指令应为 back_to_world_plus,实际 {cfg.ops[0].op!r}'
            )
