# -*- coding: utf-8 -*-
"""sim 台账/cw_dev 归档根单一源锁(cw_sim.cw_dev_dir)。

背景:批量 runner 模板曾把台账散写到仓库根 ``cw_dev/`` 当暂存位,
每批 sim 跑完 git status 再生未跟踪目录、需手工迁
``.debug/temp/currency_war/cw_dev/baselines/``。修法 = 单一源函数
``cw_dev_dir()``(基根与 SIM_RUNS_DIR 同源,动态读模块全局),测试
用 tmp_path 注入临时基根验证落点——**不写真实 .debug**(测试纪律)。
"""
from pathlib import Path

from sr_od.application.currency_war import cw_sim


def test_cw_dev_dir_follows_injected_base(tmp_path, monkeypatch) -> None:
    """注入 tmp 基root:归档根必须落 <tmp>/.debug/temp/currency_war/cw_dev/。"""
    fake_replay = (tmp_path / '.debug' / 'temp' / 'currency_war' / 'replay')
    monkeypatch.setattr(cw_sim, '_AUTO_REPLAY_DIR', fake_replay)

    root = cw_sim.cw_dev_dir()
    assert root == tmp_path / '.debug' / 'temp' / 'currency_war' / 'cw_dev'
    # 防再生的核心断言:归档根不得落在注入基的父级(仓库根形态 <base>/cw_dev)
    assert root.parent == fake_replay.parent
    assert cw_sim.cw_dev_dir('baselines', 'probe') == \
        root / 'baselines' / 'probe'


def test_cw_dev_dir_same_base_as_sim_runs() -> None:
    """同源不变量:归档根与 sim 台账默认目录共用同一基根(动态读全局)。"""
    assert cw_sim.cw_dev_dir().parent == cw_sim.SIM_RUNS_DIR.parent


def test_ledger_write_lands_under_injected_cw_dev(tmp_path, monkeypatch) -> None:
    """真实落盘烟测:write_batch_ledger 走注入基的 cw_dev 位,自建目录。"""
    fake_replay = (tmp_path / '.debug' / 'temp' / 'currency_war' / 'replay')
    monkeypatch.setattr(cw_sim, '_AUTO_REPLAY_DIR', fake_replay)

    out = cw_sim.cw_dev_dir('baselines', 'smoke_n0')
    cw_sim.write_batch_ledger([], out, pool_fp='deadbeef')

    assert (out / 'manifest.json').exists()
    assert (out / 'decisions.jsonl').exists()
    assert (out / 'outcomes.jsonl').exists()
    # 仓库根形态(<注入基>/cw_dev,即旧病灶位)不得被创建
    assert not (tmp_path / 'cw_dev').exists()


def test_small_sim_leaves_no_repo_root_cw_dev(tmp_path, monkeypatch) -> None:
    """端到端负向锁:n=1 小 sim 全管线跑完,仓库根不得出现 cw_dev/。

    仓根锚定与生产同源:从 ``_AUTO_REPLAY_DIR`` 用同一 pathlib 表达
    (parents[3],见 cw_sim 定义)回推,注入后即指向 tmp_path——
    断言「生产口径的仓库根」无 cw_dev,不写真实 .debug(测试纪律)。
    SIM_RUNS_DIR 一并注入:它是 import 期常量,默认批量落盘须重定向
    到 tmp,避免测试写真实 sim_runs。
    """
    fake_replay = (tmp_path / '.debug' / 'temp' / 'currency_war' / 'replay')
    monkeypatch.setattr(cw_sim, '_AUTO_REPLAY_DIR', fake_replay)
    monkeypatch.setattr(cw_sim, 'SIM_RUNS_DIR',
                        tmp_path / '.debug' / 'temp' / 'currency_war' / 'sim_runs')

    repo_root = cw_sim._AUTO_REPLAY_DIR.parents[3]   # 与生产同源的仓根表达
    assert repo_root == tmp_path

    rep = cw_sim.simulate_p1_batch(1, pool='snapshot', checks=False,
                                   ledger=True)
    assert rep['n'] == 1
    assert not (repo_root / 'cw_dev').exists()
