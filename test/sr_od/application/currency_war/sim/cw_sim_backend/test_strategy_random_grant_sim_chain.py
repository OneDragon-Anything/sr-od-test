"""sim 随机策略发放腿(远见腿②)与节点改写分支(远见腿③)测试(镜像
src = sim/cw_sim_backend.py 的 ``_fire_strategy_random_grants`` 两调用点 +
``_present_offer_or_node_screen`` 远见改写分支;kernel 登记表/申报行单元
面 = cw_investments/test_strategy_random_grants.py + cw_gain_chain/
test_gain_invest_strategy_yuanjian_decl.py,本文件锁 sim 接入调用与门语义)。

测试面依据 = 迭代设计 designs/T-331-yuanjian.md §4 锁 2/4/5/6 + REVIEW
T331 §4.2-R1 修订(获得链调用后就地判,直发拍即掷)+ §六 ④ 锁面:
- 授予锁(锁 2 正面):远见拾取落地 → active_strategies 含远见 +1 个
  金名(∈ 注册表金池)、excluded_invest 不含 granted 名、难度读数同帧
  = 基线 + granted 金 3(远见自身豁免 0——豁免世界级锁同帧钉死)、
  池分布披露键已登记、申报行恰一行;
- 零再发断言(钉 r1-F1 重入门):远见后继拾取(腿③单卡改写槽)金名
  计数不再增长;
- 零假发断言(钉 r1-F1 假发门):远见呈现未选局落地他卡零发放;
- T-46 直发远见局时序锁(R1 修订核心):直发拍即掷(获得时点语义)
  ——门单挂拾取拍会把腿②迟滞到下一拾取拍;后继调用点的调用零再发;
- 改写锁(锁 4):远见已登记时后继 offer 呈现 opts 长度 1 ∈ 棱彩池、
  刷新零授权(呈现 obs refresh_slots 空)、拾取落地正常入链;
- 联席槽改写锁(锁 5):联席决策 + 远见 → 额外槽单棱彩候选(「投资
  策略节点」词面辖联席槽);
- 冲突优先级锁(锁 6):远见 × 时代族 rewrite_picks 同持且本拍 env 改
  写本应命中 → 单棱彩候选(非三候选)+ 优先级披露键已登记(远见胜短路)。
驱动形态复用声明:引擎驱动助手 import 自同目录 test_p3_win_terminal.py
(已登记先例,禁追加只 import);_pick 直调形态先例 = 同目录
test_strategy_pick_diamond_grant_sim_chain.py;联席环境装配形态 =
test_sim_backend._joint_env_backend 同款。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (
    _drive_step,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_env_param,
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    STRATEGY_GRANT_DECL,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    FORESIGHT_ENV_REWRITE_PRIORITY,
    FORESIGHT_EXEMPTION_READING,
    INVESTMENT_STRATEGIES,
    STRATEGY_RANDOM_GRANT_ASSUMPTION_UNIFORM_V0,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    JOINT_DECISION_EXTRA_SLOT,
    SCREEN_BRIEFING,
    SCREEN_INVEST_STRATEGY,
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

#: 难度基线(RunConfig.enemy_difficulty;各测试同基线)。
_BASE_DIFF = 108


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(前清防他测残留、后清防本测外泄——全局缓冲被
    后续测试整池排水对账,残留行即假红;形态 =
    test_sim_backend._isolate_defect_buffer 同款,该 fixture 住主文件
    本地不可跨文件复用,本文件自带同形)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def _gold_held(b: SimBackend) -> list[str]:
    """现持金品质策略名(注册表现值判定)。"""
    return [n for n in (b.gs.active_strategies.value or [])
            if INVESTMENT_STRATEGIES[n].rarity == '金']


def _backend(seed: int) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;形态先例 =
    test_strategy_pick_diamond_grant_sim_chain._backend)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=_BASE_DIFF))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    return b


def _env_backend(seed: int, env_name: str) -> SimBackend:
    """开局选指定环境的装配后端(调用方负责 uninstall;形态 =
    test_sim_backend._joint_env_backend 同款,test_p3_win_terminal
    synthesized opts 同形)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=_BASE_DIFF,
        env_present=True))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b.gs.write_logic(b.gs.invest_env_opts,
                     ['联席决策', env_name, '轮岗'],
                     produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=1), _SIG)
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    b._maybe_finish_wait()
    return b


def _pick(b: SimBackend, name: str, opts: list[str]) -> None:
    """定向选卡落地(直写 opts 定卡 + 上报 + 声明喂入;形态先例 =
    test_strategy_pick_diamond_grant_sim_chain._pick)。"""
    gs = b.gs
    gs.write_logic(gs.invest_strategy_opts, opts,
                   produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_strategy_param(
        gs, SimpleNamespace(norm_name=name), _SIG, session=SimpleNamespace())
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)


def _drive_to_next_offer(b: SimBackend, *, single_only: bool = False,
                         limit: int = 512) -> None:
    """步进驱动至下一个策略 offer 呈现(固定日程/联席槽/远见改写屏同判
    = SCREEN_INVEST_STRATEGY;单步助手 = test_p3_win_terminal
    ._drive_step import 复用先例)。

    single_only=True:跳过 opts 长度 3 的屏(常规三候选/策略延时 extra
    到点屏——granted 金名可属延时 offer 族〔摸个鱼吧 I delay5 探针实测〕,
    其到点呈现会插在目标改写屏之前,长度 3 自动选掉继续走),命中长度 1
    = 远见改写屏。False = 命中首屏即返回(常规三候选前置构造用)。"""
    for _ in range(limit):
        if b.done:
            raise AssertionError('局已终未达 offer 呈现')
        if b.screen_identity() == SCREEN_INVEST_STRATEGY:
            opts = b.gs.invest_strategy_opts.value or ()
            if not single_only or len(opts) == 1:
                return
        _drive_step(b, b.seed)
    raise AssertionError('驱动步数超限未达 offer 呈现')


def _stub_direct_roll_foresight(monkeypatch: pytest.MonkeyPatch) -> None:
    """桩 T-46 直发分支样本恒返远见(棱彩 ∈ 直发全池——R1 修订的触发
    前提形态):流键 = M23 直发键时样本函数吃标记 rng 返远见,其余流键
    透传真实现;offer 采样桩在排除集上叠加远见(远见唯一入列路径 =
    直发桩,防途中固定日程 offer 掷出远见混淆「直发入列」判据——offer
    excluded 是调用方累计集语义,桩层叠加 = 「远见已出过」模拟)。"""
    import sr_od.application.currency_war.sim.cw_sim_backend as backend_mod
    real_stream = backend_mod.stream_rng
    real_card = backend_mod.sample_strategy_card
    real_offer = backend_mod.sample_strategy_offer

    class _M23Mark:
        """直发流标记(rng 类型判据,randrange 恒 0 不消费)。"""

        def randrange(self, n: int) -> int:
            return 0

    def fake_stream_rng(seed: int, key: str):
        if key.startswith('M23/env-pick/'):
            return _M23Mark()
        return real_stream(seed, key)

    def fake_card(rng, excluded: set[str], forced_quality: str = '') -> str:
        if isinstance(rng, _M23Mark):
            return '远见'
        return real_card(rng, excluded, forced_quality=forced_quality)

    def fake_offer(rng, excluded: set[str], forced_slots: tuple = ()):
        return real_offer(rng, {'远见'} | set(excluded),
                          forced_slots=forced_slots)

    monkeypatch.setattr(backend_mod, 'stream_rng', fake_stream_rng)
    monkeypatch.setattr(backend_mod, 'sample_strategy_card', fake_card)
    monkeypatch.setattr(backend_mod, 'sample_strategy_offer', fake_offer)


# ============================================================ 授予锁(锁 2)

def test_pick_grants_random_gold_strategy(_isolate_defect_buffer) -> None:
    """授予锁主链:远见拾取落地 → 持卡含远见 +1 金名(∈ 金池)、
    excluded_invest 不含 granted 名、难度读数同帧 = 108+3(granted 金
    +3,远见自身豁免 0——若未豁免读数应为 117,豁免世界级锁同帧钉)、
    池分布披露键已登记、申报行恰一行(granted 名非名单卡,二次入链零
    新增)。"""
    rows: list[dict] = []
    set_defect_sink(rows.append)
    b = _backend(71)
    try:
        _drive_to_next_offer(b)   # (1,3) 固定日程 offer
        assert (b.gs.node.value.plane, b.gs.node.value.round_num) == (1, 3)
        assert b.gs.enemy_difficulty.value == _BASE_DIFF, '前置基线已登记'
        _pick(b, '远见', ['远见', '躺平', '淘金客'])
        assert '远见' in (b.gs.active_strategies.value or []), '持卡含远见'
        gold = _gold_held(b)
        assert len(gold) == 1, f'恰 1 个金名入列: {gold}'
        assert gold[0] in INVESTMENT_STRATEGIES, 'granted 名 ∈ 注册表'
        assert gold[0] not in b.excluded_invest, \
            'granted 名不加入排除集(desc 无排除语义)'
        assert int(b.gs.enemy_difficulty.value) == _BASE_DIFF + 3, \
            f'难度同帧 = 基线+granted金3(远见豁免 0): ' \
            f'{b.gs.enemy_difficulty.value!r}'
        assert STRATEGY_RANDOM_GRANT_ASSUMPTION_UNIFORM_V0 \
            in b.disclosures, '池分布披露键已登记'
        assert FORESIGHT_EXEMPTION_READING in b.disclosures, \
            '豁免读法披露键已登记(远见在列即申报)'
        kinds = [r['kind'] for r in rows]
        assert kinds.count(STRATEGY_GRANT_DECL) == 1, kinds
    finally:
        uninstall_backend()


def test_foresight_presented_not_picked_zero_grant(
        _isolate_defect_buffer) -> None:
    """零假发断言(锁 2,钉 r1-F1 假发门):呈现候选含远见但落地选他卡
    → 远见不入列 → 零发放(金名零增长、池披露键未登记、门集不含远见
    ——membership 判定构造性挡住假发)。"""
    rows: list[dict] = []
    set_defect_sink(rows.append)
    b = _backend(73)
    try:
        _drive_to_next_offer(b)
        _pick(b, '躺平', ['远见', '躺平', '淘金客'])
        assert '远见' not in (b.gs.active_strategies.value or []), \
            '呈现未选不入列'
        assert _gold_held(b) == [], '零发放(金名零增长)'
        assert STRATEGY_RANDOM_GRANT_ASSUMPTION_UNIFORM_V0 \
            not in b.disclosures, '零掷骰(无池披露键)'
        assert '远见' not in b._strategy_grant_fired, '门集不含远见'
        kinds = [r['kind'] for r in rows]
        assert kinds.count(STRATEGY_GRANT_DECL) == 0, \
            '远见未获得 → 零申报行'
    finally:
        uninstall_backend()


# ============================================================ 改写锁(锁 4)

def test_foresight_rewrite_single_prism_candidate(
        _isolate_defect_buffer) -> None:
    """改写锁(锁 4)+ 零再发断言:远见拾取后后继固定日程槽 (2,2) 呈现
    opts 长度 1 ∈ 棱彩池、刷新零授权(簿记 False + 呈现 obs refresh_
    slots 空 + 容器零授权)、拾取落地正常入链;落地后金名计数不增长
    (零再发——门集记名构造保证,钉 r1-F1 重入门)。"""
    b = _backend(77)
    try:
        _drive_to_next_offer(b)
        _pick(b, '远见', ['远见', '躺平', '淘金客'])
        gold_before = _gold_held(b)
        assert len(gold_before) == 1, '前置:腿②已掷'
        _drive_to_next_offer(b, single_only=True)   # (2,2) 改写呈现(腿③)
        node = b.gs.node.value
        assert (node.plane, node.round_num) == (2, 2), '后继固定日程槽'
        opts = list(b.gs.invest_strategy_opts.value or [])
        assert len(opts) == 1, f'单候选呈现: {opts}'
        assert INVESTMENT_STRATEGIES[opts[0]].rarity == '棱彩', \
            '候选 ∈ 棱彩池(注册表现值 123 名)'
        assert opts[0] not in ('远见', *(
            b.gs.active_strategies.value or [])), '候选非持卡面(排除集吃掉)'
        assert b._offer_refreshable is False, '授权簿记 False(无法刷新)'
        assert b._offer_forced_slots == (), '槽向量簿记清零(无消费位)'
        assert opts[0] not in (b.gs.strategy_refresh_left.value or {}), \
            '改写候选零授权(容器刷新闸按卡名查,report 合并写语义下旧窗键' \
            '残留为既有行为,新候选名不入键 = 本窗不可刷)'
        obs = b.observe(SCREEN_INVEST_STRATEGY)
        assert [n for n, _x, _y in obs.options] == opts, '呈现 obs 单候选'
        assert obs.refresh_slots == [], '呈现 obs 零刷新槽'
        _pick(b, opts[0], opts)
        assert opts[0] in (b.gs.active_strategies.value or []), \
            '改写槽拾取落地正常入链'
        assert _gold_held(b) == gold_before, \
            '零再发:后继拾取落地金名计数不增长'
    finally:
        uninstall_backend()


# ============================================================ 联席槽锁(锁 5)

def test_foresight_joint_slot_rewrite(_isolate_defect_buffer) -> None:
    """联席槽改写锁(锁 5):联席决策 + 远见同持 → 额外槽 (2,6) 亦单
    棱彩候选(「投资策略节点」词面辖联席槽,offer_slots 唯一入口函数自动覆盖
    零特判)。"""
    b = _env_backend(61, '联席决策')
    try:
        _drive_to_next_offer(b)   # (1,3) 固定日程首槽
        _pick(b, '远见', ['远见', '躺平', '淘金客'])
        # 途经 (2,2) 固定日程改写屏由驱动单步自动落地单候选
        for _ in range(512):
            if b.done:
                raise AssertionError('局已终未达联席额外槽')
            if b.screen_identity() == SCREEN_INVEST_STRATEGY \
                    and b._node_pos() == JOINT_DECISION_EXTRA_SLOT:
                break
            _drive_step(b, b.seed)
        else:
            raise AssertionError('未达联席额外槽 (2,6)')
        opts = list(b.gs.invest_strategy_opts.value or [])
        assert len(opts) == 1, f'联席额外槽单候选: {opts}'
        assert INVESTMENT_STRATEGIES[opts[0]].rarity == '棱彩', \
            '候选 ∈ 棱彩池'
        assert b._offer_refreshable is False, '联席槽本就不可刷(改写同形)'
    finally:
        uninstall_backend()


# ============================================================ 冲突优先级锁(锁 6)

def test_foresight_env_rewrite_priority_wins(_isolate_defect_buffer) -> None:
    """冲突优先级锁(锁 6):远见 × 时代族(彩虹时代 rewrite_picks=
    (1,2,3))同持且本拍 env 改写本应命中(ordinal 2 ∈ rewrite_picks)
    → 单棱彩候选(非 env 改写三候选)+ 优先级披露键已登记(远见胜短路;
    证伪通道 = 实机同持局)。"""
    b = _env_backend(63, '彩虹时代')
    try:
        _drive_to_next_offer(b)   # (1,3):远见未在列,env 改写三候选生效
        assert (b.gs.node.value.plane, b.gs.node.value.round_num) == (1, 3)
        opts0 = list(b.gs.invest_strategy_opts.value or [])
        assert len(opts0) == 3, '前置:env 改写本拍三候选(全棱彩)'
        assert all(INVESTMENT_STRATEGIES[n].rarity == '棱彩'
                   for n in opts0), 'env 改写候选全棱彩(rewrite 前置自证)'
        _pick(b, '远见', ['远见', *opts0[1:]])
        assert '远见' in (b.gs.active_strategies.value or [])
        _drive_to_next_offer(b, single_only=True)   # (2,2):ordinal 2 ∈ rewrite_picks 真冲突
        node = b.gs.node.value
        assert (node.plane, node.round_num) == (2, 2)
        opts = list(b.gs.invest_strategy_opts.value or [])
        assert len(opts) == 1, \
            f'远见胜:单候选(非 env 改写三候选): {opts}'
        assert INVESTMENT_STRATEGIES[opts[0]].rarity == '棱彩'
        assert FORESIGHT_ENV_REWRITE_PRIORITY in b.disclosures, \
            '优先级披露键已登记(真冲突短路)'
    finally:
        uninstall_backend()


# ============================================================ T-46 直发时序锁(R1)

def test_t46_direct_grant_foresight_fires_at_grant_time(
        monkeypatch: pytest.MonkeyPatch,
        _isolate_defect_buffer) -> None:
    """T-46 直发远见局时序锁(R1 修订核心):持策略大师环境走至直发节点
    (extra_strategy_grant_node),直发桩恒发远见(棱彩 ∈ 直发全池)
    → 直发拍即掷(远见入列同拍金名 +1——门单挂拾取拍会把腿②迟滞到
    下一拾取拍,违「获得时点」语义);后继调用点的调用零再发(门集记名)。"""
    _stub_direct_roll_foresight(monkeypatch)
    rows: list[dict] = []
    set_defect_sink(rows.append)
    b = _env_backend(37, '策略大师')
    try:
        prev_gold: set[str] = set()
        held: set[str] = set()
        for _ in range(2048):
            if b.done:
                raise AssertionError('局已终未达直发节点')
            held = set(b.gs.active_strategies.value or [])
            if '远见' in held:
                break
            prev_gold = {n for n in held
                         if INVESTMENT_STRATEGIES[n].rarity == '金'}
            _drive_step(b, b.seed)
        else:
            raise AssertionError('未达直发节点(远见未入列)')
        assert '远见' in held, '直发远见入列(M23 桩)'
        gold_now = {n for n in held
                    if INVESTMENT_STRATEGIES[n].rarity == '金'}
        assert len(gold_now) == len(prev_gold) + 1, \
            f'直发拍即掷(获得时点语义,恰 +1 金名): {prev_gold} → {gold_now}'
        new_gold = gold_now - prev_gold
        granted = next(iter(new_gold))
        assert granted not in b.excluded_invest, \
            'granted 名不加入排除集'
        assert b._strategy_grant_fired == {'远见'}, '门集恰记远见'
        assert STRATEGY_RANDOM_GRANT_ASSUMPTION_UNIFORM_V0 \
            in b.disclosures, '池分布披露键已登记'
        # 后继调用点的调用零再发(任意拾取拍/直发拍的助手调用均被门挡)。
        b._fire_strategy_random_grants(plane=3, r=5)
        assert set(_gold_held(b)) == gold_now, '零再发:金名集合不变'
        # 申报行:直发远见入列一行 + granted 金名非名单零新增 = 恰一行。
        kinds = [r['kind'] for r in rows]
        assert kinds.count(STRATEGY_GRANT_DECL) == 1, kinds
    finally:
        uninstall_backend()
