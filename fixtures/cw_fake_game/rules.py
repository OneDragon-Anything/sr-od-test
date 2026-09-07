"""假游戏环境保真件·规则模块(T-120 sim 重设计 批 1)。

**归属判据(方案 §2.2 转移规则表)**:属于「游戏怎么运转」的模拟件——
每备战期收入 / 连胜结算 / 商店开关店画面身份迁移。这些规则在
``cw_state.simulate``(动作投影单一源)**没有分支**(Action 联合类型无
「进入新回合」语义),按方案裁决落在环境保真件层,本模块是其批次 1
交付面;prep 编排动作(收球/开箱/装备穿戴)的转移规则归批 2。

**单一源纪律**:常量与公式全部 kernel/引擎真码直调或按其重述,本模块
零平行真值——

- 收入分量:``kernel/cw_economy``(BASE_INCOME / REWARD_BASE_GOLD_BY_ROUND /
  LOSS_GOLD_BY_NODE / streak_gold / interest),口径 = ADR-0439 收入模型
  (108 局/767 轮 gold 差分实证:败轮金替换旧 streak_gold(0)=1;奖励轮
  streak 分量照发 + base 查表);
- 事件金表:``sim/engine_p1`` EVENT_GOLD_BY_ROUND(ADR-0447 校准总闸,
  ±2 抖动)——引擎退役批(方案 §6.2 批 4)该表随引擎体迁移,届时本
  import 改指新落点(申报在案,防静默双源);
- 胜负判定:``kernel/cw_coarse_battle`` WIN_CAP(coarse 主路径胜态交付值,
  F7 主从口径随迁)。

方案出处 = ``.debug/temp/currency_war/t120_sim_redesign/方案.md`` §2.2
(**易失产物**,ADR 落点待 T-120 退役批分配,后续批回填编号)。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_economy import (
    BASE_INCOME,
    DEFAULT_INTEREST_CAP,
    LOSS_GOLD_BY_NODE,
    REWARD_BASE_GOLD_BY_ROUND,
    interest,
    streak_gold,
)
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.sim.engine_p1 import EVENT_GOLD_BY_ROUND

#: 战斗类节点(连胜/连败与败轮金的判定域;奖励/补给不结连胜)
_COMBAT_NODES: tuple[str, ...] = ('battle', 'encounter', 'boss')


def event_gold(round_num: int, rng: random.Random) -> int:
    """节点事件金(规则知识自 engine_p1 ``_event_gold`` 重述,ADR-0447)。

    基值查表 + ±2 均匀抖动、下钳 0——公式与缺省 (4,) 回退逐位同源,
    表本体不复制(引擎退役批随迁改指,见模块头申报)。
    """
    base = EVENT_GOLD_BY_ROUND.get(round_num, (4,))[0]
    return max(0, int(base + rng.uniform(-2, 2)))


def income_for_round(st: GameState, rng: random.Random,
                     prev_node: str | None, prev_combat_lost: bool) -> dict[str, int]:
    """每备战期收入分解(方案 §2.2 收入行;规则知识自 engine_p1 收入段
    :829-878 重述一次,ADR-0439/0233 锚随迁——旧载体退役后本函数是
    该规则知识的存活处,非第二实现)。

    分量语义(键 = 收入分解账本口径):

    - ``base``:BASE_INCOME;奖励轮查 REWARD_BASE_GOLD_BY_ROUND(成对
      改口径:奖励轮 streak 分量照发,base 查表补位,ADR-0439);
    - ``interest``:min(息帽, gold//10)(息帽 = DEFAULT_INTEREST_CAP;
      持卡注入的息帽覆写/flat 息归投资注入面,批 3 接入时随浮层栈进);
    - ``streak``:补给轮零发(ADR-0439:实发零发放证据样本不足,条件
      升级挂账同源);奖励轮照发 streak_gold;连胜==0 且上一轮是败掉的
      战斗类节点 → 发 LOSS_GOLD_BY_NODE[prev_node](败轮金);其余 =
      streak_gold(streak);
    - ``event``:事件金(见 :func:`event_gold`)。

    ``rng`` 消费归发放股(调用方传入 FakeMatch._rng_grant):收入域加
    消费不位移日程/抽店/战斗三股的流位置(重放对账的分流前提)。
    返回分解 dict(不落金——入账由调用方对 ``state.gold`` 一次落定)。
    """
    node = st.node_type or 'battle'
    rn = st.round_num
    streak = st.streak or 0
    if node == 'supply':
        streak_amt = 0
    elif node == 'reward':
        streak_amt = streak_gold(streak)
    elif streak <= 0 and prev_combat_lost and prev_node in LOSS_GOLD_BY_NODE:
        # 带符号口径:非连胜态(≤0)+上一战斗类节点败掉 → 败轮金
        #(engine_p1 无符号 streak==0 的同构翻译;连败侧 -N 与 0 同判,
        # streak_gold 内部 max(0,) 钳制把连败值归表首,与引擎一致)
        streak_amt = LOSS_GOLD_BY_NODE[prev_node]
    else:
        streak_amt = streak_gold(streak)
    return {
        'base': (REWARD_BASE_GOLD_BY_ROUND.get(rn, BASE_INCOME)
                 if node == 'reward' else BASE_INCOME),
        'interest': interest(st.gold, DEFAULT_INTEREST_CAP),
        'streak': streak_amt,
        'event': event_gold(rn, rng),
    }


def settle_streak(st: GameState, delta: int, node: str) -> tuple[int, bool]:
    """节点结算的连胜/败轮状态迁移(输入 = 采样 delta 与节点类型)。

    返回 (new_streak, combat_lost)。带符号口径逐位随迁 engine_p1
    :2117-2130(生产契据:连胜 +/连败 −,奖励/补给轮不动;胜态判据 =
    delta > 0,与结算段 :2118 同式,非「== WIN_CAP」的窄判——coarse 表
    未来出现小正值非胜态时引擎口径仍正确,本函数随之):
    胜 → 正值域 +1(连败后首胜归 1);负 → 负值域 −1(连胜后首败归 −1)。
    combat_lost = 「本战斗类节点败掉(delta<=0)」,供下一备战期的败轮金
    判定(ADR-0439 口径的跨轮状态,非本函数入账)。
    """
    prev = st.streak or 0
    if node not in _COMBAT_NODES:
        return prev, False
    if delta > 0:
        return (prev + 1) if prev > 0 else 1, False
    return (prev - 1) if prev < 0 else -1, True
