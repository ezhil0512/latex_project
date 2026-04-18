const imageInput = document.querySelector("#imageInput");
const diagramInput = document.querySelector("#diagramInput");
const previewArea = document.querySelector(".preview-area");
const previewImage = document.querySelector("#previewImage");
const diagramPreviewImage = document.querySelector("#diagramPreviewImage");
const copyButton = document.querySelector("#copyButton");
const previewButton = document.querySelector("#previewButton");
const latexOutput = document.querySelector("#latexOutput");
const readablePreview = document.querySelector("#readablePreview");
const previewContent = document.querySelector("#previewContent");

if (imageInput && previewArea && previewImage) {
    imageInput.addEventListener("change", () => {
        const file = imageInput.files[0];
        if (!file) {
            previewArea.classList.remove("has-image");
            previewImage.removeAttribute("src");
            return;
        }

        previewImage.src = URL.createObjectURL(file);
        previewArea.classList.add("has-image");
    });
}

if (diagramInput && diagramPreviewImage) {
    const diagramPreviewArea = diagramPreviewImage.closest(".preview-area");

    diagramInput.addEventListener("change", () => {
        const file = diagramInput.files[0];
        if (!file) {
            diagramPreviewArea.classList.remove("has-image");
            diagramPreviewImage.removeAttribute("src");
            return;
        }

        diagramPreviewImage.src = URL.createObjectURL(file);
        diagramPreviewArea.classList.add("has-image");
    });
}

if (copyButton && latexOutput) {
    copyButton.addEventListener("click", async () => {
        await navigator.clipboard.writeText(latexOutput.value);
        copyButton.textContent = "Copied";
        window.setTimeout(() => {
            copyButton.textContent = "Copy LaTeX";
        }, 1400);
    });
}

if (previewButton && latexOutput && readablePreview && previewContent) {
    previewButton.addEventListener("click", () => {
        previewContent.innerHTML = latexToReadableHtml(latexOutput.value);
        readablePreview.hidden = false;
        previewButton.textContent = "Update preview";
        readablePreview.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
}

function latexToReadableHtml(latex) {
    const body = extractDocumentBody(latex);
    const blocks = extractDisplayMathBlocks(body);
    const lines = blocks.text.split(/\r?\n/);
    const html = [];

    for (const rawLine of lines) {
        const line = rawLine.trim();

        if (!line || line === "\\begin{enumerate}" || line === "\\end{enumerate}" || line === "\\end{description}") {
            continue;
        }

        if (line === "\\begin{center}" || line === "\\end{center}" || /^\\begin\{description\}/.test(line)) {
            continue;
        }

        const image = line.match(/^\\includegraphics(?:\[[^\]]*\])?\{(.+)\}$/);
        if (image) {
            html.push(imageToHtml(image[1]));
            continue;
        }

        if (blocks.display[line]) {
            html.push(`<div class="preview-display-math">${mathToHtml(blocks.display[line])}</div>`);
            continue;
        }

        const section = line.match(/^\\section\*\{(.+)\}$/);
        if (section) {
            html.push(`<h3>${inlineLatexToHtml(section[1])}</h3>`);
            continue;
        }

        const item = line.match(/^\\item\[\s*\\textbf\{([^}]+)\}\s*\]\s*(.+)$/);
        if (item) {
            html.push(optionToHtml(item[1], item[2]));
            continue;
        }

        const noIndentOption = line.match(/^\\noindent\\textbf\{([^}]+)\}\\quad\s*(.+)$/);
        if (noIndentOption) {
            html.push(optionToHtml(noIndentOption[1], noIndentOption[2]));
            continue;
        }

        const simpleOption = line.match(/^\\textbf\{([^}]+)\}\s*(.+)$/);
        if (simpleOption) {
            html.push(optionToHtml(simpleOption[1], simpleOption[2]));
            continue;
        }

        html.push(`<p>${inlineLatexToHtml(line)}</p>`);
    }

    if (!html.length) {
        return "<p>No readable content found in the current LaTeX.</p>";
    }

    return html.join("");
}

function imageToHtml(source) {
    const imageSource = source
        .replace(/^(\.\.\/)+uploads\//, "/uploads/")
        .replace(/^uploads\//, "/uploads/");

    return [
        '<div class="preview-image-wrap">',
        `<img class="preview-image" src="${escapeHtml(imageSource)}" alt="Question diagram">`,
        "</div>",
    ].join("");
}

function extractDocumentBody(latex) {
    const match = latex.match(/\\begin\{document\}([\s\S]*?)\\end\{document\}/);
    if (match) {
        return match[1].trim();
    }
    return latex.trim();
}

function extractDisplayMathBlocks(text) {
    const display = {};
    let index = 0;
    const replaced = text.replace(/\\\[([\s\S]*?)\\\]/g, (_match, math) => {
        const key = `@@DISPLAY_MATH_${index}@@`;
        display[key] = math.trim();
        index += 1;
        return key;
    });

    return { text: replaced, display };
}

function optionToHtml(label, value) {
    return [
        '<div class="preview-option">',
        `<span class="preview-option-label">${normalizeOptionLabel(label)}</span>`,
        `<span>${inlineLatexToHtml(value)}</span>`,
        "</div>",
    ].join("");
}

function normalizeOptionLabel(label) {
    const cleanLabel = label.replace(/[().\s]/g, "");
    if (cleanLabel.length === 1) {
        return `(${escapeHtml(cleanLabel)})`;
    }
    return escapeHtml(label);
}

function inlineLatexToHtml(text) {
    let output = escapeHtml(cleanTextCommands(text));

    output = output.replace(/\\\((.*?)\\\)/g, (_match, math) => {
        return `<span class="preview-math">${mathToHtml(unescapeHtml(math))}</span>`;
    });

    return output;
}

function mathToHtml(rawMath) {
    let math = rawMath
        .replace(/\\displaystyle/g, "")
        .replace(/\\leftrightarrow/g, "↔")
        .replace(/\\leftarrow/g, "←")
        .replace(/\\rightarrow/g, "→")
        .replace(/\\left/g, "")
        .replace(/\\right/g, "")
        .replace(/\\quad/g, " ")
        .replace(/\\circ/g, "°")
        .replace(/\\pm/g, "±")
        .replace(/\\times/g, "×")
        .replace(/\\leq/g, "≤")
        .replace(/\\geq/g, "≥")
        .replace(/\\neq/g, "≠")
        .trim();

    const placeholders = [];
    math = math.replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, (_match, numerator, denominator) => {
        const key = `FRACPLACEHOLDER${placeholders.length}TOKEN`;
        placeholders.push([numerator, denominator]);
        return key;
    });

    let html = escapeHtml(math)
        .replace(/\^\{([^{}]+)\}/g, "<sup>$1</sup>")
        .replace(/\^([A-Za-z0-9])/g, "<sup>$1</sup>")
        .replace(/_\{([^{}]+)\}/g, "<sub>$1</sub>")
        .replace(/_([A-Za-z0-9])/g, "<sub>$1</sub>")
        .replace(/\\times/g, "×")
        .replace(/\\rightarrow/g, "→")
        .replace(/\\(?:mathrm|text)\{([^{}]+)\}/g, "$1")
        .replace(/\\[A-Za-z]+/g, "");

    placeholders.forEach(([numerator, denominator], index) => {
        const fraction = [
            '<span class="preview-frac">',
            `<span class="preview-frac-num">${mathToHtml(numerator)}</span>`,
            `<span class="preview-frac-den">${mathToHtml(denominator)}</span>`,
            "</span>",
        ].join("");
        html = html.replace(`FRACPLACEHOLDER${index}TOKEN`, fraction);
    });

    return html;
}

function cleanTextCommands(text) {
    return text
        .replace(/\\noindent/g, "")
        .replace(/\\quad/g, " ")
        .replace(/\\textbf\{([^{}]+)\}/g, "$1");
}

function escapeHtml(value) {
    return value
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function unescapeHtml(value) {
    const textarea = document.createElement("textarea");
    textarea.innerHTML = value;
    return textarea.value;
}
