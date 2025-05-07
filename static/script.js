// script.js

// Initialize Mermaid with a default theme (will be overridden based on UI theme)
// let currentMermaidTheme = 'neutral'; // Default light theme - Set inside renderMermaid now
let lastLightMermaidTheme = 'neutral'; // Remember the user's last *light* theme choice
// It's better to initialize Mermaid right before rendering, so commenting this out:
// mermaid.initialize({ startOnLoad: false, theme: 'neutral' });

// --- DOM Element Variables ---
let graphContainer, mermaidDiagramDiv, instructionsDiv, fileInput, loadButton,
    showCodeButton, resetViewButton, reloadDiagramButton,
    statusDiv, codeModal, closeCodeButton,
    mermaidCodeTextarea, copyButton, copyFeedbackSpan, mermaidThemeSelector,
    uiThemeToggleButton, historyToggleButton, historyPanel, closeHistoryButton,
    historyList, currentWorkflowNameDisplay,
    // Settings Modal Elements
    settingsButton, settingsModal, closeSettingsButton,
    settingGraphDirectionSelect, settingGroupNodesSelect, settingDefaultConnectorSelect,
    settingDefaultShapeSelect, settingAddLinkLabelsSelect,
    saveSettingsButton, settingsFeedbackSpan;

// --- State Variables ---
let panZoomInstance = null;
let currentMermaidCode = '';
let currentWorkflowJSON = ''; // Stores the JSON content of the currently loaded workflow
let currentWorkflowName = '';
let currentMermaidTheme = 'neutral'; // Initialize with a default, will be updated by renderMermaid/setUiTheme
let statusTimeout = null;
let resizeTimeout = null;

// --- History Constants ---
const HISTORY_STORAGE_KEY = 'comfyuiMermaidHistory';
const MAX_HISTORY_SIZE_MB = 10;
const MAX_HISTORY_SIZE_BYTES = MAX_HISTORY_SIZE_MB * 1024 * 1024;


// --- Core Functions ---

async function extractWorkflowFromPng(arrayBuffer) {
    const bytes = new Uint8Array(arrayBuffer);
    const pngSignature = [137, 80, 78, 71, 13, 10, 26, 10];
    for (let i = 0; i < pngSignature.length; i++) {
        if (bytes[i] !== pngSignature[i]) {
            console.error("File is not a valid PNG.");
            return { error: "Invalid PNG file format." };
        }
    }
    let offset = 8;
    const textDecoder = new TextDecoder("utf-8");
    const dataView = new DataView(arrayBuffer);
    try {
        while (offset < bytes.length) {
            const length = dataView.getUint32(offset, false);
            offset += 4;
            const type = textDecoder.decode(bytes.slice(offset, offset + 4));
            offset += 4;
            if (type === 'tEXt') {
                const chunkData = bytes.slice(offset, offset + length);
                let keywordEnd = -1;
                for (let i = 0; i < chunkData.length; i++) {
                    if (chunkData[i] === 0) { // Null terminator
                        keywordEnd = i;
                        break;
                    }
                }
                if (keywordEnd !== -1) {
                    const keyword = textDecoder.decode(chunkData.slice(0, keywordEnd));
                    if (keyword === 'workflow') {
                        const jsonData = textDecoder.decode(chunkData.slice(keywordEnd + 1));
                        console.log("  Found workflow JSON in tEXt chunk.");
                        if (jsonData.trim().startsWith('{') && jsonData.trim().endsWith('}')) {
                             try {
                                JSON.parse(jsonData);
                                return { json: jsonData };
                             } catch (jsonError) {
                                console.error("  Extracted data is not valid JSON:", jsonError);
                                return { error: "Found 'workflow' chunk, but content is not valid JSON." };
                             }
                        } else {
                            console.error("  Extracted data doesn't look like JSON:", jsonData.substring(0, 100) + "...");
                            return { error: "Found 'workflow' chunk, but content is not valid JSON." };
                        }
                    }
                } else {
                    console.warn("  tEXt chunk found but no null terminator for keyword.");
                }
            } else if (type === 'IEND') {
                console.log("Reached IEND chunk, workflow not found.");
                break;
            }
            offset += length + 4;
        }
    } catch (e) {
        console.error("Error parsing PNG chunks:", e);
        return { error: "Error occurred while parsing PNG file structure." };
    }
    return { error: "Workflow data not found in PNG file." };
}

async function handleFile(file) {
    if (!file) {
        showStatus('No file selected', 'error');
        return;
    }
    const fileNameLower = file.name.toLowerCase();
    const isJson = fileNameLower.endsWith('.json');
    const isPng = fileNameLower.endsWith('.png');
    if (!isJson && !isPng) {
        showStatus('Error: Please select a .json or .png file containing ComfyUI workflow data', 'error');
        resetOutput();
        return;
    }
    showStatus(`Reading file: ${file.name}...`, 'processing');
    resetOutput();
    currentWorkflowName = file.name;
    const reader = new FileReader();
    reader.onerror = (event) => {
        console.error("File read error:", event.target.error);
        showStatus('File read failed', 'error');
        resetOutput();
        currentWorkflowName = '';
        currentWorkflowJSON = '';
        if (currentWorkflowNameDisplay) currentWorkflowNameDisplay.textContent = '';
    };
    if (isJson) {
        reader.onload = (event) => {
            currentWorkflowJSON = event.target.result;
            sendToServer(currentWorkflowJSON);
        };
        reader.readAsText(file);
    } else if (isPng) {
        reader.onload = async (event) => {
            const arrayBuffer = event.target.result;
            showStatus(`Parsing PNG: ${file.name}...`, 'processing');
            const result = await extractWorkflowFromPng(arrayBuffer);
            if (result.json) {
                currentWorkflowJSON = result.json;
                sendToServer(currentWorkflowJSON);
            } else {
                showStatus(`Error: ${result.error || 'Could not extract workflow from PNG.'}`, 'error');
                resetOutput();
                currentWorkflowName = '';
                currentWorkflowJSON = '';
                if (currentWorkflowNameDisplay) currentWorkflowNameDisplay.textContent = '';
            }
        };
        reader.readAsArrayBuffer(file);
    }
}

async function sendToServer(jsonString) {
    if (typeof jsonString !== 'string' || !jsonString.trim().startsWith('{') || !jsonString.trim().endsWith('}')) {
        console.error("Invalid JSON data received before sending to server:", jsonString);
        showStatus('Error: Invalid workflow data format.', 'error');
        resetOutput();
        currentWorkflowName = '';
        currentWorkflowJSON = '';
        if (currentWorkflowNameDisplay) currentWorkflowNameDisplay.textContent = '';
        return;
    }
    showStatus('Converting workflow...', 'processing');
    try {
        const response = await fetch('/api/convert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ workflow_json: jsonString }),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.message || `HTTP Error! Status: ${response.status}`);
        }
        if (data.status === 'success') {
            console.log("Conversion successful, received Mermaid code:", data.mermaid_code);
            currentMermaidCode = data.mermaid_code;
            if (mermaidCodeTextarea) mermaidCodeTextarea.value = currentMermaidCode;
            if (copyButton) copyButton.disabled = false;
            if (showCodeButton) showCodeButton.disabled = false;
            if (resetViewButton) resetViewButton.disabled = false;
            if (reloadDiagramButton) reloadDiagramButton.disabled = false;
            if (currentWorkflowNameDisplay) {
                currentWorkflowNameDisplay.textContent = currentWorkflowName;
                currentWorkflowNameDisplay.title = currentWorkflowName;
            }
            if (jsonString && currentWorkflowName) {
                 await updateHistory(currentWorkflowName, jsonString);
            }

            // Determine the theme to apply based on current UI state
            let themeToApply = document.body.classList.contains('dark-mode') ? 'dark' : lastLightMermaidTheme;
            await renderMermaid(currentMermaidCode, themeToApply, true); // Force fit/center on new load

            if (instructionsDiv) instructionsDiv.style.display = 'none';
        } else {
            throw new Error(data.message || 'Conversion failed, unknown reason');
        }
    } catch (error) {
        console.error('Request or processing error:', error);
        let errorMessage = 'Conversion failed: ' + (error instanceof Error ? error.message : 'Unknown network or server error');
        showStatus(errorMessage, 'error');
        resetOutput();
        currentWorkflowName = '';
        currentWorkflowJSON = '';
        if (currentWorkflowNameDisplay) currentWorkflowNameDisplay.textContent = '';
    }
}

async function renderMermaid(mermaidCode, themeToApply, forceFitCenter = false) {
    showStatus('Rendering diagram...', 'processing');
    console.log('[renderMermaid] Called. Requested theme:', themeToApply, '| Is body dark-mode?', document.body.classList.contains('dark-mode'));

    let savedPan = null;
    let savedZoom = null;
    if (!forceFitCenter && panZoomInstance) {
        try {
            savedPan = panZoomInstance.getPan();
            savedZoom = panZoomInstance.getZoom();
        } catch (e) {
            console.warn("Could not get pan/zoom state before re-render:", e);
        }
    }

    destroyPanZoom();

    if (!mermaidDiagramDiv) {
        showStatus('Internal error: Diagram container not found.', 'error');
        return;
    }
    mermaidDiagramDiv.innerHTML = '';

    try {
        // Determine the *actual* Mermaid theme to use based on current UI state
        let effectiveMermaidTheme;
        if (document.body.classList.contains('dark-mode')) {
            effectiveMermaidTheme = 'dark';
        } else {
            // If themeToApply is 'dark' but UI is light, use lastLightMermaidTheme
            effectiveMermaidTheme = (themeToApply === 'dark') ? lastLightMermaidTheme : themeToApply;
        }
        // Ensure it's a valid light theme if UI is light
        if (!document.body.classList.contains('dark-mode') && effectiveMermaidTheme === 'dark') {
            effectiveMermaidTheme = lastLightMermaidTheme || 'neutral';
        }

        console.log('[renderMermaid] Initializing Mermaid with effective theme:', effectiveMermaidTheme);
        // Explicitly re-initialize Mermaid with the determined theme *every time* we render.
        mermaid.initialize({
            startOnLoad: false,
            theme: effectiveMermaidTheme,
            // Optional: Add themeVariables here for finer control if needed
            // themeVariables: {
            //   darkMode: document.body.classList.contains('dark-mode'),
            //   textColor: document.body.classList.contains('dark-mode') ? '#eee' : '#333',
            // }
        });

        // Update global currentMermaidTheme state
        currentMermaidTheme = effectiveMermaidTheme;
        // Also update the selector if UI is in light mode
        if (!document.body.classList.contains('dark-mode') && mermaidThemeSelector) {
            if (Array.from(mermaidThemeSelector.options).some(opt => opt.value === effectiveMermaidTheme)) {
                mermaidThemeSelector.value = effectiveMermaidTheme;
            }
        }

        const renderId = 'mermaid-graph-' + Date.now();
        if (!mermaidCode || mermaidCode.trim() === '') {
             throw new Error("Cannot render empty Mermaid code.");
        }

        const { svg, bindFunctions } = await mermaid.render(renderId, mermaidCode);

        if (!svg || svg.trim() === '') {
             throw new Error("Mermaid rendering returned empty SVG content");
        }

        mermaidDiagramDiv.innerHTML = svg;
        const svgElement = mermaidDiagramDiv.querySelector('svg');
        if (!svgElement) {
            throw new Error("Rendered SVG element not found in the container");
        }

        svgElement.style.width = '100%';
        svgElement.style.height = '100%';
        svgElement.style.maxWidth = 'none';

        const initialState = (!forceFitCenter && savedPan && savedZoom !== null) ? { pan: savedPan, zoom: savedZoom } : null;
        initPanZoom(svgElement, initialState);

        if (bindFunctions) {
             try { bindFunctions(svgElement); }
             catch (bindError) {
                console.warn("Mermaid bindFunctions failed on SVG, trying container:", bindError);
                try { bindFunctions(mermaidDiagramDiv); }
                catch (finalBindError) { console.error("Mermaid bindFunctions failed on both SVG and container:", finalBindError); }
             }
        }
        hideStatus();

    } catch (error) {
        console.error("Mermaid rendering or Pan/Zoom initialization error:", error);
        let detail = error.message || 'Unknown rendering error';
        if (error.str) detail += `\nDetails: ${error.str}`;
        showStatus(`Rendering Error: ${detail}`, 'error');
        mermaidDiagramDiv.innerHTML = `<pre class="render-error">Render Failed:\n${detail}\n\n--- Mermaid Code ---\n${mermaidCode || '(No code generated)'}</pre>`;

        if (mermaidCodeTextarea) mermaidCodeTextarea.value = currentMermaidCode || '';
        if (copyButton) copyButton.disabled = !currentMermaidCode;
        if (showCodeButton) showCodeButton.disabled = !currentMermaidCode;
        if (resetViewButton) resetViewButton.disabled = true;
        if (reloadDiagramButton) reloadDiagramButton.disabled = true;
    }
}

function initPanZoom(svgElement, initialState = null) {
    if (!svgElement) return;
    if (panZoomInstance) destroyPanZoom();
    try {
        panZoomInstance = svgPanZoom(svgElement, {
            zoomEnabled: true,
            controlIconsEnabled: false,
            panEnabled: true,
            contain: false,
            center: !initialState,
            fit: !initialState,
            maxZoom: 10,
            minZoom: 0.1,
            zoomScaleSensitivity: 0.3,
            preventMouseEventsDefault: true,
            customEventsHandler: {
                haltEventListeners: ['touchstart', 'touchend', 'touchmove', 'touchleave', 'touchcancel'],
                init: function(options) {
                    var instance = options.instance;
                    this.hammer = Hammer(options.svgElement, {
                        inputClass: Hammer.SUPPORT_POINTER_EVENTS ? Hammer.PointerEventInput : Hammer.TouchInput
                    });
                    this.hammer.get('pinch').set({ enable: true });
                    this.hammer.on('doubletap', (ev) => {
                         ev.preventDefault();
                         instance.zoomIn();
                    });
                },
                destroy: function(){
                    if (this.hammer) {
                        this.hammer.destroy();
                        this.hammer = null;
                    }
                }
            },
             beforePan: (oldPan, newPan) => {
                if (graphContainer) graphContainer.classList.add('grabbing');
             },
             onPan: () => {
                if (graphContainer) graphContainer.classList.remove('grabbing');
             },
             onZoom: () => {
                 if (graphContainer) graphContainer.classList.remove('grabbing');
             }
        });
        if (initialState && panZoomInstance) {
             panZoomInstance.zoom(initialState.zoom);
             panZoomInstance.pan(initialState.pan);
        } else if (panZoomInstance) {
            panZoomInstance.fit();
            panZoomInstance.center();
        }
        const stopGrabbing = () => { if (graphContainer) graphContainer.classList.remove('grabbing'); };
        svgElement.addEventListener('mouseup', stopGrabbing);
        svgElement.addEventListener('mouseleave', stopGrabbing);
        svgElement.addEventListener('touchend', stopGrabbing);
    } catch (e) {
        console.error("svgPanZoom initialization failed:", e);
        if (panZoomInstance) destroyPanZoom();
    }
}

function destroyPanZoom() {
    if (panZoomInstance) {
        try {
            if (panZoomInstance.options && panZoomInstance.options.customEventsHandler && typeof panZoomInstance.options.customEventsHandler.destroy === 'function') {
                 panZoomInstance.options.customEventsHandler.destroy();
            }
            panZoomInstance.destroy();
        } catch (e) {
            console.error("Error destroying svg-pan-zoom instance:", e);
        } finally {
            panZoomInstance = null;
            if (graphContainer) graphContainer.classList.remove('grabbing');
        }
    }
}

function resetPanZoomView() {
    if (panZoomInstance) {
        panZoomInstance.reset();
        panZoomInstance.fit();
        panZoomInstance.center();
    }
}

function handleReloadDiagram() {
    if (!currentWorkflowJSON) {
        showStatus("No workflow loaded to reload.", "warning", 3000);
        console.warn("Reload button clicked but no workflow JSON is available.");
        return;
    }
    if (!reloadDiagramButton || reloadDiagramButton.disabled) {
        return;
    }

    console.log("Reloading diagram with current workflow JSON and forcing theme re-application.");
    showStatus(`Reloading '${currentWorkflowName}'...`, 'processing');
    reloadDiagramButton.disabled = true;

    // Determine the theme that *should* be active based on current UI state
    let themeForReload;
    if (document.body.classList.contains('dark-mode')) {
        themeForReload = 'dark';
    } else {
        themeForReload = lastLightMermaidTheme || 'neutral'; // Use remembered light theme or default
    }
    console.log(`[handleReloadDiagram] Determined theme for reload: ${themeForReload}`);

    setTimeout(async () => {
        try {
            // Fetch new mermaid code from server
            const response = await fetch('/api/convert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ workflow_json: currentWorkflowJSON }),
            });
            const data = await response.json();

            if (!response.ok || data.status !== 'success') {
                throw new Error(data.message || `HTTP Error! Status: ${response.status}`);
            }

            currentMermaidCode = data.mermaid_code;
            if (mermaidCodeTextarea) mermaidCodeTextarea.value = currentMermaidCode;

            // Now call renderMermaid, passing the determined themeForReload.
            // renderMermaid will internally ensure the correct 'dark' or light theme is used based on body class.
            await renderMermaid(currentMermaidCode, themeForReload, false); // false = try to keep pan/zoom

            // Re-enable buttons that might have been disabled by error path in renderMermaid
            if (copyButton) copyButton.disabled = !currentMermaidCode;
            if (showCodeButton) showCodeButton.disabled = !currentMermaidCode;
            // Enable resetViewButton only if panZoom instance exists after rendering
            if (resetViewButton) resetViewButton.disabled = !panZoomInstance;
            if (reloadDiagramButton) reloadDiagramButton.disabled = false; // Re-enable reload button


        } catch (error) {
             console.error("Error during diagram reload (fetch or render):", error);
             showStatus('Error reloading diagram: ' + error.message, 'error');
             // Ensure reload button is re-enabled even if reload failed
             if (reloadDiagramButton) reloadDiagramButton.disabled = false;
             // Other buttons might be left disabled if renderMermaid failed internally
        }
    }, 50);
}

function handleKeyDown(event) {
    if (!panZoomInstance ||
        (mermaidCodeTextarea && document.activeElement === mermaidCodeTextarea) ||
        (historyPanel && historyPanel.classList.contains('visible')) ||
        (settingsModal && settingsModal.style.display === 'block') ||
        (codeModal && codeModal.style.display === 'block')) {
        return;
    }
    const panStep = 30;
    let panChanged = false;
    switch (event.key) {
        case 'ArrowUp': panZoomInstance.panBy({ x: 0, y: panStep }); panChanged = true; break;
        case 'ArrowDown': panZoomInstance.panBy({ x: 0, y: -panStep }); panChanged = true; break;
        case 'ArrowLeft': panZoomInstance.panBy({ x: panStep, y: 0 }); panChanged = true; break;
        case 'ArrowRight': panZoomInstance.panBy({ x: -panStep, y: 0 }); panChanged = true; break;
    }
    if (panChanged) {
        event.preventDefault();
    }
}

function debouncedResizePanZoom() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        if (panZoomInstance) {
            panZoomInstance.resize();
            panZoomInstance.fit();
            panZoomInstance.center();
        }
    }, 250);
}

function handleMermaidThemeChange(event) {
    const newTheme = event.target.value;
    // currentMermaidTheme = newTheme; // Let setUiTheme handle this

    // Update the remembered light theme only if we are currently in light mode
    if (!document.body.classList.contains('dark-mode')) {
        lastLightMermaidTheme = newTheme;
        localStorage.setItem('lastLightMermaidTheme', lastLightMermaidTheme);
        // Trigger re-render with the new light theme
        if (currentMermaidCode) {
             // Call renderMermaid directly as UI mode isn't changing
             console.log(`[handleMermaidThemeChange] Light theme selected: ${newTheme}. Re-rendering.`);
             renderMermaid(currentMermaidCode, newTheme, false);
        }
    }
    // If in dark mode, changing the selector has no immediate effect,
    // but lastLightMermaidTheme is updated for when user switches back to light.
}

function toggleUiTheme() {
    const newThemeName = document.body.classList.contains('dark-mode') ? 'light-mode' : 'dark-mode';
    setUiTheme(newThemeName);
}

function setUiTheme(themeName) {
    const bodyHadDarkMode = document.body.classList.contains('dark-mode');
    document.body.classList.remove('light-mode', 'dark-mode');
    document.body.classList.add(themeName);
    localStorage.setItem('uiTheme', themeName);

    let newMermaidThemeForRender;
    let selectorDisabled;
    let selectorTitle;
    let toggleButtonIcon;

    if (themeName === 'dark-mode') {
        newMermaidThemeForRender = 'dark';
        selectorDisabled = true;
        selectorTitle = "Mermaid theme locked to Dark (UI is Dark Mode)";
        toggleButtonIcon = '☀️';
    } else { // Light mode
        newMermaidThemeForRender = lastLightMermaidTheme; // Use the remembered light theme
        selectorDisabled = false;
        selectorTitle = "Select Mermaid chart theme";
        toggleButtonIcon = '🌙';
    }

    if (uiThemeToggleButton) uiThemeToggleButton.innerHTML = toggleButtonIcon;

    if (mermaidThemeSelector) {
        mermaidThemeSelector.disabled = selectorDisabled;
        mermaidThemeSelector.title = selectorTitle;
        if (themeName === 'light-mode') {
            // Ensure the remembered theme is valid and selected
            if (Array.from(mermaidThemeSelector.options).some(opt => opt.value === newMermaidThemeForRender)) {
                mermaidThemeSelector.value = newMermaidThemeForRender;
            } else {
                console.warn(`Saved light theme "${newMermaidThemeForRender}" not found in selector, defaulting.`);
                mermaidThemeSelector.selectedIndex = 0;
                lastLightMermaidTheme = mermaidThemeSelector.value;
                localStorage.setItem('lastLightMermaidTheme', lastLightMermaidTheme);
                newMermaidThemeForRender = lastLightMermaidTheme; // Use the new default
            }
        }
    }

    // Check if the actual UI mode (light/dark) changed
    const uiModeChanged = (themeName === 'dark-mode' && !bodyHadDarkMode) || (themeName === 'light-mode' && bodyHadDarkMode);

    // Re-render if the UI mode actually changed and there's code to render
    if (uiModeChanged && currentMermaidCode) {
        console.log(`[setUiTheme] UI theme changed to ${themeName}. Target Mermaid theme for render: ${newMermaidThemeForRender}. Re-rendering.`);
        // currentMermaidTheme will be updated inside renderMermaid after initialization
        setTimeout(() => renderMermaid(currentMermaidCode, newMermaidThemeForRender, false), 50);
    } else {
        // If UI mode didn't change (e.g., page load), but the calculated theme differs from the global state, update global state.
        // This might happen if lastLightMermaidTheme was updated by the selector change while in light mode.
        if (currentMermaidTheme !== newMermaidThemeForRender && !document.body.classList.contains('dark-mode')) {
             currentMermaidTheme = newMermaidThemeForRender;
        }
        console.log(`[setUiTheme] UI theme set to ${themeName}. Target Mermaid theme is ${newMermaidThemeForRender}. No UI mode change or no code present. Global theme is now ${currentMermaidTheme}.`);
    }
}

function loadPreferences() {
    lastLightMermaidTheme = localStorage.getItem('lastLightMermaidTheme') || 'neutral';
    if (mermaidThemeSelector) {
        const validLightThemes = Array.from(mermaidThemeSelector.options).map(opt => opt.value);
        if (!validLightThemes.includes(lastLightMermaidTheme)) {
            console.warn(`Stored light theme "${lastLightMermaidTheme}" is invalid, resetting to neutral.`);
            lastLightMermaidTheme = 'neutral';
            localStorage.setItem('lastLightMermaidTheme', lastLightMermaidTheme);
        }
    } else {
        lastLightMermaidTheme = 'neutral';
    }
    const preferredUiTheme = localStorage.getItem('uiTheme') || 'dark-mode';
    setUiTheme(preferredUiTheme);
}

function toggleCodeModal() {
    if (!codeModal) return;
    const isVisible = codeModal.style.display === 'block';
    codeModal.style.display = isVisible ? 'none' : 'block';
}

async function copyCodeFromModal() {
    if (!mermaidCodeTextarea || !copyFeedbackSpan || !copyButton) return;
    if (!mermaidCodeTextarea.value) {
        copyFeedbackSpan.textContent = 'Nothing to copy!';
        setTimeout(() => { copyFeedbackSpan.textContent = ''; }, 2000);
        return;
    }
    try {
        await navigator.clipboard.writeText(mermaidCodeTextarea.value);
        copyFeedbackSpan.textContent = 'Copied!';
        copyButton.disabled = true;
        setTimeout(() => {
            copyFeedbackSpan.textContent = '';
            copyButton.disabled = !currentMermaidCode;
        }, 2000);
    } catch (err) {
        console.error('Failed to copy code:', err);
        copyFeedbackSpan.textContent = 'Copy failed!';
         mermaidCodeTextarea.focus();
         mermaidCodeTextarea.select();
         setTimeout(() => { copyFeedbackSpan.textContent = ''; }, 3000);
    }
}

function showStatus(message, type = 'info', duration = null) {
    if (!statusDiv) return;
    if (statusTimeout) clearTimeout(statusTimeout);
    statusDiv.textContent = message;
    statusDiv.className = 'status visible ' + type;
    if (duration && duration > 0) {
        statusTimeout = setTimeout(hideStatus, duration);
    }
}

function hideStatus() {
    if (!statusDiv) return;
     if (statusTimeout) clearTimeout(statusTimeout);
    statusDiv.classList.remove('visible');
}

function resetOutput() {
    destroyPanZoom();
    if (mermaidDiagramDiv) mermaidDiagramDiv.innerHTML = '';
    if (instructionsDiv && mermaidDiagramDiv && !mermaidDiagramDiv.contains(instructionsDiv)) {
         mermaidDiagramDiv.appendChild(instructionsDiv);
    }
    if (instructionsDiv) instructionsDiv.style.display = 'block';
    currentMermaidCode = '';
    currentWorkflowName = '';
    currentWorkflowJSON = '';
    if (mermaidCodeTextarea) mermaidCodeTextarea.value = '';
    if (copyButton) copyButton.disabled = true;
    if (showCodeButton) showCodeButton.disabled = true;
    if (resetViewButton) resetViewButton.disabled = true;
    if (reloadDiagramButton) reloadDiagramButton.disabled = true;
    if (copyFeedbackSpan) copyFeedbackSpan.textContent = '';
    if (settingsFeedbackSpan) settingsFeedbackSpan.textContent = '';
    if (currentWorkflowNameDisplay) {
        currentWorkflowNameDisplay.textContent = '';
        currentWorkflowNameDisplay.title = '';
    }
    hideStatus();
    if (codeModal && codeModal.style.display !== 'none') codeModal.style.display = 'none';
    if (settingsModal && settingsModal.style.display !== 'none') settingsModal.style.display = 'none';
    if (graphContainer) graphContainer.classList.remove('dragover');
}

// --- History Functions ---

async function calculateHash(string) {
    try {
        const utf8 = new TextEncoder().encode(string);
        const hashBuffer = await crypto.subtle.digest('SHA-256', utf8);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
    } catch (error) {
        console.error("Error calculating SHA-256 hash:", error);
        return `nohash-${Date.now()}-${Math.random()}`;
    }
}

function getHistory() {
    try {
        const historyJson = localStorage.getItem(HISTORY_STORAGE_KEY);
        if (!historyJson) return [];
        const history = JSON.parse(historyJson);
        return Array.isArray(history) ? history : [];
    } catch (e) {
        console.error("Error reading or parsing history from localStorage:", e);
        localStorage.removeItem(HISTORY_STORAGE_KEY);
        return [];
    }
}

function saveHistory(history) {
    try {
        if (!Array.isArray(history)) {
            console.error("Attempted to save non-array data as history.");
            return;
        }
        localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history));
    } catch (e) {
        if (e.name === 'QuotaExceededError') {
            showStatus('Could not save history: Storage quota exceeded.', 'error', 8000);
        } else {
            showStatus('Could not save history (unknown error)', 'error', 5000);
        }
        console.error("Error saving history to localStorage:", e);
    }
}

async function updateHistory(name, jsonContent) {
    if (!name || !jsonContent) return;
    try { JSON.parse(jsonContent); }
    catch (e) {
        showStatus('Internal Error: Invalid workflow data provided for history.', 'error', 5000);
        console.error("Attempted to add invalid JSON to history:", jsonContent.substring(0, 200) + "...");
        return;
    }
    const hash = await calculateHash(jsonContent);
    const timestamp = Date.now();
    const size = jsonContent.length;
    let history = getHistory();
    let currentTotalSize = history.reduce((sum, item) => sum + (item.size || item.content?.length || 0), 0);
    const existingIndex = history.findIndex(item => item.hash === hash);
    if (existingIndex > -1) {
        const removedItem = history.splice(existingIndex, 1)[0];
        currentTotalSize -= (removedItem.size || removedItem.content?.length || 0);
        console.log(`Updating existing history item: ${name}`);
    } else {
         console.log(`Adding new history item: ${name}`);
    }
    const newItem = { hash, name, timestamp, size, content: jsonContent };
    let newTotalSize = currentTotalSize + size;
    while (newTotalSize > MAX_HISTORY_SIZE_BYTES && history.length > 0) {
        history.sort((a, b) => a.timestamp - b.timestamp);
        const oldestItem = history.shift();
        if (oldestItem) {
            newTotalSize -= (oldestItem.size || oldestItem.content?.length || 0);
            console.log(`History limit exceeded: Removed oldest item '${oldestItem.name}'`);
        } else {
            break;
        }
    }
    history.unshift(newItem);
    saveHistory(history);
    if (historyPanel && historyPanel.classList.contains('visible')) {
        populateHistoryList();
    }
}

function populateHistoryList() {
    if (!historyList) return;
    const history = getHistory();
    historyList.innerHTML = '';
    if (history.length === 0) {
        historyList.innerHTML = '<li class="no-history">No history yet</li>';
        return;
    }
    history.sort((a, b) => b.timestamp - a.timestamp);
    history.forEach(item => {
        const li = document.createElement('li');
        li.dataset.hash = item.hash;
        const nameSpan = document.createElement('span');
        nameSpan.className = 'history-item-name';
        nameSpan.textContent = item.name || 'Untitled Workflow';
        nameSpan.title = item.name || 'Untitled Workflow';
        const detailsSpan = document.createElement('span');
        detailsSpan.className = 'history-item-details';
        const date = new Date(item.timestamp).toLocaleString();
        const sizeBytes = item.size || item.content?.length || 0;
        let sizeDisplay = sizeBytes > 1024 * 1024
            ? (sizeBytes / (1024 * 1024)).toFixed(1) + ' MB'
            : (sizeBytes / 1024).toFixed(1) + ' KB';
        detailsSpan.textContent = `${date} - ${sizeDisplay}`;
        li.appendChild(nameSpan);
        li.appendChild(detailsSpan);
        li.addEventListener('click', () => loadFromHistory(item.hash));
        historyList.appendChild(li);
    });
}

function loadFromHistory(hash) {
    const history = getHistory();
    const item = history.find(h => h.hash === hash);
    if (item && item.content) {
        toggleHistoryPanel(false);
        resetOutput();
        currentWorkflowName = item.name;
        currentWorkflowJSON = item.content;
        if (currentWorkflowNameDisplay) {
             currentWorkflowNameDisplay.textContent = currentWorkflowName;
             currentWorkflowNameDisplay.title = currentWorkflowName;
        }
        showStatus(`Loading '${item.name}' from history...`, 'processing');
        setTimeout(() => sendToServer(item.content), 50);
    } else {
        showStatus('Failed to load this item from history (data missing?)', 'error', 3000);
    }
}

function toggleHistoryPanel(forceState = null) {
    if (!historyPanel) return;
    const shouldBeVisible = forceState !== null ? forceState : !historyPanel.classList.contains('visible');
    if (shouldBeVisible) {
        populateHistoryList();
        historyPanel.classList.add('visible');
        document.body.classList.add('history-panel-visible');
    } else {
        historyPanel.classList.remove('visible');
        document.body.classList.remove('history-panel-visible');
    }
}

// --- Settings Modal Functions ---

async function loadCurrentSettings() {
    if (!settingGraphDirectionSelect || !settingGroupNodesSelect ||
        !settingDefaultConnectorSelect || !settingDefaultShapeSelect ||
        !settingAddLinkLabelsSelect) {
        console.error("Settings modal elements not found.");
        return;
    }
    showStatus("Loading current settings...", "processing");
    if (settingsFeedbackSpan) settingsFeedbackSpan.textContent = "Loading...";
    try {
        const response = await fetch('/api/get_config');
        const data = await response.json();
        if (response.ok && data.status === 'success') {
            const settings = data.settings;
            settingGraphDirectionSelect.value = settings.Default_Graph_Direction || "TD";
            settingGroupNodesSelect.value = (settings.Generate_ComfyUI_Subgraphs === true || String(settings.Generate_ComfyUI_Subgraphs).toLowerCase() === "true") ? "true" : "false";
            settingAddLinkLabelsSelect.value = (settings.Add_Link_Labels === true || String(settings.Add_Link_Labels).toLowerCase() === "true") ? "true" : "false";
            settingDefaultConnectorSelect.value = settings.Default_Connector || "-->";
            settingDefaultShapeSelect.value = settings.Default_Node_Shape || "rectangle";
            hideStatus();
            if (settingsFeedbackSpan) settingsFeedbackSpan.textContent = "";
        } else {
            throw new Error(data.message || "Failed to load settings from server.");
        }
    } catch (error) {
        console.error("Error loading settings:", error);
        showStatus(`Error loading settings: ${error.message}`, 'error', 5000);
        if (settingsFeedbackSpan) settingsFeedbackSpan.textContent = "Failed to load settings.";
    }
}

function toggleSettingsModal() {
    if (!settingsModal) return;
    const isVisible = settingsModal.style.display === 'block';
    if (isVisible) {
        settingsModal.style.display = 'none';
        if (settingsFeedbackSpan) settingsFeedbackSpan.textContent = '';
    } else {
        loadCurrentSettings().then(() => {
             settingsModal.style.display = 'block';
        }).catch(err => {
             settingsModal.style.display = 'block';
             if (settingsFeedbackSpan) settingsFeedbackSpan.textContent = "Error loading settings.";
        });
    }
}

async function saveAndApplySettings() {
    if (!settingGraphDirectionSelect || !settingGroupNodesSelect ||
        !settingDefaultConnectorSelect || !settingDefaultShapeSelect ||
        !settingAddLinkLabelsSelect || !saveSettingsButton || !settingsFeedbackSpan) {
        console.error("Cannot save settings: Modal elements missing.");
        return;
    }
    const newSettings = {
        Default_Graph_Direction: settingGraphDirectionSelect.value,
        Generate_ComfyUI_Subgraphs: settingGroupNodesSelect.value === "true",
        Add_Link_Labels: settingAddLinkLabelsSelect.value === "true",
        Default_Connector: settingDefaultConnectorSelect.value,
        Default_Node_Shape: settingDefaultShapeSelect.value
    };
    showStatus("Saving settings...", "processing");
    settingsFeedbackSpan.textContent = "Saving...";
    saveSettingsButton.disabled = true;
    try {
        const response = await fetch('/api/update_config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newSettings)
        });
        const data = await response.json();
        if (response.ok && data.status === 'success') {
            showStatus(data.message || "Settings saved. Rerendering if workflow loaded...", "success", 4000);
            settingsFeedbackSpan.textContent = "Saved! Rerendering...";
            setTimeout(() => {
                toggleSettingsModal();
                 if (currentWorkflowJSON) {
                    console.log("Settings saved, triggering diagram reload.");
                    handleReloadDiagram(); // Use the reload handler
                } else {
                    settingsFeedbackSpan.textContent = "Saved! Load a workflow to see changes.";
                     setTimeout(() => { if (settingsFeedbackSpan) settingsFeedbackSpan.textContent = ''; }, 3000);
                }
            }, 1000);
        } else {
            throw new Error(data.message || "Failed to save settings on server.");
        }
    } catch (error) {
        console.error("Error saving settings:", error);
        showStatus(`Error saving settings: ${error.message}`, 'error', 5000);
        settingsFeedbackSpan.textContent = `Error: ${error.message}`;
    } finally {
        saveSettingsButton.disabled = false;
    }
}

// --- Initial Setup ---
document.addEventListener('DOMContentLoaded', () => {
    // Assign DOM elements
    graphContainer = document.getElementById('graph-container');
    mermaidDiagramDiv = document.getElementById('mermaid-diagram');
    instructionsDiv = document.getElementById('instructions');
    fileInput = document.getElementById('file-input');
    loadButton = document.getElementById('load-button');
    showCodeButton = document.getElementById('show-code-button');
    resetViewButton = document.getElementById('reset-view-button');
    reloadDiagramButton = document.getElementById('reload-diagram-button');
    statusDiv = document.getElementById('status');
    codeModal = document.getElementById('code-modal');
    closeCodeButton = document.getElementById('close-code-button');
    mermaidCodeTextarea = document.getElementById('mermaid-code-modal');
    copyButton = document.getElementById('copy-button-modal');
    copyFeedbackSpan = document.getElementById('copy-feedback-modal');
    mermaidThemeSelector = document.getElementById('mermaid-theme-selector');
    uiThemeToggleButton = document.getElementById('ui-theme-toggle');
    historyToggleButton = document.getElementById('history-toggle-button');
    historyPanel = document.getElementById('history-panel');
    closeHistoryButton = document.getElementById('close-history-button');
    historyList = document.getElementById('history-list');
    currentWorkflowNameDisplay = document.getElementById('current-workflow-name-display');
    settingsButton = document.getElementById('settings-button');
    settingsModal = document.getElementById('settings-modal');
    closeSettingsButton = document.getElementById('close-settings-button');
    settingGraphDirectionSelect = document.getElementById('setting-graph-direction');
    settingGroupNodesSelect = document.getElementById('setting-group-nodes');
    settingAddLinkLabelsSelect = document.getElementById('setting-add-link-labels');
    settingDefaultConnectorSelect = document.getElementById('setting-default-connector');
    settingDefaultShapeSelect = document.getElementById('setting-default-shape');
    saveSettingsButton = document.getElementById('save-settings-button');
    settingsFeedbackSpan = document.getElementById('settings-feedback');

    // Add Event Listeners
    if (loadButton && fileInput) loadButton.addEventListener('click', () => fileInput.click());
    if (showCodeButton) showCodeButton.addEventListener('click', toggleCodeModal);
    if (closeCodeButton) closeCodeButton.addEventListener('click', toggleCodeModal);
    if (resetViewButton) resetViewButton.addEventListener('click', resetPanZoomView);
    if (reloadDiagramButton) reloadDiagramButton.addEventListener('click', handleReloadDiagram);
    if (copyButton) copyButton.addEventListener('click', copyCodeFromModal);
    if (mermaidThemeSelector) mermaidThemeSelector.addEventListener('change', handleMermaidThemeChange);
    if (uiThemeToggleButton) uiThemeToggleButton.addEventListener('click', toggleUiTheme);
    if (historyToggleButton) historyToggleButton.addEventListener('click', () => toggleHistoryPanel());
    if (closeHistoryButton) closeHistoryButton.addEventListener('click', () => toggleHistoryPanel(false));
    if (settingsButton) settingsButton.addEventListener('click', toggleSettingsModal);
    if (closeSettingsButton) closeSettingsButton.addEventListener('click', toggleSettingsModal);
    if (saveSettingsButton) saveSettingsButton.addEventListener('click', saveAndApplySettings);
    if (fileInput) fileInput.addEventListener('change', (event) => {
        if (event.target.files && event.target.files.length > 0) {
            handleFile(event.target.files[0]);
        }
        event.target.value = null;
    });
    if (graphContainer) {
        graphContainer.addEventListener('dragover', (event) => {
            event.preventDefault();
            graphContainer.classList.add('dragover');
        });
        graphContainer.addEventListener('dragleave', () => {
            graphContainer.classList.remove('dragover');
        });
        graphContainer.addEventListener('drop', (event) => {
            event.preventDefault();
            graphContainer.classList.remove('dragover');
            if (event.dataTransfer.files && event.dataTransfer.files.length > 0) {
                handleFile(event.dataTransfer.files[0]);
            }
        });
    }
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('resize', debouncedResizePanZoom);

    // Initial UI State
    if (mermaidDiagramDiv && instructionsDiv && !mermaidDiagramDiv.contains(instructionsDiv)) {
        mermaidDiagramDiv.appendChild(instructionsDiv);
    }
    if (instructionsDiv) instructionsDiv.style.display = 'block';
    loadPreferences(); // Load themes *before* setting initial button states
    populateHistoryList();
    if (copyButton) copyButton.disabled = true;
    if (showCodeButton) showCodeButton.disabled = true;
    if (resetViewButton) resetViewButton.disabled = true;
    if (reloadDiagramButton) reloadDiagramButton.disabled = true;
    if (currentWorkflowNameDisplay) currentWorkflowNameDisplay.textContent = '';

    console.log("ComfyUI to Mermaid Viewer initialized.");
});
