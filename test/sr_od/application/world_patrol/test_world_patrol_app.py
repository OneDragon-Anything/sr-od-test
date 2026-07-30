"""WorldPatrolApp 锄大地 配置 + 白名单基础设施测试(纯配置,不跑游戏)。

world_patrol 核心是大世界跑图清怪(消耗时间,需游戏),核心流程不 mock。但其 ``load_route_list``
靠 ``world_patrol_config.whitelist_id`` + ``load_all_whitelist_list`` 校验白名单再加载路线 —— 本测试
守这层数据契约(类型合法 + 设了的白名单在合法列表内)。
"""

from test.conftest import SrTestContext

from sr_od.application.world_patrol.world_patrol_whitelist_config import (
    load_all_whitelist_list,
)


class TestWorldPatrolApp:
    """锄大地:配置类型 + 白名单契约。"""

    def test_config_types(self, test_context: SrTestContext) -> None:
        """各配置字段类型合法(team_num / max_consumable_cnt 非负 int,布尔 / 字符串字段类型正确)。"""
        cfg = test_context.world_patrol_config
        assert isinstance(cfg.team_num, int) and cfg.team_num >= 0, (
            f'team_num 应为非负 int,实际 {cfg.team_num!r}'
        )
        assert isinstance(cfg.whitelist_id, str), f'whitelist_id 应为 str,实际 {cfg.whitelist_id!r}'
        assert isinstance(cfg.technique_fight, bool)
        assert isinstance(cfg.technique_only, bool)
        assert isinstance(cfg.max_consumable_cnt, int) and cfg.max_consumable_cnt >= 0

    def test_whitelist_id_valid_if_set(self, test_context: SrTestContext) -> None:
        """若设了 whitelist_id,应在合法白名单列表内(否则 load_route_list 用不上白名单)。"""
        cfg = test_context.world_patrol_config
        valid = load_all_whitelist_list()
        assert isinstance(valid, list), 'load_all_whitelist_list 应返回 list'
        if cfg.whitelist_id:
            assert cfg.whitelist_id in valid, (
                f'whitelist_id {cfg.whitelist_id!r} 不在合法白名单列表 {valid}'
            )
