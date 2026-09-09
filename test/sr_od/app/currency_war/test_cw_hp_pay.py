"""T-100 批1 锁:hp_pay 血购执行回执写点 + 遥测禁入决策输入守卫(ADR-0577)。

- 写点 = prep_actions.record_hp_pay_event(两通道共用唯一实现):店通道
  LevelUpOp.execute(单击=一行)与 prep 通道 _level_up(连点循环内每击
  一行),粒度 = 击数(F2 裁决,判读口径:行数=击数,总量=Σhp_delta)。
- mode 与判定同源注册表派生(F8):active_strategies 中 xp_buy_hp_cost>0
  的卡;非 active(金本位升级)→ 零行。
- 隔离申报(F6-2/§1.3):hp_pay 行纯观测追加写,禁入决策输入——隔离锁
  (写点零状态突变)+ grep 守卫锁(键在 strategies/impl 决策面零命中,
  手法 = ADR-0571 test_disclosure_fields_not_consumed_by_decision_modules)。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_state import GameState, LevelUp
from sr_od.application.currency_war.prep_actions import (
    PrepActionExecutor,
    record_hp_pay_event,
)
from sr_od.application.currency_war.telemetry import recorder as cw_recorder

# ===== 共用桩 =====

def _hp_session(active: list[str] | None = None) -> SimpleNamespace:
    """血购回执写点依赖面桩:active_strategies + last_state(其余无关)。"""
    return SimpleNamespace(
        active_strategies=list(active or []),
        last_state=GameState(plane=2, round_num=1, hp=61, gold=70),
    )


@pytest.fixture()
def captured_exo(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """捕获 record_exogenous 调用(写点经模块属性消费,patch 即全捕)。"""
    rows: list[dict] = []

    def _cap(round_num, kind, detail='', state=None, choice=None):
        rows.append({'round_num': round_num, 'kind': kind,
                     'detail': detail, 'choice': choice})

    monkeypatch.setattr(cw_recorder, 'record_exogenous', _cap)
    return rows


# ===== 单元:店通道(prep_actions LevelUpOp 走 cw_shop_action_ops) =====

def _shop_env(session, ledger=None):
    """ShopExecEnv 依赖面桩(LevelUpOp.execute 只触 op/ledger/match/state)。"""

    from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
        LevelUpOp,
        ShopExecEnv,
        ShopVisitLedger,
    )

    op = SimpleNamespace(ctx=SimpleNamespace(
        controller=SimpleNamespace(click=lambda p: None)))
    env = ShopExecEnv(
        op=op, match=SimpleNamespace(session=session), config=None,
        click_pts=[], level_btn=Point(1, 2), refresh_btn=Point(3, 4),
        ledger=ledger or ShopVisitLedger(), state=GameState())
    return LevelUpOp(LevelUp(cost=4)), env


def test_shop_channel_receipt_per_click(captured_exo, monkeypatch):
    """店通道协议 active → execute 一击一行,字段全锁(F8 mode=注册表派生
    卡名;plane/round 显式入 choice,currency/hp_delta/clicks/basis 定值)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops as so
    monkeypatch.setattr(so.time, 'sleep', lambda s: None)   # 动画等待桩
    op, env = _shop_env(_hp_session(['奋斗协议']))
    assert op.execute(env) is True
    rows = [r for r in captured_exo if r['kind'] == 'hp_pay']
    assert len(rows) == 1                    # 单动作形态 = 恰一击一行
    assert rows[0]['choice'] == {
        'plane': 2, 'round_num': 1, 'currency': 'hp', 'hp_delta': -6,
        'mode': '奋斗协议', 'clicks': 1, 'basis': 'modeled'}
    assert rows[0]['round_num'] == 1         # 顶层 round 同步携带(读端兼容)


def test_shop_channel_inactive_zero_rows(captured_exo, monkeypatch):
    """非血本位协议(无 xp_buy_hp_cost 卡 active)→ 零行 no-op(金本位
    升级不产 hp_pay;mode 判定与 mode 值同源注册表,零行为面遗漏)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops as so
    monkeypatch.setattr(so.time, 'sleep', lambda s: None)
    op, env = _shop_env(_hp_session(['淘金客']))   # 在册卡但非血本位
    assert op.execute(env) is True
    assert [r for r in captured_exo if r['kind'] == 'hp_pay'] == []


def test_prep_channel_four_clicks_four_rows(captured_exo, monkeypatch):
    """F2 粒度锁:prep 通道连点 4 击 → 4 行(每击已实际扣血,验证成功前
    落行);同批 level_up 事件行不混入 hp_pay 计数。"""
    import sr_od.application.currency_war.prep_actions as pa
    ex = object.__new__(PrepActionExecutor)
    sess = _hp_session(['奋斗协议'])
    sess.effect_inventory = SimpleNamespace(on_level_up=lambda: None)
    sess.last_level_obs = None
    ex._ctx = SimpleNamespace(
        cw_match=SimpleNamespace(session=sess),
        controller=SimpleNamespace(mouse_move=lambda p: None,
                                   click=lambda p: None))
    ex._op = SimpleNamespace(screenshot=lambda: None,
                             park_cursor=lambda **kw: None)
    # before=5;前 3 击验证 miss(lv None),第 4 击读到 6 → 恰 4 击
    reads = iter([5, None, None, None, 6])
    monkeypatch.setattr(pa, '_read_level_raw',
                        lambda ctx, screen: next(reads))
    monkeypatch.setattr(pa, 'read_gold', lambda ctx, screen: 100)
    monkeypatch.setattr(pa, 'area_center', lambda ctx, name: None)
    ok, detail = ex._level_up()
    assert ok is True and '5→6' in detail
    rows = [r for r in captured_exo if r['kind'] == 'hp_pay']
    assert len(rows) == 4                    # 4 击 = 4 行(粒度=击数)
    assert all(r['choice']['hp_delta'] == -6 and r['choice']['clicks'] == 1
               for r in rows)


# ===== 隔离锁(§1.4 测试3):写点零决策状态突变 =====

def test_receipt_write_isolation_no_state_mutation(captured_exo):
    """hp_pay 回执写入前后:state 序列化逐字节不变 + session 无新增属性
    ——写入路径与决策路径无共享可变状态(ADR-0577 隔离申报的可执行面)。"""
    from sr_od.application.currency_war.telemetry.schema import serialize_state
    sess = _hp_session(['奋斗协议'])
    before = json.dumps(serialize_state(sess.last_state), sort_keys=True)
    attrs_before = set(vars(sess).keys())
    record_hp_pay_event(sess, 2, 1)
    assert json.dumps(serialize_state(sess.last_state),
                      sort_keys=True) == before
    assert set(vars(sess).keys()) == attrs_before
    assert len(captured_exo) == 1            # 行照常落(隔离≠不写)


# ===== grep 守卫锁(F7,ADR-0571 同款手法):禁决策面消费 =====

#: 守卫键集:kind 名 / 结构化载荷键。'basis' 用词边界匹配——决策面在册键
#: auth_basis(授权依据记录字段,LevelUp/发射分键)是不同语义的合法存在,
#: 子串判据会误伤(\\b 在 auth_basis 的下划线处不成立,天然排除)。
_HP_PAY_SUBSTR_KEYS: tuple[str, ...] = ('hp_pay', 'hp_delta')
_HP_PAY_WORD_KEYS: tuple[str, ...] = ('basis',)


def _guard_key_hits(text: str) -> list[str]:
    """守卫判据单一实现(主扫描与变异自检共用,防自检复刻判据)。"""
    hits = [name for name in _HP_PAY_SUBSTR_KEYS if name in text]
    hits += [name for name in _HP_PAY_WORD_KEYS
             if re.search(rf'\b{name}\b', text)]
    return hits


def test_hp_pay_keys_not_consumed_by_decision_modules():
    """hp_pay 遥测键禁现于决策面(strategies/impl 全子树扫描,零白名单
    ——决策判据消费 hp_pay = 把「建模期望账」当支付真值读,违反遥测禁入
    决策输入禁令(ADR-0577 §隔离申报);写点/装配消费面分别在
    prep_actions 与 telemetry,均不在扫描根)。盲区自检:扫描根失准 =
    假绿,先证根在且非空;变异自检:判据函数对合成坏形必须可检出,
    auth_basis 合法在册键必须不误伤。"""
    root = (Path(__file__).resolve().parents[5] / 'src' / 'sr_od'
            / 'application' / 'currency_war' / 'strategies' / 'impl')
    sentinel = root / 'mandate_v1' / 'mandate.py'
    assert sentinel.is_file(), f'扫描根解析失准:{root}'
    scanned = list(root.rglob('*.py'))
    assert len(scanned) >= 20, f'扫描文件数异常({len(scanned)}),根可能错位'
    # 变异自检:正例两键可检出;auth_basis 在册键不误伤(word 边界在
    # 下划线处不成立,天然排除)。
    assert _guard_key_hits("x('hp_pay') r['hp_delta']") == \
        ['hp_pay', 'hp_delta'], '变异自检未命中'
    assert _guard_key_hits('self.auth_basis = "record"') == [], \
        '变异自检:auth_basis 被误伤'
    offenders: dict[str, str] = {}
    for path in scanned:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding='utf-8')
        for name in _guard_key_hits(text):
            offenders[f'{rel}:{name}'] = name
    assert not offenders, (
        'hp_pay 遥测键被决策面引用(禁令 = ADR-0577:血购回执纯观测,'
        f'禁回写 state.hp/session.last_hp_real/预算门):{offenders}')
