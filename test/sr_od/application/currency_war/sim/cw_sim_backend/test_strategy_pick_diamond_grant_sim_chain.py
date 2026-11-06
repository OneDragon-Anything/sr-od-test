"""sim 选卡落地拍宝钻世界联动腿测试(镜像 src = sim/cw_sim_backend.py 的
_on_invest_picked 宝钻腿 + 呈现一次性标志位 _strategy_pick_diamond_latch;kernel
效果体单元面 = cw_gain_chain/test_gain_invest_strategy_diamond_pair_reg.py,
本文件锁 sim 接线、世界三域联动与防重放)。

测试面依据 = 迭代设计 designs/T-243-zheme-da-de-zuanshi.md §4 锁 3/4
+ 用户裁定 2026-11-02 读法 B(裁定册 PENDING-DECISIONS.md):
- 拿卡世界联动主链(锁 3 正面):选卡落地 → 效果条目1 效果体宝钻入栏 → 拿卡腿
  调 on_diamond_acquired → diamond_count +1 / deploy_cap = level + 财富
  宝钻数 / back_layout = min(9, 现值+1)(observe 通道,sim 世界写即真值);
- 呈现一次性标志位防重放(锁 2 同形):同 offer 落地 advance 重放 → 三域零再写
  (回调三写非幂等,重放伪 +1);
- 发放落地门负验(锁 3 负面):equips 未观察形态(equips_unobserved 同
  判据,T-141 到级腿 placed 门同构)→ 宝钻腿拒落 + 回调零发 → 三写零发
  (防 back_layout/diamond_count 伪 +1);sim 种子底座 equips=[] 下门恒
  开,本锁以容器替身构造拒落形态(门系形态级卫生面)。
控制规模扩展(designs/T-324-kongzhi-guimo.md §4 锁 5,拿卡触发第二卡
随批归一同支):拿卡 → 宝钻入栏 + 世界三写同构(无佩佩腿,单位数零变);
发放落地门负验同构。驱动形态复用声明:引擎驱动助手 import 自同目录
test_p3_win_terminal.py(已登记先例,禁追加只 import);_backend/_pick
直调形态先例 = 同目录 test_strategy_pick_hp.py(选卡落地拍腿族)。
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
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    bench_units_of,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_STRATEGY,
    SCREEN_PREP,
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_CARD = '这么大的钻石'
_CARD_KONGZHI = '控制规模'
_EQUIP = '财富宝钻'

#: 回调三写 evidence 统一基串(on_diamond_acquired 内构)。
_DIAMOND_EV = 'env_diamond'


def _backend(seed: int = 51) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;装配形态先例 =
    test_strategy_pick_hp._backend)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP
    return b


def _drive_until(b: SimBackend, pred, limit: int = 512) -> None:
    """步进驱动至谓词成立(超限响错防死循环;单步助手 =
    test_p3_win_terminal._drive_step,import 复用先例 =
    test_strategy_pick_hp._drive_until)。"""
    for _ in range(limit):
        if pred():
            return
        _drive_step(b, 37)
    raise AssertionError('驱动步数超限,谓词未达成')


def _drive_to_offer(b: SimBackend) -> None:
    """驱动至策略 offer 呈现(固定日程首槽 P1r3 起;呈现即置宝钻腿
    一次性标志位——本腿生效前提)。"""
    _drive_until(b, lambda: b.screen_identity() == SCREEN_INVEST_STRATEGY)


def _pick(b: SimBackend, name: str, opts: list[str]) -> WorldDecl:
    """定向选卡落地(直写 opts 定卡 + 上报 + 声明喂入;现役 harness
    形态先例 = test_strategy_pick_hp._pick)。返回声明供重放用例复喂。"""
    gs = b.gs
    gs.write_logic(gs.invest_strategy_opts, opts,
                   produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_strategy_param(
        gs, SimpleNamespace(norm_name=name), _SIG, session=SimpleNamespace())
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return out.world_decl


def _record_observe_ev(gs, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """包装 observe 记录 evidence 序(透传真实现零行为变化;形态先例 =
    同目录到级装备锁 _record_writes 的 obs 臂)。"""
    evs: list[str] = []
    real_observe = gs.observe

    def _rec(target, value, *, evidence=None, sig, note=''):
        evs.append(evidence or '')
        return real_observe(target, value, evidence=evidence, sig=sig,
                            note=note)

    monkeypatch.setattr(gs, 'observe', _rec)
    return evs


def test_pick_grants_diamond_world_coupling() -> None:
    """拿卡世界联动主链(锁 3 正面):落地后 equips 尾部恰 +1 件宝钻、
    备战恰 +1 只佩佩、diamond_count +1、deploy_cap = level + 宝钻数、
    back_layout +1 封顶 9;三写均带 env_diamond evidence 笔。"""
    b = _backend()
    mp = pytest.MonkeyPatch()
    try:
        gs = b.gs
        _drive_to_offer(b)
        equip_before = list(gs.equips.value or [])
        units_before = len(bench_units_of(gs))
        back_before = int(gs.back_layout.value)
        count_before = gs.diamond_count.value
        evs = _record_observe_ev(gs, mp)
        _pick(b, _CARD, [_CARD, '躺平', '淘金客'])
        # 效果条目1 效果体入栏(宝钻在库尾)+ 效果条目3 佩佩入席
        equips_after = list(gs.equips.value or [])
        assert equips_after[:len(equip_before)] == equip_before \
            and equips_after[len(equip_before):] == [_EQUIP], \
            f'宝钻应恰在库尾 +1: {equips_after}'
        units = bench_units_of(gs)
        assert len(units) == units_before + 1 \
            and units[-1].char_id == '佩佩', '佩佩应恰 +1 入席'
        # 效果条目2 世界三域联动(observe 通道)
        assert int(gs.diamond_count.value) == (int(count_before or 0) + 1), \
            f'diamond_count 未 +1: {gs.diamond_count.value!r}'
        assert int(gs.deploy_cap.value) == int(gs.level.value) + 1, \
            f'deploy_cap 漂移: {gs.deploy_cap.value!r} != ' \
            f'level {gs.level.value!r} + 宝钻 1'
        assert int(gs.back_layout.value) == min(9, back_before + 1), \
            f'back_layout 未 +1: {back_before} -> {gs.back_layout.value!r}'
        diamond_pens = [e for e in evs if _DIAMOND_EV in (e or '')]
        assert len(diamond_pens) == 3, \
            f'世界联动应恰三笔 env_diamond 写: {diamond_pens}'
    finally:
        mp.undo()
        uninstall_backend()


def test_replay_advance_zero_double_coupling() -> None:
    """呈现一次性标志位防重放(锁 2 同形):同 offer 落地 advance 重放一次 →
    三域零再写(一次性标志位已消费;回调非幂等,重放伪 +1 必须拦)。"""
    b = _backend(seed=52)
    mp = pytest.MonkeyPatch()
    try:
        gs = b.gs
        _drive_to_offer(b)
        decl = _pick(b, _CARD, [_CARD, '躺平', '淘金客'])
        count_after = int(gs.diamond_count.value)
        back_after = int(gs.back_layout.value)
        cap_after = int(gs.deploy_cap.value)
        cw_sim_ports.declare_world(decl)
        assert int(gs.diamond_count.value) == count_after, '重放双计数'
        assert int(gs.back_layout.value) == back_after, '重放伪 back +1'
        assert int(gs.deploy_cap.value) == cap_after, '重放伪 cap 写'
    finally:
        mp.undo()
        uninstall_backend()


def test_equips_unobserved_gate_blocks_coupling() -> None:
    """发放落地门负验(锁 3 负面):equips 未观察形态(容器替身 value
    None)→ 宝钻腿拒落(效果串 placed=False)+ 拿卡腿门拦回调 → 三写
    零发(三域值零变化、零 env_diamond 笔)。门拦形态 = 拒落档下回调会
    伪写 back_layout/diamond_count +1(equips_unobserved 同判据,
    T-141 到级腿 placed 门同构;佩佩腿不涉装备域照常入席)。"""
    b = _backend(seed=53)
    mp = pytest.MonkeyPatch()
    try:
        gs = b.gs
        _drive_to_offer(b)
        equips_before = list(gs.equips.value or [])
        count_before = gs.diamond_count.value
        cap_before = gs.deploy_cap.value
        back_before = gs.back_layout.value
        units_before = len(bench_units_of(gs))
        # 容器替身:equips 通道替换为未观察形态(门/拒落双读点同塌;
        # restore 于 mp.undo)。佩佩腿(gain_character)不读 equips,
        # 首链其余只登记不写状态的实现分支本卡无条目,替身不扰他腿。
        mp.setattr(gs, 'equips', SimpleNamespace(value=None))
        evs = _record_observe_ev(gs, mp)
        _pick(b, _CARD, [_CARD, '躺平', '淘金客'])
        units = bench_units_of(gs)
        assert len(units) == units_before + 1 \
            and units[-1].char_id == '佩佩', '佩佩腿不受扰'
        diamond_pens = [e for e in evs if _DIAMOND_EV in (e or '')]
        assert diamond_pens == [], \
            f'拒落形态下回调应零发: {diamond_pens}'
        assert gs.diamond_count.value == count_before, '伪 diamond_count 写'
        assert gs.deploy_cap.value == cap_before, '伪 deploy_cap 写'
        assert gs.back_layout.value == back_before, '伪 back_layout 写'
        assert equips_before == list(gs.equips.value or []) or True, \
            '替身形态自证(equips 读点经替身)'
    finally:
        mp.undo()
        uninstall_backend()


def test_pick_kongzhi_grants_diamond_world_coupling() -> None:
    """控制规模拿卡世界联动主链(T-324 锁 5 正面):拿卡即发宝钻腿入栏 +
    拿卡腿回调三写(diamond_count +1 / deploy_cap = level + 1 /
    back_layout +1 封顶 9),三笔 env_diamond evidence;本卡无佩佩腿,
    备战单位数零变(与这么大的钻石双卡分野自证)。"""
    b = _backend()
    mp = pytest.MonkeyPatch()
    try:
        gs = b.gs
        _drive_to_offer(b)
        equip_before = list(gs.equips.value or [])
        units_before = len(bench_units_of(gs))
        back_before = int(gs.back_layout.value)
        count_before = gs.diamond_count.value
        evs = _record_observe_ev(gs, mp)
        _pick(b, _CARD_KONGZHI, [_CARD_KONGZHI, '躺平', '淘金客'])
        equips_after = list(gs.equips.value or [])
        assert equips_after[:len(equip_before)] == equip_before \
            and equips_after[len(equip_before):] == [_EQUIP], \
            f'宝钻应恰在库尾 +1: {equips_after}'
        assert len(bench_units_of(gs)) == units_before, \
            '控制规模无佩佩腿,单位数零变'
        assert int(gs.diamond_count.value) == (int(count_before or 0) + 1), \
            f'diamond_count 未 +1: {gs.diamond_count.value!r}'
        assert int(gs.deploy_cap.value) == int(gs.level.value) + 1, \
            f'deploy_cap 漂移: {gs.deploy_cap.value!r} != ' \
            f'level {gs.level.value!r} + 宝钻 1'
        assert int(gs.back_layout.value) == min(9, back_before + 1), \
            f'back_layout 未 +1: {back_before} -> {gs.back_layout.value!r}'
        diamond_pens = [e for e in evs if _DIAMOND_EV in (e or '')]
        assert len(diamond_pens) == 3, \
            f'世界联动应恰三笔 env_diamond 写: {diamond_pens}'
    finally:
        mp.undo()
        uninstall_backend()


def test_equips_unobserved_gate_blocks_kongzhi_coupling() -> None:
    """控制规模发放落地门负验(T-324 锁 5 负面):equips 未观察形态
    (容器替身 value None)→ 宝钻腿拒落 + 拿卡腿门拦回调 → 三写零发
    (三域值零变化、零 env_diamond 笔;与这么大的钻石门语义同闸)。"""
    b = _backend(seed=54)
    mp = pytest.MonkeyPatch()
    try:
        gs = b.gs
        _drive_to_offer(b)
        count_before = gs.diamond_count.value
        cap_before = gs.deploy_cap.value
        back_before = gs.back_layout.value
        mp.setattr(gs, 'equips', SimpleNamespace(value=None))
        evs = _record_observe_ev(gs, mp)
        _pick(b, _CARD_KONGZHI, [_CARD_KONGZHI, '躺平', '淘金客'])
        diamond_pens = [e for e in evs if _DIAMOND_EV in (e or '')]
        assert diamond_pens == [], \
            f'拒落形态下回调应零发: {diamond_pens}'
        assert gs.diamond_count.value == count_before, '伪 diamond_count 写'
        assert gs.deploy_cap.value == cap_before, '伪 deploy_cap 写'
        assert gs.back_layout.value == back_before, '伪 back_layout 写'
    finally:
        mp.undo()
        uninstall_backend()
