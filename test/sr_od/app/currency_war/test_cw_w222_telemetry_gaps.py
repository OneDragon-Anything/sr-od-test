"""两处遥测缺口回归锁(判读立批池①+②)。

背景(判读实锤,2026-08-27):
- 缺口① decisions.state.equips 两局恒空:owned 穿戴池的 session 写端
  (equip_all)与 _pseudo_state 读端拷贝都在,但 decisions 落盘用的 state
  是 OCR 现读对象(shop 循环 read_game_state / director obs.state),
  equips 从未被拷进去——落盘链在 record 站点断裂。
- 缺口② 「简报首领候选集读得」全日志 0 条:handle_briefing 等三模块用
  ``logging.getLogger(__name__)`` 裸 logger,而框架日志走命名 logger
  'OneDragon'(propagate=False 不经 root,无 root handler)→ 本文件所有
  INFO/WARNING 从未落地,判读无法区分「read_bosses 恒空」vs「幂等跳过」。

本锁钉死:
- record 站点(shop.py / prep_director._record_step)在落盘前从
  session.last_owned_equips 补拷(state.equips 落值 + 空值语义);
- 拷贝位置在 decide_prep **之后**(cw_comps 装备权重读 state.equips,
  提前拷=改决策行为——观测链修复的行为边界);
- 简报三模块 logger 挂框架 'OneDragon'(可见性)+ 空读可诊断行存在。
"""
from __future__ import annotations

import json
from pathlib import Path

from one_dragon.utils import log_utils
from sr_od.application.currency_war import cw_telemetry
from sr_od.application.currency_war.kernel.cw_state import GameState

_SRC_ROOT = Path('src/sr_od/application/currency_war')


def _src(rel: str) -> str:
    """读源码文本(相对 currency_war 包路径;repo 根运行 pytest)。"""
    return (_SRC_ROOT / rel).read_text(encoding='utf-8')


# ===== 缺口①:decisions.state.equips 落盘链(record 站点)=====


def test_shop_record_site_copies_owned_pool_before_record() -> None:
    """shop.py 主 record 站点:decide_prep 之后、record_decision 之前补拷。

    顺序锁三点:①拷贝行存在;②在 decide_prep 之后(装备权重读 state.equips,
    提前拷=改决策行为);③在其后的 record_decision(state 调用之前)。
    """
    src = _src('operations/prep/shop.py')
    copy_line = 'state.equips = list(getattr(match.session, \'last_owned_equips\', []) or [])'
    assert copy_line in src, 'shop record 站点缺 owned 池补拷行(W222 缺口①回归)'
    i_plan = src.index('actions = match.strategy.decide_prep')
    i_copy = src.index(copy_line)
    i_rec = src.index('cw_telemetry.record_decision(state, target_name')
    assert i_plan < i_copy < i_rec, '补拷必须在 decide_prep 之后、record 之前(行为边界)'


def test_director_record_step_copies_owned_pool_on_state_copy() -> None:
    """prep_director._record_step 步进站点:copy 后补拷(防污染 obs 决策输入)。"""
    src = _src('prep_director.py')
    i_step = src.index('def _record_step')
    i_copy = src.index('st = st.copy()', i_step)
    i_equips = src.index('last_owned_equips', i_step)
    i_rec = src.index('cw_telemetry.record_decision(', i_step)
    assert i_step < i_copy < i_equips < i_rec, \
        '_record_step 必须先 copy 再补拷 equips 再 record(W222 缺口①回归)'


def test_record_decision_state_carries_equips(tmp_path) -> None:
    """端到端空值/非空回归:state.equips 经 serialize 落 decisions 行。"""
    rec = cw_telemetry.TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    st = GameState(gold=50, round_num=1, plane=1)
    st.equips = ['财富宝钻', '分身墨镜', '拆装扳手']
    rec.record_decision('w222', 'A8', st, '', {}, {}, [])
    rows = [json.loads(r) for r in
            (tmp_path / 'decisions.jsonl').read_text(encoding='utf-8').splitlines()]
    # 全量语义(工具同进快照,ADR-0387):不专名、只锁非空与成员
    assert set(rows[-1]['state']['equips']) == {'财富宝钻', '分身墨镜', '拆装扳手'}
    # 空值语义:默认 GameState → [](不造出假持有)
    rec.record_decision('w222', 'A8', GameState(), '', {}, {}, [])
    rows = [json.loads(r) for r in
            (tmp_path / 'decisions.jsonl').read_text(encoding='utf-8').splitlines()]
    assert rows[-1]['state']['equips'] == []


# ===== 缺口②:简报日志可见性(死 logger)=====


def test_briefing_modules_use_framework_logger() -> None:
    """三模块 _log 必须是框架 'OneDragon' logger(裸 getLogger=__name__ 无 handler,
    INFO 从未落地——全日志 0 条的根因)。"""
    import importlib

    for mod_name in (
        'sr_od.application.currency_war.operations.handlers.handle_briefing',
        'sr_od.application.currency_war.cw_briefing_obs',
        'sr_od.application.currency_war.operations.entry.start_currency_war_match',
    ):
        mod = importlib.import_module(mod_name)
        assert mod._log is log_utils.log, \
            f'{mod_name}._log 不是框架 logger(死 logger 回归)'


def test_briefing_empty_read_is_logged() -> None:
    """空读可诊断:read_bosses 空也留行(区分「恒空」vs「幂等跳过」的前提)。"""
    src = _src('operations/handlers/handle_briefing.py')
    assert '简报首领读得' in src
    assert '简报首领未读到' in src, '空读分支缺日志行(W222 缺口②回归)'
    # 裸 logger 回退锁:不得再 import logging/getLogger(注释里提及不辖)
    assert 'import logging' not in src, 'handle_briefing 不得回退裸模块 logger'
    assert 'getLogger(__name__)' not in src.replace(
        '``logging.getLogger(__name__)``', ''), 'handle_briefing 不得挂裸模块 logger'
