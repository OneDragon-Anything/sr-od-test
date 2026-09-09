"""跨面一致性锁:策略侧 M3 授权分键(auth_basis = m3_batch:arm1/arm0/pop,
授权可归因三臂分键)↔ sim 侧 ADR-0354 升级授权白名单(前缀匹配)。

防漂移判据:策略侧新增分键后缀而 sim 白名单未跟随 = 合法授权被误判
「ADR-0354 违规」,污染验收锚。本锁用**真实判据函数**对拍(ledger batch
表 + segments 段表两侧镜像实现都锁),非复述白名单常量。
"""

_ROW_BASE = {
    'plane': 1,
    'round_num': 6,
    'gold': 40,
    'sim': {'shop_waves': [{'gold': 40}], 'node': 'battle'},
    'state': {'level': 5},
}


def _rows(auth: str) -> list[dict]:
    """两行构造:第一行把 level 推到 5(进追级段),第二行携带金<50 的
    LevelUp 授权依据待判。"""
    first = dict(_ROW_BASE)
    first['actions'] = []
    second = dict(_ROW_BASE)
    second['round_num'] = 7
    second['actions'] = [{'__type__': 'LevelUp', 'auth': auth}]
    return [first, second]


def test_m3batch_arm_keys_pass_sim_whitelist():
    """三臂分键后缀(m3_batch:arm1/arm0/pop)两侧白名单均放行——
    精确等值匹配回归即此处红。"""
    from sr_od.application.currency_war.sim.checks.ledger import (
        check_levelup_interest_engine_gate,
    )
    from sr_od.application.currency_war.sim.checks.segments import (
        seg_check_unjustified_levelup,
    )
    for auth in ('m3_batch', 'm3_batch:arm1', 'm3_batch:arm0',
                 'm3_batch:pop'):
        assert check_levelup_interest_engine_gate(_rows(auth)) == [], auth
        assert seg_check_unjustified_levelup(_rows(auth)) == [], auth


def test_unauthorized_basis_still_flagged():
    """对照:白名单外授权依据仍计违规(前缀匹配不得放宽成放行一切)。"""
    from sr_od.application.currency_war.sim.checks.ledger import (
        check_levelup_interest_engine_gate,
    )
    from sr_od.application.currency_war.sim.checks.segments import (
        seg_check_unjustified_levelup,
    )
    for auth in ('', 'm3_batchx', 'some_new_arm'):
        assert len(check_levelup_interest_engine_gate(_rows(auth))) == 1, auth
        assert len(seg_check_unjustified_levelup(_rows(auth))) == 1, auth
