"""effective_cost / bench_char_cost 景元费用档读口测试(镜像 src =
kernel/cw_economy.py 该两函数;银狼LV.999 档家族第二成员 = 飞光·映月
策略赋予型景元,宿主文件 test_economy.py 超限冻结,按被测函数拆目录
新文件落位,先例 = 同目录 test_strategy_interest_floor.py)。

测试面依据 = 设计稿(原件已退役) 设计稿(原件已退役) §4 锁 1/锁 2(默认案 A 全场同名同档):
- 锁 1 读口四值:档透传 None→5(未拿卡 = 注册表起始费)/1→1/3→3/5→5;
  与银狼分支并存零串档(两档字段角色互斥,银狼档行不影响景元路由);
- 锁 2 档感知:bench_char_cost 对景元 gs 给定时经读口取当前档(tier=3
  → 3 / tier=1 → 1),gs 缺省回落注册表起始 5 费(保底兼容存量调用面,
  银狼特判同形)。
"""
from __future__ import annotations

from dataclasses import replace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_economy import (
    bench_char_cost,
    effective_cost,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    Field,
    GameState,
    Unit,
)


def _gs(tier: int | None) -> GameState:
    """直构状态容器种子(tier None = 未拿卡形态;Field frozen,写 = 换帧)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if tier is not None:
        gs = replace(gs, yingyue_cost_tier=Field(value=tier, source='logic'))
    return gs


# ============================================================ 锁 1 读口四值


def test_effective_cost_yingyue_tier_four_values() -> None:
    """景元档透传四值(None→5 / 1→1 / 3→3 / 5→5):None = 未拿卡落注册表
    起始费;值域 {1,3,5} 外值(异常态)同落静态——读口只透传合法档。"""
    assert effective_cost(_gs(None), '景元') == CHARACTERS['景元'].cost, \
        '未拿卡(None)= 注册表起始 5 费'
    assert effective_cost(_gs(1), '景元') == 1, '拿卡拍初始档 1 透传'
    assert effective_cost(_gs(3), '景元') == 3, '镜流 2★ 档 3 透传'
    assert effective_cost(_gs(5), '景元') == 5, '镜流 3★ 档 5 透传'


def test_effective_cost_two_tier_branches_independent() -> None:
    """双档分支并存零串档:银狼档行不影响景元路由(景元档行不影响银狼),
    其余角色恒注册表静态——家族第二成员扩展后既有路由零漂移。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs = replace(gs, lv999_cost_tier=Field(value=5, source='logic'))
    gs = replace(gs, yingyue_cost_tier=Field(value=1, source='logic'))
    assert effective_cost(gs, '银狼LV.999') == 5, '银狼读银狼档'
    assert effective_cost(gs, '景元') == 1, '景元读景元档'
    assert effective_cost(gs, '希儿') == CHARACTERS['希儿'].cost, \
        '非档成员恒静态'


# ============================================================ 锁 2 档感知退款


def test_bench_char_cost_yingyue_tier_aware() -> None:
    """bench_char_cost 景元档感知(gs 给定时经读口;gs 缺省回落起始费):
    退款账实链按当前档计(tier=3 → 3 费公式,tier=1 → 1 费)。"""
    assert bench_char_cost(Unit(char_id='景元', star=1), _gs(3)) == 3, \
        '当前档 3 费'
    assert bench_char_cost(Unit(char_id='景元', star=1), _gs(1)) == 1, \
        '当前档 1 费'
    assert bench_char_cost(Unit(char_id='景元', star=1), _gs(None)) == \
        CHARACTERS['景元'].cost, '未拿卡回落注册表起始费'
    assert bench_char_cost(Unit(char_id='景元', star=1)) == \
        CHARACTERS['景元'].cost, 'gs 缺省 = 起始费(存量调用面保底)'
