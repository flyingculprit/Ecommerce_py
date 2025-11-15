const inputs = document.querySelectorAll(".otp-input");
const otpField = document.getElementById("otp");

// Auto move to next box
inputs.forEach((input, index) => {
    input.addEventListener("input", () => {
        if (input.value.length === 1 && index < inputs.length - 1) {
            inputs[index + 1].focus();
        }
        combineOTP();
    });

    // Backspace → go to previous box
    input.addEventListener("keydown", (e) => {
        if (e.key === "Backspace" && index > 0 && input.value === "") {
            inputs[index - 1].focus();
        }
    });
});

// Function to combine the 6 digits
function combineOTP() {
    let fullOTP = "";
    inputs.forEach(inp => fullOTP += inp.value);
    otpField.value = fullOTP;   // Set hidden input
}
