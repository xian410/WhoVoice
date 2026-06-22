"""FAISS 可视化 HTML 模板"""
FEDER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <meta name="theme-color" content="#1a1a2e"/>
  <title>WhoVoice FAISS 索引可视化 - Feder</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: #1a1a2e;
      color: #e0e0e0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      overflow-x: hidden;
    }
    .header {
      padding: 16px 24px;
      background: linear-gradient(135deg, #16213e, #0f3460);
      border-bottom: 1px solid #533483;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 10px;
    }
    .header h1 {
      font-size: 20px;
      font-weight: 600;
      background: linear-gradient(90deg, #e94560, #533483);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .header .stats {
      font-size: 13px;
      color: #a0a0b0;
    }
    .header .stats span {
      color: #e94560;
      font-weight: 600;
    }
    .controls {
      padding: 12px 24px;
      background: #16213e;
      border-bottom: 1px solid #2a2a4a;
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .controls label {
      font-size: 13px;
      color: #a0a0b0;
    }
    .controls input, .controls select {
      padding: 6px 12px;
      background: #0f3460;
      border: 1px solid #533483;
      color: #e0e0e0;
      border-radius: 4px;
      font-size: 13px;
      outline: none;
    }
    .controls input:focus, .controls select:focus {
      border-color: #e94560;
    }
    .controls button {
      padding: 6px 16px;
      background: #e94560;
      color: #fff;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 500;
      transition: background 0.2s;
    }
    .controls button:hover {
      background: #d63851;
    }
    .controls button.secondary {
      background: #533483;
    }
    .controls button.secondary:hover {
      background: #6b42a0;
    }
    .controls .hint {
      font-size: 12px;
      color: #666;
      margin-left: auto;
    }
    #feder-container {
      width: 100%;
      min-height: calc(100vh - 120px);
      position: relative;
    }
    .loading {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 60vh;
      font-size: 18px;
      color: #a0a0b0;
      flex-direction: column;
      gap: 20px;
    }
    .loading .spinner {
      width: 48px;
      height: 48px;
      border: 3px solid #2a2a4a;
      border-top: 3px solid #e94560;
      border-radius: 50%;
      animation: spin 1s linear infinite;
    }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    .error-box {
      display: none;
      align-items: center;
      justify-content: center;
      height: 60vh;
      font-size: 16px;
      color: #ff6b6b;
      flex-direction: column;
      gap: 16px;
      padding: 40px;
      text-align: center;
    }
    .error-box.show {
      display: flex;
    }
    .error-box .err-icon {
      font-size: 48px;
    }
    .error-box .err-detail {
      font-size: 13px;
      color: #a0a0b0;
      max-width: 600px;
      word-break: break-all;
      background: rgba(0,0,0,0.3);
      padding: 12px 16px;
      border-radius: 8px;
      font-family: monospace;
    }
    .error-box button {
      padding: 8px 24px;
      background: #e94560;
      color: #fff;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 14px;
    }
    .back-link {
      position: fixed;
      top: 16px;
      right: 24px;
      color: #a0a0b0;
      text-decoration: none;
      font-size: 13px;
      z-index: 100;
      padding: 6px 12px;
      background: rgba(15,52,96,0.8);
      border-radius: 4px;
      border: 1px solid #533483;
    }
    .back-link:hover {
      color: #e94560;
    }
    .hidden { display: none !important; }
  </style>
</head>
<body>
  <a href="/" class="back-link">&larr; 返回首页</a>

  <div class="header">
    <h1>FAISS 声纹索引可视化</h1>
    <div class="stats">
      <span>__TOTAL__</span> 位明星 &middot;
      向量维度 <span>192</span> &middot;
      索引类型 <span>IVF_FLAT</span> &middot;
      <span>__TOTAL__</span> 个向量
    </div>
  </div>

  <div class="controls" id="controls" style="opacity:0.5;pointer-events:none">
    <label>Top-K:</label>
    <select id="topK">
      <option value="3">3</option>
      <option value="5" selected>5</option>
      <option value="10">10</option>
      <option value="20">20</option>
    </select>

    <label>搜索 ID:</label>
    <input type="number" id="targetId" value="0" min="0" max="__MAX_ID__" style="width:80px" />

    <button id="searchBtn" disabled style="opacity:0.5">&#128269; 搜索</button>
    <button id="overviewBtn" disabled style="opacity:0.5">&#128202; 概览</button>
    <button id="randomBtn" disabled style="opacity:0.5">&#127922; 随机搜索</button>

    <span class="hint" id="statusText">正在初始化...</span>
  </div>

  <div id="feder-container">
    <div class="loading" id="loading">
      <div class="spinner"></div>
      <div id="loadingText">正在加载 Feder.js...</div>
    </div>
  </div>

  <div class="error-box" id="errorBox">
    <div class="err-icon">&#9888;&#65039;</div>
    <div id="errorTitle">加载失败</div>
    <div class="err-detail" id="errorDetail"></div>
    <button onclick="location.reload()">重试</button>
  </div>

  <script type="module">
    import { Feder } from "https://unpkg.com/@zilliz/feder@1.0.7/dist/index.js";
    window.Feder = Feder;

    (async function() {
      var $ = function(id) { return document.getElementById(id); };
      var loading = $("loading");
      var loadingText = $("loadingText");
      var errorBox = $("errorBox");
      var errorDetail = $("errorDetail");
      var controls = $("controls");
      var statusText = $("statusText");
      var searchBtn = $("searchBtn");
      var overviewBtn = $("overviewBtn");
      var randomBtn = $("randomBtn");

      function showError(msg, detail) {
        loading.classList.add("hidden");
        errorBox.classList.add("show");
        errorDetail.textContent = detail || msg;
      }

      function setStatus(text) {
        statusText.textContent = text;
      }

      function enableControls() {
        [searchBtn, overviewBtn, randomBtn].forEach(function(b) {
          b.disabled = false;
          b.style.opacity = "1";
        });
        controls.style.opacity = "1";
        controls.style.pointerEvents = "auto";
        setStatus("就绪");
      }

      try {
        if (!window.Feder) {
          showError("Feder.js 未能正确加载", "请检查网络连接");
          return;
        }

        loadingText.textContent = "正在加载 FAISS 索引文件 (__TOTAL__ 位明星)...";
        setStatus("正在加载索引...");

        var mediaUrls = __NAMES_JSON__;
        var mediaCallback = function(rowId) { return mediaUrls[rowId] || null; };

        var feder = new window.Feder({
          filePath: "__INDEX_URL__",
          source: "faiss",
          domSelector: "#feder-container",
          viewParams: {
            width: window.innerWidth - 40,
            height: Math.max(window.innerHeight - 160, 500),
            mediaType: "text",
            mediaCallback: mediaCallback,
            fineSearchWithProjection: 0,
          },
        });

        await feder.initFederPromise;

        loadingText.textContent = "正在渲染可视化...";
        setStatus("正在渲染...");

        feder.overview();

        setTimeout(function() {
          loading.classList.add("hidden");
          enableControls();
        }, 1500);

        setTimeout(function() {
          if (!loading.classList.contains("hidden")) {
            loading.classList.add("hidden");
            enableControls();
          }
        }, 20000);

        searchBtn.addEventListener("click", function() {
          var k = parseInt($("topK").value);
          var targetId = parseInt($("targetId").value);
          setStatus("搜索 ID=" + targetId);
          feder.setSearchParams({ k: k });
          feder.searchById(targetId);
        });

        overviewBtn.addEventListener("click", function() {
          setStatus("概览");
          feder.overview();
        });

        randomBtn.addEventListener("click", function() {
          var randomId = Math.floor(Math.random() * __TOTAL__);
          $("targetId").value = randomId;
          var k = parseInt($("topK").value);
          setStatus("随机 ID=" + randomId);
          feder.setSearchParams({ k: k });
          feder.searchById(randomId);
        });

      } catch (err) {
        showError(
          "加载可视化失败",
          err.message + "\\n" + (err.stack || "")
        );
      }
    })();
  </script>
</body>
</html>"""
