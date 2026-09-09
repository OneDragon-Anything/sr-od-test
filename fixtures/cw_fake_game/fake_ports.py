"""假游戏的两端口实现(T-120 批 0 骨架 + 批 1 重观察/账本位补全)。

``FakeCwObserver``/``FakeActionSink`` 结构化满足
``sr_od.application.currency_war.cw_game_ports`` 的两个 Protocol
(conform 锁 = test_cw_game_ports.py,含批 1 落地审 L4 修后的签名级
断言)。真值来源 = ``FakeMatch`` 状态机直出;本文件零识别逻辑、零平行
真值——观察即状态快照,动作即状态转移。

**批 1 补全面**(落地审 L3/登记项的承接):

- 观察源 heavy 字段从状态机填充(bench_chars/deployed_chars/
  free_bench_slots/deploy_vacancy/front_occupied/back_occupied)——
  批 1 备战入口观察改道(cw_screen_prep._observe 端口分支)与对账段
  直接消费这些字段,批 0 的三槽填充不再够用;
- 执行器「账本位随动」(方案 §2.4「规则外效应(池 ret/take、账本位)
  一次落定」的执行器半边):``execute_action`` 消费宿主语境 env
  (ShopExecEnv),按 live 动作 op execute 的同一账户增量落 ledger 计数、
  tracked 账(kernel ``mutate_bench_deployed`` 单一源)与卖出登记
  (``register_round_sold`` 单一源)——假环境跳过的是点击/等待/OCR,
  不是记账语义;计数语义与 live op 的逐项对照在方法注内申报。
"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from fixtures.cw_fake_game.fake_match import PHASE_PREP_SHOP_OPEN, FakeMatch
from sr_od.application.currency_war.cw_game_ports import (
    ExecResult,
    ObservationBundle,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PrepObservation,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    Action,
    GameState,
    ShopCard,
)

if TYPE_CHECKING:
    from sr_od.context.sr_context import SrContext


class FakeCwObserver:
    """观察源端口假实现:状态机真值直出(方案 §2.3 表「假游戏实现」列)。

    每次调用经 ``FakeMatch.record_observation`` 留痕——读屏次数语义保留
    (方案 §2.3 契约二则:注入换掉的是读图,不是观察这个语义事件)。
    """

    def __init__(self, match: FakeMatch) -> None:
        self._match: FakeMatch = match

    def screen_identity(self, ctx: SrContext) -> str:
        """画面档名 = 状态机 ``phase`` 直出(方案 §2.3 表)。"""
        self._match.record_observation('screen_identity', None)
        return self._match.phase

    def observe_prep(self, ctx: SrContext, phase: str) -> ObservationBundle:
        """入口观察:状态真值快照直填(方案 §2.3 表「保真位恒真」)。

        heavy 字段(落地审 L3 承接)全部由状态机真值推导:bench/deployed
        占用身份、空席数、部署空位、前后排占用物理槽位——坐标/视觉域
        字段(spheres/boxes/tomes/overlay 检测)结构性为零(无读图),
        是「识别缺陷面结构性为零」申报(方案 §4-6)的一部分,消费方按
        空值分流(备战环 overlay 防线在假环境天然不触发)。
        """
        self._match.record_observation('observe_prep', phase)
        st = self._snapshot_state()
        # 契约一则:保真位恒真 = 「完美观测」环境参数(方案 §2.3;
        # sim-wiring 三节「完美观测=终态」既有豁免口径),判读按方案
        # §4-6 申报「执行/识别缺陷面结构性为零」,识别质量归实机遥测
        st.hp_readable = True
        st.hp_trusted = True
        st.gold_readable = True
        st.board_readable = True
        st.level_readable = True
        # 部署上限真值规则:cap = level(ADR-0281 布局裁定;宝钻叠加项
        # 归装备域,批 1 假环境无装备 overlay → 恒基础式)
        st.deploy_cap = st.level
        # 槽号保真(落地审 L-3):真值 bench 槽位表自带物理槽号(1 基),
        # 按位次重排会压实带洞布局的物理槽——批 2 拖拽目标/落位审计按
        # 物理槽消费,须与 tracked 重播(同文件)「物理槽位 1 基」同契
        bench_occ = [replace(b) for b in st.bench if b is not None]
        dep_occ = [replace(d) for d in st.deployed if d is not None]
        # prep 编排域真值字段(批 2;球/箱 = 状态机事实直出,坐标域 =
        # 结构位假环境不消费点击,占位坐标确定性生成):
        # spheres = read_reward_spheres [(color, Point, r)] 对位;
        # boxes = read_supply_boxes [(slot, Point)] 对位(箱占席由 bench
        # 的 is_item_slot 件承载,此处只供观察面);tomes 恒空(典籍 =
        # P2 投资策略发放域,批 2 不建模,申报面见 FakeMatch.apply_prep)。
        from one_dragon.base.geometry.point import Point

        spheres = [(color, Point(300 + 60 * i, 990), r)
                   for i, (color, r) in enumerate(self._match.spheres)]
        boxes = [(slot, Point(563, 911)) for slot in self._match.boxes]
        prep = PrepObservation(
            state=st,
            # state_gold_trusted 语义 = heavy 时 shop 开(PrepObservation
            # 字段注);假环境 gold 恒真读
            state_gold_trusted=True,
            bench_chars=bench_occ,
            deployed_chars=dep_occ,
            # 空席 = 9 − 占用(占用含箱:箱 = bench 上 is_item_slot 件,
            # bench_occ 计数天然覆盖——free_bench_slots 词表注同式)
            free_bench_slots=max(0, BENCH_CAPACITY - len(bench_occ)),
            deploy_vacancy=max(0, (st.deploy_cap or st.level) - len(dep_occ)),
            front_occupied={d.slot for d in dep_occ
                            if getattr(d, 'row', '') == 'front'},
            back_occupied={d.slot for d in dep_occ
                           if getattr(d, 'row', '') == 'back'},
            shop_open=(self._match.phase == PHASE_PREP_SHOP_OPEN),
            spheres=spheres,
            boxes=boxes,
        )
        return ObservationBundle(state=st, prep=prep)

    def observe_shop_cards(self, ctx: SrContext) -> list[ShopCard]:
        """店面卡牌 = 状态机 shop 槽直出(快照拷贝,断对象别名)。"""
        self._match.record_observation('observe_shop_cards', None)
        return [replace(c) for c in self._match.state.shop]

    def overlay_options(self, ctx: SrContext, kind: str) -> list[Any]:
        """浮层选项 = 栈顶匹配浮层载荷直出(空栈/无匹配 = 空,非 None——
        「无浮层」与「浮层无选项」在假环境同义,消费方按空列表分流)。"""
        self._match.record_observation('overlay_options', kind)
        frame = self._match.top_overlay(kind)
        return list(frame.payload) if frame is not None else []

    def evidence_snapshot(self, tag: str) -> dict[str, Any]:
        """留证面载荷(方案 §2.3 契约三则「留证面改形」;duck-typed 能力,
        协议不辖)。决策帧留证在假环境 = 观察内容快照:画面身份 + 对局
        真值摘要 + 观察留痕尾(消费端按 kind=observation_evidence 分型)。"""
        m = self._match
        return {'phase': m.phase,
                'gold': m.state.gold, 'hp': m.state.hp,
                'level': m.state.level, 'plane': m.state.plane,
                'round_num': m.state.round_num,
                'shop': [c.name for c in m.state.shop],
                'observation_log_tail': [
                    {'method': e.method, 'arg': e.arg, 'clock': e.clock}
                    for e in m.observation_log[-8:]]}

    def _snapshot_state(self) -> GameState:
        """状态快照:deepcopy 断别名(ADR-0465 §9 快照拷贝语义同源)——
        观察帧改动不得污染状态机真值(观察是快照,动作才转移)。"""
        return self._match.state.copy()


class FakeActionSink:
    """执行器端口假实现:动作落假游戏状态机(方案 §2.4)。

    转移委托 ``FakeMatch.apply``;applied 时按宿主语境 env 落「账本位
    随动」(见类 docstring 与 :meth:`_land_ledger`)。本类零执行逻辑、
    零点击——执行失败面结构性为零(方案 §2.4 边界申报)。
    """

    def __init__(self, match: FakeMatch) -> None:
        self._match: FakeMatch = match

    def execute_action(self, ctx: SrContext, action: Action,
                       env: Any | None = None) -> ExecResult:
        """执行动作 = 状态机转移 + 账本位随动(env 在场时)。"""
        # 刷新有效性对拍的「刷前牌名集」:转移前取(与 live RefreshShopOp
        # 「点击前现读」同语义位,来源换状态机真值)
        pre_shop_names = [c.name for c in self._match.state.shop if c.name]
        # 卖出登记名源(批 2 裂口③收敛):转移**前**状态机真值——期望帧
        # (env.state)与真值陈旧错位时,登记名仍随真值(批 1 取期望帧
        # 槽位,陈旧可漂;修法 = 来源换真值,语义位不变)
        pre_truth = self._match.state.copy()
        res = self._match.apply(action)
        if res.applied and env is not None:
            self._land_ledger(env, action, res, pre_shop_names, pre_truth)
        return res

    def _land_ledger(self, env: Any, action: Action, res: ExecResult,
                     pre_shop_names: list[str],
                     pre_truth: GameState | None = None) -> None:
        """账本位随动(方案 §2.4;与 live 动作 op execute 的账户增量
        逐项对照——对照锚 = cw_shop_action_ops 各 op 类的 execute,行号
        为 2026-09-08 时点):计数单一源 = 同一 ShopVisitLedger 槽位。

        **tracked 账随动 = 游戏规则真值重播**(自 ExecResult.observed
        整表重播,非逐动作 mutate 增量复刻):方案 §2.4 双账检测力②
        「tracked 账在假环境 = 游戏规则真值」。历史注:满栏 k-merge 买入
        语境下 live mutate 曾与 simulate 的 §2.5 多买分支不同构(丢件
        漏记),真值重播当年顺带归零该类分叉;T-182 修复批已让 live
        mutate 与 simulate 同分支单一源(带 shop 视图),真值重播保留
        = 更强语义(不只同构,还覆盖 mutate 未建模的面,如店侧 k 张
        下架),非历史包袱。

        - BuyCard(对照 BuyCardOp.execute):total_buy/spend_executed/
          bought_names/merge 满栏补差/BuyPurchase(count=merge_buy_k
          单一源现算)+ tracked 真值重播;
        - SellBench(对照 SellBenchOp.execute):register_round_sold/
          total_sell/buy_has_sell/total_sell_income(income = 执行点
          真值 ExecResult.income,较 live 的 action.income 期望值更真
          ——方案 §2.4 income 字段语义)+ tracked 真值重播;
        - LevelUp(对照 LevelUpOp.execute):total_level/spend_executed;
          血购执行回执(record_hp_pay_event)不落——HP 支付是 live
          机械事实,假环境不建模(simulate LevelUp 分支同不扣 HP),
          申报为环境边界非遗漏;
        - RefreshShop(对照 RefreshShopOp.execute):refresh_attempted/
          spend(fee)/total_refresh/did_refresh/refresh_board_changed
          (refresh_effective 单一源对拍)+ 刷后 shop_snapshots 行
          (金 = 状态机真值,较 live 的期望值列更真)。
        """
        from sr_od.application.currency_war.kernel.cw_exec_state import (
            exec_state_of,
        )
        from sr_od.application.currency_war.kernel.cw_round_ledger import (
            register_round_sold,
        )
        from sr_od.application.currency_war.kernel.cw_state import (
            BENCH_CAPACITY,
            BuyCard,
            LevelUp,
            RefreshShop,
            SellBench,
            bench_occupied,
            merge_buy_k,
            pad_bench,
            pad_deployed,
        )
        ledger = env.ledger
        session = env.match.session
        state = env.state
        # tracked 账真值重播(整表替换;pad 单一源归一形状——compact 态
        # 先重播再 pad,槽位语义 = 物理槽位 1 基,与 live tracking 同契)
        _exec = exec_state_of(session)
        _obs = res.observed
        _exec.tracked_bench_chars[:] = [
            replace(b) if b is not None else None
            for b in (_obs.bench if _obs is not None else [])]
        pad_bench(_exec.tracked_bench_chars)
        _exec.tracked_deployed[:] = [
            replace(d) if d is not None else None
            for d in (_obs.deployed if _obs is not None else [])]
        pad_deployed(_exec.tracked_deployed)
        if isinstance(action, BuyCard):
            ledger.total_buy += 1
            ledger.spend_executed += action.card.cost
            if action.card.name:
                ledger.bought_names.append(action.card.name)
                # 满栏例外张数(与 BuyCardOp.execute 同一单一源现算;
                # 金账补差 (k−1)×单价,张数禁执行侧二算)
                k = 1
                if bench_occupied(state.bench) >= BENCH_CAPACITY:
                    k = max(1, merge_buy_k(
                        action.card.name, action.card.star or 1, state.bench,
                        _exec.tracked_deployed, state.shop))
                    ledger.spend_executed += (action.card.cost or 0) * (k - 1)
                from sr_od.application.currency_war.kernel.cw_prep_expect import (
                    BuyPurchase,
                )
                ledger.buy_purchases.append(BuyPurchase(
                    name=action.card.name, star=action.card.star,
                    count=k, unit_cost=action.card.cost or 0,
                    crop=None))   # 像素裁证 = 读图域,假环境结构性为零
            else:
                ledger.buy_unidentified = True
        elif isinstance(action, SellBench):
            # 登记名源 = 转移前真值(pre_truth;批 2 裂口③收敛——期望帧
            # 陈旧时不再漂);pre_truth 缺席(旧调用形)回落期望帧槽位
            _truth_slot = (pre_truth.bench[action.bench_idx]
                           if pre_truth is not None
                           and 0 <= action.bench_idx < len(pre_truth.bench)
                           else None)
            _expected = (_truth_slot
                         if _truth_slot is not None
                         else (state.bench[action.bench_idx]
                               if 0 <= action.bench_idx < len(state.bench)
                               else None))
            _expected_name = (_expected.char_id
                              if _expected is not None else None)
            register_round_sold([_expected_name], state, session)
            ledger.total_sell += 1
            ledger.buy_has_sell = True
            ledger.total_sell_income += (res.income if res.income is not None
                                         else (action.income or 0))
        elif isinstance(action, LevelUp):
            ledger.total_level += 1
            ledger.spend_executed += action.cost
        elif isinstance(action, RefreshShop):
            from sr_od.application.currency_war.kernel.cw_state import (
                REFRESH_COST_BASE,
            )
            from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
                refresh_effective,
            )
            from sr_od.application.currency_war.telemetry import recorder
            ledger.refresh_attempted = True
            _fee = state.shop_refresh_cost or REFRESH_COST_BASE
            ledger.spend_executed += _fee
            ledger.total_refresh += 1
            ledger.did_refresh = True
            ledger.refresh_board_changed = refresh_effective(
                pre_shop_names,
                [c.name for c in self._match.state.shop if c.name])
            post_gold = self._match.state.gold
            recorder.record_shop_snapshot(
                'refresh', [replace(c) for c in self._match.state.shop],
                post_gold, self._match.state.plane, self._match.state.round_num)
