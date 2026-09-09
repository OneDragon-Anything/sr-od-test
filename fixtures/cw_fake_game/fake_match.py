"""假游戏状态机(T-120 批 0 骨架 + 批 1 环境规则补全 + 开局态保真校准)。

**状态容器 + 转移单一源 + 战斗结算 + 回合规则**(批 1 补全面):在批 0
骨架(状态容器/``apply`` 直调 simulate/coarse+Δ池结算/四股随机流)之上,
补全 P1 全段可跑所需的回合域规则——收入分解(:mod:`rules`,ADR-0439
口径)、连胜/败轮状态迁移、hp 结算上界钳制(ADR-0287,批 0 申报的
「上界钳制缺位」归本批)、商店开关店画面身份规则(``open_shop``/
``close_shop``;落地审登记的「终结动作 phase 转移语义」批 1 边界的
承接形)。prep 编排动作(收球/开箱/装备穿戴)与位面继承仍归批 2/3
(方案 §6.2 分批表)。

**开局态保真校准**(env_version v2):开局等级/金库按实机机制真值建模
(lv3/金 5,三源互证锚见 ``_OPENING_LEVEL``/``DEFAULT_OPENING_GOLD`` 注)
——校准前 lv1 开局使 XP 表外态卡死升级链、注金 30 放大囤金假象,假局
金/等级/花销三指标全面偏离实机分布(对账 =
``.debug/temp/currency_war/t120_sim_redesign/保真度校准.md``)。

**单一源纪律(本文件的存在理由)**:动作转移**只经**
``cw_state.simulate`` 直调——假游戏不内联任何动作转移(sim-design §2.1
双源禁令在假游戏侧同样生效;方案 §2.2 商店动作结算行)。刷新重抽、
牌池 take/ret、回合域收入属「规则外效应」,是假游戏规则层职责
(RefreshShop 在 simulate 侧只扣金不模拟牌,``cw_state.simulate`` 的
RefreshShop 分支注释在案)。

**确定性契约**:同 seed + 同环境指纹 → 逐位可复现(方案 §2.2 确定性行;
sim-testing「重放 = seed + 池指纹」契约的假游戏侧扩形)。随机流 = 主
种子派生四股(日程/抽店/战斗/发放),股间互不串扰——某域加消费不位移
他域的流位置。真值来源全部是 kernel/sim 真码直调,本文件零平行实现。

**Δ池源显式 snapshot**:本骨架固定 ``resolve_pool('snapshot')``(主仓
提交快照,零本地产物依赖)——不用 'auto'(读生产 replay 目录 = 测试
真实副作用,违反测试零副作用纪律);缺源大声报错纪律由 pool 自带。
方案出处 = `.debug/temp/currency_war/t120_sim_redesign/方案.md` §2.2
(**易失产物**,ADR 落点待 T-120 退役批分配,后续批回填指针)。
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from fixtures.cw_fake_game import rules
from sr_od.application.currency_war.cw_game_ports import ExecResult
from sr_od.application.currency_war.kernel import cw_state
from sr_od.application.currency_war.kernel.cw_battle_calib import (
    _deployable_depth,
    _settle_rung,
    node_delta,
    sample_node_sequence,
)
from sr_od.application.currency_war.kernel.cw_coarse_battle import (
    sample_battle_delta,
)
from sr_od.application.currency_war.kernel.cw_opening_hp import (
    OPENING_HP_BASE,
)
from sr_od.application.currency_war.kernel.cw_state import (
    XP_TO_NEXT_LEVEL,
    Action,
    GameState,
    bench_place,
)
from sr_od.application.currency_war.sim.engine_p1 import (
    HP_UPPER_BOUND,
    START_BENCH_COST_WEIGHTS,
    START_BENCH_COUNT,
)
from sr_od.application.currency_war.sim.pool import (
    _Pool,
    live_delta_for,
    resolve_pool,
)

#: 假游戏规则层版本位。语义 = 方案 §2.2 LEVEL_CAP 裁决的申报载体:假游戏
#: 按游戏真值(lv10 禁购)建模,不继承 engine_p1 ``LEVEL_CAP=9`` sim-only
#: 冻结——lv10 真值封顶由 simulate 自带(cw_state.py:1512 ``s.level < 10``),
#: 本骨架直调即继承。环境指纹含本位,跨版本对照禁裸串比(与池指纹同纪律)。
#: v2 = 开局态校准(开局等级/金对齐实机机制) + 收入事件金分量归零,
#: 出处 = ``.debug/temp/currency_war/t120_sim_redesign/保真度校准.md``;
#: v3 = prep 编排域实体化(球金入账/收球/开箱/装备穿戴/部署走真链,
#: 批 2;球域参数账见 :mod:`rules` prep 节)——分布面变更,与 v1/v2 不可比。
#: v1 批次(批 1 保真度基线)与本版不可比。
FAKE_GAME_ENV_VERSION: int = 3

#: 开局等级 = 3(重述 engine_p1 开局真值 ``st.level = 3``——引擎行是裸
#: 字面量无符号名,故本骨架按值重述+锚注,非 import)。三源互证:
#: ①引擎 P1 开局态(engine_p1.py:692);②``XP_TO_NEXT_LEVEL`` 键域从 3
#: 起(cw_state.py:44)——lv1/lv2 是真游戏不存在的表外态(校准前假局
#: 开局 lv1 使升级链落入表外回退:lv2 的 need 回退 0 = 假满级,策略器
#: 停升、等级停滞 lv1-2);③实机 13 局近期档案 P1 r1 帧等级恒 3。
_OPENING_LEVEL: int = 3

#: 开局金库 = 5(同款重述 engine_p1 ``st.gold = 5``;实机 13 局 r1 决策
#: 帧金中位 5|p90 7 互证——校准前剧本注金 30 放大「只进不出」假象)。
DEFAULT_OPENING_GOLD: int = 5

# ---- 画面身份词表(方案 §2.2:词表 = screen_info 画面档名,外循环
# ---- dispatch 消费同名;骨架只列核心推进档,浮层档随批 2/3 词汇扩展。
# ---- 单一源 = assets/game_data/screen_info/<screen_id>.yml 的 screen_name)----
PHASE_PREP: str = '货币战争-备战'
PHASE_PREP_SHOP_OPEN: str = '货币战争-备战-开商店'
PHASE_BATTLE: str = '货币战争-战斗'
PHASE_SETTLE: str = '货币战争-战斗结算'
PHASE_PLANE_TRANSITION: str = '货币战争-位面过渡'
PHASE_LOBBY: str = '货币战争-大厅'

#: 开局 hp 缺省(骨架便捷值)——单一源 = kernel/cw_opening_hp.
#: OPENING_HP_BASE(ADR-0559 初值表:A8/108 基础 82 零方差;import 非复写,
#: 初值表重校准自动跟随,落地审 L1 修后口径)。仅免「hp=None 无法结算」
#: 的样板,非环境保真申报面——开局词缀/难度对 hp 的影响归批 1 规则模块。
DEFAULT_OPENING_HP: int = OPENING_HP_BASE


@dataclass
class OverlayFrame:
    """待处理浮层(kind + 选项载荷;方案 §2.2 浮层栈行)。

    ``kind`` = pick 族词表键(invest/supply/encounter/...);``payload``
    = 选项载荷(元素形状随 kind,同端口 ``overlay_options`` 的契约——
    不折叠结构)。
    """

    kind: str
    payload: list[Any] = field(default_factory=list)


@dataclass
class ObservationRecord:
    """一次观察调用的留痕(方案 §2.3 契约二则:读屏次数语义保留)。

    观察注入换掉的是读图,不是「观察」这个语义事件——读屏节奏类判读
    (如刷新终结→重观察结构)在假环境靠本留痕审计。
    """

    seq: int
    # [索引定义] 坐标系: observation_log 列表下标(1 起,append-only)
    #             取值时机: 生成期=执行期恒稳(只追加,不删改)
    method: str   # 端口方法名(screen_identity/observe_prep/...)
    arg: str | None   # 方法主参(observe_prep=阶段键 / overlay_options=kind)
    clock: int    # 留痕时点的逻辑时钟(FakeMatch.clock,语义事件序非真实时间)


@dataclass
class BattleSettlement:
    """一次节点结算的回执(骨架最小面)。

    ``delta`` 极性与产线一致 = hp 变化量(方案 §4-4:killed/胜负语义
    同产线——killed 判定读 ``hp_after <= 0``,streak/遥测行归批 1)。
    """

    node: str
    delta: int      # hp 变化量(采样原值,未含 hp 下钳)
    hp_after: int   # 钳制后 hp(≥0 = 假游戏死亡态)


class FakeMatch:
    """一局假游戏的状态机(方案 §2.2「单一对象 FakeMatch」)。

    状态槽:对局态 = 真 ``GameState``(零平行结构);画面身份 =
    ``phase``(screen_info 画面档名);节点日程 = ``node_sequence``
    (剧本注入或 ``sample_node_sequence`` 真码采样);牌池 = ``_Pool``
    真码;浮层栈 = ``overlay_stack``;随机流 = 主种子派生四股。
    """

    def __init__(self, seed: int, *,
                 node_sequence: list[str] | None = None,
                 initial_hp: int = DEFAULT_OPENING_HP) -> None:
        self.seed: int = seed
        # 随机流:主种子派生四股(getrandbits 派生,股间互不串扰——
        # 某域新增 rng 消费不位移他域流位置,重放对账的分流前提)
        _master = random.Random(seed)
        self._rng_schedule: random.Random = random.Random(_master.getrandbits(64))
        self._rng_draw: random.Random = random.Random(_master.getrandbits(64))
        self._rng_battle: random.Random = random.Random(_master.getrandbits(64))
        self._rng_grant: random.Random = random.Random(_master.getrandbits(64))
        # 节点日程:剧本注入(确定性测试)优先,否则真码采样
        self.node_sequence: list[str] = (
            list(node_sequence) if node_sequence is not None
            else sample_node_sequence(self._rng_schedule))
        self._node_idx: int = 0
        # Δ池:显式 snapshot 源(确定性 + 零本地产物依赖,见模块头注)
        self._delta_pool_map, self.delta_pool_fingerprint, _ = resolve_pool(
            'snapshot')
        self.shop_pool: _Pool = _Pool(self._rng_draw)
        self.overlay_stack: list[OverlayFrame] = []
        self.observation_log: list[ObservationRecord] = []
        self.clock: int = 0
        self.phase: str = PHASE_PREP
        # 败轮金判定跨轮状态(engine_p1 :2128-2130 同构:prev_node 每
        # 节点更新,prev_combat_lost 只由战斗类节点置位;初值 = 无前轮)
        self._prev_node: str | None = None
        self._prev_combat_lost: bool = False
        # prep 编排域状态(批 2;方案 §2.2 F6 行):
        # spheres = 待收奖励球 [(color, r)](r 大 = 大球,观察面直出);
        # boxes = 占席补给箱的物理槽位表(1 基;箱 = bench 上 is_item_slot
        # 占位件,派生量 free_bench_slots/围栏 held 因此天然 truthful);
        # overlay 栈复用批 0 面('box' kind = 武装箱 4 选 1)。
        self.spheres: list[tuple[str, int]] = []
        self.boxes: list[int] = []
        self.state: GameState = GameState(
            plane=1,
            round_num=1,
            node_type=self.node_sequence[0],
            gold=DEFAULT_OPENING_GOLD,
            level=_OPENING_LEVEL,
            # xp 进度 = 当前级门槛表现算(单一源 XP_TO_NEXT_LEVEL,禁手抄;
            # 开局等级在表键域内——lv1/lv2 表外态禁再现,见 _OPENING_LEVEL 注)
            xp_progress=(0, XP_TO_NEXT_LEVEL[_OPENING_LEVEL]),
            hp=initial_hp,
        )
        self._deal_opening_bench()
        # 开局奖励球(screen_flow_timing.md #5「开局补给:给开局角色 +
        # 奖励球」实录;rng 归发放股)
        self.spawn_balls(1)

    def _deal_opening_bench(self) -> None:
        """开局补给 bench(校准面:真游戏开局给初始角色——机制锚 =
        screen_flow_timing.md #5「开局补给:给开局角色 + 奖励球,开局每局
        必经」;构成真值 = engine_p1 ``START_BENCH_COUNT``/
        ``START_BENCH_COST_WEIGHTS`` 直调,该常量注记「遥测校准:开局 4 张,
        1 费主导」,抽取序与引擎开局段同构)。校准前 bench 空开局的连锁:
        部署围栏无件可上 → deployed 恒空 → 板深 0(Δ池最凶掉血桶)+
        M3 升级触发信号 arm1_existence(板满∧bench 有候补)构造性不可达。
        rng 消费归发放股(开局补给 = 发放域;不位移日程/抽店/战斗三股)。
        牌从牌池 take(池守恒:开局牌占用副本计数)。
        """
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        from sr_od.application.currency_war.kernel.cw_state import BenchChar
        costs = [c for c, _ in START_BENCH_COST_WEIGHTS]
        weights = [w for _, w in START_BENCH_COST_WEIGHTS]
        for _ in range(START_BENCH_COUNT):
            cost = self._rng_grant.choices(costs, weights=weights, k=1)[0]
            names = [n for n in self.shop_pool.copies
                     if CHARACTERS[n].cost == cost
                     and self.shop_pool.copies[n] > 0]
            if not names:
                continue
            name = self._rng_grant.choice(names)
            self.shop_pool.take(name)
            bench_place(self.state.bench, BenchChar(
                slot=0, char_id=name,
                faction=(CHARACTERS[name].factions or ['散'])[0]))

    def _deal_bench_char(self, bc: cw_state.BenchChar) -> int | None:
        """一个角色入座首个空席并回填物理槽号(开局补给/球角色通道/选卡
        共用;座位真值 = bench 槽位表,禁列表 append)。"""
        from sr_od.application.currency_war.kernel.cw_state import bench_place

        placed = bench_place(self.state.bench, bc)
        return placed

    # ---- prep 编排域环境事实生成(批 2;球/箱生成 = 环境事件,非动作)----

    def spawn_balls(self, n: int) -> None:
        """生成 n 个待收奖励球(开局补给/奖励节点事件;大球优先语义的
        r 值 = 20 基础 + 序内抖动,观察面消费)。rng 归发放股。"""
        for _ in range(max(0, n)):
            r = 20 + self._rng_grant.randint(0, 6)
            self.spheres.append(('晶矿', r))

    def spawn_box(self) -> int | None:
        """生成一个占席补给箱(bench 上 is_item_slot 占位件;席满 = 无箱,
        返回 None)。物理槽 = 首个空席。"""
        from sr_od.application.currency_war.kernel.cw_state import BenchChar

        for i, b in enumerate(self.state.bench):
            if b is None:
                bc = BenchChar(slot=i + 1, char_id='', faction='?',
                               is_item_slot=True)
                self.state.bench[i] = bc
                self.boxes.append(i + 1)
                return i + 1
        return None

    def _take_first_free_slot(self) -> int | None:
        for i, b in enumerate(self.state.bench):
            if b is None:
                return i + 1
        return None

    # ---- prep 编排动作转移(批 2;方案 §2.2 F6 行「批 2 词汇」)----

    def apply_prep(self, action: Any) -> ExecResult:
        """族B(PrepAction 词表)动作落假游戏的唯一入口(批 2)。

        坐标系换算发生在本边界(族B 物理槽位 1 基 → 族A 槽位表下标
        0 基;对照表 = cw_state.py Action 节约定块),换算后一律直调
        :meth:`apply`(simulate 单一源)——本方法不内联任何动作转移。

        无 simulate 分支域(收球/开箱/选卡/装备穿戴)= 环境保真件层
        新增规则(方案 F6 裁决);常量单一源 = :mod:`rules` prep 节。
        StartBattle = 出战的环境承接(applied 恒真;战斗结算由编排方
        驱动 settle_battle)。OpenTome(典籍)批 2 不建模(P2 投资策略
        发放域)→ applied=False 显式拒绝;退役/兼容动作同判。
        """
        from sr_od.application.currency_war.kernel import cw_prep_actions as pa
        from sr_od.application.currency_war.kernel import cw_state

        if isinstance(action, pa.SellBench):
            return self.apply(cw_state.SellBench(bench_idx=action.slot - 1))
        if isinstance(action, pa.SellDeployed):
            idx = (action.slot - 1 if action.row == 'front'
                   else 4 + action.slot - 1)
            return self.apply(cw_state.SellDeployed(deployed_idx=idx))
        if isinstance(action, pa.DeployMove):
            target = (self.state.bench[action.from_slot - 1]
                      if 1 <= action.from_slot <= len(self.state.bench)
                      else None)
            faction = (target.faction if target is not None and target.faction
                       else '?')
            return self.apply(cw_state.DeployMove(
                bench_idx=action.from_slot - 1, to_row=action.to_row,
                faction=faction))
        if isinstance(action, pa.LevelUp):
            return self._apply_levelup_clicks()
        if isinstance(action, pa.ClickSpheres):
            return self._collect_spheres(action.max_k)
        if isinstance(action, pa.OpenBox):
            return self._open_box(action.slot)
        if isinstance(action, pa.PickBoxCard):
            return self._pick_box_card(action.card_idx)
        if isinstance(action, pa.RunDeploy):
            # 计划装配消费策略会话语境(target/fence 输入),由执行缝
            # 层(harness)组装后落本入口的单步转移——状态机不持会话。
            # 直发(无会话语境)= 保守围栏基干(cap 填空/去重)仍可落地。
            return self._run_deploy_basic()
        if isinstance(action, pa.RunEquip):
            return self._wear_equips(action)
        if isinstance(action, pa.StartBattle):
            self.clock += 1
            return ExecResult(applied=True, observed=self.state.copy())
        if isinstance(action, pa.OpenShop):
            self.open_shop()
            return ExecResult(applied=True, observed=self.state.copy())
        if isinstance(action, (pa.OpenTome, pa.DeferSpheres, pa.BailToOuter,
                               pa.EnsureShopOpen, pa.EnsureShopClosed,
                               pa.RunBuyPhase, pa.RunTools)):
            # OpenTome 批 2 不建模;其余 = 控制流/退役兼容面(控制流动作
            # 到不了执行缝,防御兜底);显式拒绝非静默。
            self.clock += 1
            return ExecResult(applied=False, observed=self.state.copy())
        raise TypeError(f'apply_prep 不认识的动作类型: {type(action).__name__}')

    def _apply_levelup_clicks(self) -> ExecResult:
        """prep LevelUp = 点「购买经验」至 level+1(词表语义)。

        simulate LevelUp 分支 = 单击(+XP_PER_BUY/−单击价,cw_state.py
        真实语义 ADR-0129);单击价/击数单一源 = kernel ``xp_click_cost``
        / ``clicks_to_next_level``(cw_economy)。金不足即停(fail-closed,
        与 live 执行器 _level_up 同向)。HP 支付结构性为零 = 环境边界
        (simulate 同不扣 HP,批 1 落地审申报面)。
        """
        from sr_od.application.currency_war.kernel.cw_economy import (
            clicks_to_next_level,
            xp_click_cost,
        )
        from sr_od.application.currency_war.kernel.cw_state import LevelUp

        level_pre = self.state.level
        clicks = clicks_to_next_level(self.state)
        spent = 0
        for _ in range(max(1, clicks)):
            price = xp_click_cost(self.state)
            if self.state.gold < price:
                break
            res = self.apply(LevelUp(cost=price))
            if not res.applied:
                break
            spent += price
        applied = self.state.level > level_pre or spent > 0
        return ExecResult(applied=applied, income=None,
                          verification={'levelup_spent': spent},
                          observed=self.state.copy()
                          if applied else None)

    def _collect_spheres(self, max_k: int) -> ExecResult:
        """收球(点奖励球):逐球三通道(rules.ball_reward_channel 单一源)。

        - gold:BALL_GOLD 入账;equip:基础件入 state.equips(库存正本,
          simulate 卖出回收分支同域);char:牌池 take + 入座空席
          (席满 = 收球中断,球保留——live 口径「席满时部分球可能没点开,
          由后续 heavy 观察自然回补」,screen_flow_timing #16);
        - 掉箱(rules.BALL_BOX_DROP_P):箱占一空席,席满落空;
        - 内验早停同词表(球数减即进展)。
        """

        picked = 0
        gained_gold = 0
        got_equip = 0
        got_char = ''
        dropped_box = 0
        while self.spheres and picked < max(1, max_k):
            channel = rules.ball_reward_channel(self._rng_grant)
            picked += 1
            self.spheres.pop()
            if channel == 'gold':
                gained_gold += rules.BALL_GOLD
                self.state.gold += rules.BALL_GOLD
            elif channel == 'equip':
                self.state.equips.append(self._draw_base_equip())
                got_equip += 1
            else:  # char
                bc = self._draw_pool_char_to_bench()
                if bc is None:
                    # 席满:角色奖励落空即中断(球已消耗,live 同口)
                    break
                got_char = bc.char_id
            if (self._rng_grant.random() < rules.BALL_BOX_DROP_P
                    and self._take_first_free_slot() is not None):
                if self.spawn_box() is not None:
                    dropped_box += 1
                    break   # 掉箱即停(词表注:回环交规则统筹)
        applied = picked > 0
        return ExecResult(applied=applied, income=None,
                          verification={'picked': picked,
                                        'gold': gained_gold,
                                        'equip': got_equip,
                                        'char': got_char,
                                        'box_dropped': dropped_box},
                          observed=self.state.copy() if applied else None)

    def _draw_base_equip(self) -> str:
        """基础件均匀抽选(库存正本 state.equips 的来源通道)。

        基础件名集单一源 = kernel ``cw_synthesis.RESERVED_COMPONENTS``
        ∩ 装备名册(engine 供给校准段 3 选 1 池的同源过滤式,非第二表)。
        """
        from sr_od.application.currency_war.data.cw_equipment_data import (
            EQUIPMENT_ROSTER,
        )
        from sr_od.application.currency_war.data.cw_synthesis import (
            RESERVED_COMPONENTS,
        )
        basics = [n for n in RESERVED_COMPONENTS if n in EQUIPMENT_ROSTER]
        return self._rng_grant.choice(basics)

    def _draw_pool_char_to_bench(self) -> cw_state.BenchChar | None:
        """牌池抽一角色入座空席(池守恒:take;席满/池空返回 None)。"""
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        from sr_od.application.currency_war.kernel.cw_state import BenchChar

        if self._take_first_free_slot() is None:
            return None
        names = [n for n, c in self.shop_pool.copies.items() if c > 0]
        if not names:
            return None
        name = self._rng_grant.choice(names)
        self.shop_pool.take(name)
        ch = CHARACTERS[name]
        bc = BenchChar(slot=0, char_id=name,
                       faction=(ch.factions or ['散'])[0],
                       position_pref=ch.position_pref())
        self._deal_bench_char(bc)
        return bc

    def _open_box(self, slot: int | None) -> ExecResult:
        """开补给箱:箱离席(腾席)+ 压「box」浮层(4 选 1 载荷)。

        选项 = 武装箱同店抽池(rules.box_card_options 单一源);选中件
        take、未选件 ret 的守恒语义在 _pick_box_card 落(选项暂存 = 浮层
        载体,不占池)。
        """
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS

        slot_no = slot
        if slot_no is None and self.boxes:
            slot_no = self.boxes[0]
        if slot_no is None or slot_no not in self.boxes:
            return ExecResult(applied=False, observed=self.state.copy())
        idx = slot_no - 1
        target = (self.state.bench[idx]
                  if 0 <= idx < len(self.state.bench) else None)
        if target is None or not target.is_item_slot:
            return ExecResult(applied=False, observed=self.state.copy())
        self.state.bench[idx] = None
        self.boxes = [s for s in self.boxes if s != slot_no]
        options = rules.box_card_options(
            [n for n, c in self.shop_pool.copies.items() if c > 0],
            self._rng_grant)
        self.push_overlay('box', [(n, CHARACTERS[n].cost) for n in options])
        return ExecResult(applied=bool(options), observed=self.state.copy())

    def _pick_box_card(self, card_idx: int | None) -> ExecResult:
        """武装箱选卡:点选项入座(选中 take/未选 ret,池守恒)。"""
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        from sr_od.application.currency_war.kernel.cw_state import BenchChar

        frame = self.top_overlay('box')
        if frame is None:
            return ExecResult(applied=False, observed=self.state.copy())
        options = list(frame.payload)
        if not options:
            self.pop_overlay()
            return ExecResult(applied=False, observed=self.state.copy())
        idx = (card_idx if card_idx is not None else 1) - 1
        if not (0 <= idx < len(options)):
            return ExecResult(applied=False, observed=self.state.copy())
        name = options[idx][0]
        self.pop_overlay()
        # 守恒落账:选中 take,未选 ret(选项期不占池)
        for j, (opt_name, _c) in enumerate(options):
            if j == idx:
                self.shop_pool.take(opt_name)
            elif opt_name != name:
                self.shop_pool.ret(opt_name)
        ch = CHARACTERS[name]
        bc = BenchChar(slot=0, char_id=name,
                       faction=(ch.factions or ['散'])[0],
                       position_pref=ch.position_pref())
        placed = self._deal_bench_char(bc)
        if placed is None:
            self.shop_pool.ret(name)
            return ExecResult(applied=False, observed=self.state.copy())
        return ExecResult(applied=True, observed=self.state.copy())

    def _run_deploy_basic(self) -> ExecResult:
        """围栏基干部署(无会话语境面;有会话语境的完整装配在执行缝层)。

        同一纯函数 ``cw_deploy_logic.select_deployments`` 直调(cap 填空/
        成对点火/板空保底/伪槽恒拒主干);单步转移经 :meth:`apply`
        (DeployMove simulate 分支),本方法零直接落位。
        """
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        from sr_od.application.currency_war.kernel import cw_deploy_logic
        from sr_od.application.currency_war.kernel.cw_state import (
            DeployMove,
            iter_occupied_deployed,
        )

        st = self.state
        # 紧缩占用序含物品槽(箱 is_item_slot=True 进装配,kernel 恒拒
        # 语义真实激活;与生产装配单一源同式,cw_op_deploy B1 返工注)
        occ = [b for b in st.bench if b is not None]
        if not occ:
            return ExecResult(applied=False, observed=self.state.copy())
        cap = st.max_units()
        if cap is None:
            return ExecResult(applied=False, observed=self.state.copy())
        dep_occ = list(iter_occupied_deployed(st.deployed))
        dep_fac: dict[str, int] = {}
        for d in dep_occ:
            ch = CHARACTERS.get(d.char_id)
            if ch is not None and ch.factions:
                dep_fac[ch.factions[0]] = dep_fac.get(ch.factions[0], 0) + 1
        up_idx, _held = cw_deploy_logic.select_deployments(
            occ,
            deployed_cids={d.char_id for d in dep_occ if d.char_id},
            deployed_fac=dep_fac,
            board=dict(st.board or {}),
            cap=cap,
        )
        n_up = 0
        for i in up_idx:
            if i >= len(occ):
                continue
            bc = occ[i]
            if bc is None or bc.is_item_slot:
                continue
            bench_idx = st.bench.index(bc)
            ch = CHARACTERS.get(bc.char_id)
            row = (ch.position_pref() if ch is not None else None) \
                or bc.position_pref or 'back'
            res = self.apply(DeployMove(bench_idx=bench_idx, to_row=row,
                                        faction=bc.faction or '?'))
            if res.applied:
                n_up += 1
        return ExecResult(applied=n_up > 0, verification={'up': n_up},
                          observed=self.state.copy())

    def _wear_equips(self, action: Any) -> ExecResult:
        """装备穿戴(分配计划单一源 = kernel ``equip_allocation``)。

        occupied 容量扣减输入 = 真值已穿列表;穿戴 = 分配序列逐件落
        ``BenchChar.equips`` + 库存出账(state.equips)。计划空 = applied
        False(无件可穿/无位可穿,live 空批出口同向)。
        """
        from sr_od.application.currency_war.kernel.cw_comps import (
            EQUIP_CAPACITY,
            equip_allocation,
        )
        from sr_od.application.currency_war.kernel.cw_state import (
            iter_occupied_deployed,
        )

        if not self.state.equips:
            return ExecResult(applied=False, observed=self.state.copy())
        dep_occ = list(iter_occupied_deployed(self.state.deployed))
        if not dep_occ:
            return ExecResult(applied=False, observed=self.state.copy())
        occupied = {
            ((d.position_pref or ''), d.slot): list(d.equips or [])
            for d in dep_occ}
        plan = equip_allocation(None, dep_occ, list(self.state.equips),
                                occupied=occupied)
        if not plan:
            return ExecResult(applied=False, observed=self.state.copy())
        worn = 0
        for char_name, equip_name in plan:
            if equip_name not in self.state.equips:
                continue
            for d in dep_occ:
                if (d.char_id == char_name
                        and len(d.equips or []) < EQUIP_CAPACITY):
                    d.equips = list(d.equips or []) + [equip_name]
                    self.state.equips.remove(equip_name)
                    worn += 1
                    break
        return ExecResult(applied=worn > 0, verification={'worn': worn},
                          observed=self.state.copy())

    # ---- 观察留痕(契约二则:读屏次数语义保留)----

    def record_observation(self, method: str, arg: str | None) -> None:
        """记录一次观察调用并推进逻辑时钟(端口假实现统一经此留痕)。"""
        self.clock += 1
        self.observation_log.append(ObservationRecord(
            seq=len(self.observation_log) + 1, method=method, arg=arg,
            clock=self.clock))

    # ---- 浮层栈 ----

    def push_overlay(self, kind: str, payload: list[Any]) -> None:
        """压栈一个待处理浮层(状态机按日程推进压栈,方案 §2.2)。"""
        self.overlay_stack.append(OverlayFrame(kind=kind,
                                               payload=list(payload)))

    def pop_overlay(self) -> OverlayFrame | None:
        """弹栈顶浮层(被测 op 消费后调用);空栈返回 None。"""
        return self.overlay_stack.pop() if self.overlay_stack else None

    def top_overlay(self, kind: str | None = None) -> OverlayFrame | None:
        """栈顶匹配浮层(``kind`` None = 不筛);无匹配返回 None。"""
        for frame in reversed(self.overlay_stack):
            if kind is None or frame.kind == kind:
                return frame
        return None

    # ---- 动作转移(唯一入口)----

    def apply(self, action: Action) -> ExecResult:
        """动作转移唯一入口(方案 §2.2「转移规则唯一入口 apply」)。

        动作语义 = ``cw_state.simulate`` 单一源直调(经模块属性访问,
        测试可 spy 断言接线);规则外效应(牌池 take/ret、刷新重抽)只在
        **applied** 时一次落定。判定语义(落地审 B1/B2 修后口径,出处 =
        cw_state v2 动作契约「拒绝记录进账本」冻结 invariant +
        ``_log_action`` 条目形 ``{'action','result',...}``):

        - **规则性拒绝**(SellBench/SellDeployed expect 守卫、DeployMove
          重名、SwapDeploy、CompTransaction 整体拒):simulate 返回
          「原状态 + rejected 日志条目」——状态整体不等**不能**当
          applied;判据 = 本次调用的日志增量含 ``result=='rejected'``
          (对全部 simulate 分支统一成立)。拒绝时不落任何规则外效应
          (不 ret/不 take/不重抽),账本条目照常入档(可见性 invariant)。
        - **no-op 路径**(空槽卖出/lv10 升级/满栏非合成拒买):无日志、
          状态原样副本 → 状态不等为 False → applied=False。
        - **合成买入**(满栏 merge-buy,ADR-0453):simulate 按 k 张下架 +
          k×cost 扣金;牌池 take 次数 = 店内下架数(普通买 1/合成买 k)。
        """
        self.clock += 1
        before = self.state
        log_base = len(before.action_log)
        after = cw_state.simulate(before, action)
        rejected = any(e.get('result') == 'rejected'
                       for e in after.action_log[log_base:])
        applied = (not rejected) and after != before
        # 拒绝条目也入档(账本可见性 invariant;拒绝态其余字段与原态零差)
        self.state = after
        if not applied:
            return ExecResult(applied=False, observed=after.copy())
        income: int | None = None
        verification: dict = {}
        if isinstance(action, cw_state.BuyCard):
            # 牌池规则外效应:下架几张取走几张(真机制;普通买 1、
            # 合成买 k——k 由 simulate 的下架数承载,不二算 merge_buy_k)
            taken = len(before.shop) - len(after.shop)
            for _ in range(max(1, taken)):
                self.shop_pool.take(action.card.name)
            verification['shop_slot'] = action.card.x
        elif isinstance(action, (cw_state.SellBench, cw_state.SellDeployed)):
            # 卖出回执:income = 金变化量(执行点真值,免复算 sell_refund
            # 链——金变化就是回金的落地面);卖出的副本回池(真机制),
            # 非牌池角色名(如开拓者)不回池
            income = after.gold - before.gold
            _sold = self._sold_char(before, action)
            if _sold is not None and _sold.char_id in self.shop_pool.copies:
                self.shop_pool.ret(_sold.char_id)
        elif isinstance(action, cw_state.RefreshShop):
            # 刷新重抽 = 假游戏规则层(simulate 只扣金不模拟牌);
            # probs 非空 = 轮岗翻倍后的概率表(ADR-0286,GameState 概率条
            # 真值同构),None = 基线 REFRESH_PROB
            self.state.shop = self.shop_pool.draw_shop(
                self.state.level, probs=self.state.refresh_probs)
            verification['dealt'] = len(self.state.shop)
        # DeployMove/SwapDeploy/CompTransaction/LevelUp:转移语义全部在
        # simulate 内,无规则外效应(装备发放归批 1 规则模块)
        return ExecResult(applied=True, income=income,
                          verification=verification,
                          observed=self.state.copy())

    @staticmethod
    def _sold_char(before: GameState,
                   action: Action) -> cw_state.BenchChar | None:
        """卖出动作的目标角色(投影前快照取,供回池;取不到返回 None)。"""
        if isinstance(action, cw_state.SellBench):
            if 0 <= action.bench_idx < len(before.bench):
                return before.bench[action.bench_idx]
            return None
        if isinstance(action, cw_state.SellDeployed):
            if 0 <= action.deployed_idx < len(before.deployed):
                return before.deployed[action.deployed_idx]
        return None

    # ---- 战斗结算(coarse 主路径 + Δ池直调)----

    def settle_battle(self, node: str | None = None) -> BattleSettlement:
        """节点战斗结算(方案 §2.2 战斗结算行;F7 主从口径:coarse 主路径)。

        - battle/encounter/boss → ``sample_battle_delta``(coarse 查表
          主路径,engine_p1.py:2022-2029 现行口径随迁);
        - reward/supply → Δ池直接采样(``live_delta_for``,桶键 =
          ``_deployable_depth`` 单一源);池缺回退 ``node_delta`` 单一源;
        - 采样键单一源直调(``_settle_rung``/``_deployable_depth``,
          cw_battle_calib;同 engine_p1 先例)。

        结算把 hpΔ 落到 ``state.hp``(下钳 0 = 死亡态;上界钳
        HP_UPPER_BOUND = ADR-0287,engine_p1:2112 同式——批 0 申报的
        「上界钳制缺位」批 1 补全)。战斗类节点随结算迁移连胜/败轮状态
        (:func:`rules.settle_streak`,engine_p1 :2117-2130 带符号口径)。
        """
        self.clock += 1
        _node = node or self.state.node_type or 'battle'
        st = self.state
        if _node in ('battle', 'encounter', 'boss'):
            delta = sample_battle_delta(
                _node, _settle_rung(st), st.hp if st.hp is not None else 0,
                self._rng_battle,
                difficulty=st.enemy_difficulty, plane=st.plane)
        elif _node in ('reward', 'supply'):
            _ld = live_delta_for(_node, _deployable_depth(st),
                                 self._rng_battle,
                                 pool_map=self._delta_pool_map,
                                 plane=st.plane)
            # 池缺 → node_delta 回退(reward/supply 桶缺回退 = 恒 +2 档,
            # EARLY_WIN_DELTA,单一源在 node_delta 内)
            delta = _ld if _ld is not None else node_delta(
                _node, st.round_num, st.round_num, self._rng_battle,
                plane=st.plane)
        else:
            delta = node_delta(_node, st.round_num, st.round_num,
                               self._rng_battle, plane=st.plane)
        hp_after = max(0, min(HP_UPPER_BOUND,
                              (st.hp if st.hp is not None else 0) + delta))
        st.hp = hp_after
        # 连胜/败轮状态迁移(奖励/补给不动 streak;败态跨奖励轮保留——
        # engine_p1 :2125-2130 注记口径,_prev_node 每节点更新)
        st.streak, self._prev_combat_lost = rules.settle_streak(
            st, delta, _node)
        self._prev_node = _node
        return BattleSettlement(node=_node, delta=delta, hp_after=hp_after)

    # ---- 回合域规则(批 1;方案 §2.2 收入/商店身份行)----

    def apply_income(self) -> dict[str, int]:
        """每备战期收入入账(规则 = :func:`rules.income_for_round`,单一
        源分解;金一次落定,分解 dict 返还调用方留证/对拍用)。

        调用时机 = 备战期开始、商店访问前(游戏语义:收入在备战期入账,
        开店决策消费的是含收入金)。rng 消费归发放股(事件金抖动)。
        """
        self.clock += 1
        inc = rules.income_for_round(self.state, self._rng_grant,
                                     self._prev_node, self._prev_combat_lost)
        self.state.gold += sum(inc.values())
        return inc

    def open_shop(self) -> None:
        """开店:画面身份切「备战-开商店」并按当前等级发牌一帧店。

        牌面真值 = ``_Pool.draw_shop`` 单一源(概率表经 ``refresh_probs``
        条——骨架未建模轮岗翻倍时恒 None = 基线概率,与批 0 口径一致);
        调用时机 = harness 编排备战访问前(环境对「开店动作」的承接,
        真环境的开店点击在假环境由本规则表达)。
        """
        self.clock += 1
        self.phase = PHASE_PREP_SHOP_OPEN
        self.state.shop = list(self.shop_pool.draw_shop(
            self.state.level, probs=self.state.refresh_probs))

    def close_shop(self) -> None:
        """收店:画面身份回「备战」(CloseShop 终结动作的环境承接)。

        生产链 = run_buy_waves 对 CloseShop 环侧截停(决策后不执行)→
        编排壳 close_shop 点击收起——假环境由本规则表达收起结果;
        牌面保留(下次 open_shop 重发,与真机「重开重发」同形)。
        """
        self.clock += 1
        self.phase = PHASE_PREP

    # ---- 日程推进(骨架最小实现)----

    def advance_node(self) -> str:
        """推进到下一节点(方案 §2.2 节点日程/位面推进行的骨架面)。

        最小实现:节点位前移 → 轮次/节点类型随日程 → 画面身份切备战。
        战斗等待/结算画面的编排细节归批 1,位面过渡后的 P2 进场继承归
        批 3(现只表态:日程耗尽 → 画面身份切位面过渡,节点位不回绕)。
        """
        self.clock += 1
        self._node_idx += 1
        if self._node_idx >= len(self.node_sequence):
            self.phase = PHASE_PLANE_TRANSITION
            return self.phase
        self.state.round_num = self._node_idx + 1
        self.state.node_type = self.node_sequence[self._node_idx]
        self.phase = PHASE_PREP
        return self.phase

    # ---- 环境指纹(重放三元之「环境指纹」)----

    def env_fingerprint(self) -> dict[str, str | int]:
        """环境指纹 = 规则层版本 + Δ池指纹(方案 §2.2 确定性行:同 seed +
        同环境指纹 → 逐位可复现;跨版本对照禁裸串比)。"""
        return {'env_version': FAKE_GAME_ENV_VERSION,
                'delta_pool': self.delta_pool_fingerprint}
