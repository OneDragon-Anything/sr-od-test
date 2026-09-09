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
  streak 分量照发 + base 查表);三分量全集 = 结算金币明细弹窗
  (docs/game/currency_war/research/economy.md §11:基础+连胜+利息,
  无第四分量);
- 事件金分量恒 0(保真度校准裁定,出处 =
  ``.debug/temp/currency_war/t120_sim_redesign/保真度校准.md``):奖励球
  是备战期收球动作(方案 §2.2 prep 编排面,归批 2),假环境观察面
  spheres 结构性为零 → 收入侧如实不发球金。引擎 ``EVENT_GOLD_BY_ROUND``
  **不继承**——该表是 ADR-0447 残差补偿闸(按「实机帧金均值 − 引擎帧
  金均值」整定,吸收执行缺陷时代的全部金流缺口,r9 分量含泄金补偿;
  表 docstring 明文「策略面修复后不得以此表回填」),语义非节点事件金
  机制真值,直继承会把补偿量当收入发给正常花销的策略器(校准前假局
  r9 期初金 220+ vs 实机 48-73 的主因);批 2 接球域时按球真值另行
  建模,禁回指本表;
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

#: 战斗类节点(连胜/连败与败轮金的判定域;奖励/补给不结连胜)
_COMBAT_NODES: tuple[str, ...] = ('battle', 'encounter', 'boss')


def income_for_round(st: GameState, rng: random.Random,
                     prev_node: str | None, prev_combat_lost: bool) -> dict[str, int]:
    """每备战期收入分解(方案 §2.2 收入行;规则知识自 engine_p1 收入段
    :829-878 重述一次,ADR-0439/0233 锚随迁——旧载体退役后本函数是
    该规则知识的存活处,非第二实现)。

    分量语义(键 = 收入分解账本口径;三分量全集 = 结算金币明细弹窗,
    economy.md §11):

    - ``base``:BASE_INCOME;奖励轮查 REWARD_BASE_GOLD_BY_ROUND(成对
      改口径:奖励轮 streak 分量照发,base 查表补位,ADR-0439);
    - ``interest``:min(息帽, gold//10)(息帽 = DEFAULT_INTEREST_CAP;
      持卡注入的息帽覆写/flat 息归投资注入面,批 3 接入时随浮层栈进);
    - ``streak``:补给轮零发(ADR-0439:实发零发放证据样本不足,条件
      升级挂账同源);奖励轮照发 streak_gold;连胜==0 且上一轮是败掉的
      战斗类节点 → 发 LOSS_GOLD_BY_NODE[prev_node](败轮金);其余 =
      streak_gold(streak);
    - ``event``:恒 0(奖励球金归批 2 收球域,机制申报见模块头——
      引擎 EVENT_GOLD_BY_ROUND 为残差补偿闸,非机制真值,不继承)。

    ``rng`` 消费归发放股(调用方传入 FakeMatch._rng_grant):收入域加
    消费不位移日程/抽店/战斗三股的流位置(重放对账的分流前提)。本批
    收入域暂无 rng 消费者(球金批 2 回填时启用),参数保留占股约定。
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
        'event': 0,
    }


# ============================================================ prep 编排域(批 2)
# 归属判据(方案 §2.2 F6 行):收球/开箱/装备穿戴在 ``cw_state.simulate``
# 无分支(Action 联合类型无对应动作),转移语义落在环境保真件层;本节
# 只放**校准层参数常量**(带误差,参数账纪律),转移机制在 FakeMatch
# (状态机职责,需多槽联动:pool/浮层栈/座位表)。
#
# 球奖励三通道**结构** = 实录锚 ``docs/game/currency_war/research/
# screen_flow_timing.md`` #16(备战画面点奖励球:奖励角色→备战 /
# 金币→商店 / 装备→右侧装备栏);**概率与金额** = 校准层参数
# (注册表无球金机制真值;引擎 ``EVENT_GOLD_BY_ROUND`` 是 ADR-0447
# 残差补偿闸,禁回指——批 1 锁 test_income_event_component_stays_zero
# 在辖)。参数变更 = 环境分布变更,须随 env_version 位升版申报。

#: 单球奖励通道权重(校准层;金币主导 = 开局/前期观测面缺定量记录的
#: 保守形态,后续按实机球奖励画像重校准时改此处 + 升 env_version)
BALL_REWARD_WEIGHTS: dict[str, float] = {'gold': 0.7, 'equip': 0.2, 'char': 0.1}

#: 单球金币额(校准层;收入 event 分量恒 0 的对立面 = 球金只经收球
#: 动作入账,Income 分解不承载)
BALL_GOLD: int = 4

#: 点球掉箱概率(校准层;「掉箱即停回环交规则统筹」= ClickSpheres
#: 词表注的规则面:掉箱占一备战空席,席满时该通道落空不结算)
BALL_BOX_DROP_P: float = 0.25

#: 奖励节点带球数(校准层;开局球恒 1 件 = screen_flow_timing #5
#: 「开局补给:给开局角色 + 奖励球」实录,落在 FakeMatch 开局段)
BALLS_PER_REWARD_NODE: int = 2


def ball_reward_channel(rng: random.Random) -> str:
    """单球奖励通道采样(权重单一源 = :data:`BALL_REWARD_WEIGHTS`)。

    ``rng`` = 发放股(FakeMatch._rng_grant):球域加消费不位移
    日程/抽店/战斗三股(重放对账的分流前提)。
    """
    channels = list(BALL_REWARD_WEIGHTS)
    weights = [BALL_REWARD_WEIGHTS[c] for c in channels]
    return rng.choices(channels, weights=weights, k=1)[0]


def box_card_options(pool_names: list[str], rng: random.Random,
                     k: int = 4) -> list[str]:
    """武装箱选项抽选(同店抽池同源;数量 4 = PickBoxCard card_idx 1-4 词表)。

    ``pool_names`` = 牌池可发名字集(调用方从 _Pool.copies 过滤正库存);
    抽序归发放股。选中件 take、未选件 ret 的守恒语义由调用方落
    (FakeMatch.apply_prep 的 PickBoxCard 分支)。
    """
    names = list(pool_names)
    rng.shuffle(names)
    return names[:k]


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
