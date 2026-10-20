# -*- coding: utf-8 -*-
"""真题检索与配额子系统（考研 / 执业医师）。

模块划分：
  answer_recovery — 从解析文本恢复答案
  schema          — 统一题目记录、去重、JSONL 读写
  sources         — GoldenSet / CMExam 源适配
  retrieval       — BM25 题目级检索与查询构造
  planner         — 双配额 + 教师重点覆盖约束选题
  check           — 终审门禁

设计原则：
  - 只读原始素材，不修改 GoldenSet / CMExam；
  - 答案不可核的题不进入可选池；
  - 检索不到时输出 insufficient，不用无关题凑数；
  - 所有产物带 source_id / keypoint_ref / answer_confidence / license。
"""
