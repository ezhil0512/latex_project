/**
 * Multi-question interface JavaScript
 */

function previewQuestion(qNum) {
    const latexTextarea = document.getElementById(`latex-q${qNum}`);
    const previewDiv = document.getElementById(`preview-q${qNum}`);
    const previewContent = document.getElementById(`preview-content-q${qNum}`);

    if (!latexTextarea || !previewDiv) {
        console.error(`Preview elements not found for question ${qNum}`);
        return;
    }

    if (previewDiv.hidden) {
        // Convert LaTeX to readable HTML
        try {
            const htmlContent = latexToReadableHtml(latexTextarea.value);
            previewContent.innerHTML = htmlContent;
            previewDiv.hidden = false;
            
            // Trigger MathJax rerendering if available
            if (window.MathJax) {
                MathJax.typesetPromise([previewContent]).catch(err => console.log(err));
            }
        } catch (error) {
            console.error('Error generating preview:', error);
            previewContent.innerHTML = '<p style="color: red;">Error generating preview</p>';
            previewDiv.hidden = false;
        }
    } else {
        previewDiv.hidden = true;
    }
}

function closePreview(qNum) {
    const previewDiv = document.getElementById(`preview-q${qNum}`);
    if (previewDiv) {
        previewDiv.hidden = true;
    }
}

function copyLatex(qNum) {
    const latexTextarea = document.getElementById(`latex-q${qNum}`);
    const btn = event.target;
    
    if (!latexTextarea) {
        console.error(`LaTeX textarea not found for question ${qNum}`);
        return;
    }
    
    navigator.clipboard.writeText(latexTextarea.value).then(() => {
        const originalText = btn.textContent;
        btn.textContent = '✓ Copied!';
        btn.disabled = true;
        setTimeout(() => {
            btn.textContent = originalText;
            btn.disabled = false;
        }, 1500);
    }).catch(err => {
        console.error('Failed to copy:', err);
        alert('Failed to copy LaTeX');
    });
}

/**
 * Convert LaTeX to readable HTML
 * Simplified version - compatible with main.js version
 */
function latexToReadableHtml(latex) {
    try {
        const body = extractDocumentBody(latex);
        const blocks = extractDisplayMathBlocks(body);
        const lines = blocks.text.split(/\r?\n/);
        const html = [];

        for (const rawLine of lines) {
            const line = rawLine.trim();

            if (!line || 
                line === "\\begin{enumerate}" || 
                line === "\\end{enumerate}" || 
                line === "\\end{description}" ||
                line === "\\begin{center}" ||
                line === "\\end{center}" ||
                /^\\begin\{description\}/.test(line)) {
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
    } catch (error) {
        console.error('Error converting LaTeX:', error);
        return `<p style="color: red;">Error: ${escapeHtml(error.message)}</p>`;
    }
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

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Multi-question interface initialized');
});
