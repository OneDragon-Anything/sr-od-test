"""sim 策略选卡获得链交换分支轨迹成对测试(镜像 src = sim/cw_sim_backend.py
的 _on_invest_picked 交换分支轨迹成对效果条目 + 三呈现点呈现一次性标志位;按被测方法拆
目录规范落位,先例 = 同目录 test_strategy_pick_hp.py)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§4 锁 5(原稿评审锁(§ 号 = 原稿节序)§五.④ 同面;kernel 侧锁 1-4 落
kernel/cw_gain_chain/ 同批新文件,本文件只锁 sim 侧):
- 固定 seed 局持卡选卡(锁 5):kernel 交换分支写行落状态容器后,落地拍
  hp_trail 恰追加一行且尾值 == gs.hp 现值(写流↔轨迹全序同构);
- 呈现一次性标志位防重放:落地 advance 重放 → 轨迹零再追加(kernel 写行恰一,
  配对必须恰一);
- 等值交换仍配对:交换前 hp 已 == min(gold, SQUAD_HP_CAP) 时写行照落
  (等值写先例 = apply_hp_outcome 胜局支),轨迹仍同拍追加——尾值检测式
  在此形态漏配,呈现一次性标志位 + 判别按「每发恰一写行」计数天然覆盖;
- 未落卡零扰动:opts 含本卡但选另一张 → 交集空 → 零 hp 写行零追加。

复用声明:装配与驱动助手 import 自 sim/test_sim_backend.py 与同目录
test_p3_win_terminal.py / test_strategy_pick_hp.py(先例形态,只 import
复用不改)。
"""
from __future__ import annotations

from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (
    _drive_step,
)
from test.sr_od.application.currency_war.sim.cw_sim_backend.test_strategy_pick_hp import (
    _backend,
    _drive_to_offer,
    _pick,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    SQUAD_HP_CAP,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    uninstall_backend,
)

#: 交换分支双字段写行 evidence 同串(单一源 = cw_gain_chain 交换分支
#: 写点字面;kernel write_logic 不经 sim_evidence 前缀包装)。
_SWAP_EVIDENCE = 'strategy:hp_gold_swap'


def test_swap_pick_writes_and_trail_pairs_exactly_once() -> None:
    """持卡交换真值 + 轨迹成对(锁 5):自然 offer 呈现(三呈现点统一
    置一次性标志位)后定向选不等价交换 → hp == min(gold_old, SQUAD_HP_CAP) ∧
    gold == hp_old(双字段各一条交换写行,evidence 同串)→ hp_trail 恰
    追加一行且尾值 == gs.hp 现值;下一战斗结算笔照常配对不受扰。"""
    b = _backend(seed=48)
    try:
        gs = b.gs
        _drive_to_offer(b)
        hp_before = int(gs.hp.value)
        gold_before = int(gs.gold.value or 0)
        trail_before = list(b.hp_trail)
        assert trail_before and trail_before[-1] == hp_before, \
            f'开局轨迹首段异常: {trail_before} vs {hp_before}'
        _pick(b, '不等价交换',
              ['不等价交换', '躺平', '随便一张未收录卡'])
        assert gs.hp.value == min(gold_before, SQUAD_HP_CAP), \
            f'交换后 hp: {gs.hp.value} (gold_old={gold_before})'
        assert gs.gold.value == hp_before, \
            f'交换后 gold 应 == hp_old: {gs.gold.value}'
        assert gs.hp.evidence == _SWAP_EVIDENCE, \
            f'交换写行 evidence: {gs.hp.evidence}'
        assert list(b.hp_trail) == trail_before + [int(gs.hp.value)], \
            f'轨迹未同步恰追加: {list(b.hp_trail)} vs {trail_before}'
        # 下一战斗结算笔照常落账(写流↔轨迹同构的战斗笔不受扰)。
        for _ in range(512):
            if len(b.hp_trail) > len(trail_before) + 1:
                break
            _drive_step(b, 37)
        else:
            raise AssertionError('驱动步数超限,未见下一战斗结算笔')
        assert b.hp_trail[-1] == int(gs.hp.value), \
            f'战斗笔轨迹不同步: {b.hp_trail[-1]} vs {gs.hp.value}'
    finally:
        uninstall_backend()


def test_swap_replay_advance_zero_double_append() -> None:
    """呈现一次性标志位防重放:同 offer 落地 advance 重放一次 → kernel 写行不再
    产生(上报不在重放路径)、轨迹零再追加(一次性标志位已消费;重放多配一行即
    破写流↔轨迹全序同构)。"""
    b = _backend(seed=49)
    try:
        gs = b.gs
        _drive_to_offer(b)
        trail0 = len(b.hp_trail)
        decl = _pick(b, '不等价交换',
                     ['不等价交换', '躺平', '随便一张未收录卡'])
        assert len(b.hp_trail) == trail0 + 1, '前置:落地应恰配对一行'
        cw_sim_ports.declare_world(decl)
        assert gs.hp.evidence == _SWAP_EVIDENCE, '重放不应换 evidence'
        assert len(b.hp_trail) == trail0 + 1, \
            f'重放轨迹追加: {list(b.hp_trail)}'
    finally:
        uninstall_backend()


def test_equal_value_swap_still_pairs_trail() -> None:
    """等值交换仍配对:交换前 hp 已 == min(gold, SQUAD_HP_CAP) → 等值
    写行照落、轨迹仍同拍追加(尾值检测式在此形态漏配,呈现一次性标志位 + 判别
    按每发恰一写行计数;本锁钉死配对形态选择的正确性)。"""
    b = _backend(seed=50)
    try:
        gs = b.gs
        _drive_to_offer(b)
        # 直构等值形态:hp = gold = 50(观察同写入口,先例 = 同目录
        # test_strategy_pick_hp 直构 hp=15 形)。
        sig_obs = ChannelSig(family='obs', actor='TestSwapPair', mode='read')
        gs.observe(gs.hp, 50, evidence='t:seed:hp', sig=sig_obs)
        gs.observe(gs.gold, 50, evidence='t:seed:gold', sig=sig_obs)
        trail0 = len(b.hp_trail)
        _pick(b, '不等价交换',
              ['不等价交换', '躺平', '随便一张未收录卡'])
        assert gs.hp.value == 50, f'等值交换 hp 不变: {gs.hp.value}'
        assert gs.gold.value == 50, f'等值交换 gold 不变: {gs.gold.value}'
        assert gs.hp.evidence == _SWAP_EVIDENCE, \
            f'等值写行应在案(evidence 换为交换笔): {gs.hp.evidence}'
        assert len(b.hp_trail) == trail0 + 1, \
            f'等值交换轨迹仍应恰追加一行: {list(b.hp_trail)}'
        assert b.hp_trail[-1] == int(gs.hp.value), \
            f'轨迹尾值应同步现值: {b.hp_trail[-1]}'
    finally:
        uninstall_backend()


def test_unpicked_swap_card_zero_write_zero_append() -> None:
    """未落卡零扰动:opts 含本卡但选另一张 → 落地交集空 → 零交换写行
    零轨迹追加(kernel 分支按上报卡名触发不按 opts 触发;一次性标志位同拍消费,
    本次不残留)。"""
    b = _backend(seed=51)
    try:
        gs = b.gs
        _drive_to_offer(b)
        hp0, ev0 = gs.hp.value, gs.hp.evidence
        gold0, gev0 = gs.gold.value, gs.gold.evidence
        trail0 = len(b.hp_trail)
        _pick(b, '躺平', ['不等价交换', '躺平', '随便一张未收录卡'])
        assert '不等价交换' not in (gs.active_strategies.value or [])
        assert gs.hp.value == hp0 and gs.hp.evidence == ev0, \
            f'未落卡出现 hp 写行: {gs.hp.value} / {gs.hp.evidence}'
        assert gs.gold.value == gold0 and gs.gold.evidence == gev0, \
            f'未落卡出现 gold 写行: {gs.gold.value} / {gs.gold.evidence}'
        assert len(b.hp_trail) == trail0, \
            f'未落卡轨迹追加: {list(b.hp_trail)}'
    finally:
        uninstall_backend()
