"""假游戏环境保真件·规则模块(T-120 sim 重设计 批 1)。

**归属判据(方案 §2.2 转移规则表)**:属于「游戏怎么运转」的模拟件——
每备战期收入 / 连胜结算 / 商店开关店画面身份迁移。这些规则在
``cw_state.simulate``(动作投影单一源)**没有分支**(Action 联合类型无
「进入新回合」语义),按方案裁决落在环境保真件层,本模块是其批次 1
交付面;prep 编排动作(收球/开箱/装备穿戴)的转移规则归批 2。

**单一源纪律**:常量与公式全部 kernel/引擎真码直调或按其重述,本模块
零平行真值——

- 收入值分量(base/interest/streak):``kernel/cw_economy
  .round_start_income`` 单一源直调(T-64 切源,与引擎消费缝
  ``sim_round_income`` 同源同式;原 ``REWARD_BASE_GOLD_BY_ROUND``
  奖励轮 round 单键直查 = P2r1/P3r1 误返 3 的 hazard 形态,
  fields.md §4.2 奖励轮行明文禁用——随切源结构性消灭)。连胜分量
  已乘 ``win_reward_mult``(伟大征服 ×3;fields.md §4.1「施于连胜
  分量含奖励轮」,聚合取最大不叠乘 = ADR-0623)。败轮金槽仍按
  ``LOSS_GOLD_BY_NODE`` 类型表连胜槽替换(ADR-0439 口径;与 kernel
  败补支 = 玩家裁定口径的竞争挂账 ADR-0623 决策3 待定谳,sim 常量
  修正随定谳);三分量全集 = 结算金币明细弹窗
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
    LOSS_GOLD_BY_NODE,
    round_start_income,
)
from sr_od.application.currency_war.kernel.cw_state import GameState

#: 战斗类节点(连胜/连败与败轮金的判定域;奖励/补给不结连胜)
_COMBAT_NODES: tuple[str, ...] = ('battle', 'encounter', 'boss')


def income_for_round(st: GameState, rng: random.Random,
                     prev_node: str | None, prev_combat_lost: bool) -> dict[str, int]:
    """每备战期收入分解(方案 §2.2 收入行;规则知识按 kernel 真码直调
    重述一次,ADR-0439 锚随迁——旧载体退役后本函数是该规则知识的
    存活处,非第二实现)。

    值分量三支(base/interest/streak)= ``round_start_income`` 单一源
    直调(T-64 切源;T-21 引擎侧同款收口):原奖励轮 base 按 round
    单键直查注册表 = P2r1/P3r1 误返 3 的 hazard 形态(fields.md §4.2
    奖励轮行明文禁用),随切源结构性消灭;连胜分量已乘
    ``win_reward_mult``(伟大征服 ×3,施于连胜分量含奖励轮——
    fields.md §4.1;缺省无持卡恒 1.0 = 逐位零漂移)。

    分量语义(键 = 收入分解账本口径;三分量全集 = 结算金币明细弹窗,
    economy.md §11):

    - ``base``:平面感知键(kernel ``reward_base_gold``;P1 {1:3,2:4}、
      P2r1/P3r1=5、其余 5,各分支同款键);
    - ``interest``:min(息帽, gold//10) + flat 息。息帽/flat 单一源 =
      kernel 聚合链(``aggregate_economy`` + ``interest_cap_resolved``,
      ADR-0516 cap 三源归一/ADR-0598 息帽死链修复口径):已持投资
      策略聚合取 cap 覆写(并持取宽 = ADR-0131,**0 是有效覆写**——
      买断制息通道改写,判别只认 None,禁 ``or 缺省`` 真值折叠)与
      flat 息(狸财经狸,与息帽无关);未持卡回 DEFAULT_INTEREST_CAP
      = 缺省主路径零漂移;
    - ``streak``:补给轮零发(连胜不动,ADR-0439 决策 2);奖励/常规
      轮 = streak_gold × win_reward_mult(四舍五入取整,kernel 同式);
      非连胜态(≤0)且上一轮是败掉的战斗类节点 → 连胜槽替换
      LOSS_GOLD_BY_NODE[prev_node](败轮金;**不乘** win_reward_mult)。
      带符号口径:连败侧 -N 与 0 同判(streak_gold 内部 max(0,) 钳制
      把连败值归表首,与引擎无符号 streak==0 判据同值);
    - ``event``:恒 0(奖励球金归收球域,机制申报见模块头——
      引擎 EVENT_GOLD_BY_ROUND 为残差补偿闸,非机制真值,不继承);
    - ``invest``(**仅在有持卡且聚合 gold_per_node>0 时出现**的第四键,
      engine_p1 账本行形状同构——缺省路径分解恒 3 键 + event,行形状
      不变):gold_per_node(每节点给金,注册表聚合值)。

    ``rng`` 消费归发放股(调用方传入 FakeMatch._rng_grant):收入域加
    消费不位移日程/抽店/战斗三股的流位置(重放对账的分流前提)。本域
    现无 rng 消费者,参数保留占股约定。
    返回分解 dict(不落金——入账由调用方对 ``state.gold`` 一次落定)。
    """
    node = st.node_type or 'battle'
    rn = st.round_num
    streak = st.streak or 0
    # 持卡聚合(kernel 单一源;惰性 import 保模块导入轻,与文件内
    # 数据模块同模式)
    from sr_od.application.currency_war.kernel.cw_investments import (
        aggregate_economy,
    )
    _held = list(st.active_strategies or [])
    _agg = aggregate_economy(_held) if _held else None
    # 值分量三支 = kernel 单一源(T-64 切源;cap/flat/mult 经聚合入参,
    # kernel 内部 interest_cap_resolved 归一——None 判别缺省,0 覆写有效)
    _inc = round_start_income(
        st.plane, rn, node, st.gold, streak,
        win_reward_mult=(_agg.win_reward_mult
                         if _agg is not None else 1.0),
        interest_flat=(_agg.interest_flat_per_node
                       if _agg is not None else 0),
        interest_cap=(_agg.interest_cap_override
                      if _agg is not None else None))
    streak_amt = _inc.streak
    if (node not in ('supply', 'reward') and streak <= 0
            and prev_combat_lost and prev_node in LOSS_GOLD_BY_NODE):
        # 带符号口径:非连胜态(≤0)+上一战斗类节点败掉 → 败轮金
        #(engine_p1 无符号 streak==0 的同构翻译;连败侧 -N 与 0 同判,
        # streak_gold 内部 max(0,) 钳制把连败值归表首,与引擎一致;
        # ADR-0439 类型表连胜槽替换,win_reward_mult 不生效)
        streak_amt = LOSS_GOLD_BY_NODE[prev_node]
    out = {
        'base': _inc.base,
        'interest': _inc.interest,
        'streak': streak_amt,
        'event': 0,
    }
    if _agg is not None and _agg.gold_per_node:
        out['invest'] = _agg.gold_per_node
    return out


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


# ============================================================ 供给/典籍发放域(批 3)
# 归属判据(方案 §2.2 装备发放行):供给节点 3 选 1(基础件池)+ 追加件
# 通道的**校准层参数**单一源 = engine_p1 EQUIP_GRANT 校准族直调(import
# 身份,禁复写第二源);选项/追加件抽选纯函数在此,转移机制在 FakeMatch
# (需多槽联动:库存/座位/浮层栈)。机制原文锚:
# - 供给选项池 = 基础件 8 名均匀池(engine_p1:204 区供给校准注原文
#   「供给节点 3 选项采自基础件 8 名均匀池」);
# - 追加件 = 每供给节点按 EQUIP_GRANT_BONUS_P 概率 +1 件,其中进阶占比
#   EQUIP_GRANT_BONUS_ADV_SHARE(engine 校准段口径随迁);
# - 典籍(星徽四选一选项)= 注册表星徽件(category='星徽')均匀抽 4,
#   注册表单一源 = cw_equipment_data.EQUIPMENTS。
#
# 供给校准版本位:engine ``EQUIP_GRANT_CALIB_VERSION`` 语义随环境指纹
# (FakeMatch.env_fingerprint)升级申报,不另立第二版本号。

from sr_od.application.currency_war.sim.engine_p1 import (  # noqa: E402
    EQUIP_GRANT_BONUS_ADV_SHARE,
    EQUIP_GRANT_BONUS_P,
)


def supply_options(rng: random.Random, k: int = 3) -> list[str]:
    """供给节点选项抽选(基础件 8 名均匀池;engine 供给校准段同构)。

    ``rng`` = 发放股(FakeMatch._rng_grant):发放域加消费不位移
    日程/抽店/战斗三股(重放对账的分流前提)。
    """
    from sr_od.application.currency_war.data.cw_synthesis import (
        RESERVED_COMPONENTS,
    )
    bases = sorted(RESERVED_COMPONENTS)
    return rng.choices(bases, k=k)


def supply_bonus(rng: random.Random) -> str | None:
    """供给节点追加件掷签(命中返装备名,未命中返 None)。

    概率/构成单一源 = engine EQUIP_GRANT 校准族(本模块 import 身份);
    进阶/基础构成 = ADV_SHARE 掷进阶,进阶件从注册表进阶层均匀抽,
    基础件同 :func:`supply_options` 池。
    """
    from sr_od.application.currency_war.data.cw_equipment_data import (
        EQUIPMENTS,
    )
    if rng.random() >= EQUIP_GRANT_BONUS_P:
        return None
    if rng.random() < EQUIP_GRANT_BONUS_ADV_SHARE:
        advances = sorted(n for n, e in EQUIPMENTS.items()
                          if e.category == '进阶')
        return rng.choice(advances)
    return supply_options(rng, k=1)[0]


def tome_emblem_options(rng: random.Random, k: int = 4) -> list[str]:
    """星徽秘典四选一选项抽选(注册表星徽件均匀抽 k;不重复)。

    注册表单一源 = ``cw_equipment_data.EQUIPMENTS``(category='星徽',
    22 张;equipment_mechanics.md §6)。选项名 = 星徽装备全名('X星徽');
    rng 归发放股。
    """
    from sr_od.application.currency_war.data.cw_equipment_data import (
        EQUIPMENTS,
    )
    emblems = sorted(n for n, e in EQUIPMENTS.items()
                     if e.category == '星徽')
    return rng.sample(emblems, k=min(k, len(emblems)))

# ---- 商店直出 2★ 通道(T-122;机制层,非收入层)----

#: 直出 2★ 每槽每帧升档概率(校准层·演练偏置):机制锚 = merge_mechanics
#: §2.6/§2.7 实锤(商店直出 2★/3★ 存在,费用 ×3 实付;**频率「概率待实机
#: 调研」零样本存档**)——本常量取值使机制在批量局可观测(装载设计 §3.2),
#: **禁把该速率下频次读成真值估计**;真值随采集批(商店 2★ 直出频次)
#: 回填并升 env_version。3★ 直出(×9)未建模。
SHOP_DIRECT_OUT_2STAR_P: float = 0.05
