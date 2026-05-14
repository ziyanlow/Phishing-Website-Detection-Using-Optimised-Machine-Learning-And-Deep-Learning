const params = new URLSearchParams(window.location.search);

document.getElementById("prob").innerText =
  "Probability: " + (params.get("p") * 100).toFixed(2) + "%";

document.getElementById("closeBtn").onclick = () => {
  window.close(); 
};
