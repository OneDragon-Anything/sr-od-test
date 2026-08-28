"""过渡框架启动重接线测试(开关 framework_startup_v2_enabled 生命周期第 1 态)。

锁四件事:
1. 启动判据单帧锁:纯持有权 ≥2 主门(命中/不命中例)+ 持有1+在售2 加速项
   + 纯在售不启动 + 滞后保持(语义见 cw_transition.pick_framework_startup);
2. 零漂移锁:开关默认关,decide_prep 不触碰 session.transition_framework;
3. 开关值锁:DEFAULT_REGISTRY 默认 False;
4. 遥测契约锁:cw_sim_checks.check_transition_framework_liveness
   (armed 执法抓静默死亡;自动档对全空不误报)。
"""
import dataclasses
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_sim_checks import (  # noqa: E402
    check_transition_framework_liveness,
)
from sr_od.application.currency_war.cw_state import (  # noqa: E402
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession  # noqa: E402
from sr_od.application.currency_war.cw_transition import (  # noqa: E402
    pick_framework_startup,
)
from sr_od.application.currency_war.decision_v2.registry import (  # noqa: E402
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.strategy import (  # noqa: E402
    DecisionV2Strategy,
)


def _state(owned_xz: int = 0, shop_xz: int = 0) -> GameState:
    """P1 中局态:bench 放 owned_xz 张仙舟框架件,shop 放 shop_xz 张。"""
    s = GameState()
    s.plane, s.round_num, s.level, s.gold, s.hp = 1, 3, 5, 60, 80
    s.board = {'仙舟': owned_xz}
    bench: list = [None] * 9
    xz = ['藿藿', '爻光', '丹恒·饮月', '椒丘', '卡芙卡']
    for i in range(min(owned_xz, 5)):
        bench[i] = BenchChar(slot=i, char_id=xz[i], faction='仙舟')
    s.bench = bench
    s.deployed = []
    s.shop = [ShopCard(x=i + 1, faction='仙舟', name='丹恒·饮月', cost=2)
              for i in range(shop_xz)]
    return s


# ===== 1. 启动判据单帧锁 =====

def test_startup_owned_gate_hit() -> None:
    """纯持有权 ≥2 → 选定领先框架(主门命中例)。"""
    got = pick_framework_startup(
        [BenchChar(slot=0, char_id='藿藿', faction='仙舟')],
        [BenchChar(slot=0, char_id='爻光', faction='仙舟')],
        shop=[], current='')
    assert got == '仙舟'


def test_startup_owned_gate_miss() -> None:
    """持有 1(无在售加速)→ 不启动,无现任返 ''(主门不命中例)。"""
    got = pick_framework_startup(
        [BenchChar(slot=0, char_id='藿藿', faction='仙舟')],
        [], shop=[], current='')
    assert got == ''


def test_startup_shop_accelerator() -> None:
    """持有 1 + 开门店同框架 ≥2(半权合计 ≥1.0)→ 加速启动。"""
    shop = [ShopCard(x=1, faction='仙舟', name='丹恒·饮月', cost=2),
            ShopCard(x=2, faction='仙舟', name='椒丘', cost=2)]
    got = pick_framework_startup(
        [BenchChar(slot=0, char_id='藿藿', faction='仙舟')],
        [], shop=shop, current='')
    assert got == '仙舟'


def test_startup_pure_shop_never_starts() -> None:
    """纯在售(持有 0)永不启动——防刷新噪声翻转。"""
    shop = [ShopCard(x=1, faction='仙舟', name='丹恒·饮月', cost=2)]
    assert pick_framework_startup([], [], shop=shop, current='') == ''


def test_startup_hysteresis_keeps_current() -> None:
    """现任框架手里有真件 → 未达门也保持,不闪回 ''(滞后语义)。"""
    got = pick_framework_startup(
        [BenchChar(slot=0, char_id='藿藿', faction='仙舟')],
        [], shop=[], current='仙舟')
    assert got == '仙舟'
    # 挑战者(列车:持有1+在售2 → 合并权领先)持有权未领先现任 ≥1 → 保持现任
    bench = [BenchChar(slot=1, char_id='三月七', faction='列车同行')]
    shop = [ShopCard(x=1, faction='列车同行', name='花火', cost=2),
            ShopCard(x=2, faction='列车同行', name='姬子·启行', cost=3)]
    got = pick_framework_startup(
        [BenchChar(slot=0, char_id='藿藿', faction='仙舟')],
        bench, shop=shop, current='仙舟')
    assert got == '仙舟'


# ===== 2/3. 零漂移锁 + 开关值锁 =====

def test_registry_default_off() -> None:
    """开关值锁:默认 False(开关生命周期第 1 态:落码默认关)。"""
    assert DEFAULT_REGISTRY.framework_startup_v2_enabled is False


def test_flag_off_zero_drift() -> None:
    """零漂移锁:开关关,decide_prep 不触碰 transition_framework——即使
    板面持有 ≥2 也保持未写入(消费面读缺省 '',与现状逐位一致)。"""
    s = _state(owned_xz=2, shop_xz=2)
    sess = StrategySession()
    strat = DecisionV2Strategy()   # 默认注册表 = 关
    strat.update_target(s, sess, None)
    acts_a = strat.decide_prep(s, sess, None)
    assert getattr(sess, 'transition_framework', '') == ''
    acts_b = strat.decide_prep(s, sess, None)
    assert acts_a == acts_b   # 同态重入决策序列确定(关态无异源分支)


# ===== 开态行为锁 =====

def test_flag_on_selects_and_clears_on_lock() -> None:
    """开态:decide_prep 按纯持有权刷新 session 字段;意向锁线后
    (in_early_phase 为假)清空——与旧栈「定型后清框架」语义对齐。"""
    reg = dataclasses.replace(DEFAULT_REGISTRY,
                              framework_startup_v2_enabled=True)
    s = _state(owned_xz=2, shop_xz=2)
    sess = StrategySession()
    strat = DecisionV2Strategy(registry=reg)
    strat.update_target(s, sess, None)
    strat.decide_prep(s, sess, None)
    assert sess.transition_framework == '仙舟'
    # 意向锁线 → committed → 清空
    sess.v3_intention.locked_comp = '某终局套'
    strat.decide_prep(s, sess, None)
    assert sess.transition_framework == ''


# ===== 4. 遥测契约锁 =====

def _decisions_row(recorded: str, owned_xz: int, shop_xz: int) -> dict:
    s = _state(owned_xz=owned_xz, shop_xz=shop_xz)
    return {
        'plane': 1, 'round_num': s.round_num,
        'sess_framework': recorded, 'sess_active_env': '',
        'state': {
            'bench': [{'char_id': b.char_id} for b in s.bench if b],
            'deployed': [],
            'shop': [{'name': c.name} for c in s.shop],
        },
    }


def test_liveness_contract_healthy() -> None:
    """健康管线:recorded 与帧内重放一致 → armed 执法零违规。"""
    row = _decisions_row('仙舟', owned_xz=2, shop_xz=0)
    out = check_transition_framework_liveness([row], armed=True)
    assert out['violations'] == 0
    assert out['eligible_rows'] == 1 and out['refresh_rows'] == 1


def test_liveness_contract_silent_death() -> None:
    """静默死亡指纹:重放可选定而 recorded 恒空(载体死代码形态)
    → armed 执法必红(刷新调用=0 + 一致率跌破)。"""
    rows = [_decisions_row('', owned_xz=2, shop_xz=2),
            _decisions_row('', owned_xz=3, shop_xz=0)]
    out = check_transition_framework_liveness(rows, armed=True)
    assert out['violations'] >= 1
    assert out['refresh_rows'] == 0


def test_liveness_contract_auto_no_false_alarm_off() -> None:
    """自动档:全空(合法默认关/零漂移锚)不误报;sims 账本行无
    sess_framework 字段 → 合格帧 0,也零违规只披露。"""
    rows = [_decisions_row('', owned_xz=2, shop_xz=2)]
    out = check_transition_framework_liveness(rows)
    assert out['violations'] == 0 and out['armed'] is False
    sim_rows = [{'plane': 1, 'round_num': 3, 'state': {}}]   # 无 sess_framework
    out = check_transition_framework_liveness(sim_rows)
    assert out['violations'] == 0 and out['eligible_rows'] == 0
