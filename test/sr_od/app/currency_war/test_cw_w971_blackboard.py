"""W971 §2 黑板模式 + ADR-0583 策略契约形状锁。

覆盖:
- 黑板决策接口(备战 prep_obs_frame / 商店 shop_state_frame)冒烟与
  缺帧契约(decide_prep 兼容 shim、decide_prep_action 薄委托已随
  ADR-0517/ADR-0583 退役,对拍锁随删);
- ADR-0583 契约形状(L6):CwStrategy abstract 面全集 = 冷建 1 + 分画面
  决策入口 11(抽象 12)+ 非 abstract 工厂 create_state;update_target/
  生命周期钩子/decide_prep_action/decide_shop_screen 出契约面的墓碑;
  v3_intention_key 与帧类槽的写点空间守卫;
- 方向节拍内化(L1/L2/L3/L7):full 帧键守卫贵段每 game-round 恰一次;
  view 帧(破墙/finalize 买后暂存)只刷派生视图、驱动延迟到下一 full 帧;
  商店 visit 首段 full/续段 none;驱动输入 hp 同门(gated)。
全部离线纯逻辑,零 IO。
"""
from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    CloseShop,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CwStrategy,
)
from sr_od.application.currency_war.strategies.mandate_v1_strategy import (
    MandateV1Live,
)

# ADR-0517 迁移批:旧死码核具现(_decide_prep_action_impl 桥)退役,
# 直用活策略核(下述测试全部消费 live 接口)。
_FlowStrategy = MandateV1Live
def _make_state() -> GameState:
    """探针态:中局常态(金足/店有目标件/bench 有件)——决策必有产出。"""
    s = GameState()
    s.plane, s.round_num, s.level, s.gold, s.hp = 1, 5, 5, 60, 80
    s.board = {'仙舟': 2, '持续伤害': 1}
    s.deployed = [BenchChar(slot=0, char_id='藿藿', faction='仙舟'),
                  BenchChar(slot=1, char_id='爻光', faction='仙舟')]
    s.bench = [BenchChar(slot=0, char_id='丹恒·饮月', faction='仙舟'),
               BenchChar(slot=1, char_id='青雀', faction='仙舟'),
               None, None, None, None, None, None, None]   # ADR-0316 pad
    s.shop = [ShopCard(x=1, faction='仙舟', name='丹恒·饮月', cost=2),
              ShopCard(x=2, faction='护盾', name='三月七', cost=1)]
    return s


def _fresh(strategy) -> SimpleNamespace:
    """同源 session(create_session 唯一冷建口,ADR-0583;两臂输入完全一致的对拍前提)。"""
    return strategy.create_session(None)


def _norm_seq(actions: list) -> list[tuple[str, dict]]:
    """动作序列归一化:类型名(LevelUpShop≡LevelUp)+ 字段 dict(对拍口径)。"""
    out = []
    for a in actions:
        name = type(a).__name__
        if name == 'LevelUpShop':
            name = 'LevelUp'
        out.append((name, dict(dataclasses.asdict(a))))
    return out


# ===== 商店屏:新旧入口决策对拍 =====


def test_shop_screen_probe_smoke() -> None:
    """商店屏唯一入口冒烟(退役批:decide_prep 兼容 shim 已删,对拍锁随删)。

    探针态(金足/店有目标件)经黑板入口应产出采纳动作;等价性保障改由
    结构承载(单一入口 = decide_shop_screen,无第二实现可漂移)。
    """
    strat = _FlowStrategy()
    state = _make_state()
    sess = _fresh(strat)
    sess.shop_state_frame = state
    acts = strat.decide_shop_screen(sess, None)
    assert len(acts) > 0, '探针态(金足/店有目标件)应有采纳动作'

# (test_shop_screen_emits_levelup_shop 已随 v2 _decide_shop_plan 出口映射删除——
#  统一迁移批 ②;mandate 商店线出口形态由 test_cw4_shop_line 锁组辖。)


def test_shop_screen_missing_frame_raises() -> None:
    """黑板契约:观察帧缺失 = 观察层失约 → 抛错,禁静默按空态决策。"""
    strat = _FlowStrategy()
    sess = _fresh(strat)
    assert sess.shop_state_frame is None
    with pytest.raises(ValueError, match='shop_state_frame'):
        strat.decide_shop_screen(sess, None)


# ===== 备战屏:黑板缺帧契约 =====


def test_prep_screen_missing_frame_raises() -> None:
    """黑板契约:prep_obs_frame 缺失 → 抛错(同商店屏)。"""
    strat = _FlowStrategy()
    sess = _fresh(strat)
    with pytest.raises(ValueError, match='prep_obs_frame'):
        strat.decide_prep_screen(sess, None)


# (test_prep_action_delegates_via_frame 已随 ADR-0583 删除:deprecated 薄委托
#  decide_prep_action 出契约面并删实现(P5 挂账兑现,方案 §4-#9),旧入口
#  「写 prep_obs_frame」路径由画面 op 观察段直接承担。)


# ===== match 建立前移(W971 §2.1)=====


def test_establish_new_match_and_idempotent(monkeypatch) -> None:
    """入口建立:新建 → True + 职级拷入;已存在 → False 幂等(保续跑语义)。"""
    from sr_od.application.currency_war.strategies.impl.cw_strategy_manager import (
        establish_new_match,
    )

    ctx = SimpleNamespace(
        cw_match=None,
        currency_war_strategy_plugin_dirs=[],
        cw_selected_difficulty='A5',
    )
    monkeypatch.setattr(
        'sr_od.application.currency_war.strategies.impl.cw_strategy_manager.'
        'StrategyManager.instantiate',
        lambda self, strategy_id: _FlowStrategy())
    assert establish_new_match(ctx, SimpleNamespace(
        strategy_id='mandate_v1', strategy_seed=None)) is True
    assert ctx.cw_match is not None
    assert ctx.cw_match.session.selected_difficulty == 'A5'
    assert establish_new_match(ctx, SimpleNamespace(
        strategy_id='mandate_v1', strategy_seed=None)) is False   # 幂等


def test_absorb_selected_difficulty_only_after_mailbox_retirement() -> None:
    """run loop 入口中转(P3 改写):ctx 信箱退役(01-opening §1)——吸收段
    只剩职级难度;简报三字段唯一写点 = CwScreenBriefing 直写 session,不再经 ctx。"""
    from sr_od.application.currency_war.operations.cw_loop import (
        CwLoop,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )
    rl = CwLoop.__new__(CwLoop)
    rl.ctx = SimpleNamespace(
        cw_briefing_affixes=['酸性浓缩'],
        cw_selected_difficulty='A8',
        cw_enemy_difficulty=55,
        cw_briefing_bosses=['虫王·断壳'],
    )
    sess = StrategySession()
    rl._absorb_selected_difficulty(sess)
    # 只吸收职级难度(3.5.1 接线);简报字段不被吸收(信箱退役口径)
    assert sess.selected_difficulty == 'A8'
    assert rl.ctx.cw_selected_difficulty is None
    assert sess.briefing_affixes == []
    assert sess.enemy_difficulty is None
    assert sess.briefing_bosses == []
    assert rl.ctx.cw_briefing_affixes == ['酸性浓缩']
    assert rl.ctx.cw_briefing_bosses == ['虫王·断壳']


# ===== ADR-0583 契约形状锁(L6)+ 方向节拍内化锁(L1/L2/L3/L7)=====


def _pick_cfg() -> SimpleNamespace:
    """mock CurrencyWarConfig(pick 契约成员 getattr 读)。"""
    return SimpleNamespace(
        faction_priority=['贝洛伯格', '仙舟', '巡海游侠'],
        character_priority=['阿格莱雅'],
        character_build_around=[],
        strategy_id='mandate_v1',
        strategy_seed=None,
    )


def _prep_frame(state: GameState):
    """备战黑板帧(pick 入口只消费 .state 字段;dataclass 保真形态)。"""
    from sr_od.application.currency_war.kernel.cw_prep_actions import (
        PrepObservation,
    )
    obs = PrepObservation()
    obs.state = state
    return obs


def _st(round_num: int = 1, bench=None) -> GameState:
    st = GameState()
    st.plane, st.round_num = 1, round_num
    st.bench = bench if bench is not None else [None] * 9
    return st


class TestContractShapeL6:
    """L6 契约形状锁(出处 = ADR-0583 §2.1/§3.1/§3.4 + 方案 §5.4)。

    锁红时的登记语义:契约面成员增删(abstract 集合变化)、退役符号回流
    (update_target/生命周期钩子族)、方向幂等键或帧代次槽越出白名单空间
    ——每条都有明确的登记动作,非快照陷阱。
    """

    def test_abstract_members_exact_set(self) -> None:
        """abstract 面 = 冷建 1 + 分画面决策入口 11,恰 12 个;create_state
        非 abstract(保留总成员 13);退役成员出契约面(墓碑,否定式 +
        ADR-0583 退役背书)。"""
        expected = {
            'create_session',
            'decide_prep_screen', 'decide_shop_action',
            'decide_invest', 'decide_supply', 'decide_encounter',
            'decide_megastar', 'decide_partner', 'decide_planner',
            'decide_star_tome', 'decide_wish_trial', 'decide_box_card',
        }
        assert set(CwStrategy.__abstractmethods__) == expected
        assert 'create_state' not in CwStrategy.__abstractmethods__
        for retired in ('update_target', 'on_match_start', 'on_round_end',
                        'on_match_end', 'decide_prep_action',
                        'decide_shop_screen'):
            assert not hasattr(CwStrategy, retired), (
                f'{retired} 已随 ADR-0583 出契约面,禁回流 ABC')
        # 驱动器降格落点:decide_shop_screen = flow 层非 abstract 缺省实现
        from sr_od.application.currency_war.strategies.impl.flow import (
            CwFlowStrategy,
        )
        assert callable(CwFlowStrategy.decide_shop_screen)

    def test_intention_key_and_frame_slot_space_guard(self) -> None:
        """方向幂等键与帧代次槽的空间守卫(ADR-0583 §3.1 键归属/§3.4-D6):
        - v3_intention_key 只出现在策略器状态(mandate_state)、kernel 纵深
          防御(cw_intention)与策略器内化刷新(flow)——operations/sim/其余
          kernel 零接触;
        - 帧类槽(prep/shop_frame_class)只出现在载体定义、三个流程观察
          写点文件与策略器读口——strategies/impl 内零 'full'/'view' 字面量
          标注写点(策略器永不宣告帧新鲜度,消费复位 'none' = 读协议半部);
        - update_target/drive_intention 在 operations/+sim/ 全子树零回流
          (墓碑扫描,含注释——历史措辞回流会重新误导实施)。"""
        root = (Path(__file__).resolve().parents[5] / 'src' / 'sr_od'
                / 'application' / 'currency_war')
        assert (root / 'kernel' / 'cw_intention.py').is_file(), '扫描根失准'
        key_allowed = {'strategies\\impl\\mandate_v1\\mandate_state.py',
                       'kernel\\cw_intention.py', 'strategies\\impl\\flow.py'}
        slot_allowed = {'kernel\\cw_strategy_session.py',
                        'operations\\cw_screen\\cw_screen_prep.py',
                        'operations\\cw_op\\cw_op_buy_cards.py',
                        'sim\\engine_p1.py', 'strategies\\impl\\flow.py'}
        offenders: dict[str, str] = {}
        for path in root.rglob('*.py'):
            rel = str(path.relative_to(root))
            text = path.read_text(encoding='utf-8')
            if 'v3_intention_key' in text and rel not in key_allowed:
                offenders[f'key:{rel}'] = 'v3_intention_key'
            if ('prep_frame_class' in text or 'shop_frame_class' in text) \
                    and rel not in slot_allowed:
                offenders[f'slot:{rel}'] = 'frame_class'
            if rel.startswith(('operations\\', 'sim\\')) \
                    and ('update_target' in text or 'drive_intention' in text):
                offenders[f'tombstone:{rel}'] = 'update_target/drive_intention'
        assert not offenders, (
            f'方向键/帧类槽越出白名单空间或退役符号回流: {offenders}')
        # D6 正面断言:策略器实现包内禁 'full'/'view' 标注写点
        impl = root / 'strategies' / 'impl'
        for path in impl.rglob('*.py'):
            for line in path.read_text(encoding='utf-8').splitlines():
                assert not _FRAME_WRITE_PAT.search(line), (
                    f'{path}: 策略器侧帧类标注写点 {line.strip()!r}')


_FRAME_WRITE_PAT = re.compile(
    r"(prep_frame_class|shop_frame_class)\s*=\s*['\"](?:full|view)['\"]")


class TestDirectionRhythmL1L2L3L7:
    """方向节拍内化行为锁(出处 = ADR-0583 §3.2/§3.3 + 方案 §5.4)。

    观测口 = flow.update_intention 计数 spy(贵段唯一入口)+ target_comp
    派生视图(便宜段唯一决策读端);键面/视图源/幂等语义对原 update_target
    逐位同源。
    """

    @pytest.fixture()
    def strat_and_sess(self):
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        s = MandateV1Strategy()
        return s, s.create_session(None)

    def _spy_update_intention(self, monkeypatch) -> list[GameState]:
        import sr_od.application.currency_war.strategies.impl.flow as flow_mod
        seen: list[GameState] = []
        real = flow_mod.update_intention

        def spy(state, ist, session, **kw):
            seen.append(state)
            return real(state, ist, session, **kw)

        monkeypatch.setattr(flow_mod, 'update_intention', spy)
        return seen

    def _write_prep_frame(self, sess, state: GameState, cls: str) -> None:
        sess.prep_obs_frame = _prep_frame(state)
        sess.prep_frame_class = cls

    def test_l1_full_frame_drives_once_per_game_round(
            self, strat_and_sess, monkeypatch) -> None:
        """L1 方向节拍锁:连续 2 个 game-round 的 full 帧 → 状态机恰驱动 2 次
        (miss 分母 = 轮);同轮追加 full 帧 → 不再驱动(键守卫短路),
        便宜段照常执行(pick 契约成员正常返回)。"""
        strat, sess = strat_and_sess
        seen = self._spy_update_intention(monkeypatch)
        self._write_prep_frame(sess, _st(round_num=1), 'full')
        pick = strat.decide_invest(
            'strategy', ['定期福利'], _st(), sess, _pick_cfg())
        assert pick is not None and len(seen) == 1
        # 同轮第二个 full 帧:键同 → 不驱动
        self._write_prep_frame(sess, _st(round_num=1), 'full')
        strat.decide_invest('strategy', ['定期福利'], _st(), sess, _pick_cfg())
        assert len(seen) == 1, '同轮 full 帧不得重复驱动机器(键守卫)'
        # 下一轮 full 帧:键新 → 恰再驱动一次
        self._write_prep_frame(sess, _st(round_num=2), 'full')
        strat.decide_invest('strategy', ['定期福利'], _st(), sess, _pick_cfg())
        assert len(seen) == 2, '每 game-round 恰驱动一次(贵段节拍)'

    def test_l2_view_frame_refreshes_without_drive_pick_window(
            self, strat_and_sess, monkeypatch) -> None:
        """L2 窗口帧锁(finalize 买后暂存 → pick 消费,§3.3-③):view 帧
        只刷派生视图(基底 = 暂存帧 state,与原 :2271 买后重估逐位同源)、
        不驱动机器;驱动延迟到下一 full 帧。差分构造 = p1_early_pair 依赖
        bench(空板 pair 仙舟+持续伤害 vs 希儿在手 pair 仙舟+希儿系)。"""
        strat, sess = strat_and_sess
        seen = self._spy_update_intention(monkeypatch)
        # 轮入口 full 帧(空板 pair)——pick 消费驱动 + 建视图
        self._write_prep_frame(sess, _st(round_num=1), 'full')
        strat.decide_invest('strategy', ['定期福利'], _st(), sess, _pick_cfg())
        from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
            state_of,
        )
        base_name = state_of(sess).target_comp.name
        assert base_name == '过渡配方·仙舟+持续伤害'
        assert len(seen) == 1
        # finalize 买后暂存:state 换成含买后 bench 的 _post,帧类 = view
        post = _st(round_num=1,
                   bench=[None] * 9)
        post.bench[0] = BenchChar(slot=1, char_id='希儿', faction='量子')
        sess.prep_obs_frame = _prep_frame(post)
        sess.prep_frame_class = 'view'
        # pick 窗口消费 view 帧:视图刷新到 _post 基准,机器零驱动
        strat.decide_invest('strategy', ['定期福利'], _st(), sess, _pick_cfg())
        assert len(seen) == 1, 'view 帧不触状态机'
        assert state_of(sess).target_comp.name == '过渡配方·仙舟+希儿系', (
            'pick 决策读到的 target_comp = 暂存 _post 基准(原 :2271 语义)')
        assert sess.prep_frame_class == 'none', '消费即清(读后即复位)'
        # 驱动延迟:下一 full 帧(新轮)才再驱动机器
        self._write_prep_frame(sess, _st(round_num=2), 'full')
        strat.decide_invest('strategy', ['定期福利'], _st(), sess, _pick_cfg())
        assert len(seen) == 2

    def test_l3_shop_first_segment_full_rest_segments_none(
            self, strat_and_sess) -> None:
        """L3 商店段锁(§3.3-②):visit 首段 full 帧刷新(键同只刷视图);
        续段(刷新重观察)none 帧视图保持首段值 = 旧 _target_seeded 语义;
        消费后帧类复位 'none'。"""
        strat, sess = strat_and_sess
        from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
            state_of,
        )
        st1 = _st(round_num=1)
        sess.shop_state_frame = st1
        sess.shop_frame_class = 'full'
        assert isinstance(strat.decide_shop_action(sess, _pick_cfg()),
                          CloseShop)
        first_name = state_of(sess).target_comp.name
        assert first_name == '过渡配方·仙舟+持续伤害'
        assert sess.shop_frame_class == 'none', '消费即清'
        st2 = _st(round_num=1,
                  bench=[None] * 9)
        st2.bench[0] = BenchChar(slot=1, char_id='希儿', faction='量子')
        sess.shop_state_frame = st2
        sess.shop_frame_class = 'none'   # 续段:刷新重观察 = 投影语境
        strat.decide_shop_action(sess, _pick_cfg())
        assert state_of(sess).target_comp.name == first_name, (
            '续段 none 帧不刷新(视图保持首段值,_target_seeded 语义等价)')

    def test_l7_drive_input_hp_is_gated_not_raw(
            self, strat_and_sess, monkeypatch) -> None:
        """L7 驱动输入门锁(出处 = ADR-0583 §5.5-戊 行为收敛申报,r68 同门
        教训):决策入口刷新中 update_intention 的 hp 输入 = gated 后值
        (session.last_hp 链)而非血条现读——钉住方向驱动并入结算新鲜度门
        的新行为,防实施批无意识回退到 pre-gated 输入。"""
        strat, sess = strat_and_sess
        seen = self._spy_update_intention(monkeypatch)
        # 结算真值链:上一结算 hp=50,t=10;备战帧现读 hp=80(OCR 误读形态)
        sess.last_hp = 50
        sess.last_hp_t = 10
        frame_state = _st(round_num=1)
        frame_state.hp = 80
        frame_state.hp_readable = True
        # 生产观察终饰(原 cw_screen_prep :1411 同式调用):gated_hp 覆写
        from sr_od.application.currency_war.strategies.impl.cw_strategy import (
            gated_hp,
        )
        frame_state.hp = gated_hp(frame_state.hp, sess, 11, current_readable=True)
        assert frame_state.hp == 50, 'gap==1 门内:结算真值覆盖现读(门语义前提)'
        self._write_prep_frame(sess, frame_state, 'full')
        strat.decide_invest('strategy', ['定期福利'], frame_state, sess,
                            _pick_cfg())
        assert len(seen) == 1
        assert seen[0].hp == 50, (
            '驱动输入 hp 必须为 gated 后值(结算门),不得回退血条现读 80')
