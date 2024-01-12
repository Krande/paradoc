document.addEventListener("DOMContentLoaded", function() {
        const navbar = document.createElement("div");
        navbar.className = "navbar";

        const appendixStartText = document.querySelector('meta[name="data-appendix-start"]').getAttribute("content").replace(/\s+/g, '');

        let counters = [0, 0, 0, 0, 0, 0];
        let currentAppendixLetter = 'A';
        let inAppendix = false;
        const indentSize = 20; // Indent size in pixels

        const headers = document.querySelectorAll("h1, h2, h3, h4, h5, h6");

        headers.forEach(function(header) {
            const headerText = header.textContent.replace(/\s+/g, '');
            const level = parseInt(header.tagName.substring(1)) - 1; // Define level here

            if (headerText === appendixStartText) {
                inAppendix = true;
                counters = [0, 0, 0, 0, 0, 0];
            }

            let number;
            if (inAppendix) {
                if (level === 0) { // Increment letter for each h1 in appendix
                    if (counters[0] > 0) { // Increment letter after the first h1
                        currentAppendixLetter = String.fromCharCode(currentAppendixLetter.charCodeAt(0) + 1);
                    }
                    counters = [0, 0, 0, 0, 0, 0];
                }
                counters[level]++;
                number = (level === 0 ? "Appendix " : "") + currentAppendixLetter + (level > 0 ? "." + counters.slice(1, level + 1).join(".") : "");
            } else {
                counters[level]++;
                number = counters.slice(0, level + 1).join(".");
            }
            // reset lower levels
            for (let i = level + 1; i < counters.length; i++) {
                counters[i] = 0;
            }

            header.id = header.id || "heading" + number;
            header.textContent = number + " " + header.textContent;

            const link = document.createElement("a");
            link.href = "#" + header.id;
            link.textContent = header.textContent;
            link.style.paddingLeft = `${indentSize * level}px`;

            navbar.appendChild(link);
        });

        document.body.prepend(navbar);
    });