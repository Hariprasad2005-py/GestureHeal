function showIntakeError(message) {
  const box = document.getElementById("intake-error");
  if (!box) return;
  if (!message) {
    box.textContent = "";
    box.classList.add("hidden");
    return;
  }
  box.textContent = message;
  box.classList.remove("hidden");
  box.scrollIntoView({ behavior: "smooth", block: "start" });
}

function generatePatientId() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `P${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

function showIntakeView() {
  const landing = document.getElementById("landing-view");
  const intake = document.getElementById("intake-view");
  if (landing) landing.classList.add("hidden");
  if (intake) intake.classList.remove("hidden");
  window.scrollTo(0, 0);
}

function showLandingView() {
  const landing = document.getElementById("landing-view");
  const intake = document.getElementById("intake-view");
  if (intake) intake.classList.add("hidden");
  if (landing) landing.classList.remove("hidden");
  window.scrollTo(0, 0);
}

function wireLandingToIntake() {
  const buttons = document.querySelectorAll(".js-start-rehab");
  if (!buttons.length) return;
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => showIntakeView());
  });
}

function wireIntakeBack() {
  const back1 = document.getElementById("intake-back");
  const back2 = document.getElementById("intake-back-2");
  const backTop = document.getElementById("intake-back-top");
  [back1, back2, backTop].forEach((el) => {
    if (!el) return;
    el.addEventListener("click", (e) => {
      e.preventDefault();
      showLandingView();
    });
  });
}

function wireIntakePage() {
  const form = document.getElementById("intake-form");
  if (!form) return;

  const patientId = document.getElementById("patient_id");
  if (patientId && !patientId.value) patientId.value = generatePatientId();

  const startBtn = document.getElementById("start-session");
  const startLabel = startBtn ? startBtn.querySelector("[data-label]") : null;

  const prevTherapy = document.getElementById("prev_therapy");
  const prevWeeks = document.getElementById("prev_therapy_weeks");
  const syncPrevWeeks = () => {
    if (!prevTherapy || !prevWeeks) return;
    const yes = prevTherapy.value === "Yes";
    prevWeeks.disabled = !yes;
    prevWeeks.required = yes;
    if (!yes) prevWeeks.value = "";
  };
  if (prevTherapy && prevWeeks) {
    prevTherapy.addEventListener("change", syncPrevWeeks);
    syncPrevWeeks();
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    showIntakeError(null);

    syncPrevWeeks();
    if (!form.checkValidity()) {
      form.reportValidity();
      showIntakeError("Please fill all required fields correctly.");
      return;
    }

    const getRadio = (name) => {
      const el = document.querySelector(`input[name="${name}"]:checked`);
      return el ? el.value : "";
    };
    window.GestureHealRenderer = {
  startSession: function(data) {
    // data has: full_name, age, gender, patient_id,
    // condition, surgery_date, affected_side, doctor_name,
    // prev_therapy, therapist_notes, pain_before,
    // target_reps, session_goal, therapist_name
  }
};
    const intake = {
      full_name: form.full_name.value.trim(),
      age: Number(form.age.value),
      gender: form.gender.value.trim(),
      patient_id: form.patient_id.value.trim(),
      condition: form.condition.value.trim(),
      affected_side: getRadio("affected_side"),
      surgery_date: form.surgery_date.value,
      doctor_name: form.doctor_name.value.trim(),
      prev_therapy: form.prev_therapy.value.trim(),
      prev_therapy_weeks: form.prev_therapy.value === "Yes" ? Number(form.prev_therapy_weeks.value) : null,
      pain_before: Number(form.pain_before.value),
      session_goal: form.session_goal.value.trim(),
      therapist_name: form.therapist_name.value.trim(),
      target_reps: Number(form.target_reps.value),
      therapist_notes: form.therapist_notes.value.trim(),
    };

    if (!intake.affected_side) {
      showIntakeError("Please select the affected side.");
      return;
    }

    if (!window.rehab || !window.rehab.saveIntake || !window.rehab.start) {
      showIntakeError("App bridge not available. Please restart the Electron launcher.");
      return;
    }

    try {
      if (startBtn) startBtn.disabled = true;
      if (startLabel) startLabel.textContent = "Starting…";
      await window.rehab.saveIntake(intake);
      await window.rehab.start();
    } catch (err) {
      showIntakeError(`Could not start session: ${err && err.message ? err.message : String(err)}`);
    } finally {
      if (startBtn) startBtn.disabled = false;
      if (startLabel) startLabel.textContent = "Start Session";
    }
  });
}

window.addEventListener("DOMContentLoaded", () => {
  wireLandingToIntake();
  wireIntakeBack();
  wireIntakePage();
});
