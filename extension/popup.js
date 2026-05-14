const apiUrl = "http://localhost:5000/predict";

document.getElementById("checkBtn").addEventListener("click", () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const currentUrl = tabs[0].url;
    checkUrl(currentUrl);
  });
});

async function checkUrl(url) {
  const resultBox = document.getElementById("resultBox");
  const resultText = document.getElementById("result");
  const statusText = document.getElementById("statusText");

  resultBox.classList.remove("hidden");
  resultBox.classList.remove("safe", "phishing");

  resultText.textContent = "Checking…";
  resultText.style.color = "black";
  statusText.textContent = "Analyzing URL";

  try {
    const response = await fetch(apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });

    if (!response.ok) {
      resultText.textContent = "API error: " + response.status;
      return;
    }

    const data = await response.json();
    const prob = (data.probability * 100).toFixed(2);

    if (data.label === "phishing") {
      resultBox.classList.add("phishing");
      statusText.textContent = "⚠️ PHISHING DETECTED";
      resultText.textContent = `Risk Score: ${prob}%`;
    } else {
      resultBox.classList.add("safe");
      statusText.textContent = "✔ SAFE WEBSITE";
      resultText.textContent = `Confidence: ${prob}%`;
    }

  } catch (err) {
    resultBox.classList.add("phishing");
    statusText.textContent = "Error";
    resultText.textContent = "Could not contact the API.";
  }
}
