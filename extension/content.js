console.log("=== PhishGuard content.js INITIALIZED ===", window.location.href);

const currentUrl = window.location.href;

chrome.runtime.sendMessage(
  {
    action: "check_url",
    url: currentUrl
  },
  (response) => {
    console.log("PhishGuard content.js GOT RESPONSE:", response);

    if (!response || !response.success) {
      console.error(
        "PhishGuard failed:",
        response && response.error ? response.error : "Unknown error"
      );
      return;
    }


    const data = response.data;
    console.log("PhishGuard result:", data);

    if (data.label === "phishing") {
      chrome.runtime.sendMessage({
        action: "open_warning_popup",
        url: currentUrl,
        probability: data.probability
      });
    }
  }
);
