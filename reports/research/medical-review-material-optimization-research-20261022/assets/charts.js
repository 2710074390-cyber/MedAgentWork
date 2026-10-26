(function () {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var risk = style.getPropertyValue('--risk').trim();

  function init(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    return echarts.init(el, null, { renderer: 'svg' });
  }

  function baseGrid(extra) {
    return Object.assign({
      left: 18,
      right: 26,
      top: 34,
      bottom: 24,
      containLabel: true
    }, extra || {});
  }

  function resizeOn(chart) {
    if (!chart) return;
    window.addEventListener('resize', function () { chart.resize(); });
  }

  /* ---------- 图 1：教育 AI 市场规模 ---------- */
  var market = init('chart-market');
  if (market) {
    market.setOption({
      animation: false,
      tooltip: {
        trigger: 'axis',
        appendToBody: true,
        axisPointer: { type: 'shadow' },
        valueFormatter: function (v) { return v == null ? '—' : v + ' 十亿美元'; }
      },
      legend: { top: 0, right: 8, textStyle: { color: muted, fontSize: 11 } },
      grid: baseGrid({ top: 44, left: 10, right: 120, bottom: 10 }),
      xAxis: {
        type: 'value',
        max: 70,
        axisLabel: { color: muted, fontSize: 11 },
        splitLine: { lineStyle: { color: rule } },
        axisLine: { show: false }
      },
      yAxis: {
        type: 'category',
        inverse: true,
        data: ['AI + 教育整体', 'AI 导师（AI tutors）', '生成式 AI 教育内容工具'],
        axisLabel: { color: ink, fontSize: 12, width: 170, overflow: 'break' },
        axisLine: { show: false },
        axisTick: { show: false }
      },
      series: [
        {
          name: '2025',
          type: 'bar',
          barWidth: '26%',
          data: [8.3, 2.1, 2.1],
          itemStyle: { color: muted, opacity: 0.55, borderRadius: [0, 4, 4, 0] },
          label: { show: true, position: 'right', color: muted, fontSize: 10, formatter: '{c}' }
        },
        {
          name: '预测终点（2033/2034）',
          type: 'bar',
          barWidth: '26%',
          data: [57.2, 17.7, 23.8],
          itemStyle: { color: accent, borderRadius: [0, 4, 4, 0] },
          label: {
            show: true,
            position: 'right',
            color: ink,
            fontSize: 11,
            formatter: function (p) {
              var cagr = ['CAGR 25.9%', 'CAGR 30.5%', 'CAGR 31.2%'][p.dataIndex];
              return p.value + '  ·  ' + cagr;
            }
          }
        }
      ]
    });
    resizeOn(market);
  }

  /* ---------- 图 2：学生与教师 AI 采用率 ---------- */
  var adoption = init('chart-adoption');
  if (adoption) {
    adoption.setOption({
      animation: false,
      tooltip: {
        trigger: 'axis',
        appendToBody: true,
        axisPointer: { type: 'shadow' },
        valueFormatter: function (v) { return v == null ? '—' : v + '%'; }
      },
      legend: { top: 0, right: 8, textStyle: { color: muted, fontSize: 11 } },
      grid: baseGrid({ top: 42, left: 10, right: 70, bottom: 8 }),
      xAxis: {
        type: 'value',
        max: 100,
        axisLabel: { color: muted, fontSize: 11, formatter: '{value}%' },
        splitLine: { lineStyle: { color: rule } },
        axisLine: { show: false }
      },
      yAxis: {
        type: 'category',
        inverse: true,
        data: ['任何用途（HEPI 英国）', '评估用途（HEPI 英国）', '学习中用 AI（DEC 全球）', '高校教师日常用 AI（中国）'],
        axisLabel: { color: ink, fontSize: 12, width: 190, overflow: 'break' },
        axisLine: { show: false },
        axisTick: { show: false }
      },
      series: [
        {
          name: '2024',
          type: 'bar',
          barWidth: '26%',
          data: [66, 53, null, null],
          itemStyle: { color: muted, opacity: 0.45, borderRadius: [0, 4, 4, 0] },
          label: { show: true, position: 'right', color: muted, fontSize: 10, formatter: '{c}%' }
        },
        {
          name: '2025 / 最新',
          type: 'bar',
          barWidth: '26%',
          data: [92, 88, 86, 70],
          itemStyle: { color: accent, borderRadius: [0, 4, 4, 0] },
          label: { show: true, position: 'right', color: ink, fontSize: 11, formatter: '{c}%' }
        }
      ]
    });
    resizeOn(adoption);
  }

  /* ---------- 图 3：关键干预的效应量 ---------- */
  var evidence = init('chart-evidence');
  if (evidence) {
    var ev = [
      { name: 'GAI 知识获得（11 RCT）', v: 0.27, ci: '95% CI −0.31–0.85 · 不显著', color: muted },
      { name: 'GAI 实践技能（11 RCT）', v: 0.63, ci: '95% CI 0.10–1.16', color: accent },
      { name: '间隔重复（21,415 人）', v: 0.78, ci: '95% CI 0.56–0.99', color: accent },
      { name: '练习测试（元分析）', v: 0.61, ci: 'g ≈ 0.61', color: accent }
    ];
    evidence.setOption({
      animation: false,
      tooltip: {
        trigger: 'axis',
        appendToBody: true,
        axisPointer: { type: 'shadow' },
        formatter: function (ps) {
          var p = ps[0];
          var d = ev[p.dataIndex];
          return d.name + '<br/>SMD / g = <b>' + d.v + '</b><br/>' + d.ci;
        }
      },
      grid: baseGrid({ left: 10, right: 170, top: 18, bottom: 12 }),
      xAxis: {
        type: 'value',
        min: -0.1,
        max: 1.0,
        axisLabel: { color: muted, fontSize: 11 },
        splitLine: { lineStyle: { color: rule } },
        axisLine: { show: false }
      },
      yAxis: {
        type: 'category',
        inverse: true,
        data: ev.map(function (d) { return d.name; }),
        axisLabel: { color: ink, fontSize: 12, width: 190, overflow: 'break' },
        axisLine: { show: false },
        axisTick: { show: false }
      },
      series: [{
        type: 'bar',
        barWidth: '46%',
        data: ev.map(function (d) {
          return { value: d.v, itemStyle: { color: d.color, borderRadius: [0, 4, 4, 0] } };
        }),
        label: {
          show: true,
          position: 'right',
          color: ink,
          fontSize: 11,
          formatter: function (p) { return p.value + '  ·  ' + ev[p.dataIndex].ci; }
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: risk, type: 'dashed', width: 1.4 },
          label: { show: false },
          data: [{ xAxis: 0 }]
        }
      }]
    });
    resizeOn(evidence);
  }

  /* ---------- 图 4：12 维学习价值雷达（10 轴呈现） ---------- */
  var radar = init('chart-radar');
  if (radar) {
    radar.setOption({
      animation: false,
      tooltip: { appendToBody: true },
      legend: { top: 0, right: 8, textStyle: { color: muted, fontSize: 11 } },
      radar: {
        center: ['50%', '54%'],
        radius: '62%',
        indicator: [
          { name: '内容深度', max: 5 },
          { name: '准确性', max: 5 },
          { name: '考点匹配', max: 5 },
          { name: '逻辑结构', max: 5 },
          { name: '记忆强化', max: 5 },
          { name: '学习效率', max: 5 },
          { name: '临床关联', max: 5 },
          { name: '可溯源', max: 5 },
          { name: '格式易用', max: 5 },
          { name: '个性化/交互', max: 5 }
        ],
        axisName: { color: ink, fontSize: 11 },
        splitLine: { lineStyle: { color: rule } },
        splitArea: { areaStyle: { color: ['#FFFFFF', '#F7FAF9'] } },
        axisLine: { lineStyle: { color: rule } }
      },
      series: [{
        type: 'radar',
        data: [
          {
            name: '当前（专家评分 3.63/5）',
            value: [4.0, 3.8, 4.3, 4.2, 3.4, 3.0, 3.2, 4.0, 3.8, 1.7],
            lineStyle: { color: accent, width: 2 },
            itemStyle: { color: accent },
            areaStyle: { color: accent, opacity: 0.18 }
          },
          {
            name: '目标（4.6/5）',
            value: [4.6, 4.6, 4.6, 4.6, 4.6, 4.6, 4.6, 4.6, 4.6, 4.0],
            lineStyle: { color: accent2, width: 1.5, type: 'dashed' },
            itemStyle: { color: accent2 },
            areaStyle: { color: accent2, opacity: 0.05 }
          }
        ]
      }]
    });
    resizeOn(radar);
  }

  /* ---------- 图 5：教师版卡片数与蓝图权重偏差 ---------- */
  var blueprint = init('chart-blueprint');
  if (blueprint) {
    var mods = ['M01', 'M02', 'M03', 'M04', 'M05', 'M06', 'M07'];
    var devs = [17.6, -11.8, 2.9, -15.0, 26.1, -29.4, 56.9];
    blueprint.setOption({
      animation: false,
      tooltip: {
        trigger: 'axis',
        appendToBody: true,
        axisPointer: { type: 'shadow' },
        valueFormatter: function (v) { return v + '%'; }
      },
      grid: baseGrid({ top: 24, bottom: 26 }),
      xAxis: {
        type: 'category',
        data: mods,
        axisLabel: { color: ink, fontSize: 12 },
        axisLine: { lineStyle: { color: rule } },
        axisTick: { show: false }
      },
      yAxis: {
        type: 'value',
        min: -40,
        max: 70,
        axisLabel: { color: muted, fontSize: 11, formatter: '{value}%' },
        splitLine: { lineStyle: { color: rule } },
        axisLine: { show: false }
      },
      series: [{
        type: 'bar',
        barWidth: '52%',
        data: devs.map(function (v) {
          return {
            value: v,
            itemStyle: {
              color: Math.abs(v) > 20 ? risk : accent,
              borderRadius: v >= 0 ? [4, 4, 0, 0] : [0, 0, 4, 4]
            }
          };
        }),
        label: {
          show: true,
          position: 'top',
          color: ink,
          fontSize: 11,
          formatter: function (p) { return (p.value > 0 ? '+' : '') + p.value + '%'; }
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: accent2, type: 'dashed', width: 1.2 },
          label: { show: false },
          data: [{ yAxis: 20 }, { yAxis: -20 }]
        }
      }]
    });
    resizeOn(blueprint);
  }

  /* ---------- 图 6：优先级矩阵 ---------- */
  var priority = init('chart-priority');
  if (priority) {
    var items = [
      { id: 'D1', name: '知识组件映射', short: '知识组件', x: 6, y: 5, e: 0.8, pos: 'top' },
      { id: 'D2', name: '掌握度诊断', short: '掌握度', x: 7.3, y: 4.05, e: 0.8, pos: 'top' },
      { id: 'D3', name: '间隔重复', short: '间隔重复', x: 4, y: 5, e: 1.0, pos: 'top' },
      { id: 'D4', name: '错误认知反馈', short: '错误反馈', x: 7.9, y: 4.05, e: 0.8, pos: 'bottom' },
      { id: 'D5', name: '疾病脚本', short: '疾病脚本', x: 8.5, y: 4.05, e: 0.8, pos: 'top' },
      { id: 'D6', name: '断言级溯源', short: '断言溯源', x: 9.1, y: 4.05, e: 0.8, pos: 'right' },
      { id: 'D7', name: '文档级学习价值门禁', short: '文档门禁', x: 5, y: 4.05, e: 0.8, pos: 'bottom' },
      { id: 'D8', name: '交互式界面', short: '交互界面', x: 2.5, y: 4.05, e: 0.8, pos: 'left' },
      { id: 'D9', name: '多模态可视化', short: '多模态', x: 12, y: 3, e: 0.6, pos: 'left' },
      { id: 'D10', name: '蓝图配平', short: '蓝图配平', x: 3.5, y: 4.05, e: 0.8, pos: 'top' }
    ];
    priority.setOption({
      animation: false,
      tooltip: {
        trigger: 'item',
        appendToBody: true,
        formatter: function (p) {
          var d = p.data;
          return '<b>' + d.id + ' · ' + d.name + '</b><br/>综合工作量：' + d.x + '/12<br/>预期收益：' + d.y + '/5<br/>证据强度：' + d.e;
        }
      },
      grid: baseGrid({ left: 30, right: 40, top: 24, bottom: 30 }),
      xAxis: {
        type: 'value',
        min: 0,
        max: 13,
        name: '综合工作量（技术难度 + 成本 + 风险）',
        nameLocation: 'middle',
        nameGap: 28,
        nameTextStyle: { color: muted, fontSize: 11 },
        axisLabel: { color: muted, fontSize: 10 },
        splitLine: { lineStyle: { color: rule } },
        axisLine: { show: false }
      },
      yAxis: {
        type: 'value',
        min: 2,
        max: 6,
        name: '收益',
        nameLocation: 'middle',
        nameGap: 20,
        nameTextStyle: { color: muted, fontSize: 11 },
        axisLabel: { color: muted, fontSize: 10 },
        splitLine: { lineStyle: { color: rule } },
        axisLine: { show: false }
      },
      series: [{
        type: 'scatter',
        data: items.map(function (d) {
          return {
            value: [d.x, d.y],
            id: d.id,
            name: d.name,
            e: d.e,
            symbolSize: 16 + d.e * 16,
            itemStyle: {
              color: d.e >= 1 ? accent : (d.x <= 6 ? accent2 : muted),
              opacity: 0.85,
              borderColor: bg2,
              borderWidth: 2
            },
            label: {
              show: true,
              position: d.pos,
              color: ink,
              fontSize: 11,
              formatter: d.id
            }
          };
        }),
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: rule, type: 'dashed', width: 1.4 },
          label: { color: muted, fontSize: 10 },
          data: [{ xAxis: 6, label: { formatter: '工作量中位' } }, { yAxis: 4, label: { show: false } }]
        },
        markArea: {
          silent: true,
          itemStyle: { color: 'rgba(11,110,95,.04)' },
          label: { color: accent, fontSize: 10, position: 'insideTopLeft' },
          data: [[{ name: '优先做：高收益 / 低工作量', xAxis: 0, yAxis: 4 }, { xAxis: 6, yAxis: 6 }]]
        }
      }]
    });
    resizeOn(priority);
  }
})();
