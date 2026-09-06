"""决策帧截图留证钩子锁(decision_frame_hooks)。

锁三件:①输出文件名格式(ts 前缀可对齐 decisions.jsonl 行 ts);
②滚动删除逻辑(每挂点保留最近 KEEP_PER_TAG 帧,旧的被删);
③挂点调用存在(源码级:4 类挂点在宿主文件中有 save_decision_frame 调用)。
"""
import re
from pathlib import Path

import numpy as np
import pytest

from sr_od.application.currency_war.operations import decision_frame_hooks as dfh


class _FakeOp:
    def screenshot(self):
        return np.zeros((4, 4, 3), dtype=np.uint8)


@pytest.fixture
def frame_env(tmp_path, monkeypatch):
    """落盘重定向到 tmp_path + 固定 run_id(测试零真实副作用,不写真实 .debug/)。"""
    root = tmp_path
    monkeypatch.setattr(dfh, 'get_project_root', lambda: root)
    import sr_od.application.currency_war.telemetry.state as tel_state
    monkeypatch.setattr(tel_state, 'current_run_id', lambda: 'run_t')
    return root / '.debug' / 'temp' / 'currency_war' / 'decision_frames' / 'run_t'


def _img() -> np.ndarray:
    return np.zeros((4, 4, 3), dtype=np.uint8)


def test_filename_format(frame_env):
    """锁文件名格式:<yyyymmdd_HHMMSS>_<mmm>_<tag>.png(ts 与 decisions 行对齐)。"""
    fn = dfh.save_decision_frame(_FakeOp(), 'shop_entry', _img())
    assert fn is not None
    assert re.fullmatch(r'\d{8}_\d{6}_\d{3}_shop_entry\.png', fn), fn
    assert (frame_env / fn).is_file()


def test_rolling_delete_keeps_recent(frame_env):
    """锁滚动删除:同 tag 超 KEEP_PER_TAG 帧后,最旧的被删、保留最近 N 帧。"""
    # 先铺 KEEP_PER_TAG + 5 个旧文件(文件名 ts 递增保字典序=时间序)
    for i in range(dfh.KEEP_PER_TAG + 5):
        name = f'20260101_0000{i // 10:02d}_{i % 10:03d}_deploy.png'
        frame_env.mkdir(parents=True, exist_ok=True)
        (frame_env / name).write_bytes(b'old')
    fn = dfh.save_decision_frame(_FakeOp(), 'deploy', _img())
    assert fn is not None
    mine = sorted(frame_env.glob('*_deploy.png'))
    assert len(mine) == dfh.KEEP_PER_TAG
    # 最旧的 5 个被删;新写入的帧在(最近一帧保留)
    assert (frame_env / fn) in mine
    assert not (frame_env / '20260101_000000_000_deploy.png').exists()
    # 不同 tag 不被误删(滚动按 tag 维度隔离)
    other = frame_env / '20260101_000000_000_shop_entry.png'
    other.write_bytes(b'other-tag')
    dfh.save_decision_frame(_FakeOp(), 'deploy', _img())
    assert other.is_file()


def test_hook_call_sites_exist():
    """锁挂点存在(源码级):4 类决策依据帧各有 save_decision_frame 调用。"""
    src_root = Path(__file__).parents[5] / 'src' / 'sr_od' / 'application' \
        / 'currency_war'
    buy = (src_root / 'operations' / 'cw_op' / 'cw_op_buy_cards.py').read_text(
        encoding='utf-8')
    deploy = (src_root / 'operations' / 'cw_op' / 'cw_op_deploy.py').read_text(
        encoding='utf-8')
    loop = (src_root / 'operations' / 'cw_loop.py').read_text(encoding='utf-8')
    # 挂点 1/2:商店入口观察(每段一帧;刷新重观察同点覆盖)
    assert "save_decision_frame(op, 'shop_entry'" in buy
    # 挂点 3:部署决策帧
    assert "save_decision_frame(self, 'deploy'" in deploy
    # 挂点 4:0 系 overlay 分支命中(抽样锚 + 全量下限:分支数 ≥ 20)
    for tag in ('overlay_partner', 'overlay_invest_strategy', 'overlay_shop_open',
                'overlay_wish_trial', 'overlay_frontless'):
        assert f"save_decision_frame(self, '{tag}'" in loop, tag
    n_overlay = loop.count('save_decision_frame(self, ')
    assert n_overlay >= 20, n_overlay
