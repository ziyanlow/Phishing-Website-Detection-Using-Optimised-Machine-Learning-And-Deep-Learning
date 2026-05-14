chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "check_url") {
    fetch("http://localhost:5000/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: message.url })
    })
      .then(response => response.json())
      .then(data => sendResponse({ success: true, data }))
      .catch(error => sendResponse({ success: false, error: error.toString() }));

    // IMPORTANT: allow async response
    return true;
  }
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "open_warning_popup") {

    chrome.windows.create({
      url: `warning.html?url=${encodeURIComponent(msg.url)}&p=${msg.probability}`,
      type: "popup",
      width: 550,
      height: 450
    });
  }
});


