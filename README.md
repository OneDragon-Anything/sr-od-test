# SR测试项目

需要将本目录设置成 test source folder

## 测试纪律(硬规则)

1. **`test_context` 是 session 级共享**(conftest):改其属性(`run_context`/`controller` 等)一律
   `monkeypatch.setattr`(自动还原);裸赋值会污染后续**别的测试文件**(单跑必过/全量必挂的假
   flaky),conftest 有 autouse 守卫(警告+还原),但守卫不是写裸赋值的许可。
2. **测试不写真实 `.debug/` 路径**:落盘一律 `tmp_path` 或 monkeypatch 重定向目标模块的
   `_DIR` 常量;`finally` 还原动过的外部状态(文件备份-恢复、flag 清理)。
3. **fixture 驱动的 op 流程测试**用 `test/harness/fixture_controller.py`(`FixtureController`
   + `WatchdogOperationMixin` + `enter_running_state`/`reset_running_state`);运行态前置/复位
   已封装在 helper 里,别手写 `_run_state` 裸赋值。
4. **op 流程测试的 `execute()` 必须包 `fast_sleep()`**(harness 提供):mock 画面瞬间切换,
   框架的轮间/点击前等待(`pre_delay`/`_after_round_wait`)纯属空等——2026-08-25 实测流程
   测试 ~60% 时间在 `time.sleep`。用法 `with fast_sleep(): result = op.execute()`。
5. **测试不发真实网络请求**:凡被测链路会触网(如配置初始化拉代理地址),在测试入口
   mock 掉——网络不仅慢(实测单次 ~1s)还引入不确定性(断网/代理变化 = 假 flaky)。
   已有的:conftest 短路 `ghproxy_service.update_proxy_url`;新增触网路径照此办理。
6. **锁契约不锁分布,重结果一次复用**:
   - 断言「输出结构/范围/回显」而非统计数值——锁分布数值 = change-detector 陷阱,
     任何合法改动必红(判例:`test_batch_stats_shape` 只锁形状;smoke 的 docstring 同款约定);
   - 同一份昂贵计算在**同一次测试运行内只算一次**,多条断言共享结果——逐条各算
     = 纯浪费(判例:kwarg 审计三条测试曾各扫全仓一遍 3×3s,现共享一次;
     cli_smoke 曾同 seed 独立跑两遍 25 局);
   - 昂贵的**可序列化中间产物**(逐局终值等)优先从已有产物(账本/报告)提取,
     别为断言再跑一遍。
7. **批量/循环模拟的 n 取「断言成立的最小值」**:断言全是形状检查时 n=10 与 n=60
   等价(实测 7.9s→1.2s);更大的样本量属于 sim A/B 日常工作流(n=300 三窗口),
   不该由单元测试承担。同理:不落盘选项(`ledger=False`)优先于默认落盘。

## 运行速度

- **标准跑法 = 串行**:`uv run pytest sr-od-test/`(CI 资源有限,测试规范以串行为准;
  2026-08-25 全链路优化后实测:冷跑 ~2:15、warm 跑 **~2:00**;优化前 5:15)。
- **OCR 结果持久缓存**(`.pytest_cache/d/ocr_memo/`,conftest 内置):内容哈希
  + 模型指纹键控,跨会话复用同一 fixture 的推理结果(id_mark 单文件 65s→8s);
  模型更新自动失效,`pytest --cache-clear` 一键清;CI 恒冷路径,无收益也无成本。
- **OCR 设备跟随本地 `config/model.yml` 的 `ocr_use_gpu`**(测试 ctx 继承):
  本机 `true` = DirectML,实测 553ms/张 vs CPU 759ms/张(快 ~27%),且 6 张 fixture
  两种设备文本集完全一致、DML 同图多次自洽;无 DML 的环境(CI)自动回退纯 CPU,
  不会崩。注意:开 GPU 时若同机还有实机局/MCP server 在用 DML,会互相争用。
- **sim 日志已降噪**(conftest 模块级 framework log INFO→WARNING):sim 逐决策
  INFO 曾一轮全量写 100MB+ test.log。排查具体测试时,临时注释 conftest 里
  `setLevel(logging.WARNING)` 那行重跑即可。
- 本机可选 `-n 8`(dev 组已带 pytest-xdist;缓存生效后 OCR 大头已摊薄,并行
  边际收益缩小,不再显著优于串行 warm),**不作规范**:内存 ~1.2-2GB/worker、
  CPU 峰值 15+ 核;机器忙时(实机局/其他 agent 在跑)别用——实测两套 -n 8 并跑
  互相挤到 6 分钟且出时序性失败。
- 剩余耗时大头(warm 下都是真实覆盖成本):~1900 条纯逻辑测试本体、sim 真实
  计算、session 初始化(~13s)、少量冷路径 OCR(新 fixture 首见)。
- conftest 已内置两项 session 级优化:初始化时短路 `ghproxy_service.update_proxy_url`
  (避免真实网络请求);`ocr_service` 包内容哈希 memo(同一 fixture 图跨文件只推理一次)。
