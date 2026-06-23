const photo = document.getElementById("photo");
const preview = document.getElementById("preview");
const btn = document.getElementById("analyze");
const loading = document.getElementById("loading");
const result = document.getElementById("result");

let selectedFile = null;

photo.addEventListener("change", () => {
  selectedFile = photo.files[0];
  if (selectedFile) {
    preview.src = URL.createObjectURL(selectedFile);
    preview.style.display = "block";
  }
});

function setText(id, value) {
  document.getElementById(id).textContent = value ?? "-";
}

btn.addEventListener("click", async () => {
  if (!selectedFile) {
    alert("Спочатку зроби фото графіка");
    return;
  }

  loading.classList.remove("hidden");
  result.classList.add("hidden");
  btn.disabled = true;
  btn.textContent = "⏳ Аналізую...";

  const form = new FormData();
  form.append("file", selectedFile);
  form.append("asset", document.getElementById("asset").value || "");

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      body: form
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Помилка сервера");
    }

    setText("assetOut", data.asset || "");
    setText("signal", data.signal || "Нейтрально");
    setText("trend", data.trend || "-");
    setText("up", (data.probability_up ?? "-") + "%");
    setText("down", (data.probability_down ?? "-") + "%");
    setText("confidence", data.confidence || "-");
    setText("support", data.support || "-");
    setText("resistance", data.resistance || "-");
    setText("state", data.market_state || "-");
    setText("entry", data.entry_zone || "-");
    setText("reasoning", data.reasoning || "");
    setText("risk", data.risk_note || "");

    result.classList.remove("hidden");
  } catch (e) {
    alert("Помилка аналізу: " + e.message);
  } finally {
    loading.classList.add("hidden");
    btn.disabled = false;
    btn.textContent = "🤖 Аналізувати";
  }
});
