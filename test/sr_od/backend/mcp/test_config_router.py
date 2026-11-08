"""config_router 通用配置路由单测(trailblaze_power 体力计划接入)。

锁的内容：

- 注册冒烟：trailblaze_power entry 存在，id_kind=idx（计划项无自动生成标识，
  按列表下标删）、item_kind=dataclass、全 ops；describe 的 add_example 含必填字段
  （智能体可照抄生成 add 调用的入口保障）。
- validate_item 数值边界：空 mission_id / plan_times<1 / run_times 越界拒绝，合法通过。
- add/delete/get_config 全链（经 entry 调用 = 注册后的最终行为）：
  - get_config 当前实例返回 ctx.power_config 同一对象 —— MCP 写穿与一条龙
    开拓力 app 共用实例、「改完即生效无需重启」的关键契约；
  - add：合法 mission_id 经 guide_data 关联 mission 对象、save 被触发；
    idx=None 尾部追加，指定 idx 插到该位（原位项后移 —— 一条龙按 plan_list
    顺序执行，插入位置即执行顺位）；不可解析 mission_id / idx 越界抛
    ValueError（新增是显式动作，失败必须可知）；
  - delete：按下标删除成功、越界 False、非数字 ValueError。

测试零真实副作用：save 经 monkeypatch 置为计数 no-op（仍断言落盘被触发），
不写任何实例的 yml；add/delete 后还原 plan_list 内存态，测试幂等。
"""

import pytest
from test.conftest import SrTestContext

from sr_od.backend.config_router import _build_list_fields, get_entry


def _entry():
    """取 trailblaze_power 路由条目（未注册即失败，锁注册契约）。"""
    entry = get_entry('trailblaze_power')
    assert entry is not None, 'trailblaze_power 路由未注册'
    return entry


def _item_from(data: dict):
    """经 entry 反序列化构造计划项（与 MCP handler 同一入口）。"""
    return _entry().item_from_dict(data)


class TestTrailblazePowerRoute:
    """trailblaze_power 路由 entry 行为。"""

    def test_route_registered(self) -> None:
        """注册冒烟 + describe add_example 含必填字段。"""
        entry = _entry()
        assert entry.id_kind == 'idx'
        assert entry.item_kind == 'dataclass'
        assert set(entry.supported_ops) == {'get', 'set', 'add', 'delete', 'describe'}

        fields = _build_list_fields(entry, [])
        example = fields[0]['add_example']
        assert 'mission_id' in example and 'plan_times' in example

    def test_validate_item_bounds(self) -> None:
        """数值边界拒绝/通过（validate 只做数值校验，不含 ctx 依赖）。"""
        entry = _entry()
        assert entry.validate_item(None, _item_from({'mission_id': '', 'plan_times': 1})) is not None
        assert entry.validate_item(None, _item_from({'mission_id': 'x', 'plan_times': 0})) is not None
        assert entry.validate_item(
            None, _item_from({'mission_id': 'x', 'plan_times': 2, 'run_times': 3})
        ) is not None
        assert entry.validate_item(
            None, _item_from({'mission_id': 'x', 'plan_times': 2, 'run_times': 1})
        ) is None

    def test_add_delete_roundtrip(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """写穿契约 + add/delete 全链，save 置 no-op 零落盘。"""
        entry = _entry()
        config = test_context.power_config
        assert entry.get_config(test_context, None, None) is config, (
            '当前实例 get_config 必须返回 ctx.power_config 同一对象（写穿即生效的契约）'
        )

        save_calls: list[int] = []
        monkeypatch.setattr(type(config), 'save', lambda self: save_calls.append(1))
        original_len = len(config.plan_list)
        try:
            # add：mission_id 从指南数据现取（真实可解析，不随数据更新失效）
            category = test_context.guide_data.get_category_list_in_power_plan()[0].value
            mission = test_context.guide_data.get_mission_list_in_power_plan(category)[0].value

            item_a = _item_from({'mission_id': mission.unique_id, 'plan_times': 1})
            entry.add(config, item_a)  # 默认尾部追加
            assert config.plan_list[-1] is item_a
            assert item_a.mission is not None, 'add 必须关联 mission（一条龙运行按它导航）'
            assert save_calls, 'add 后必须触发落盘'

            # 指定 idx 插头:插入位置即执行顺位,尾部项被顶到其后(不依赖原列表内容,空列表亦成立)
            head = _item_from({'mission_id': mission.unique_id, 'plan_times': 1})
            entry.add(config, head, 0)
            assert config.plan_list[0] is head
            assert config.plan_list[1] is item_a
            assert len(config.plan_list) == original_len + 2

            with pytest.raises(ValueError):
                entry.add(config, _item_from({'mission_id': '生存索引 不存在', 'plan_times': 1}))
            with pytest.raises(ValueError):
                entry.add(config, _item_from({'mission_id': mission.unique_id, 'plan_times': 1}), 999)

            assert entry.delete(config, 0) is True  # 删头部项
            assert entry.delete(config, str(original_len)) is True  # 删尾部项,还原
            assert len(config.plan_list) == original_len
            assert entry.delete(config, '999') is False
            with pytest.raises(ValueError):
                entry.delete(config, 'abc')
        finally:
            del config.plan_list[original_len:]  # 原地还原内存态，不触发共享对象赋值守卫
