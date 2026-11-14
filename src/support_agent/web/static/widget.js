/*
 * ai-support-agent chat widget.
 *
 * Embed on any page:
 *   <script src="https://your-agent-host/widget.js" defer
 *           data-title="Help" data-color="#2f6b4f"></script>
 *
 * All text is rendered with textContent, never innerHTML, so messages
 * can't inject markup into the host page.
 */
(function () {
  "use strict";

  var script = document.currentScript;
  var apiBase = new URL(script.src, window.location.href).origin;
  var title = script.getAttribute("data-title") || "Customer support";
  var color = script.getAttribute("data-color") || "#2f6b4f";
  var greeting =
    script.getAttribute("data-greeting") ||
    "Hi! I can check your order status or answer questions about shipping, returns and products.";
  var storageKey = "ai-support-agent:conversation";

  var css =
    ".asa-launch{position:fixed;right:20px;bottom:20px;width:56px;height:56px;border-radius:50%;border:0;" +
    "background:" + color + ";color:#fff;font-size:24px;cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,.2);z-index:2147483000}" +
    ".asa-panel{position:fixed;right:20px;bottom:88px;width:min(380px,calc(100vw - 40px));height:min(560px,calc(100vh - 120px));" +
    "background:#fff;border-radius:14px;box-shadow:0 12px 40px rgba(0,0,0,.22);display:none;flex-direction:column;overflow:hidden;" +
    "font:14px/1.45 system-ui,-apple-system,'Segoe UI',sans-serif;color:#1d2a23;z-index:2147483000}" +
    ".asa-panel.asa-open{display:flex}" +
    ".asa-head{background:" + color + ";color:#fff;padding:14px 16px;font-weight:600;display:flex;justify-content:space-between;align-items:center}" +
    ".asa-head button{background:none;border:0;color:#fff;font-size:20px;cursor:pointer;line-height:1}" +
    ".asa-log{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:8px;background:#f6f8f6}" +
    ".asa-msg{max-width:85%;padding:9px 12px;border-radius:12px;white-space:pre-wrap;word-wrap:break-word}" +
    ".asa-user{align-self:flex-end;background:" + color + ";color:#fff;border-bottom-right-radius:4px}" +
    ".asa-bot{align-self:flex-start;background:#fff;border:1px solid #dfe5e1;border-bottom-left-radius:4px}" +
    ".asa-sources{margin-top:6px;font-size:12px;color:#5d6b63}" +
    ".asa-note{align-self:center;font-size:12px;color:#a1561c;background:#f6e9de;padding:4px 10px;border-radius:999px}" +
    ".asa-typing{align-self:flex-start;color:#5d6b63;font-size:13px;font-style:italic}" +
    ".asa-form{display:flex;gap:8px;padding:10px;border-top:1px solid #dfe5e1;background:#fff}" +
    ".asa-form textarea{flex:1;resize:none;border:1px solid #dfe5e1;border-radius:8px;padding:8px 10px;font:inherit;height:40px}" +
    ".asa-form button{border:0;border-radius:8px;background:" + color + ";color:#fff;padding:0 14px;font:inherit;cursor:pointer}" +
    ".asa-form button:disabled{opacity:.5;cursor:default}";

  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  var launch = el("button", "asa-launch", "\u{1F4AC}");
  launch.setAttribute("aria-label", "Open " + title);
  var panel = el("div", "asa-panel");
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", title);

  var head = el("div", "asa-head");
  head.appendChild(el("span", "", title));
  var close = el("button", "", "×");
  close.setAttribute("aria-label", "Close");
  head.appendChild(close);

  var log = el("div", "asa-log");
  log.setAttribute("aria-live", "polite");

  var form = el("form", "asa-form");
  var input = el("textarea");
  input.placeholder = "Type your message...";
  input.setAttribute("aria-label", "Message");
  input.maxLength = 2000;
  var send = el("button", "", "Send");
  send.type = "submit";
  form.appendChild(input);
  form.appendChild(send);

  panel.appendChild(head);
  panel.appendChild(log);
  panel.appendChild(form);
  document.body.appendChild(panel);
  document.body.appendChild(launch);

  function scrollDown() {
    log.scrollTop = log.scrollHeight;
  }

  function addMessage(role, text, sources) {
    var bubble = el("div", "asa-msg " + (role === "user" ? "asa-user" : "asa-bot"), text);
    if (sources && sources.length) {
      var titles = [];
      sources.forEach(function (s) {
        var name = s.title.split(" > ").pop();
        if (titles.indexOf(name) === -1) titles.push(name);
      });
      bubble.appendChild(el("div", "asa-sources", "Sources: " + titles.slice(0, 3).join(" · ")));
    }
    log.appendChild(bubble);
    scrollDown();
  }

  function addNote(text) {
    log.appendChild(el("div", "asa-note", text));
    scrollDown();
  }

  function getConversation() {
    try {
      return window.sessionStorage.getItem(storageKey);
    } catch (e) {
      return null;
    }
  }

  function setConversation(id) {
    try {
      if (id) window.sessionStorage.setItem(storageKey, id);
      else window.sessionStorage.removeItem(storageKey);
    } catch (e) {
      /* storage blocked: the conversation lasts for this page only */
    }
  }

  var greeted = false;
  var handedOff = false;
  function open() {
    panel.classList.add("asa-open");
    if (!greeted) {
      addMessage("bot", greeting);
      greeted = true;
    }
    input.focus();
  }

  launch.addEventListener("click", function () {
    if (panel.classList.contains("asa-open")) panel.classList.remove("asa-open");
    else open();
  });
  close.addEventListener("click", function () {
    panel.classList.remove("asa-open");
  });

  input.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var text = input.value.trim();
    if (!text || send.disabled) return;

    addMessage("user", text);
    input.value = "";
    send.disabled = true;
    var typing = el("div", "asa-typing", "Assistant is typing...");
    log.appendChild(typing);
    scrollDown();

    fetch(apiBase + "/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, conversation_id: getConversation() }),
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, status: response.status, data: data };
        });
      })
      .then(function (result) {
        typing.remove();
        if (result.status === 404) {
          setConversation(null);
          addNote("Your previous chat expired. Please send your message again.");
          return;
        }
        if (!result.ok) {
          addNote(result.data.detail || "Something went wrong. Please try again.");
          return;
        }
        setConversation(result.data.conversation_id);
        addMessage("bot", result.data.reply, result.data.sources);
        if (result.data.handed_off && !handedOff) {
          handedOff = true;
          addNote("A person from our team will follow up on this conversation.");
        }
      })
      .catch(function () {
        typing.remove();
        addNote("Can't reach support right now. Please try again.");
      })
      .finally(function () {
        send.disabled = false;
        input.focus();
      });
  });
})();
