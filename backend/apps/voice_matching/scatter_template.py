"""FAISS 声纹散点图可视化模板"""
SCATTER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>WhoVoice 声纹向量散点图</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: #1a1a2e;
      color: #e0e0e0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      overflow: hidden;
      height: 100vh;
    }
    .header {
      padding: 10px 20px;
      background: linear-gradient(135deg, #16213e, #0f3460);
      border-bottom: 1px solid #533483;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
      height: 52px;
    }
    .header h1 {
      font-size: 16px;
      font-weight: 600;
      background: linear-gradient(90deg, #e94560, #533483);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .header .stats {
      font-size: 12px;
      color: #a0a0b0;
    }
    .header .stats span { color: #e94560; font-weight: 600; }
    .toolbar {
      padding: 8px 20px;
      background: #16213e;
      border-bottom: 1px solid #2a2a4a;
      display: flex;
      align-items: center;
      gap: 12px;
      height: 44px;
      font-size: 13px;
    }
    .toolbar label { color: #a0a0b0; font-size: 12px; }
    .toolbar input {
      padding: 4px 10px;
      background: #0f3460;
      border: 1px solid #533483;
      color: #e0e0e0;
      border-radius: 4px;
      font-size: 12px;
      outline: none;
      width: 150px;
    }
    .toolbar input:focus { border-color: #e94560; }
    .toolbar button {
      padding: 4px 14px;
      background: #e94560;
      color: #fff;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
    }
    .toolbar button:hover { background: #d63851; }
    .toolbar button.sec {
      background: #533483;
    }
    .toolbar button.sec:hover { background: #6b42a0; }
    .toolbar .hint { color: #666; font-size: 11px; margin-left: auto; }
    #canvas-wrap {
      position: relative;
      width: 100vw;
      height: calc(100vh - 96px);
      overflow: hidden;
      cursor: grab;
    }
    #canvas-wrap:active { cursor: grabbing; }
    #scatter-canvas {
      display: block;
      width: 100%;
      height: 100%;
    }
    #tooltip {
      position: absolute;
      display: none;
      background: rgba(15, 52, 96, 0.92);
      border: 1px solid #533483;
      border-radius: 6px;
      padding: 6px 12px;
      font-size: 13px;
      color: #fff;
      pointer-events: none;
      z-index: 100;
      white-space: nowrap;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    #search-highlight {
      position: absolute;
      pointer-events: none;
      z-index: 50;
    }
    .back-link {
      position: fixed;
      top: 8px;
      right: 20px;
      color: #a0a0b0;
      text-decoration: none;
      font-size: 12px;
      z-index: 100;
      padding: 4px 10px;
      background: rgba(15,52,96,0.8);
      border-radius: 4px;
      border: 1px solid #533483;
    }
    .back-link:hover { color: #e94560; }
    .legend {
      position: fixed;
      bottom: 20px;
      right: 20px;
      z-index: 50;
      font-size: 11px;
      color: #a0a0b0;
      background: rgba(15,52,96,0.92);
      padding: 10px 14px;
      border-radius: 8px;
      border: 1px solid #2a2a4a;
      max-height: 260px;
      overflow-y: auto;
      min-width: 120px;
    }
    .legend-title {
      font-size: 11px;
      color: #e94560;
      font-weight: 600;
      margin-bottom: 6px;
      padding-bottom: 4px;
      border-bottom: 1px solid #2a2a4a;
    }
    .legend-item {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 2px 0;
      cursor: pointer;
      transition: opacity 0.2s;
    }
    .legend-item:hover { opacity: 0.8; }
    .legend-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      flex-shrink: 0;
      border: 1px solid rgba(255,255,255,0.15);
    }
    .legend-count {
      margin-left: auto;
      color: #666;
      font-size: 10px;
    }
    @media (max-width: 768px) {
      .header h1 { font-size: 14px; }
      .toolbar { flex-wrap: wrap; height: auto; padding: 8px; }
      .toolbar input { width: 100px; }
      .legend { display: none; }
    }
  </style>
</head>
<body>
  <a href="/" class="back-link">&larr; 返回首页</a>

  <div class="header">
    <h1>WhoVoice 声纹向量分布图</h1>
    <div class="stats">
      <span id="totalCount">__TOTAL__</span> 位明星 &middot;
      向量维度 <span>192</span> &middot;
      降维方式 <span>PCA</span> &middot;
      <span id="shownCount">__TOTAL__</span> 个点可见
    </div>
  </div>

  <div class="toolbar">
    <label>&#128270; 搜索:</label>
    <input type="text" id="searchInput" placeholder="输入明星名字搜索..." />
    <button id="searchBtn">定位</button>
    <button id="resetViewBtn" class="sec">重置视图</button>
    <span class="hint" id="statusHint">滚轮缩放 · 拖拽平移 · 悬停查看名字</span>
  </div>

  <div id="canvas-wrap">
    <canvas id="scatter-canvas"></canvas>
    <div id="tooltip"></div>
  </div>

  <div class="legend" id="legend">
    <div class="legend-title">&#9679; 声纹聚类</div>
    <div id="legend-items"></div>
  </div>

  <script>
    (function() {
      // ---- 坐标数据 ----
      var points = __POINTS_JSON__;
      var total = points.length;

      // 聚类名称信息
      var clusterInfo = __CLUSTER_INFO__;

      // 聚类颜色调色板（高对比度，色相均匀分布）
      var clusterColors = [
        "#e94560", "#4cc9f0", "#f9c74f", "#90be6d",
        "#7209b7", "#f9844a", "#43aa8b", "#f72585",
        "#4361ee", "#fcbf49", "#06d6a0", "#ef476f",
        "#118ab2", "#ffd166", "#073b4c", "#e63946",
      ];

      // 统计每个聚类的点数量
      var clusterCounts = {};
      points.forEach(function(p) {
        var cid = p.c !== undefined ? p.c : 0;
        clusterCounts[cid] = (clusterCounts[cid] || 0) + 1;
        p.color = clusterColors[cid % clusterColors.length];
        p.cid = cid;
      });

      // 聚类 ID 排序（按数量降序排列）
      var sortedClusters = Object.keys(clusterCounts)
        .map(function(k) { return { id: parseInt(k), count: clusterCounts[k] }; })
        .sort(function(a, b) { return b.count - a.count; });

      // 渲染聚类图例
      var legendContainer = document.getElementById("legend-items");
      sortedClusters.forEach(function(cluster) {
        var item = document.createElement("div");
        item.className = "legend-item";
        var dot = document.createElement("span");
        dot.className = "legend-dot";
        dot.style.background = clusterColors[cluster.id % clusterColors.length];
        item.appendChild(dot);
        var label = document.createElement("span");
        var info = clusterInfo && clusterInfo[cluster.id];
        var displayName = info ? info.name : ("聚类 " + cluster.id);
        label.textContent = displayName;
        item.appendChild(label);
        var count = document.createElement("span");
        count.className = "legend-count";
        count.textContent = cluster.count;
        item.appendChild(count);
        legendContainer.appendChild(item);

        // 图例点击：搜索该聚类的代表明星
        item.addEventListener("click", function() {
          if (info && info.desc) {
            var match = info.desc.match(/代表: (.+?)(?: \\||$)/);
            if (match) {
              searchInput.value = match[1];
              doSearch();
            }
          }
        });
      });

      // ---- Canvas 设置 ----
      var canvas = document.getElementById("scatter-canvas");
      var ctx = canvas.getContext("2d");
      var wrap = document.getElementById("canvas-wrap");
      var tooltip = document.getElementById("tooltip");
      var searchInput = document.getElementById("searchInput");
      var statusHint = document.getElementById("statusHint");
      var shownCount = document.getElementById("shownCount");

      // ---- 视图状态 ----
      var view = {
        offsetX: 0, offsetY: 0,
        scale: 1.0,
        minScale: 0.1,
        maxScale: 20,
      };
      var dragStart = null;
      var hoveredIdx = -1;
      var searchIdx = -1;

      // ---- 计算边界 ----
      var minX = Infinity, maxX = -Infinity;
      var minY = Infinity, maxY = -Infinity;
      points.forEach(function(p) {
        if (p.x < minX) minX = p.x;
        if (p.x > maxX) maxX = p.x;
        if (p.y < minY) minY = p.y;
        if (p.y > maxY) maxY = p.y;
      });
      var rangeX = maxX - minX || 1;
      var rangeY = maxY - minY || 1;

      // 初始视图：居中显示所有点
      function resetView() {
        var w = canvas.width, h = canvas.height;
        var scaleX = w / rangeX * 0.85;
        var scaleY = h / rangeY * 0.85;
        view.scale = Math.min(scaleX, scaleY);
        view.offsetX = (w - (minX + maxX) * view.scale) / 2;
        view.offsetY = (h - (minY + maxY) * view.scale) / 2;
        searchIdx = -1;
      }

      // ---- 坐标转换 ----
      function dataToScreen(x, y) {
        return {
          sx: x * view.scale + view.offsetX,
          sy: y * view.scale + view.offsetY
        };
      }

      function screenToData(sx, sy) {
        return {
          x: (sx - view.offsetX) / view.scale,
          y: (sy - view.offsetY) / view.scale
        };
      }

      // ---- 绘制 ----
      var animId = null;
      function render() {
        var w = canvas.width, h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        // 背景
        var grad = ctx.createRadialGradient(w/2, h/2, 0, w/2, h/2, Math.max(w,h)/1.5);
        grad.addColorStop(0, "#16213e");
        grad.addColorStop(1, "#0a0a1a");
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, w, h);

        // 绘制数据点
        var radius = Math.max(3, Math.min(8, 6 * view.scale / 3));
        var visibleCount = 0;

        for (var i = 0; i < points.length; i++) {
          var p = points[i];
          var s = dataToScreen(p.x, p.y);

          // 视口裁剪
          if (s.sx < -20 || s.sx > w + 20 || s.sy < -20 || s.sy > h + 20) continue;
          visibleCount++;

          var isHover = (i === hoveredIdx);
          var isSearch = (i === searchIdx);

          if (isSearch) {
            ctx.beginPath();
            ctx.arc(s.sx, s.sy, radius + 6, 0, Math.PI * 2);
            ctx.fillStyle = "rgba(233, 69, 96, 0.35)";
            ctx.fill();
            ctx.strokeStyle = "#e94560";
            ctx.lineWidth = 2;
            ctx.stroke();
          }

          ctx.beginPath();
          ctx.arc(s.sx, s.sy, isHover || isSearch ? radius + 2 : radius, 0, Math.PI * 2);
          ctx.fillStyle = isSearch ? "#ffffff" : p.color;
          ctx.fill();

          if (isHover || isSearch) {
            ctx.strokeStyle = isSearch ? "#e94560" : "#ffffff";
            ctx.lineWidth = isSearch ? 2 : 1.5;
            ctx.stroke();
          }
        }

        shownCount.textContent = visibleCount;
      }

      // ---- 调整大小 ----
      function resize() {
        var rect = wrap.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = rect.height;
        if (view.scale === 1 && view.offsetX === 0 && view.offsetY === 0) {
          resetView();
        }
        render();
      }

      // ---- 鼠标事件 ----
      function getPos(e) {
        var rect = canvas.getBoundingClientRect();
        var clientX = e.clientX || (e.touches && e.touches[0].clientX) || 0;
        var clientY = e.clientY || (e.touches && e.touches[0].clientY) || 0;
        return { x: clientX - rect.left, y: clientY - rect.top };
      }

      function findNearest(cx, cy, maxDist) {
        maxDist = maxDist || 15;
        var bestIdx = -1, bestDist = maxDist * maxDist;
        for (var i = 0; i < points.length; i++) {
          var s = dataToScreen(points[i].x, points[i].y);
          var dx = cx - s.sx, dy = cy - s.sy;
          var d2 = dx * dx + dy * dy;
          if (d2 < bestDist) {
            bestDist = d2;
            bestIdx = i;
          }
        }
        return bestIdx;
      }

      function showTooltip(idx, cx, cy) {
        if (idx >= 0 && idx < points.length) {
          tooltip.style.display = "block";
          tooltip.style.left = (cx + 14) + "px";
          tooltip.style.top = (cy - 10) + "px";
          tooltip.textContent = "#" + idx + " " + points[idx].name;
          hoveredIdx = idx;
        } else {
          tooltip.style.display = "none";
          hoveredIdx = -1;
        }
        render();
      }

      canvas.addEventListener("mousemove", function(e) {
        var pos = getPos(e);
        var idx = findNearest(pos.x, pos.y);
        showTooltip(idx, pos.x, pos.y);
      });

      canvas.addEventListener("mouseleave", function() {
        tooltip.style.display = "none";
        hoveredIdx = -1;
        render();
      });

      // 拖拽
      canvas.addEventListener("mousedown", function(e) {
        dragStart = { x: e.clientX, y: e.clientY, ox: view.offsetX, oy: view.offsetY };
      });

      window.addEventListener("mousemove", function(e) {
        if (!dragStart) return;
        var dx = e.clientX - dragStart.x;
        var dy = e.clientY - dragStart.y;
        view.offsetX = dragStart.ox + dx;
        view.offsetY = dragStart.oy + dy;
        render();
      });

      window.addEventListener("mouseup", function() {
        dragStart = null;
      });

      // 滚轮缩放
      canvas.addEventListener("wheel", function(e) {
        e.preventDefault();
        var pos = getPos(e);
        var data = screenToData(pos.x, pos.y);
        var factor = e.deltaY > 0 ? 0.9 : 1.1;
        view.scale = Math.min(view.maxScale, Math.max(view.minScale, view.scale * factor));
        view.offsetX = pos.x - data.x * view.scale;
        view.offsetY = pos.y - data.y * view.scale;
        render();
      }, { passive: false });

      // 触摸支持
      var touchStartDist = 0;
      canvas.addEventListener("touchstart", function(e) {
        if (e.touches.length === 1) {
          dragStart = { x: e.touches[0].clientX, y: e.touches[0].clientY, ox: view.offsetX, oy: view.offsetY };
        } else if (e.touches.length === 2) {
          touchStartDist = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY
          );
        }
      }, { passive: true });

      canvas.addEventListener("touchmove", function(e) {
        e.preventDefault();
        if (e.touches.length === 1 && dragStart) {
          view.offsetX = dragStart.ox + (e.touches[0].clientX - dragStart.x);
          view.offsetY = dragStart.oy + (e.touches[0].clientY - dragStart.y);
          render();
        } else if (e.touches.length === 2 && touchStartDist > 0) {
          var dist = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY
          );
          var pos = getPos(e);
          var data = screenToData(pos.x, pos.y);
          view.scale = Math.min(view.maxScale, Math.max(view.minScale, view.scale * dist / touchStartDist));
          view.offsetX = pos.x - data.x * view.scale;
          view.offsetY = pos.y - data.y * view.scale;
          touchStartDist = dist;
          render();
        }
      }, { passive: false });

      canvas.addEventListener("touchend", function() {
        dragStart = null;
        touchStartDist = 0;
      }, { passive: true });

      // ---- 搜索 ----
      function doSearch() {
        var q = searchInput.value.trim().toLowerCase();
        if (!q) { searchIdx = -1; render(); return; }
        var found = -1;
        for (var i = 0; i < points.length; i++) {
          if (points[i].name.toLowerCase().includes(q)) {
            found = i;
            break;
          }
        }
        if (found >= 0) {
          searchIdx = found;
          var s = dataToScreen(points[found].x, points[found].y);
          // 中心对准
          view.offsetX = canvas.width / 2 - points[found].x * view.scale;
          view.offsetY = canvas.height / 2 - points[found].y * view.scale;
          statusHint.textContent = "已定位: " + points[found].name;
          render();
        } else {
          statusHint.textContent = "未找到: " + q;
          searchIdx = -1;
          render();
        }
      }

      document.getElementById("searchBtn").addEventListener("click", doSearch);
      searchInput.addEventListener("keydown", function(e) {
        if (e.key === "Enter") doSearch();
      });

      document.getElementById("resetViewBtn").addEventListener("click", function() {
        resetView();
        searchIdx = -1;
        searchInput.value = "";
        statusHint.textContent = "滚轮缩放 · 拖拽平移 · 悬停查看名字";
        render();
      });

      // ---- 窗口变化 ----
      window.addEventListener("resize", resize);

      // ---- 初始化 ----
      resize();
    })();
  </script>
</body>
</html>"""
